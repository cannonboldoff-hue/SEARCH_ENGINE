"""
Enum strings for Experience Card LLM prompts.

All values are derived from src.domain (single source of truth).
Do not define enums here—only import from domain and format for prompts.
"""

from typing import get_args

from src.domain import (
    Intent,
    ChildIntent,
    ChildRelationType,
    ENTITY_TAXONOMY,
    ALLOWED_CHILD_TYPES,
)

# Comma-separated strings for embedding in prompt templates
INTENT_ENUM = ", ".join(get_args(Intent))
CHILD_INTENT_ENUM = ", ".join(get_args(ChildIntent))
CHILD_RELATION_TYPE_ENUM = ", ".join(get_args(ChildRelationType))
ENTITY_TYPES = ", ".join(ENTITY_TAXONOMY)
ALLOWED_CHILD_TYPES_STR = ", ".join(ALLOWED_CHILD_TYPES)
