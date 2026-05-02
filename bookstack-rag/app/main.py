"""FastAPI application factory for the BookStack RAG add-on."""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api import router
from app.config import load_config


def create_app() -> FastAPI:
    """Build a FastAPI app with the loaded add-on config attached to its state."""
    config = load_config()
    app = FastAPI(
        title="BookStack RAG",
        description="Local RAG over BookStack-exported Home Assistant documentation",
        version=__version__,
    )
    app.state.config = config
    app.include_router(router, prefix="/api")
    return app
