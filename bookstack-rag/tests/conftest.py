"""Shared pytest fixtures for the BookStack RAG add-on test suite."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from app.main import create_app
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    """Empty Markdown-export directory the API is pointed at."""
    target = tmp_path / "bookstack_export"
    target.mkdir()
    return target


@pytest.fixture
def client(
    export_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """FastAPI TestClient bound to a temporary export directory."""
    options_file = tmp_path / "options.json"
    options_file.write_text(
        json.dumps({"bookstack_export_path": str(export_dir)}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))
    return TestClient(create_app())
