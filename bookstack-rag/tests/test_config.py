"""Tests for app.config.load_config()."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EXPORT_PATH,
    DEFAULT_TOP_K,
    QDRANT_COLLECTION,
    QDRANT_URL,
    load_config,
)


def test_load_config_with_explicit_path(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"bookstack_export_path": "/custom/path"}),
        encoding="utf-8",
    )
    config = load_config(options)
    assert config.bookstack_export_path == Path("/custom/path")
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.top_k == DEFAULT_TOP_K
    assert config.qdrant_url == QDRANT_URL
    assert config.qdrant_collection == QDRANT_COLLECTION


def test_load_config_falls_back_when_file_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / "no-such.json")
    assert config.bookstack_export_path == DEFAULT_EXPORT_PATH


def test_load_config_falls_back_when_option_empty(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text(json.dumps({"bookstack_export_path": ""}), encoding="utf-8")
    config = load_config(options)
    assert config.bookstack_export_path == DEFAULT_EXPORT_PATH


def test_load_config_uses_env_override(tmp_path: Path, monkeypatch) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"bookstack_export_path": "/from/env"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ADDON_OPTIONS", str(options))
    config = load_config()
    assert config.bookstack_export_path == Path("/from/env")


def test_load_config_reads_stage1_options(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps(
            {
                "bookstack_export_path": "/x",
                "embedding_model": "BAAI/bge-base-en-v1.5",
                "top_k": 12,
                "qdrant_url": "http://qdrant:7000",
                "qdrant_collection": "alt",
            },
        ),
        encoding="utf-8",
    )
    config = load_config(options)
    assert config.embedding_model == "BAAI/bge-base-en-v1.5"
    assert config.top_k == 12
    assert config.qdrant_url == "http://qdrant:7000"
    assert config.qdrant_collection == "alt"
