"""
LLM prompt templates for experience extraction and Experience Card v1 pipeline.

Converts RAW, unstructured text (informal, noisy, incomplete) into structured
ExperienceCards. Normalizes terms, infers meaning carefully, and preserves
the user's original intent.

Pipeline order:
  1. REWRITE            -- messy user text -> clear + cleaned text
  2. DETECT_EXPERIENCES -- cleaned text -> count + labels (user picks one)
  3. EXTRACT_SINGLE     -- one experience by index -> parent + children
  4. VALIDATE / CLARIFY  -- correct and optionally ask for missing fields

Placeholders (double-brace, replace before sending to LLM):
  - {{USER_TEXT}}                -- raw user message
  - {{PERSON_ID}}                -- person_id / created_by
  - {{PARENT_AND_CHILDREN_JSON}} -- parent + children JSON
"""

from .experience_card import (
    PROMPT_REWRITE,
    PROMPT_FILL_MISSING_FIELDS,
    PROMPT_CLARIFY_PLANNER,
    PROMPT_CLARIFY_QUESTION_WRITER,
    PROMPT_CLARIFY_APPLY_ANSWER,
    fill_prompt,
)

__all__ = [
    "PROMPT_REWRITE",
    "PROMPT_FILL_MISSING_FIELDS",
    "PROMPT_CLARIFY_PLANNER",
    "PROMPT_CLARIFY_QUESTION_WRITER",
    "PROMPT_CLARIFY_APPLY_ANSWER",
    "fill_prompt",
]
