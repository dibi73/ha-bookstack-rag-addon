"""Tests for the FakeEmbedder used by the rest of the suite.

Real SentenceTransformerEmbedder needs network + ~500 MB model download, so
it has its own opt-in integration test (skipped by default).
"""

from __future__ import annotations

import math

import pytest
from app.embedder import FakeEmbedder, SentenceTransformerEmbedder


def test_fake_embedder_is_deterministic() -> None:
    e = FakeEmbedder(vector_size=8)
    v1 = e.embed("hello world")
    v2 = e.embed("hello world")
    assert v1 == v2


def test_fake_embedder_different_text_different_vector() -> None:
    e = FakeEmbedder(vector_size=8)
    assert e.embed("foo") != e.embed("bar")


def test_fake_embedder_returns_unit_vector() -> None:
    e = FakeEmbedder(vector_size=16)
    vec = e.embed("anything")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-6
    assert len(vec) == 16


def test_fake_embedder_batch_matches_singles() -> None:
    e = FakeEmbedder(vector_size=8)
    batch = e.embed_batch(["a", "b", "c"])
    assert batch == [e.embed("a"), e.embed("b"), e.embed("c")]


def test_sentence_transformer_embedder_unloaded_raises() -> None:
    e = SentenceTransformerEmbedder(model_name="dummy")
    with pytest.raises(RuntimeError, match="not loaded"):
        _ = e.vector_size
