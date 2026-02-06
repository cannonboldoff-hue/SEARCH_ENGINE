"""
LLM prompt templates for experience extraction and Experience Card v1 pipeline.

Converts RAW, unstructured text (informal, noisy, incomplete) into structured
ExperienceCards. Normalizes terms, infers meaning carefully, and preserves
the user's original intent.

Pipeline order:
  1. ATOMIZER            — messy user text → list of atoms
                           (atom_id, raw_text_span, cleaned_text, suggested_intent, why)
  2. PARENT_AND_CHILDREN — one atom → one parent + 0–10 children (full schema)
  3. VALIDATOR           — parent + children → corrected, backend-ready JSON

Placeholders (double-brace, replace before sending to LLM):
  - {{USER_TEXT}}              — raw user message (atomizer)
  - {{ATOM_TEXT}}              — single atom text, preferably cleaned (parent+children)
  - {{PERSON_ID}}              — person_id / created_by
  - {{PARENT_AND_CHILDREN_JSON}} — parent + children JSON (validator)
"""

from .experience_card_v1 import (
    PROMPT_REWRITE,
    PROMPT_ATOMIZER,
    PROMPT_PARENT_AND_CHILDREN,
    PROMPT_VALIDATOR,
    fill_prompt,
)

__all__ = [
    "PROMPT_REWRITE",
    "PROMPT_ATOMIZER",
    "PROMPT_PARENT_AND_CHILDREN",
    "PROMPT_VALIDATOR",
    "fill_prompt",
]
