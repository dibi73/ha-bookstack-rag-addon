"""Parse YAML frontmatter and Markdown body from add-on-managed export files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import frontmatter

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ParsedDocument:
    """A Markdown file split into structured metadata and body text."""

    filepath: Path
    metadata: dict[str, Any]
    body: str
    content_hash: str


def parse_markdown_file(path: Path) -> ParsedDocument:
    """Read a Markdown file and split it into frontmatter metadata + body.

    The content hash is computed over the raw file bytes so that tombstoning,
    rename detection and idempotency checks all see the same value regardless
    of how YAML serialisation might reorder keys.
    """
    raw_bytes = path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    parsed = frontmatter.loads(raw_bytes.decode("utf-8"))

    return ParsedDocument(
        filepath=path,
        metadata=dict(parsed.metadata),
        body=parsed.content,
        content_hash=content_hash,
    )


def hash_file(path: Path) -> str:
    """Compute the SHA-256 of a file's bytes — same algorithm as parse_markdown_file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
