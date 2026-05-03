"""FastAPI application factory for the BookStack RAG add-on."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from qdrant_client import QdrantClient

from app import __version__
from app.api import router
from app.config import load_config
from app.conversations import ConversationStore
from app.embedder import SentenceTransformerEmbedder
from app.index import Index
from app.llm import LLMClient
from app.pipeline import Pipeline
from app.watcher import Watcher

UI_DIR = Path(__file__).parent / "ui"

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.config import Config

logger = logging.getLogger(__name__)


async def _run_initial_reconcile(pipeline: Pipeline) -> None:
    """Run the bulk reconcile in a thread so the asyncio loop stays free.

    Initial-reconcile on aarch64 with hundreds of Markdown files takes
    minutes (each file = one embedding pass). We run it in
    :func:`asyncio.to_thread` so HTTP requests can be served by uvicorn
    in parallel — the API is responsive within seconds of container
    start, queries arriving before the sweep finishes simply see a
    partially-populated index.
    """
    try:
        summary = await asyncio.to_thread(pipeline.reconcile_all)
    except Exception:
        logger.exception("Initial reconcile failed in background")
        return
    logger.info(
        "Initial reconcile (background) complete: "
        "indexed=%d unchanged=%d skipped=%d failed=%d",
        summary.indexed,
        summary.unchanged,
        summary.skipped,
        summary.failed,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise embedder, Qdrant index, watcher, LLM, conversation store.

    Heavy work that blocks the lifespan critical path causes HA Ingress
    502s for the entire startup duration: uvicorn does not bind the port
    until the lifespan yields. We therefore keep this function bounded
    (~30 s on aarch64) by deferring the initial reconcile sweep to a
    background task — the watcher is already up and catches any
    filesystem events that arrive during the sweep, so consistency is
    preserved.
    """
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

    watcher = Watcher(pipeline=pipeline)
    watcher.start()

    llm = LLMClient(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        model=config.llm_model,
        timeout=float(config.llm_timeout),
    )
    if llm.is_configured:
        logger.info(
            "LLM configured: model=%s base_url=%s",
            config.llm_model,
            config.llm_base_url,
        )
    else:
        logger.info(
            "LLM not configured — /api/query stays in retrieval-only mode "
            "until llm_base_url and llm_model are set",
        )

    conversations = ConversationStore(db_path=config.conversations_db_path)

    app.state.embedder = embedder
    app.state.index = index
    app.state.pipeline = pipeline
    app.state.watcher = watcher
    app.state.llm = llm
    app.state.conversations = conversations

    reconcile_task = asyncio.create_task(_run_initial_reconcile(pipeline))
    app.state.reconcile_task = reconcile_task
    logger.info("Initial reconcile dispatched as background task — API is now ready")

    try:
        yield
    finally:
        reconcile_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reconcile_task
        watcher.stop()
        await llm.close()
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
    if UI_DIR.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=UI_DIR, html=True),
            name="ui",
        )
    return app
