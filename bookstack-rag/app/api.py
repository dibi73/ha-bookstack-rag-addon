"""REST endpoints exposed by the BookStack RAG add-on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Request

if TYPE_CHECKING:
    from pathlib import Path

    from app.config import Config

router = APIRouter()


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    """Return export-path health and Markdown-file count."""
    config: Config = request.app.state.config
    export_path: Path = config.bookstack_export_path
    if not export_path.is_dir():
        return {
            "status": "no_export_dir",
            "export_path": str(export_path),
            "markdown_files": 0,
        }
    markdown_count = sum(1 for _ in export_path.rglob("*.md"))
    return {
        "status": "ok",
        "export_path": str(export_path),
        "markdown_files": markdown_count,
    }
