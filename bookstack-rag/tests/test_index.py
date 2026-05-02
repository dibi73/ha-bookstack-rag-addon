"""Tests for the Qdrant Index wrapper, using :memory: mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.index import IndexedDocument, doc_id_for_path

if TYPE_CHECKING:
    from app.embedder import FakeEmbedder


def test_doc_id_is_stable_and_path_dependent() -> None:
    a = doc_id_for_path("devices/light.md")
    b = doc_id_for_path("devices/light.md")
    c = doc_id_for_path("devices/other.md")
    assert a == b
    assert a != c


def test_ensure_collection_is_idempotent(qdrant_client, index) -> None:
    # second call should not blow up
    index.ensure_collection()
    assert index.count() == 0


def test_upsert_and_get_stored_hash(index, fake_embedder: FakeEmbedder) -> None:
    doc_id = doc_id_for_path("devices/light.md")
    payload = {
        "title": "Light",
        "content_hash": "deadbeef",
        "tombstoned": False,
    }
    index.upsert(
        IndexedDocument(
            doc_id=doc_id,
            vector=fake_embedder.embed("Light"),
            payload=payload,
        ),
    )
    assert index.get_stored_hash(doc_id) == "deadbeef"
    assert index.count() == 1


def test_search_returns_hits_sorted_by_score(
    index,
    fake_embedder: FakeEmbedder,
) -> None:
    docs = [
        ("a.md", "alpha document"),
        ("b.md", "beta document"),
        ("c.md", "gamma document"),
    ]
    for path, body in docs:
        index.upsert(
            IndexedDocument(
                doc_id=doc_id_for_path(path),
                vector=fake_embedder.embed(body),
                payload={
                    "title": path,
                    "content_preview": body,
                    "content_hash": "h",
                    "tombstoned": False,
                    "bookstack_page_id": None,
                },
            ),
        )

    hits = index.search(query_vector=fake_embedder.embed("alpha document"), top_k=3)
    assert len(hits) == 3
    assert hits[0].title == "a.md"  # exact match wins
    # scores must be monotonically non-increasing
    assert all(hits[i].score >= hits[i + 1].score for i in range(len(hits) - 1))


def test_tombstoned_documents_are_excluded_from_search(
    index,
    fake_embedder: FakeEmbedder,
) -> None:
    doc_id = doc_id_for_path("devices/light.md")
    index.upsert(
        IndexedDocument(
            doc_id=doc_id,
            vector=fake_embedder.embed("light entity"),
            payload={
                "title": "Light",
                "content_preview": "light entity",
                "content_hash": "h",
                "tombstoned": False,
                "bookstack_page_id": None,
            },
        ),
    )
    hits_before = index.search(fake_embedder.embed("light entity"), top_k=5)
    assert len(hits_before) == 1

    index.tombstone(doc_id)
    hits_after = index.search(fake_embedder.embed("light entity"), top_k=5)
    assert hits_after == []
    # but the point is still there
    assert index.count() == 1


def test_get_stored_hash_returns_none_for_missing(index) -> None:
    assert index.get_stored_hash(doc_id_for_path("never/seen.md")) is None
