import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Optional Google Cloud Logging integration
if os.getenv("ENABLE_GCLOUD_LOGGING") == "1":
    try:
        from google.cloud import logging as gcloud_logging  # type: ignore

        gcloud_logging.Client().setup_logging()
    except Exception:
        # Fall back to standard logging if client not available
        pass


# Basic structured access logging
logger = logging.getLogger("valuagent")


# Rate limiting (SlowAPI)
from slowapi import Limiter  # type: ignore
from slowapi.errors import RateLimitExceeded  # type: ignore
from slowapi.middleware import SlowAPIMiddleware  # type: ignore
from slowapi.util import get_remote_address  # type: ignore

limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])  # export for route decorators


app = FastAPI(title="Valuagent API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded, lambda request, exc: PlainTextResponse("Too Many Requests", 429)
)
app.add_middleware(SlowAPIMiddleware)

# Signed cookie session for simple login page
session_secret = os.getenv("SESSION_SECRET", "change-this-in-prod")
app.add_middleware(SessionMiddleware, secret_key=session_secret, same_site="lax")


@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "request",
        extra={
            "httpRequest": {
                "requestMethod": request.method,
                "requestUrl": str(request.url),
                "status": response.status_code,
                "userAgent": request.headers.get("user-agent"),
                "remoteIp": request.client.host if request.client else None,
                "latency": f"{duration_ms}ms",
            }
        },
    )
    return response


app.mount("/static", StaticFiles(directory="src/app/static"), name="static")

from src.app.api.routes import router  # noqa: E402  (after limiter definition)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}