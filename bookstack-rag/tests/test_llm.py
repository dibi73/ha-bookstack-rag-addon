"""Tests for the LLM client and prompt builder.

Real-network calls are out of scope for the test suite. The prompt-builder
tests are pure-Python; the streaming/non-streaming HTTP paths are exercised
via :class:`httpx.MockTransport` so we never actually open a socket.
"""

from __future__ import annotations

import json

import httpx
import pytest
from app.embedder import FakeEmbedder
from app.index import SearchHit
from app.llm import (
    DEFAULT_SYSTEM_PROMPT,
    FakeLLMClient,
    LLMClient,
    LLMNotConfiguredError,
    build_messages,
)


def _hit(title: str, preview: str) -> SearchHit:
    return SearchHit(
        doc_id="1",
        score=0.9,
        title=title,
        content_preview=preview,
        bookstack_page_id=10,
    )


def test_build_messages_wraps_hits_in_doc_tags() -> None:
    msgs = build_messages(
        system_prompt="SYS",
        history=[],
        hits=[
            _hit("Living Room Light", "ceiling lamp on motion sensor"),
            _hit("Kitchen Light", "smart plug pendant"),
        ],
        query="What does the living-room light do?",
    )
    assert msgs[0] == {"role": "system", "content": "SYS"}
    user = msgs[-1]
    assert user["role"] == "user"
    assert '<doc index="1" title="Living Room Light">' in user["content"]
    assert '<doc index="2" title="Kitchen Light">' in user["content"]
    assert "Question: What does the living-room light do?" in user["content"]


def test_build_messages_handles_no_hits() -> None:
    msgs = build_messages(
        system_prompt="SYS",
        history=[],
        hits=[],
        query="anything",
    )
    assert "No context documents matched" in msgs[-1]["content"]


def test_build_messages_includes_history_in_order() -> None:
    history = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    msgs = build_messages(
        system_prompt="SYS",
        history=history,
        hits=[_hit("doc", "body")],
        query="follow-up",
    )
    assert [m["role"] for m in msgs] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert msgs[1]["content"] == "earlier question"
    assert msgs[2]["content"] == "earlier answer"


def test_default_system_prompt_is_bilingual() -> None:
    assert "German" in DEFAULT_SYSTEM_PROMPT or "language" in DEFAULT_SYSTEM_PROMPT


# --- FakeLLMClient ----------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_chat_returns_canned_response() -> None:
    fake = FakeLLMClient(canned_response="hello")
    answer = await fake.chat([{"role": "user", "content": "ping"}])
    assert answer == "hello"
    assert fake.calls == [[{"role": "user", "content": "ping"}]]


@pytest.mark.asyncio
async def test_fake_chat_stream_yields_each_delta() -> None:
    fake = FakeLLMClient(deltas=["a", "b", "c"])
    deltas = [
        delta
        async for delta in fake.chat_stream(
            [{"role": "user", "content": "ping"}],
        )
    ]
    assert deltas == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_fake_unconfigured_raises() -> None:
    fake = FakeLLMClient(is_configured=False)
    with pytest.raises(LLMNotConfiguredError):
        await fake.chat([])


# --- Real LLMClient via MockTransport --------------------------------------


def _openai_completion(content: str) -> dict:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "model": "fake-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            },
        ],
    }


def _make_client(handler: httpx.MockTransport) -> LLMClient:
    return LLMClient(
        base_url="http://test/v1",
        api_key="sk-test",
        model="fake-model",
        transport=handler,
    )


@pytest.mark.asyncio
async def test_chat_posts_correct_body_and_returns_content() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body)
        assert request.headers["Authorization"] == "Bearer sk-test"
        return httpx.Response(200, json=_openai_completion("the answer"))

    client = _make_client(httpx.MockTransport(handler))
    answer = await client.chat([{"role": "user", "content": "hi"}])
    assert answer == "the answer"
    assert captured[0]["model"] == "fake-model"
    assert captured[0]["stream"] is False
    assert captured[0]["messages"] == [{"role": "user", "content": "hi"}]
    await client.close()


@pytest.mark.asyncio
async def test_chat_propagates_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    client = _make_client(httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await client.chat([{"role": "user", "content": "hi"}])
    await client.close()


@pytest.mark.asyncio
async def test_chat_unconfigured_raises() -> None:
    client = LLMClient(base_url="", api_key="", model="")
    assert client.is_configured is False
    with pytest.raises(LLMNotConfiguredError):
        await client.chat([])
    await client.close()


@pytest.mark.asyncio
async def test_chat_stream_parses_sse_deltas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sse = (
            "data: " + json.dumps(_sse_delta("Hello")) + "\n\n"
            "data: " + json.dumps(_sse_delta(", ")) + "\n\n"
            "data: " + json.dumps(_sse_delta("world!")) + "\n\n"
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            content=sse.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    client = _make_client(httpx.MockTransport(handler))
    deltas = [
        chunk
        async for chunk in client.chat_stream(
            [{"role": "user", "content": "hi"}],
        )
    ]
    assert "".join(deltas) == "Hello, world!"
    await client.close()


@pytest.mark.asyncio
async def test_chat_stream_skips_non_data_lines_and_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        sse = (
            ": comment line\n\n"
            "data: not json\n\n"
            "data: " + json.dumps(_sse_delta("real")) + "\n\n"
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            content=sse.encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    client = _make_client(httpx.MockTransport(handler))
    deltas = [
        chunk
        async for chunk in client.chat_stream(
            [{"role": "user", "content": "hi"}],
        )
    ]
    assert deltas == ["real"]
    await client.close()


def _sse_delta(content: str) -> dict:
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion.chunk",
        "model": "fake-model",
        "choices": [
            {
                "index": 0,
                "delta": {"content": content},
                "finish_reason": None,
            },
        ],
    }


# Quick sanity: build_messages + FakeEmbedder play together --------------


def test_build_messages_works_with_fake_embedder_hit_payload() -> None:
    fe = FakeEmbedder(vector_size=8)
    vec = fe.embed("anything")
    assert len(vec) == 8
    msgs = build_messages(
        system_prompt="x",
        history=[],
        hits=[_hit("a", "b")],
        query="q",
    )
    assert isinstance(msgs, list)
