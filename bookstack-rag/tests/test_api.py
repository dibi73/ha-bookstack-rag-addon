"""Tests for the REST endpoints exposed by the add-on."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app import __version__
from app.api import router
from app.config import load_config
from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path

    from app.pipeline import Pipeline


def test_status_with_empty_export_dir(client: TestClient, export_dir: Path) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["export_path"] == str(export_dir)
    assert body["markdown_files"] == 0
    assert body["indexed"] == 0


def test_status_counts_markdown_files_recursively(
    client: TestClient,
    write_markdown,
) -> None:
    write_markdown("a.md", "# A")
    write_markdown("b.md", "# B")
    write_markdown("devices/c.md", "# C")
    write_markdown("ignore.txt", "not markdown")  # rglob *.md ignores this

    response = client.get("/api/status")
    body = response.json()
    assert body["status"] == "ok"
    assert body["markdown_files"] == 3


def test_status_when_export_dir_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    options_file = tmp_path / "options.json"
    options_file.write_text(
        json.dumps({"bookstack_export_path": str(tmp_path / "does_not_exist")}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))

    config = load_config()
    app = FastAPI(title="t", version=__version__)
    app.state.config = config
    app.include_router(router, prefix="/api")
    with TestClient(app) as missing_client:
        response = missing_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_export_dir"
    assert body["markdown_files"] == 0


def test_query_returns_top_k(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    write_markdown(
        "lr.md",
        "Living room ceiling lamp with motion-sensor automation.",
        metadata={"title": "Living Room Light", "bookstack_page_id": 1},
    )
    write_markdown(
        "kitchen.md",
        "Kitchen island pendant on a smart plug.",
        metadata={"title": "Kitchen Light", "bookstack_page_id": 2},
    )
    pipeline.reconcile_all()

    response = client.post(
        "/api/query",
        json={"text": "Living room ceiling lamp with motion-sensor automation."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"].startswith("Living room")
    assert body["top_k"] == 5
    assert len(body["hits"]) >= 1
    assert body["hits"][0]["title"] == "Living Room Light"
    assert body["hits"][0]["bookstack_page_id"] == 1


def test_query_respects_explicit_top_k(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    for i in range(5):
        write_markdown(f"d{i}.md", f"document number {i} alpha")
    pipeline.reconcile_all()

    response = client.post("/api/query", json={"text": "alpha", "top_k": 2})
    body = response.json()
    assert body["top_k"] == 2
    assert len(body["hits"]) == 2


def test_query_validates_empty_text(client: TestClient) -> None:
    response = client.post("/api/query", json={"text": ""})
    assert response.status_code == 422


def test_query_503_when_index_not_ready(client_no_index: TestClient) -> None:
    response = client_no_index.post("/api/query", json={"text": "anything"})
    assert response.status_code == 503


def test_reindex_runs_reconcile_sweep(
    client: TestClient,
    write_markdown,
) -> None:
    write_markdown("a.md", "first")
    write_markdown("b.md", "second")
    response = client.post("/api/reindex")
    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] == 2
    assert body["total"] == 2


def test_reindex_503_when_pipeline_not_ready(client_no_index: TestClient) -> None:
    response = client_no_index.post("/api/reindex")
    assert response.status_code == 503
