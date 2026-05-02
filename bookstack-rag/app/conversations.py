"""SQLite-backed conversation history store for multi-turn chat.

Storage is intentionally minimal: one ``conversations`` row per chat,
one ``messages`` row per turn. The schema lives in :data:`SCHEMA` and is
applied idempotently on construction so a fresh add-on volume bootstraps
without a separate migration step.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
"""

TITLE_PREVIEW_LIMIT = 80


@dataclass(frozen=True)
class Message:
    """One stored turn in a conversation."""

    role: str
    content: str
    created_at: str


@dataclass(frozen=True)
class ConversationSummary:
    """Listing entry for /api/conversations — lightweight, no full history."""

    id: str
    title_preview: str
    message_count: int
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ConversationStore:
    """Thin wrapper around SQLite for conversation-history persistence."""

    def __init__(self, db_path: Path) -> None:
        """Open the SQLite file and ensure the schema is applied."""
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create(self) -> str:
        """Insert a new empty conversation and return its UUID."""
        cid = str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations (id, created_at, updated_at) "
                "VALUES (?, ?, ?)",
                (cid, now, now),
            )
        return cid

    def exists(self, conv_id: str) -> bool:
        """Return True if the conversation exists."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
        return row is not None

    def append(self, conv_id: str, role: str, content: str) -> None:
        """Append one message to ``conv_id`` and bump the conversation's updated_at."""
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (conv_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )

    def load(self, conv_id: str) -> list[Message]:
        """Return all messages of a conversation ordered by insertion."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages "
                "WHERE conversation_id = ? ORDER BY id",
                (conv_id,),
            ).fetchall()
        return [
            Message(
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def list_summaries(self, limit: int = 50) -> list[ConversationSummary]:
        """Return summaries ordered by most-recently-updated first."""
        query = """
            SELECT
                c.id,
                c.created_at,
                c.updated_at,
                (
                    SELECT content FROM messages
                    WHERE conversation_id = c.id AND role = 'user'
                    ORDER BY id LIMIT 1
                ) AS first_user,
                (
                    SELECT COUNT(*) FROM messages
                    WHERE conversation_id = c.id
                ) AS msg_count
            FROM conversations c
            ORDER BY c.updated_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
        result: list[ConversationSummary] = []
        for row in rows:
            preview = (row["first_user"] or "")[:TITLE_PREVIEW_LIMIT]
            result.append(
                ConversationSummary(
                    id=row["id"],
                    title_preview=preview,
                    message_count=int(row["msg_count"] or 0),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                ),
            )
        return result

    def delete(self, conv_id: str) -> None:
        """Hard-delete a conversation and all its messages (CASCADE)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def truncate_to_last_n_turns(messages: list[Message], max_turns: int) -> list[Message]:
    """Keep only the last ``max_turns`` user/assistant pairs.

    A "turn" here is a (user, assistant) pair; system messages are not
    counted but are preserved at the front. We approximate by keeping
    at most ``max_turns * 2`` user/assistant rows from the tail —
    which works correctly when conversations alternate cleanly, and
    degrades gracefully otherwise.
    """
    if max_turns <= 0:
        return [m for m in messages if m.role == "system"]
    system_msgs = [m for m in messages if m.role == "system"]
    other_msgs = [m for m in messages if m.role != "system"]
    keep = other_msgs[-(max_turns * 2) :] if other_msgs else []
    return system_msgs + keep
