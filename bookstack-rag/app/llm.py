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
from typing import TYPE_CHECKING, Any

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
    "Keep answers clear and accessible for non-technical household members.\n"
    "When a context document carries a 'Sources: ...' line, you may cite "
    "those Markdown links in your answer so the user can jump to the "
    "BookStack page (for context / notes) or the Home Assistant UI (to "
    "edit the actual device, automation, or area). Use them sparingly — "
    "one or two source links per answer is usually enough."
)


# Map ha_object_kind (from the sister-integration's frontmatter) to the
# Home Assistant frontend deep-link path. Mirrors the table in the
# Architektur doc §3 (HA-Frontend-Deep-Links, ab v0.14.5 of ha-bookstack-sync).
HA_DEEP_LINK_PATTERNS: dict[str, str] = {
    "device": "/config/devices/device/{id}",
    "area": "/config/areas/area/{id}",
    "automation": "/config/automation/edit/{id}",
    "script": "/config/script/edit/{id}",
    "scene": "/config/scene/edit/{id}",
    "integration": "/config/integrations/integration/{id}",
    "entity": "/developer-tools/state?entity_id={id}",
    "helper": "/config/helpers",
}

# Friendly labels for the source-link footer. "helper" stays generic
# because Home Assistant's helper page is a collection, not per-id.
HA_DEEP_LINK_LABELS: dict[str, str] = {
    "device": "HA Gerät",
    "area": "HA Bereich",
    "automation": "HA Automation",
    "script": "HA Skript",
    "scene": "HA Szene",
    "integration": "HA Integration",
    "entity": "HA Entity",
    "helper": "HA Helfer",
}


def build_source_links(
    payload: dict[str, Any],
    *,
    bookstack_base_url: str,
    homeassistant_base_url: str,
) -> str | None:
    """Return a 'Sources: [BookStack](...) · [HA Device](...)' Markdown line.

    Either link is omitted when its base URL is not configured or when the
    matching frontmatter field is missing. Returns ``None`` when neither
    link can be built.
    """
    parts: list[str] = []

    bookstack_page_id = payload.get("bookstack_page_id")
    if bookstack_base_url and bookstack_page_id is not None:
        bs_url = f"{bookstack_base_url.rstrip('/')}/link/{bookstack_page_id}"
        parts.append(f"[BookStack]({bs_url})")

    ha_object_kind = payload.get("ha_object_kind")
    ha_object_id = payload.get("ha_object_id")
    if (
        homeassistant_base_url
        and isinstance(ha_object_kind, str)
        and ha_object_kind in HA_DEEP_LINK_PATTERNS
    ):
        pattern = HA_DEEP_LINK_PATTERNS[ha_object_kind]
        ha_url: str | None = None
        if "{id}" not in pattern:
            ha_url = f"{homeassistant_base_url.rstrip('/')}{pattern}"
        elif ha_object_id:
            ha_url = (
                f"{homeassistant_base_url.rstrip('/')}{pattern.format(id=ha_object_id)}"
            )
        if ha_url is not None:
            label = HA_DEEP_LINK_LABELS.get(ha_object_kind, ha_object_kind)
            parts.append(f"[{label}]({ha_url})")

    if not parts:
        return None
    return " · ".join(parts)


class LLMNotConfiguredError(RuntimeError):
    """Raised when an LLM call is attempted but the endpoint is not configured."""


def build_messages(  # noqa: PLR0913
    *,
    system_prompt: str,
    history: list[dict[str, str]],
    hits: list[SearchHit],
    query: str,
    bookstack_base_url: str = "",
    homeassistant_base_url: str = "",
) -> list[dict[str, str]]:
    """Assemble the OpenAI-format messages list for one chat completion.

    The retrieval hits are wrapped in ``<doc>`` marker tags so the LLM
    cannot confuse retrieved content with user instructions — that is the
    prompt-injection-defence pattern from the project's security spec
    (Anforderungsdokument §6.1).

    When ``bookstack_base_url`` / ``homeassistant_base_url`` are configured
    and the hit's frontmatter carries the matching id fields, each
    ``<doc>`` block gets a trailing ``Sources: ...`` line with Markdown
    links the LLM can cite verbatim.
    """
    if hits:
        blocks: list[str] = []
        for i, hit in enumerate(hits):
            block = (
                f'<doc index="{i + 1}" title="{hit.title}">\n{hit.content_preview}\n'
            )
            sources = build_source_links(
                hit.payload,
                bookstack_base_url=bookstack_base_url,
                homeassistant_base_url=homeassistant_base_url,
            )
            if sources:
                block += f"Sources: {sources}\n"
            block += "</doc>"
            blocks.append(block)
        context_blocks = "\n\n".join(blocks)
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
