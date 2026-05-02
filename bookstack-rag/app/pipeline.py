"""Reconcile pipeline shared by the watcher, the startup scan, and the manual reindex.

Per HARD RULE §3.7 of the project conventions, all three entry points (file
watcher event, container-startup initial scan, manual ``/api/reindex``) MUST
call into the same logic — that's what this module is. Each one wraps
:func:`reconcile_path` for a single file or :func:`reconcile_all` for a full
sweep, and the actual hash-vs-Qdrant comparison lives in exactly one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.frontmatter_parser import hash_file, parse_markdown_file
from app.index import IndexedDocument, doc_id_for_path

if TYPE_CHECKING:
    from pathlib import Path

    from app.embedder import SentenceTransformerEmbedder
    from app.index import Index

logger = logging.getLogger(__name__)

CONTENT_PREVIEW_LIMIT = 500


@dataclass(frozen=True)
class ReconcileOutcome:
    """Per-file result of a reconcile pass — used by the API + tests for assertions."""

    relative_path: str
    action: str  # "indexed" | "unchanged" | "skipped" | "failed"
    reason: str | None = None


@dataclass(frozen=True)
class ReconcileSummary:
    """Aggregate of a reconcile sweep."""

    indexed: int
    unchanged: int
    skipped: int
    failed: int

    @property
    def total(self) -> int:
        """Sum of all per-action buckets — convenience for status responses."""
        return self.indexed + self.unchanged + self.skipped + self.failed


class Pipeline:
    """Glue between filesystem, embedder, and vector index."""

    def __init__(
        self,
        export_path: Path,
        embedder: SentenceTransformerEmbedder,
        index: Index,
    ) -> None:
        """Bind the pipeline to a watched export root, an embedder, and the index."""
        self._export_path = export_path
        self._embedder = embedder
        self._index = index

    @property
    def export_path(self) -> Path:
        """Return the directory the pipeline watches and reconciles."""
        return self._export_path

    def reconcile_path(self, path: Path) -> ReconcileOutcome:
        """Reconcile a single Markdown file against the index."""
        if not path.exists():
            return self._handle_deleted(path)

        skip_reason = self._skip_reason(path)
        if skip_reason is not None:
            return ReconcileOutcome(
                relative_path=self._relative(path),
                action="skipped",
                reason=skip_reason,
            )

        relative = self._relative(path)
        doc_id = doc_id_for_path(relative)

        try:
            current_hash = hash_file(path)
        except OSError as exc:
            logger.warning("Could not hash %s: %s", path, exc)
            return ReconcileOutcome(
                relative_path=relative,
                action="failed",
                reason=str(exc),
            )

        stored_hash = self._index.get_stored_hash(doc_id)
        if stored_hash == current_hash:
            return ReconcileOutcome(relative_path=relative, action="unchanged")

        try:
            doc = parse_markdown_file(path)
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Could not parse %s: %s", path, exc)
            return ReconcileOutcome(
                relative_path=relative,
                action="failed",
                reason=str(exc),
            )

        vector = self._embedder.embed(doc.body)
        payload = self._build_payload(doc.metadata, doc.body, current_hash, relative)
        self._index.upsert(
            IndexedDocument(doc_id=doc_id, vector=vector, payload=payload),
        )

        logger.info("Indexed %s (hash %s)", relative, current_hash[:12])
        return ReconcileOutcome(relative_path=relative, action="indexed")

    @staticmethod
    def _skip_reason(path: Path) -> str | None:
        """Return a reason if the path should be skipped, else None."""
        if path.is_dir():
            return "path is a directory"
        if path.suffix.lower() != ".md":
            return "not a Markdown file"
        return None

    def reconcile_all(self) -> ReconcileSummary:
        """Walk the export directory and reconcile every Markdown file."""
        if not self._export_path.is_dir():
            logger.info(
                "Export path %s does not exist — nothing to reconcile",
                self._export_path,
            )
            return ReconcileSummary(0, 0, 0, 0)

        indexed = unchanged = skipped = failed = 0
        for path in self._export_path.rglob("*.md"):
            outcome = self.reconcile_path(path)
            if outcome.action == "indexed":
                indexed += 1
            elif outcome.action == "unchanged":
                unchanged += 1
            elif outcome.action == "skipped":
                skipped += 1
            else:
                failed += 1
        logger.info(
            "Reconcile sweep: indexed=%d unchanged=%d skipped=%d failed=%d",
            indexed,
            unchanged,
            skipped,
            failed,
        )
        return ReconcileSummary(
            indexed=indexed,
            unchanged=unchanged,
            skipped=skipped,
            failed=failed,
        )

    def _handle_deleted(self, path: Path) -> ReconcileOutcome:
        relative = self._relative(path)
        doc_id = doc_id_for_path(relative)
        if self._index.get_stored_hash(doc_id) is not None:
            self._index.tombstone(doc_id)
            logger.info("Tombstoned %s", relative)
            return ReconcileOutcome(
                relative_path=relative,
                action="indexed",
                reason="tombstoned",
            )
        return ReconcileOutcome(
            relative_path=relative,
            action="skipped",
            reason="not in index",
        )

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(self._export_path).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _build_payload(
        metadata: dict[str, object],
        body: str,
        content_hash: str,
        relative: str,
    ) -> dict[str, object]:
        bookstack_page_id = metadata.get("bookstack_page_id")
        return {
            "title": metadata.get("title", relative),
            "bookstack_page_id": (
                int(bookstack_page_id) if isinstance(bookstack_page_id, int) else None
            ),
            "bookstack_chapter": metadata.get("bookstack_chapter"),
            "ha_object_kind": metadata.get("ha_object_kind"),
            "ha_object_id": metadata.get("ha_object_id"),
            "tombstoned": False,
            "last_synced": metadata.get("last_synced"),
            "content_hash": content_hash,
            "content_preview": body[:CONTENT_PREVIEW_LIMIT],
            "filepath": relative,
        }
