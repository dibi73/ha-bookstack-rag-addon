"""Tests for the REST endpoints exposed by the add-on."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.main import create_app
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path


def test_status_with_empty_export_dir(client: TestClient, export_dir: Path) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ok",
        "export_path": str(export_dir),
        "markdown_files": 0,
    }


def test_status_counts_markdown_files_recursively(
    client: TestClient,
    export_dir: Path,
) -> None:
    (export_dir / "a.md").write_text("# A", encoding="utf-8")
    (export_dir / "b.md").write_text("# B", encoding="utf-8")
    nested = export_dir / "devices"
    nested.mkdir()
    (nested / "c.md").write_text("# C", encoding="utf-8")
    (export_dir / "ignore.txt").write_text("not markdown", encoding="utf-8")

    response = client.get("/api/status")
    assert response.status_code == 200
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

    with TestClient(create_app()) as missing_client:
        response = missing_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_export_dir"
    assert body["markdown_files"] == 0
