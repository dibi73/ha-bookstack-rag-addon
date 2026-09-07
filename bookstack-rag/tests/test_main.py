"""Tests for the background startup chain in ``app.main`` (issue #50).

Only the ``startup_delay_seconds`` gate is exercised here — everything else
in ``_run_startup`` (real embedder download, real Qdrant server, watcher
threads) is exactly what :mod:`tests.conftest` deliberately bypasses for the
rest of the suite. We monkeypatch the embedder + Qdrant client with fakes so
the chain runs end-to-end fast, and assert on the one thing that changed:
whether/how long we wait before the heavy chain starts.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from app import main as main_module
from app.embedder import FakeEmbedder
from fastapi import FastAPI
from qdrant_client import QdrantClient

if TYPE_CHECKING:
    from app.config import Config


class _FakeEmbedderWithLoad(FakeEmbedder):
    """FakeEmbedder + a no-op ``load()`` — main.py always calls load() once."""

    def load(self) -> None:
        """No-op: the fake never needs a real model load."""


@pytest.fixture
def startup_app(base_config: Config, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """A FastAPI app wired for ``_run_startup``, with heavy deps faked out."""
    monkeypatch.setattr(
        main_module,
        "SentenceTransformerEmbedder",
        lambda model_name: _FakeEmbedderWithLoad(vector_size=8),
    )
    monkeypatch.setattr(
        main_module,
        "QdrantClient",
        lambda url: QdrantClient(":memory:"),
    )
    app = FastAPI()
    app.state.config = base_config
    app.state.startup = main_module.StartupState()
    return app


async def _run_and_cleanup(app: FastAPI) -> None:
    await main_module._run_startup(app)
    watcher = getattr(app.state, "watcher", None)
    if watcher is not None:
        watcher.stop()


async def test_run_startup_waits_when_delay_positive(
    startup_app: FastAPI,
    base_config: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A positive delay sleeps for exactly that long before loading anything."""
    startup_app.state.config = dataclasses.replace(
        base_config,
        startup_delay_seconds=42,
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(main_module.asyncio, "sleep", sleep_mock)

    await _run_and_cleanup(startup_app)

    sleep_mock.assert_awaited_once_with(42)
    assert startup_app.state.startup.phase == "ready"


async def test_run_startup_skips_delay_when_zero(
    startup_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``startup_delay_seconds=0`` (the test default) never calls sleep at all."""
    sleep_mock = AsyncMock()
    monkeypatch.setattr(main_module.asyncio, "sleep", sleep_mock)

    await _run_and_cleanup(startup_app)

    sleep_mock.assert_not_awaited()
    assert startup_app.state.startup.phase == "ready"
