"""Shared utilities."""

from src.core import EMBEDDING_DIM


def strip_json_from_response(raw: str) -> str:
    """Strip markdown/code fences from an LLM response and return JSON text."""
    s = (raw or "").strip()
    if "```" not in s:
        return s
    for part in s.split("```"):
        p = part.strip()
        if p.lower().startswith("json"):
            p = p[4:].strip()
        if p.startswith("{"):
            return p
    return s


def normalize_embedding(vec: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    """Truncate or zero-pad vector to fixed dimension (e.g. for DB storage)."""
    if len(vec) < dim:
        return vec[:dim] + [0.0] * (dim - len(vec))
    return vec[:dim]
