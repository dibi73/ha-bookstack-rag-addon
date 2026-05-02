"""Tests for app.config.load_config()."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import DEFAULT_EXPORT_PATH, load_config


def test_load_config_with_explicit_path(tmp_path: Path) -> None:
    options = tmp_path / "options.json"
    options.write_text(
        json.dumps({"bookstack_export_path": "/custom/path"}),
        encoding="utf-8",
    )
    config = load_config(options)
    assert config.bookstack_export_path == Path("/custom/path")


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
