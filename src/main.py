from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(title="Valuagent API", version="0.1.0")
app.include_router(router)
