"""Tests for the SQLite-backed ConversationStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.conversations import ConversationStore, Message, truncate_to_last_n_turns

if TYPE_CHECKING:
    from pathlib import Path


def test_create_returns_unique_id(conversations_store: ConversationStore) -> None:
    a = conversations_store.create()
    b = conversations_store.create()
    assert a != b


def test_exists_after_create(conversations_store: ConversationStore) -> None:
    cid = conversations_store.create()
    assert conversations_store.exists(cid) is True


def test_exists_false_for_unknown(conversations_store: ConversationStore) -> None:
    assert conversations_store.exists("not-a-real-id") is False


def test_append_then_load_returns_in_order(
    conversations_store: ConversationStore,
) -> None:
    cid = conversations_store.create()
    conversations_store.append(cid, "user", "first")
    conversations_store.append(cid, "assistant", "second")
    conversations_store.append(cid, "user", "third")

    messages = conversations_store.load(cid)
    assert [m.content for m in messages] == ["first", "second", "third"]
    assert [m.role for m in messages] == ["user", "assistant", "user"]


def test_list_summaries_orders_by_recent_update(
    conversations_store: ConversationStore,
) -> None:
    a = conversations_store.create()
    b = conversations_store.create()
    conversations_store.append(a, "user", "old")
    conversations_store.append(b, "user", "newer")

    summaries = conversations_store.list_summaries()
    assert summaries[0].id == b
    assert summaries[1].id == a


def test_summary_includes_first_user_preview(
    conversations_store: ConversationStore,
) -> None:
    cid = conversations_store.create()
    long_question = "What does the motion sensor in the hallway do?" * 4
    conversations_store.append(cid, "user", long_question)
    conversations_store.append(cid, "assistant", "It detects motion.")

    summary = conversations_store.list_summaries()[0]
    assert summary.message_count == 2
    assert summary.title_preview.startswith("What does the motion sensor")
    assert len(summary.title_preview) <= 80


def test_delete_cascades_messages(
    conversations_store: ConversationStore,
    tmp_path: Path,
) -> None:
    cid = conversations_store.create()
    conversations_store.append(cid, "user", "vanish")
    conversations_store.delete(cid)
    assert conversations_store.exists(cid) is False
    assert conversations_store.load(cid) == []
    # second open of the same DB sees zero rows in messages
    fresh = ConversationStore(db_path=tmp_path / "conversations.db")
    assert fresh.list_summaries() == []


def test_truncate_keeps_last_n_user_assistant_pairs() -> None:
    msgs = [
        Message(role="user", content="q1", created_at="t1"),
        Message(role="assistant", content="a1", created_at="t2"),
        Message(role="user", content="q2", created_at="t3"),
        Message(role="assistant", content="a2", created_at="t4"),
        Message(role="user", content="q3", created_at="t5"),
        Message(role="assistant", content="a3", created_at="t6"),
    ]
    kept = truncate_to_last_n_turns(msgs, max_turns=2)
    assert len(kept) == 4
    assert [m.content for m in kept] == ["q2", "a2", "q3", "a3"]


def test_truncate_preserves_system_messages() -> None:
    msgs = [
        Message(role="system", content="sys", created_at="t0"),
        Message(role="user", content="q1", created_at="t1"),
        Message(role="assistant", content="a1", created_at="t2"),
        Message(role="user", content="q2", created_at="t3"),
        Message(role="assistant", content="a2", created_at="t4"),
    ]
    kept = truncate_to_last_n_turns(msgs, max_turns=1)
    assert kept[0].role == "system"
    assert [m.content for m in kept[1:]] == ["q2", "a2"]


def test_truncate_with_empty_history() -> None:
    assert truncate_to_last_n_turns([], max_turns=5) == []
