"""Compatibility entrypoint; prefer src.app.main:app."""
from src.app.main import app  # re-export for uvicorn
