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
DEFAULT_MAX_TURNS = 20
DEFAULT_LLM_TIMEOUT = 60
DEFAULT_CONVERSATIONS_DB = Path("/data/conversations.db")
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
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: int
    max_turns: int
    system_prompt: str
    conversations_db_path: Path
    bookstack_base_url: str
    homeassistant_base_url: str


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
    raw_max_turns = data.get("max_turns") or DEFAULT_MAX_TURNS
    raw_llm_timeout = data.get("llm_timeout") or DEFAULT_LLM_TIMEOUT
    raw_conversations_db = data.get("conversations_db_path") or str(
        DEFAULT_CONVERSATIONS_DB
    )

    return Config(
        bookstack_export_path=Path(str(raw_export_path)),
        embedding_model=str(raw_embedding_model),
        top_k=int(raw_top_k),  # type: ignore[arg-type]
        qdrant_url=str(raw_qdrant_url),
        qdrant_collection=str(raw_qdrant_collection),
        llm_base_url=str(data.get("llm_base_url") or ""),
        llm_api_key=str(data.get("llm_api_key") or ""),
        llm_model=str(data.get("llm_model") or ""),
        llm_timeout=int(raw_llm_timeout),  # type: ignore[arg-type]
        max_turns=int(raw_max_turns),  # type: ignore[arg-type]
        system_prompt=str(data.get("system_prompt") or ""),
        conversations_db_path=Path(str(raw_conversations_db)),
        bookstack_base_url=str(data.get("bookstack_base_url") or ""),
        homeassistant_base_url=str(data.get("homeassistant_base_url") or ""),
    )
