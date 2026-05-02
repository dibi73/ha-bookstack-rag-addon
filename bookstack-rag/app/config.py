"""Add-on configuration loaded from `/data/options.json` (HA Supervisor)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPTIONS_PATH = Path("/data/options.json")
DEFAULT_EXPORT_PATH = Path("/config/bookstack_export")
ADDON_OPTIONS_ENV = "ADDON_OPTIONS"


@dataclass(frozen=True)
class Config:
    """Resolved add-on configuration."""

    bookstack_export_path: Path


def _resolve_options_path(options_path: Path | None) -> Path:
    """Allow tests to override the options-file location via env var."""
    if options_path is not None:
        return options_path
    override = os.environ.get(ADDON_OPTIONS_ENV)
    if override:
        return Path(override)
    return DEFAULT_OPTIONS_PATH


def load_config(options_path: Path | None = None) -> Config:
    """Read add-on options from disk; fall back to defaults if missing."""
    path = _resolve_options_path(options_path)
    data: dict[str, object] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    raw_export_path = data.get("bookstack_export_path") or str(DEFAULT_EXPORT_PATH)
    return Config(bookstack_export_path=Path(str(raw_export_path)))
