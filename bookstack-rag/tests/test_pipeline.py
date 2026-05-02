"""Tests for the reconcile pipeline that owns the watcher / startup-scan / API logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.index import doc_id_for_path

if TYPE_CHECKING:
    from app.pipeline import Pipeline


def test_reconcile_indexes_new_file(pipeline: Pipeline, write_markdown) -> None:
    write_markdown(
        "devices/light.md",
        "Light entity in the living room.",
        metadata={"title": "Living Room Light", "bookstack_page_id": 11},
    )
    summary = pipeline.reconcile_all()
    assert summary.indexed == 1
    assert summary.unchanged == 0
    assert summary.total == 1


def test_reconcile_skips_unchanged_file(pipeline: Pipeline, write_markdown) -> None:
    write_markdown("a.md", "stable body")
    pipeline.reconcile_all()
    second = pipeline.reconcile_all()
    assert second.indexed == 0
    assert second.unchanged == 1


def test_reconcile_picks_up_modified_file(pipeline: Pipeline, write_markdown) -> None:
    path = write_markdown("a.md", "first version")
    pipeline.reconcile_all()
    path.write_text("second version", encoding="utf-8")
    summary = pipeline.reconcile_all()
    assert summary.indexed == 1
    assert summary.unchanged == 0


def test_reconcile_skips_non_markdown(pipeline: Pipeline, export_dir) -> None:
    (export_dir / "ignore.txt").write_text("not markdown", encoding="utf-8")
    summary = pipeline.reconcile_all()
    assert summary.total == 0  # rglob *.md does not list it at all


def test_reconcile_handles_subdirectories(pipeline: Pipeline, write_markdown) -> None:
    write_markdown("devices/a.md", "device A")
    write_markdown("devices/b.md", "device B")
    write_markdown("areas/lr.md", "living room")
    summary = pipeline.reconcile_all()
    assert summary.indexed == 3


def test_reconcile_path_tombstones_on_delete(
    pipeline: Pipeline,
    write_markdown,
    index,
) -> None:
    path = write_markdown("a.md", "transient")
    pipeline.reconcile_all()
    relative = path.relative_to(pipeline.export_path).as_posix()
    doc_id = doc_id_for_path(relative)
    assert index.get_stored_hash(doc_id) is not None

    path.unlink()
    outcome = pipeline.reconcile_path(path)
    assert outcome.action == "indexed"
    assert outcome.reason == "tombstoned"
    # The point still exists but is filtered from search.
    hits = index.search(query_vector=[0.0] * index._vector_size, top_k=10)
    assert hits == []


def test_reconcile_payload_contains_frontmatter_metadata(
    pipeline: Pipeline,
    write_markdown,
    index,
) -> None:
    path = write_markdown(
        "devices/light.md",
        "Living room light with manual notes.",
        metadata={
            "title": "Living Room Light",
            "bookstack_page_id": 42,
            "bookstack_chapter": "Devices",
            "ha_object_kind": "device",
            "ha_object_id": "light.lr_main",
        },
    )
    pipeline.reconcile_path(path)

    relative = path.relative_to(pipeline.export_path).as_posix()
    stored_hash = index.get_stored_hash(doc_id_for_path(relative))
    assert stored_hash is not None
    # search and assert payload made it through
    hits = index.search(
        query_vector=pipeline._embedder.embed("Living room light"),
        top_k=1,
    )
    assert hits
    assert hits[0].title == "Living Room Light"
    assert hits[0].bookstack_page_id == 42
    assert hits[0].payload["bookstack_chapter"] == "Devices"
    assert hits[0].payload["ha_object_kind"] == "device"
