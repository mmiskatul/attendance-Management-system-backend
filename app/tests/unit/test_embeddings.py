"""Tests for embedding serialization helpers."""

import numpy as np

from app.utils.embeddings import binary_to_embedding, embedding_to_binary, normalize_embedding


def test_embedding_binary_round_trip() -> None:
    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    binary = embedding_to_binary(vector)
    restored = binary_to_embedding(binary, embedding_dim=3)
    np.testing.assert_allclose(restored, normalize_embedding(vector), rtol=1e-6, atol=1e-6)
