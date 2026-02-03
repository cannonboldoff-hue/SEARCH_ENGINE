"""Shared utilities."""

from src.constants import EMBEDDING_DIM


def normalize_embedding(vec: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    """Truncate or zero-pad vector to fixed dimension (e.g. for DB storage)."""
    if len(vec) < dim:
        return vec[:dim] + [0.0] * (dim - len(vec))
    return vec[:dim]
