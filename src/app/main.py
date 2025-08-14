import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Configure logging
def setup_logging():
    """Configure logging for the application."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels for our modules
    logging.getLogger("src.infrastructure.clients.genai_client").setLevel(log_level)
    logging.getLogger("src.services.process").setLevel(log_level)
    logging.getLogger("src.app.api.routes").setLevel(log_level)
    
    # Reduce noise from some third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger("valuagent")

# Setup logging
logger = setup_logging()

# Optional Google Cloud Logging integration
if os.getenv("ENABLE_GCLOUD_LOGGING") == "1":
    try:
        from google.cloud import logging as gcloud_logging  # type: ignore
        gcloud_logging.Client().setup_logging()
        logger.info("Google Cloud Logging enabled")
    except Exception as e:
        logger.warning(f"Failed to setup Google Cloud Logging: {e}")
        # Fall back to standard logging if client not available
        pass

logger.info("Valuagent application starting up")


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