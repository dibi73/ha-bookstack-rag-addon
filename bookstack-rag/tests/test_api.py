"""Tests for the REST endpoints exposed by the add-on."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app import __version__
from app.api import router
from app.config import load_config
from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pathlib import Path

    from app.conversations import ConversationStore
    from app.llm import FakeLLMClient
    from app.pipeline import Pipeline


def test_status_with_empty_export_dir(client: TestClient, export_dir: Path) -> None:
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["export_path"] == str(export_dir)
    assert body["markdown_files"] == 0
    assert body["indexed"] == 0
    assert body["llm_configured"] is True


def test_status_counts_markdown_files_recursively(
    client: TestClient,
    write_markdown,
) -> None:
    write_markdown("a.md", "# A")
    write_markdown("b.md", "# B")
    write_markdown("devices/c.md", "# C")
    write_markdown("ignore.txt", "not markdown")  # rglob *.md ignores this

    response = client.get("/api/status")
    body = response.json()
    assert body["status"] == "ok"
    assert body["markdown_files"] == 3


def test_status_when_export_dir_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    options_file = tmp_path / "options.json"
    options_file.write_text(
        json.dumps({"bookstack_export_path": str(tmp_path / "does_not_exist")}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ADDON_OPTIONS", str(options_file))

    config = load_config()
    app = FastAPI(title="t", version=__version__)
    app.state.config = config
    app.include_router(router, prefix="/api")
    with TestClient(app) as missing_client:
        response = missing_client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_export_dir"
    assert body["markdown_files"] == 0
    assert body["llm_configured"] is False


def test_status_reports_llm_configured_false_when_no_llm(
    client_no_llm: TestClient,
) -> None:
    response = client_no_llm.get("/api/status")
    assert response.json()["llm_configured"] is False


def test_query_oneshot_returns_answer_and_creates_conversation(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
    fake_llm: FakeLLMClient,
) -> None:
    write_markdown(
        "lr.md",
        "Living room ceiling lamp with motion-sensor automation.",
        metadata={"title": "Living Room Light", "bookstack_page_id": 1},
    )
    pipeline.reconcile_all()

    response = client.post(
        "/api/query",
        json={"text": "Living room ceiling lamp with motion-sensor automation."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "[fake answer]"
    assert body["conversation_id"]
    assert body["hits"][0]["title"] == "Living Room Light"
    # the LLM was called exactly once
    assert len(fake_llm.calls) == 1


def test_query_multi_turn_loads_history_into_prompt(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
    fake_llm: FakeLLMClient,
    conversations_store: ConversationStore,
) -> None:
    write_markdown("a.md", "doc body")
    pipeline.reconcile_all()

    first = client.post("/api/query", json={"text": "first question"})
    conv_id = first.json()["conversation_id"]
    fake_llm.calls.clear()

    second = client.post(
        "/api/query",
        json={"text": "follow-up", "conversation_id": conv_id},
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == conv_id

    # The fake LLM saw the prior turn in its messages list.
    sent = fake_llm.calls[0]
    contents = [m["content"] for m in sent]
    assert any("first question" in c for c in contents)
    assert any("follow-up" in c for c in contents)

    # Both turns are persisted as user+assistant pairs (4 messages total).
    stored = conversations_store.load(conv_id)
    assert [m.role for m in stored] == ["user", "assistant", "user", "assistant"]


def test_query_unknown_conversation_id_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/query",
        json={"text": "hello", "conversation_id": "does-not-exist"},
    )
    assert response.status_code == 404


def test_query_streaming_emits_hit_delta_done_events(
    client_streaming_llm: TestClient,
    pipeline: Pipeline,
    write_markdown,
    conversations_store: ConversationStore,
) -> None:
    write_markdown(
        "lr.md",
        "Living room lamp",
        metadata={"title": "Living Room Light", "bookstack_page_id": 1},
    )
    pipeline.reconcile_all()

    with client_streaming_llm.stream(
        "POST",
        "/api/query",
        json={"text": "what about the lamp?", "stream": True},
    ) as response:
        assert response.status_code == 200
        body_text = "".join(chunk for chunk in response.iter_text())

    assert "event: hit" in body_text
    assert "event: delta" in body_text
    assert "event: done" in body_text
    # the streaming fake yields three deltas — Hello, space, world
    assert body_text.count("event: delta") == 3

    # The streamed answer was persisted in the auto-created conversation.
    summaries = conversations_store.list_summaries()
    assert len(summaries) == 1
    full_history = conversations_store.load(summaries[0].id)
    assert full_history[0].role == "user"
    assert full_history[1].role == "assistant"
    assert full_history[1].content == "Hello world"


def test_query_stage1_mode_when_no_llm(
    client_no_llm: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    write_markdown(
        "lr.md",
        "Living room",
        metadata={"title": "Living Room Light", "bookstack_page_id": 1},
    )
    pipeline.reconcile_all()
    response = client_no_llm.post("/api/query", json={"text": "Living room"})
    assert response.status_code == 200
    body = response.json()
    assert body.get("answer") is None
    assert body.get("conversation_id") is None
    assert body["hits"][0]["title"] == "Living Room Light"


def test_query_stream_without_llm_returns_503(client_no_llm: TestClient) -> None:
    response = client_no_llm.post(
        "/api/query",
        json={"text": "anything", "stream": True},
    )
    assert response.status_code == 503


def test_query_conversation_id_without_llm_returns_503(
    client_no_llm: TestClient,
) -> None:
    response = client_no_llm.post(
        "/api/query",
        json={"text": "anything", "conversation_id": "made-up"},
    )
    assert response.status_code == 503


def test_query_validates_empty_text(client: TestClient) -> None:
    response = client.post("/api/query", json={"text": ""})
    assert response.status_code == 422


def test_query_503_when_index_not_ready(client_no_index: TestClient) -> None:
    response = client_no_index.post("/api/query", json={"text": "anything"})
    assert response.status_code == 503


def test_list_conversations_returns_recent_first(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    write_markdown("a.md", "doc")
    pipeline.reconcile_all()
    client.post("/api/query", json={"text": "earlier"})
    client.post("/api/query", json={"text": "later"})

    response = client.get("/api/conversations")
    assert response.status_code == 200
    summaries = response.json()
    assert summaries[0]["title_preview"].startswith("later")
    assert summaries[1]["title_preview"].startswith("earlier")


def test_get_conversation_returns_full_history(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    write_markdown("a.md", "doc")
    pipeline.reconcile_all()
    created = client.post("/api/query", json={"text": "hello"}).json()
    conv_id = created["conversation_id"]

    response = client.get(f"/api/conversations/{conv_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == conv_id
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][0]["content"] == "hello"
    assert detail["messages"][1]["content"] == "[fake answer]"


def test_get_conversation_404_for_unknown(client: TestClient) -> None:
    response = client.get("/api/conversations/missing")
    assert response.status_code == 404


def test_delete_conversation_removes_it(
    client: TestClient,
    pipeline: Pipeline,
    write_markdown,
) -> None:
    write_markdown("a.md", "doc")
    pipeline.reconcile_all()
    created = client.post("/api/query", json={"text": "hello"}).json()
    conv_id = created["conversation_id"]

    delete_resp = client.delete(f"/api/conversations/{conv_id}")
    assert delete_resp.status_code == 204

    follow_up = client.get(f"/api/conversations/{conv_id}")
    assert follow_up.status_code == 404


def test_delete_conversation_404_for_unknown(client: TestClient) -> None:
    response = client.delete("/api/conversations/missing")
    assert response.status_code == 404


def test_reindex_runs_reconcile_sweep(
    client: TestClient,
    write_markdown,
) -> None:
    write_markdown("a.md", "first")
    write_markdown("b.md", "second")
    response = client.post("/api/reindex")
    assert response.status_code == 200
    body = response.json()
    assert body["indexed"] == 2
    assert body["total"] == 2


def test_reindex_503_when_pipeline_not_ready(client_no_index: TestClient) -> None:
    response = client_no_index.post("/api/reindex")
    assert response.status_code == 503
