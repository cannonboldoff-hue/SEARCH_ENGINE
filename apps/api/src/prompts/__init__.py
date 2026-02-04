"""
LLM prompt templates for experience extraction and Experience Card v1 pipeline.

Pipeline order:
  1. ATOMIZER       — messy user text → list of atoms (atom_id, raw_text_span, suggested_intent, why)
  2. PARENT_EXTRACTOR — one atom → one parent Experience Card v1 (depth=0)
  3. CHILD_GENERATOR  — one parent → 0–10 child Experience Cards (depth=1)
  4. VALIDATOR       — parent + children → corrected final JSON

Placeholders (double-brace, replace before sending to LLM):
  - {{USER_TEXT}}              — raw user message (atomizer)
  - {{ATOM_TEXT}}              — single atom text (parent extractor)
  - {{PERSON_ID}}              — person_id / created_by (parent extractor)
  - {{PARENT_ID}}              — parent card id (child generator)
  - {{PARENT_CARD_JSON}}       — full parent card JSON (child generator)
  - {{PARENT_AND_CHILDREN_JSON}} — parent + children JSON (validator)
"""

from .experience_card_v1 import (
    PROMPT_ATOMIZER,
    PROMPT_PARENT_EXTRACTOR,
    PROMPT_CHILD_GENERATOR,
    PROMPT_VALIDATOR,
    fill_prompt,
)

__all__ = [
    "PROMPT_ATOMIZER",
    "PROMPT_PARENT_EXTRACTOR",
    "PROMPT_CHILD_GENERATOR",
    "PROMPT_VALIDATOR",
    "fill_prompt",
]
