"""Qdrant wrapper for collection lifecycle, idempotent upserts, and search."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    """One result from a vector search, ready to be returned to the client."""

    doc_id: str
    score: float
    title: str
    content_preview: str
    bookstack_page_id: int | None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IndexedDocument:
    """The minimal record stored per Markdown file."""

    doc_id: str
    vector: list[float]
    payload: dict[str, Any]


def doc_id_for_path(filepath: str) -> str:
    """Stable, Qdrant-acceptable point ID derived from the relative file path."""
    # Qdrant accepts UUIDs or unsigned ints — we hash the path to a 64-bit int
    # so renames produce a different doc_id (which is what we want — rename =
    # new logical document).
    digest = hashlib.sha256(filepath.encode("utf-8")).digest()
    return str(int.from_bytes(digest[:8], "big"))


class Index:
    """Thin wrapper over QdrantClient that owns the add-on's single collection."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        vector_size: int,
    ) -> None:
        """Bind the wrapper to a QdrantClient and the single owned collection."""
        self._client = client
        self._collection = collection_name
        self._vector_size = vector_size

    @property
    def collection_name(self) -> str:
        """Return the Qdrant collection name owned by this wrapper."""
        return self._collection

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            return
        logger.info(
            "Creating Qdrant collection %s with vector size %d",
            self._collection,
            self._vector_size,
        )
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(
                size=self._vector_size,
                distance=Distance.COSINE,
            ),
        )

    def get_stored_hash(self, doc_id: str) -> str | None:
        """Return the content_hash currently stored for ``doc_id``, or None."""
        points = self._client.retrieve(
            collection_name=self._collection,
            ids=[int(doc_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        payload = points[0].payload or {}
        stored = payload.get("content_hash")
        if stored is None:
            return None
        return str(stored)

    def upsert(self, document: IndexedDocument) -> None:
        """Insert or replace one document. Caller is expected to have hashed already."""
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(
                    id=int(document.doc_id),
                    vector=document.vector,
                    payload=document.payload,
                ),
            ],
        )

    def tombstone(self, doc_id: str) -> None:
        """Mark a document as gone without deleting it (preserves search history)."""
        self._client.set_payload(
            collection_name=self._collection,
            payload={"tombstoned": True},
            points=[int(doc_id)],
        )

    def delete(self, doc_id: str) -> None:
        """Hard-delete a point. Only used when we know the file is gone for good."""
        self._client.delete(
            collection_name=self._collection,
            points_selector=[int(doc_id)],
        )

    def search(self, query_vector: list[float], top_k: int) -> list[SearchHit]:
        """Cosine search excluding tombstoned points."""
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            query_filter=Filter(
                must_not=[
                    FieldCondition(
                        key="tombstoned",
                        match=MatchValue(value=True),
                    ),
                ],
            ),
        ).points
        hits: list[SearchHit] = []
        for point in results:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    doc_id=str(point.id),
                    score=float(point.score),
                    title=str(payload.get("title", "")),
                    content_preview=str(payload.get("content_preview", "")),
                    bookstack_page_id=(
                        int(payload["bookstack_page_id"])
                        if payload.get("bookstack_page_id") is not None
                        else None
                    ),
                    payload=dict(payload),
                ),
            )
        return hits

    def count(self) -> int:
        """Total number of points in the collection (including tombstoned ones)."""
        return self._client.count(collection_name=self._collection, exact=True).count
