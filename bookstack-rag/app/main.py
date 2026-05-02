"""FastAPI application factory for the BookStack RAG add-on."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from qdrant_client import QdrantClient

from app import __version__
from app.api import router
from app.config import load_config
from app.embedder import SentenceTransformerEmbedder
from app.index import Index
from app.pipeline import Pipeline
from app.watcher import Watcher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.config import Config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise embedder, Qdrant index, watcher; tear them down cleanly on exit."""
    config: Config = app.state.config
    logger.info("Starting BookStack RAG v%s", __version__)

    embedder = SentenceTransformerEmbedder(model_name=config.embedding_model)
    embedder.load()

    client = QdrantClient(url=config.qdrant_url)
    index = Index(
        client=client,
        collection_name=config.qdrant_collection,
        vector_size=embedder.vector_size,
    )
    index.ensure_collection()

    pipeline = Pipeline(
        export_path=config.bookstack_export_path,
        embedder=embedder,
        index=index,
    )

    summary = pipeline.reconcile_all()
    logger.info(
        "Initial reconcile: indexed=%d unchanged=%d skipped=%d failed=%d",
        summary.indexed,
        summary.unchanged,
        summary.skipped,
        summary.failed,
    )

    watcher = Watcher(pipeline=pipeline)
    watcher.start()

    app.state.embedder = embedder
    app.state.index = index
    app.state.pipeline = pipeline
    app.state.watcher = watcher

    try:
        yield
    finally:
        watcher.stop()
        client.close()


def create_app() -> FastAPI:
    """Build a FastAPI app with the loaded add-on config attached to its state."""
    config = load_config()
    app = FastAPI(
        title="BookStack RAG",
        description="Local RAG over BookStack-exported Home Assistant documentation",
        version=__version__,
        lifespan=_lifespan,
    )
    app.state.config = config
    app.include_router(router, prefix="/api")
    return app
