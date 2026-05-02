"""Add-on configuration loaded from `/data/options.json` (HA Supervisor)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPTIONS_PATH = Path("/data/options.json")
DEFAULT_EXPORT_PATH = Path("/config/bookstack_export")
DEFAULT_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
DEFAULT_TOP_K = 5
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "bookstack_smart_home"
ADDON_OPTIONS_ENV = "ADDON_OPTIONS"


@dataclass(frozen=True)
class Config:
    """Resolved add-on configuration."""

    bookstack_export_path: Path
    embedding_model: str
    top_k: int
    qdrant_url: str
    qdrant_collection: str


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
    raw_embedding_model = data.get("embedding_model") or DEFAULT_EMBEDDING_MODEL
    raw_top_k = data.get("top_k") or DEFAULT_TOP_K
    raw_qdrant_url = data.get("qdrant_url") or QDRANT_URL
    raw_qdrant_collection = data.get("qdrant_collection") or QDRANT_COLLECTION

    return Config(
        bookstack_export_path=Path(str(raw_export_path)),
        embedding_model=str(raw_embedding_model),
        top_k=int(raw_top_k),  # type: ignore[arg-type]
        qdrant_url=str(raw_qdrant_url),
        qdrant_collection=str(raw_qdrant_collection),
    )
