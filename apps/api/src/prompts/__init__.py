"""
LLM prompt templates for experience extraction and Experience Card v1 pipeline.

Converts RAW, unstructured text (informal, noisy, incomplete) into structured
ExperienceCards. Normalizes terms, infers meaning carefully, and preserves
the user's original intent.

Pipeline order:
  1. REWRITE            -- messy user text -> clear + cleaned text
  2. EXTRACT_ALL_CARDS  -- cleaned text -> parents + children (single pass)
  3. VALIDATE_ALL_CARDS -- full set -> corrected, backend-ready JSON

Placeholders (double-brace, replace before sending to LLM):
  - {{USER_TEXT}}                -- raw user message
  - {{PERSON_ID}}                -- person_id / created_by
  - {{PARENT_AND_CHILDREN_JSON}} -- parent + children JSON
"""

from .experience_card import (
    PROMPT_REWRITE,
    PROMPT_EXTRACT_ALL_CARDS,
    PROMPT_VALIDATE_ALL_CARDS,
    fill_prompt,
)

__all__ = [
    "PROMPT_REWRITE",
    "PROMPT_EXTRACT_ALL_CARDS",
    "PROMPT_VALIDATE_ALL_CARDS",
    "fill_prompt",
]
