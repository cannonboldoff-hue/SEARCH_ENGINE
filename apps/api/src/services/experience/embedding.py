"""
Experience card embedding: build embed texts, call provider, persist vectors.

Flow:
  1. build_embedding_inputs(parents, children) -> texts and targets (order-preserving)
  2. fetch_embedding_vectors(texts) -> normalized vectors (via provider)
  3. embed_experience_cards(db, parents, children) runs 1+2, assigns vectors, flushes DB

Used by:
  - run_draft_single (after persist_families)
  - PATCH experience card / child (after apply_card_patch / apply_child_patch)
  - clarify-experience and fill-missing-from-text (after persisting filled data)
"""

import logging
from dataclasses import dataclass
from typing import Union

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ExperienceCard, ExperienceCardChild
from src.providers import get_embedding_provider, EmbeddingServiceError
from src.utils import normalize_embedding

from .errors import PipelineError, PipelineStage
from .search_document import build_parent_search_document, get_child_search_document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ExperienceCardOrChild = Union[ExperienceCard, ExperienceCardChild]


@dataclass(frozen=True)
class EmbeddingInput:
    """One text-to-embed with its target card or child (for assigning the vector later)."""
    text: str
    target: ExperienceCardOrChild


# ---------------------------------------------------------------------------
# Step 1: Build inputs (texts + targets)
# ---------------------------------------------------------------------------

def build_embedding_inputs(
    parents: list[ExperienceCard],
    children: list[ExperienceCardChild],
) -> list[EmbeddingInput]:
    """
    Build the ordered list of (text, target) for embedding.

    Parent: uses build_parent_search_document(parent) (derived from card fields).
    Child: uses search_document (trimmed); skipped if empty.

    Order: all parents first, then all children. Used to assign vectors back in the same order.
    """
    inputs: list[EmbeddingInput] = []

    for parent in parents:
        text = build_parent_search_document(parent).strip()
        if text:
            inputs.append(EmbeddingInput(text=text, target=parent))

    for child in children:
        text = get_child_search_document(child)
        if text:
            inputs.append(EmbeddingInput(text=text, target=child))

    return inputs


# ---------------------------------------------------------------------------
# Step 2: Fetch vectors from provider
# ---------------------------------------------------------------------------

async def fetch_embedding_vectors(texts: list[str]) -> list[list[float]]:
    """
    Call the embedding provider and return normalized vectors in the same order as texts.

    Raises:
        EmbeddingServiceError: If the provider fails.
    """
    if not texts:
        return []
    provider = get_embedding_provider()
    vectors = await provider.embed(texts)
    return [normalize_embedding(v, dim=provider.dimension) for v in vectors]


# ---------------------------------------------------------------------------
# Step 3: Main API – embed and persist
# ---------------------------------------------------------------------------

async def embed_experience_cards(
    db: AsyncSession,
    parents: list[ExperienceCard],
    children: list[ExperienceCardChild],
) -> None:
    """
    Generate embeddings for the given cards and persist them.

    - Builds embedding inputs (search_document or derived).
    - Fetches vectors from the embedding provider and normalizes them.
    - Assigns vectors to parent/child .embedding and flushes the session.

    Raises:
        PipelineError: If embedding fails or vector count mismatches.
    """
    inputs = build_embedding_inputs(parents, children)
    if not inputs:
        logger.warning("No documents to embed")
        return

    texts = [inp.text for inp in inputs]

    try:
        vectors = await fetch_embedding_vectors(texts)
    except EmbeddingServiceError as e:
        raise PipelineError(
            PipelineStage.EMBED,
            f"Embedding service failed: {str(e)}",
            cause=e,
        ) from e
    except Exception as e:
        raise PipelineError(
            PipelineStage.EMBED,
            f"Embedding failed: {str(e)}",
            cause=e,
        ) from e

    if len(vectors) != len(inputs):
        raise PipelineError(
            PipelineStage.EMBED,
            f"Embedding API returned {len(vectors)} vectors but expected {len(inputs)}",
        )

    for inp, vec in zip(inputs, vectors):
        inp.target.embedding = vec

    await db.flush()
    logger.info("Successfully embedded %d documents", len(texts))


# Backward-compatible alias
embed_cards = embed_experience_cards
