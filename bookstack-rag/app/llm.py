"""OpenAI-compatible chat-completions client.

The add-on speaks the ``/v1/chat/completions`` dialect — that is the
de-facto standard implemented by OpenAI, Anthropic (since their 2024
compatibility layer), Google Gemini's OpenAI-compat endpoint, and Ollama.
Any of those, plus self-hosted servers like vLLM or LM Studio, can be
plugged in by setting :class:`~app.config.Config` ``llm_*`` options.

Tests inject a :class:`FakeLLMClient` rather than poking at a real
endpoint — see ``tests/test_llm.py`` for the shape of the mock.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.index import SearchHit

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant for a Home Assistant smart-home setup.\n"
    "Answer questions strictly based on the provided documentation.\n"
    "Answer in the language of the user's question (German or English).\n"
    "If you cannot find an answer in the documentation, say so honestly — "
    "never invent device details.\n"
    "Keep answers clear and accessible for non-technical household members."
)


class LLMNotConfiguredError(RuntimeError):
    """Raised when an LLM call is attempted but the endpoint is not configured."""


def build_messages(
    *,
    system_prompt: str,
    history: list[dict[str, str]],
    hits: list[SearchHit],
    query: str,
) -> list[dict[str, str]]:
    """Assemble the OpenAI-format messages list for one chat completion.

    The retrieval hits are wrapped in ``<doc>`` marker tags so the LLM
    cannot confuse retrieved content with user instructions — that is the
    prompt-injection-defence pattern from the project's security spec
    (Anforderungsdokument §6.1).
    """
    if hits:
        context_blocks = "\n\n".join(
            f'<doc index="{i + 1}" title="{hit.title}">\n{hit.content_preview}\n</doc>'
            for i, hit in enumerate(hits)
        )
        user_with_context = (
            f"Context documents:\n\n{context_blocks}\n\nQuestion: {query}"
        )
    else:
        user_with_context = f"No context documents matched. Question: {query}"

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(
        {"role": turn["role"], "content": turn["content"]} for turn in history
    )
    messages.append({"role": "user", "content": user_with_context})
    return messages


class LLMClient:
    """Async client for an OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Hold the connection settings; HTTP client is created eagerly."""
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    @property
    def is_configured(self) -> bool:
        """True when both base URL and model name are set."""
        return bool(self._base_url and self._model)

    @property
    def model(self) -> str:
        """Configured model name (empty string when unconfigured)."""
        return self._model

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """One-shot non-streaming completion. Returns the assistant content."""
        if not self.is_configured:
            msg = "LLM endpoint is not configured"
            raise LLMNotConfiguredError(msg)
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            json={"model": self._model, "messages": messages, "stream": False},
            headers=self._headers(),
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Streaming completion. Yields content deltas as they arrive."""
        if not self.is_configured:
            msg = "LLM endpoint is not configured"
            raise LLMNotConfiguredError(msg)
        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json={"model": self._model, "messages": messages, "stream": True},
            headers=self._headers(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: ") :]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    yield delta

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()


class FakeLLMClient:
    """Deterministic stub LLM used by the test suite.

    The fake returns a canned reply (or a sequence of deltas) regardless of
    the input messages. That is enough to exercise the wiring without
    needing a real network endpoint.
    """

    def __init__(
        self,
        *,
        canned_response: str = "[fake answer]",
        deltas: list[str] | None = None,
        is_configured: bool = True,
    ) -> None:
        """Configure the stub's reply payload."""
        self._canned_response = canned_response
        self._deltas = deltas if deltas is not None else [canned_response]
        self._configured = is_configured
        self.calls: list[list[dict[str, str]]] = []

    @property
    def is_configured(self) -> bool:
        """Mirrors :attr:`LLMClient.is_configured` for duck-typed swap-in."""
        return self._configured

    @property
    def model(self) -> str:
        """Always reports ``fake-model`` so logs remain interpretable."""
        return "fake-model"

    async def chat(self, messages: list[dict[str, str]]) -> str:
        """Record the call and return the canned response."""
        self.calls.append(messages)
        if not self._configured:
            msg = "LLM endpoint is not configured"
            raise LLMNotConfiguredError(msg)
        return self._canned_response

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Record the call and yield each canned delta."""
        self.calls.append(messages)
        if not self._configured:
            msg = "LLM endpoint is not configured"
            raise LLMNotConfiguredError(msg)
        for delta in self._deltas:
            yield delta

    async def close(self) -> None:
        """No-op — stub holds no resources."""
        return
