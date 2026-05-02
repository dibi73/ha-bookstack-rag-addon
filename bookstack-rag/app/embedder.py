"""Embedding-model wrapper.

Production code uses :class:`SentenceTransformerEmbedder`; tests pass a
:class:`FakeEmbedder` (deterministic dummy vectors derived from text hash) so
the suite stays fast and offline. Both expose ``embed`` / ``embed_batch`` /
``vector_size`` via duck typing — there is no formal Protocol because we keep
the surface small enough that adding one would be more noise than insight.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedder:
    """Lazy-loaded sentence-transformers embedder.

    The model is heavy (~500 MB on disk for nomic-embed-text-v1.5 plus loaded
    tensors). We construct the wrapper at import time but defer the actual
    model load to :meth:`load` so tests, lint and config-only code paths do
    not pay that cost.
    """

    def __init__(self, model_name: str) -> None:
        """Hold the model name; defer the heavy model load to :meth:`load`."""
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    def load(self) -> None:
        """Import sentence-transformers and instantiate the model."""
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        logger.info("Loading embedding model %s", self.model_name)
        self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        logger.info(
            "Embedding model loaded — vector size %d",
            self._model.get_sentence_embedding_dimension(),
        )

    @property
    def vector_size(self) -> int:
        """Return the model's output dimension; requires :meth:`load` to have run."""
        if self._model is None:
            msg = "Embedder not loaded yet — call load() first"
            raise RuntimeError(msg)
        return self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        """Embed a single text into one vector."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors via one ``model.encode`` call."""
        if self._model is None:
            self.load()
        assert self._model is not None  # for type checker  # noqa: S101
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]


class FakeEmbedder:
    """Deterministic dummy embedder for tests.

    Produces a fixed-size vector derived from the SHA-256 of the input. Same
    text always returns the same vector; different texts return different
    vectors. The vector is L2-normalised so cosine-distance maths in Qdrant
    behaves like real embeddings.
    """

    def __init__(self, vector_size: int = 8) -> None:
        """Configure the deterministic stub vector size."""
        self._vector_size = vector_size

    @property
    def vector_size(self) -> int:
        """Return the configured stub dimension."""
        return self._vector_size

    def embed(self, text: str) -> list[float]:
        """Return the deterministic stub vector for ``text``."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts; identical to repeated :meth:`embed` calls."""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        # SHA-256 gives 32 bytes; we slice to 4-byte chunks and read as floats
        # until we have vector_size components, then L2-normalise.
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        floats: list[float] = []
        offset = 0
        while len(floats) < self._vector_size:
            if offset + 4 > len(seed):
                seed = hashlib.sha256(seed).digest()
                offset = 0
            (raw,) = struct.unpack(">i", seed[offset : offset + 4])
            floats.append(raw / 2**31)
            offset += 4
        norm = sum(f * f for f in floats) ** 0.5
        if norm == 0.0:
            return floats
        return [f / norm for f in floats]
