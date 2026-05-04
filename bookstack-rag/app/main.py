"""FastAPI application factory for the BookStack RAG add-on."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
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


@dataclass
class StartupState:
    """Tracks heavy-init progress so /api/status can surface it to the UI.

    Phase progression is monotonic during a healthy boot:
    starting → loading_embedder → creating_collection → indexing → ready.
    Any uncaught exception in the background init flips us to ``failed``
    and parks ``error`` with a human-readable message for the SPA to show.
    """

    phase: str = "starting"
    error: str | None = None


async def _run_startup(app: FastAPI) -> None:
    """Heavy init in the background so uvicorn binds the port within seconds.

    Loading sentence-transformers (~10-30 s on aarch64), bringing up the
    qdrant collection, and the initial reconcile sweep used to live inside
    the lifespan critical path. uvicorn does not bind the port until the
    lifespan ``yield`` is reached, so HA Ingress returned 502 for the
    entire startup duration — users saw "add-on dead". By moving the heavy
    chain into a background task we yield in <1 s; the SPA loads and polls
    ``/api/status`` for the actual readiness phase.
    """
    config: Config = app.state.config
    startup: StartupState = app.state.startup
    try:
        startup.phase = "loading_embedder"
        embedder = SentenceTransformerEmbedder(model_name=config.embedding_model)
        await asyncio.to_thread(embedder.load)
        app.state.embedder = embedder

        startup.phase = "creating_collection"
        qdrant_client = QdrantClient(url=config.qdrant_url)
        index = Index(
            client=qdrant_client,
            collection_name=config.qdrant_collection,
            vector_size=embedder.vector_size,
        )
        await asyncio.to_thread(index.ensure_collection)
        app.state.qdrant_client = qdrant_client
        app.state.index = index

        pipeline = Pipeline(
            export_path=config.bookstack_export_path,
            embedder=embedder,
            index=index,
        )
        app.state.pipeline = pipeline

        watcher = Watcher(pipeline=pipeline)
        watcher.start()
        app.state.watcher = watcher

        startup.phase = "indexing"
        summary = await asyncio.to_thread(pipeline.reconcile_all)
        logger.info(
            "Initial reconcile complete: indexed=%d unchanged=%d skipped=%d failed=%d",
            summary.indexed,
            summary.unchanged,
            summary.skipped,
            summary.failed,
        )

        startup.phase = "ready"
        logger.info("Startup complete — add-on fully ready")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Startup initialisation failed")
        startup.phase = "failed"
        startup.error = str(exc)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring up lightweight services synchronously; defer heavy work.

    Light deps (LLM client construction, SQLite conversation-store
    bootstrap) initialise here so they're ready the moment the API is
    reachable. The embedder, qdrant collection, watcher and initial
    reconcile run in a background task — see :func:`_run_startup`.
    """
    config: Config = app.state.config
    logger.info("Starting BookStack RAG v%s", __version__)

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

    app.state.llm = llm
    app.state.conversations = conversations
    app.state.startup = StartupState()
    app.state.embedder = None
    app.state.index = None
    app.state.pipeline = None
    app.state.watcher = None
    app.state.qdrant_client = None

    startup_task = asyncio.create_task(_run_startup(app))
    app.state.startup_task = startup_task
    logger.info(
        "Heavy initialisation dispatched as background task — "
        "API is now serving requests",
    )

    try:
        yield
    finally:
        startup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await startup_task
        watcher = getattr(app.state, "watcher", None)
        if watcher is not None:
            watcher.stop()
        await llm.close()
        qdrant_client = getattr(app.state, "qdrant_client", None)
        if qdrant_client is not None:
            qdrant_client.close()


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
