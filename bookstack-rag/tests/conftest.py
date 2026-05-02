"""Shared pytest fixtures for the BookStack RAG add-on test suite.

Tests deliberately bypass the production FastAPI lifespan — that one connects
to a live Qdrant sidecar, downloads a 500 MB embedding model, and opens a
real HTTP client to the configured LLM endpoint. We build the same dependency
graph by hand using a deterministic :class:`FakeEmbedder`, Qdrant's
``:memory:`` mode, a SQLite ``ConversationStore`` on a tmp_path file, and
either no LLM or a :class:`FakeLLMClient`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from app import __version__
from app.api import router
from app.config import Config, load_config
from app.conversations import ConversationStore
from app.embedder import FakeEmbedder
from app.index import Index
from app.llm import FakeLLMClient
from app.pipeline import Pipeline
from fastapi import FastAPI
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    """Empty Markdown-export directory the API is pointed at."""
    target = tmp_path / "bookstack_export"
    target.mkdir()
    return target


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    """Deterministic embedder used everywhere except real-model integration tests."""
    return FakeEmbedder(vector_size=8)


@pytest.fixture
def qdrant_client() -> QdrantClient:
    """In-memory Qdrant — no sidecar, no disk, isolated per test."""
    return QdrantClient(":memory:")


@pytest.fixture
def index(qdrant_client: QdrantClient, fake_embedder: FakeEmbedder) -> Index:
    idx = Index(
        client=qdrant_client,
        collection_name="test_collection",
        vector_size=fake_embedder.vector_size,
    )
    idx.ensure_collection()
    return idx


@pytest.fixture
def pipeline(
    export_dir: Path,
    fake_embedder: FakeEmbedder,
    index: Index,
) -> Pipeline:
    return Pipeline(export_path=export_dir, embedder=fake_embedder, index=index)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    """Stub LLM that returns a single canned reply."""
    return FakeLLMClient(canned_response="[fake answer]")


@pytest.fixture
def fake_llm_streaming() -> FakeLLMClient:
    """Stub LLM that yields a small sequence of streaming deltas."""
    return FakeLLMClient(deltas=["Hello", " ", "world"])


@pytest.fixture
def conversations_store(tmp_path: Path) -> ConversationStore:
    """Per-test SQLite conversation store at a temporary path."""
    return ConversationStore(db_path=tmp_path / "conversations.db")


@pytest.fixture
def options_file(export_dir: Path, tmp_path: Path) -> Path:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"bookstack_export_path": str(export_dir)}),
        encoding="utf-8",
    )
    return options


def _build_app(  # noqa: PLR0913
    *,
    config: Config,
    embedder: FakeEmbedder | None = None,
    index: Index | None = None,
    pipeline: Pipeline | None = None,
    llm: FakeLLMClient | None = None,
    conversations: ConversationStore | None = None,
) -> FastAPI:
    app = FastAPI(title="BookStack RAG", description="test", version=__version__)
    app.state.config = config
    if embedder is not None:
        app.state.embedder = embedder
    if index is not None:
        app.state.index = index
    if pipeline is not None:
        app.state.pipeline = pipeline
    if llm is not None:
        app.state.llm = llm
    if conversations is not None:
        app.state.conversations = conversations
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def test_app(  # noqa: PLR0913
    options_file: Path,
    fake_embedder: FakeEmbedder,
    index: Index,
    pipeline: Pipeline,
    fake_llm: FakeLLMClient,
    conversations_store: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    """FastAPI app with a fully wired prod-equivalent state for happy-path tests."""
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))
    config = load_config()
    return _build_app(
        config=config,
        embedder=fake_embedder,
        index=index,
        pipeline=pipeline,
        llm=fake_llm,
        conversations=conversations_store,
    )


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    return TestClient(test_app)


@pytest.fixture
def client_no_llm(  # noqa: PLR0913
    options_file: Path,
    fake_embedder: FakeEmbedder,
    index: Index,
    pipeline: Pipeline,
    conversations_store: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Client where index is ready but no LLM is configured (Stage-1 mode)."""
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))
    config = load_config()
    no_llm = FakeLLMClient(is_configured=False)
    app = _build_app(
        config=config,
        embedder=fake_embedder,
        index=index,
        pipeline=pipeline,
        llm=no_llm,
        conversations=conversations_store,
    )
    return TestClient(app)


@pytest.fixture
def client_streaming_llm(  # noqa: PLR0913
    options_file: Path,
    fake_embedder: FakeEmbedder,
    index: Index,
    pipeline: Pipeline,
    fake_llm_streaming: FakeLLMClient,
    conversations_store: ConversationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Client with a streaming-capable FakeLLMClient — exercises the SSE path."""
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))
    config = load_config()
    app = _build_app(
        config=config,
        embedder=fake_embedder,
        index=index,
        pipeline=pipeline,
        llm=fake_llm_streaming,
        conversations=conversations_store,
    )
    return TestClient(app)


@pytest.fixture
def client_no_index(
    options_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Variant without embedder/index/pipeline — used to verify 503 fallback paths."""
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))
    config = load_config()
    app = _build_app(config=config)
    return TestClient(app)


@pytest.fixture
def write_markdown(export_dir: Path):
    """Helper to drop a Markdown file (optionally with frontmatter) into the export dir."""  # noqa: E501

    def _write(
        relative: str,
        body: str,
        metadata: dict[str, object] | None = None,
    ) -> Path:
        target = export_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if metadata:
            import frontmatter as fm  # noqa: PLC0415

            post = fm.Post(body, **metadata)
            text = fm.dumps(post)
        else:
            text = body
        target.write_text(text, encoding="utf-8")
        return target

    return _write


@pytest.fixture
def base_config(export_dir: Path) -> Config:
    return Config(
        bookstack_export_path=export_dir,
        embedding_model="nomic-ai/nomic-embed-text-v1.5",
        top_k=5,
        qdrant_url="http://localhost:6333",
        qdrant_collection="test_collection",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        llm_timeout=60,
        max_turns=20,
        system_prompt="",
        conversations_db_path=export_dir.parent / "conversations.db",
        bookstack_base_url="",
        homeassistant_base_url="",
    )
