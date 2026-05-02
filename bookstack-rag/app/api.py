"""REST endpoints exposed by the BookStack RAG add-on."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.conversations import truncate_to_last_n_turns
from app.llm import DEFAULT_SYSTEM_PROMPT, build_messages

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from app.config import Config
    from app.conversations import ConversationStore
    from app.embedder import SentenceTransformerEmbedder
    from app.index import Index, SearchHit
    from app.llm import LLMClient
    from app.pipeline import Pipeline


logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    """Body of POST /api/query."""

    text: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    conversation_id: str | None = None
    stream: bool = False


class HitResponse(BaseModel):
    """One result entry returned by /api/query."""

    doc_id: str
    score: float
    title: str
    content_preview: str
    bookstack_page_id: int | None


class QueryResponse(BaseModel):
    """Body of /api/query response (non-streaming)."""

    query: str
    top_k: int
    hits: list[HitResponse]
    conversation_id: str | None = None
    answer: str | None = None


class ConversationSummaryResponse(BaseModel):
    """One entry of GET /api/conversations."""

    id: str
    title_preview: str
    message_count: int
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    """One stored message in a conversation."""

    role: str
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    """Full conversation history returned by GET /api/conversations/{id}."""

    id: str
    messages: list[MessageResponse]


class ReindexResponse(BaseModel):
    """Body of /api/reindex response — mirrors ReconcileSummary."""

    indexed: int
    unchanged: int
    skipped: int
    failed: int
    total: int


def _hit_to_response(hit: SearchHit) -> HitResponse:
    return HitResponse(
        doc_id=hit.doc_id,
        score=hit.score,
        title=hit.title,
        content_preview=hit.content_preview,
        bookstack_page_id=hit.bookstack_page_id,
    )


def _resolved_system_prompt(config: Config) -> str:
    return config.system_prompt or DEFAULT_SYSTEM_PROMPT


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    """Return export-path health, Markdown-file count, and index size."""
    config: Config = request.app.state.config
    export_path: Path = config.bookstack_export_path
    index: Index | None = getattr(request.app.state, "index", None)
    indexed_count = index.count() if index is not None else 0
    llm: LLMClient | None = getattr(request.app.state, "llm", None)
    llm_configured = bool(llm and llm.is_configured)

    if not export_path.is_dir():
        return {
            "status": "no_export_dir",
            "export_path": str(export_path),
            "markdown_files": 0,
            "indexed": indexed_count,
            "llm_configured": llm_configured,
        }
    markdown_count = sum(1 for _ in export_path.rglob("*.md"))
    return {
        "status": "ok",
        "export_path": str(export_path),
        "markdown_files": markdown_count,
        "indexed": indexed_count,
        "llm_configured": llm_configured,
    }


@router.post("/query", response_model=None)
async def query(
    request: Request,
    body: QueryRequest,
) -> QueryResponse | StreamingResponse:
    """Embed the query, retrieve top-K hits, optionally synthesise an LLM answer.

    Three modes coexist on this endpoint:

    1. **Stage-1 retrieval-only mode** — when no LLM is configured and the
       client passes neither ``stream`` nor ``conversation_id``, we return
       the raw ranked hits (backwards-compatible with v0.2.0 callers).
    2. **One-shot LLM answer** — when LLM is configured and ``stream`` is
       false, the answer is returned synchronously alongside the hits.
    3. **Streaming SSE** — when ``stream`` is true, hits are emitted as
       ``event: hit`` first, then ``event: delta`` per content chunk,
       ending with ``event: done``.

    A ``conversation_id`` enables multi-turn chat: history is loaded,
    truncated to the last ``max_turns`` user/assistant pairs, and both the
    new user turn and the synthesised answer are persisted.
    """
    config: Config = request.app.state.config
    embedder: SentenceTransformerEmbedder | None = getattr(
        request.app.state,
        "embedder",
        None,
    )
    index: Index | None = getattr(request.app.state, "index", None)
    llm: LLMClient | None = getattr(request.app.state, "llm", None)
    store: ConversationStore | None = getattr(
        request.app.state,
        "conversations",
        None,
    )

    if embedder is None or index is None:
        raise HTTPException(
            status_code=503,
            detail="index not ready yet — try again in a moment",
        )

    top_k = body.top_k if body.top_k is not None else config.top_k
    vector = embedder.embed(body.text)
    hits = index.search(vector, top_k=top_k)

    llm_ready = bool(llm and llm.is_configured)

    if not llm_ready:
        if body.stream or body.conversation_id is not None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "LLM endpoint not configured — "
                    "streaming and multi-turn chat require an LLM"
                ),
            )
        return QueryResponse(
            query=body.text,
            top_k=top_k,
            hits=[_hit_to_response(hit) for hit in hits],
        )

    assert llm is not None  # for type-checker  # noqa: S101
    assert store is not None  # for type-checker  # noqa: S101

    conv_id = body.conversation_id
    if conv_id is not None and not store.exists(conv_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    if conv_id is None:
        conv_id = store.create()

    history_messages = store.load(conv_id)
    truncated = truncate_to_last_n_turns(history_messages, config.max_turns)
    history_dicts = [{"role": msg.role, "content": msg.content} for msg in truncated]

    chat_messages = build_messages(
        system_prompt=_resolved_system_prompt(config),
        history=history_dicts,
        hits=hits,
        query=body.text,
        bookstack_base_url=config.bookstack_base_url,
        homeassistant_base_url=config.homeassistant_base_url,
    )

    store.append(conv_id, "user", body.text)

    if body.stream:
        return StreamingResponse(
            _stream_events(
                hits=hits,
                chat_messages=chat_messages,
                llm=llm,
                store=store,
                conv_id=conv_id,
            ),
            media_type="text/event-stream",
        )

    answer = await llm.chat(chat_messages)
    store.append(conv_id, "assistant", answer)
    return QueryResponse(
        query=body.text,
        top_k=top_k,
        hits=[_hit_to_response(hit) for hit in hits],
        conversation_id=conv_id,
        answer=answer,
    )


async def _stream_events(
    *,
    hits: list[SearchHit],
    chat_messages: list[dict[str, str]],
    llm: LLMClient,
    store: ConversationStore,
    conv_id: str,
) -> AsyncIterator[str]:
    for hit in hits:
        payload = {
            "doc_id": hit.doc_id,
            "score": hit.score,
            "title": hit.title,
            "content_preview": hit.content_preview,
            "bookstack_page_id": hit.bookstack_page_id,
        }
        yield f"event: hit\ndata: {json.dumps(payload)}\n\n"

    parts: list[str] = []
    try:
        async for delta in llm.chat_stream(chat_messages):
            parts.append(delta)
            yield f"event: delta\ndata: {json.dumps({'content': delta})}\n\n"
    except Exception as exc:
        logger.exception("LLM streaming failed")
        yield ("event: error\ndata: " + json.dumps({"detail": str(exc)}) + "\n\n")
        return

    full_answer = "".join(parts)
    store.append(conv_id, "assistant", full_answer)
    yield ("event: done\ndata: " + json.dumps({"conversation_id": conv_id}) + "\n\n")


@router.get("/conversations", response_model=list[ConversationSummaryResponse])
def list_conversations(
    request: Request,
    limit: int = 50,
) -> list[ConversationSummaryResponse]:
    """Return up to ``limit`` conversations ordered by most-recently-updated."""
    store: ConversationStore | None = getattr(
        request.app.state,
        "conversations",
        None,
    )
    if store is None:
        raise HTTPException(status_code=503, detail="store not ready")
    return [
        ConversationSummaryResponse(
            id=summary.id,
            title_preview=summary.title_preview,
            message_count=summary.message_count,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )
        for summary in store.list_summaries(limit=limit)
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    request: Request,
    conversation_id: str,
) -> ConversationDetailResponse:
    """Return the full message list for one conversation."""
    store: ConversationStore | None = getattr(
        request.app.state,
        "conversations",
        None,
    )
    if store is None:
        raise HTTPException(status_code=503, detail="store not ready")
    if not store.exists(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return ConversationDetailResponse(
        id=conversation_id,
        messages=[
            MessageResponse(
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in store.load(conversation_id)
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(request: Request, conversation_id: str) -> None:
    """Hard-delete a conversation and all its messages."""
    store: ConversationStore | None = getattr(
        request.app.state,
        "conversations",
        None,
    )
    if store is None:
        raise HTTPException(status_code=503, detail="store not ready")
    if not store.exists(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    store.delete(conversation_id)


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
