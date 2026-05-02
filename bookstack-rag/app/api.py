"""REST endpoints exposed by the BookStack RAG add-on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path

    from app.config import Config
    from app.embedder import SentenceTransformerEmbedder
    from app.index import Index
    from app.pipeline import Pipeline


router = APIRouter()


class QueryRequest(BaseModel):
    """Body of POST /api/query."""

    text: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)


class HitResponse(BaseModel):
    """One result entry returned by /api/query."""

    doc_id: str
    score: float
    title: str
    content_preview: str
    bookstack_page_id: int | None


class QueryResponse(BaseModel):
    """Body of /api/query response."""

    query: str
    top_k: int
    hits: list[HitResponse]


class ReindexResponse(BaseModel):
    """Body of /api/reindex response — mirrors ReconcileSummary."""

    indexed: int
    unchanged: int
    skipped: int
    failed: int
    total: int


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    """Return export-path health, Markdown-file count, and index size."""
    config: Config = request.app.state.config
    export_path: Path = config.bookstack_export_path
    index: Index | None = getattr(request.app.state, "index", None)
    indexed_count = index.count() if index is not None else 0

    if not export_path.is_dir():
        return {
            "status": "no_export_dir",
            "export_path": str(export_path),
            "markdown_files": 0,
            "indexed": indexed_count,
        }
    markdown_count = sum(1 for _ in export_path.rglob("*.md"))
    return {
        "status": "ok",
        "export_path": str(export_path),
        "markdown_files": markdown_count,
        "indexed": indexed_count,
    }


@router.post("/query", response_model=QueryResponse)
def query(request: Request, body: QueryRequest) -> QueryResponse:
    """Embed the user's question and return the top-K matching documents."""
    config: Config = request.app.state.config
    embedder: SentenceTransformerEmbedder | None = getattr(
        request.app.state,
        "embedder",
        None,
    )
    index: Index | None = getattr(request.app.state, "index", None)
    if embedder is None or index is None:
        raise HTTPException(
            status_code=503,
            detail="index not ready yet — try again in a moment",
        )

    top_k = body.top_k if body.top_k is not None else config.top_k
    vector = embedder.embed(body.text)
    hits = index.search(vector, top_k=top_k)

    return QueryResponse(
        query=body.text,
        top_k=top_k,
        hits=[
            HitResponse(
                doc_id=hit.doc_id,
                score=hit.score,
                title=hit.title,
                content_preview=hit.content_preview,
                bookstack_page_id=hit.bookstack_page_id,
            )
            for hit in hits
        ],
    )


@router.post("/reindex", response_model=ReindexResponse)
def reindex(request: Request) -> ReindexResponse:
    """Trigger a full reconcile sweep — same logic as the startup scan."""
    pipeline: Pipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="index not ready yet — try again in a moment",
        )
    summary = pipeline.reconcile_all()
    return ReindexResponse(
        indexed=summary.indexed,
        unchanged=summary.unchanged,
        skipped=summary.skipped,
        failed=summary.failed,
        total=summary.total,
    )
