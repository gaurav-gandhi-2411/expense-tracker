from __future__ import annotations

import functools

import numpy as np

from app.config import get_settings


@functools.lru_cache(maxsize=1)
def get_embedding_model():  # type: ignore[return]
    """Load and cache the SentenceTransformer model on first call.

    Import is deferred inside the function so the heavy sentence-transformers
    module does not load at app import time, keeping FastAPI startup fast.
    """
    from sentence_transformers import (  # type: ignore[import-untyped]  # noqa: PLC0415
        SentenceTransformer,
    )

    model_name = get_settings().embedding_model
    return SentenceTransformer(model_name)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Return L2-normalised embeddings for *texts* as a float32 numpy array.

    Args:
        texts: Strings to embed.  May be empty.

    Returns:
        Array of shape ``(len(texts), dim)`` with unit-norm rows, or
        ``np.empty((0, 0), dtype=np.float32)`` when *texts* is empty.
    """
    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    return get_embedding_model().encode(
        texts,
        convert_to_numpy=True,
        # Unit-norm rows make cosine similarity equivalent to a dot product,
        # avoiding an extra division at query time.
        normalize_embeddings=True,
    )
