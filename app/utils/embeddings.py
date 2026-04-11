"""Embedding serialization helpers."""

from __future__ import annotations

import numpy as np
from bson.binary import Binary


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """L2-normalize an embedding vector."""

    vector = np.asarray(embedding, dtype=np.float32)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Embedding norm cannot be zero.")
    return vector / norm


def embedding_to_binary(embedding: np.ndarray) -> Binary:
    """Convert a float32 vector into BSON binary form."""

    normalized = normalize_embedding(np.asarray(embedding, dtype=np.float32))
    return Binary(normalized.astype(np.float32).tobytes())


def binary_to_embedding(binary_value: bytes | Binary, embedding_dim: int) -> np.ndarray:
    """Convert BSON binary data back into a float32 vector."""

    vector = np.frombuffer(bytes(binary_value), dtype=np.float32)
    if vector.size != embedding_dim:
        raise ValueError(f"Expected embedding_dim={embedding_dim}, got {vector.size}")
    return vector.copy()
