"""
Enum strings for Experience Card LLM prompts.

All values are derived from src.domain (single source of truth).
Do not define enums here — only import from domain and format for prompts.

Usage:
    from src.prompts.experience_card_enums import INTENT_ENUM, ALLOWED_CHILD_TYPES_STR
    prompt = fill_prompt(PROMPT_EXTRACT, {"INTENT_ENUM": INTENT_ENUM})
"""

from typing import get_args

from src.domain import (
    # Core card enums
    Intent,
    ChildIntent,
    ChildRelationType,
    # Parent card enums
    SeniorityLevel,
    EmploymentType,
    CompanyType,
    # Relation enum
    ExperienceRelationType,
    # Structured field enums
    Confidence,
    Visibility,
    ClaimState,
    EvidenceType,
    ToolType,
    EntityType,
    # Constants
    ALLOWED_CHILD_TYPES,
    ENTITY_TAXONOMY,
)

# -----------------------------------------------------------------------------
# Core card enums
# Used in: extract, detect, clarify prompts
# -----------------------------------------------------------------------------

INTENT_ENUM = ", ".join(get_args(Intent))
CHILD_INTENT_ENUM = ", ".join(get_args(ChildIntent))
CHILD_RELATION_TYPE_ENUM = ", ".join(get_args(ChildRelationType))

# -----------------------------------------------------------------------------
# Parent card enums
# Used in: extract, clarify planner, apply answer prompts
# -----------------------------------------------------------------------------

SENIORITY_LEVEL_ENUM = ", ".join(get_args(SeniorityLevel))
EMPLOYMENT_TYPE_ENUM = ", ".join(get_args(EmploymentType))
COMPANY_TYPE_ENUM = ", ".join(get_args(CompanyType))

# -----------------------------------------------------------------------------
# Experience relation enum
# Used in: clarify planner (relations between parallel cards)
# -----------------------------------------------------------------------------

EXPERIENCE_RELATION_TYPE_ENUM = ", ".join(get_args(ExperienceRelationType))

# -----------------------------------------------------------------------------
# Child dimension types
# Used in: extract, clarify planner, apply answer prompts
# -----------------------------------------------------------------------------

ALLOWED_CHILD_TYPES_STR = ", ".join(ALLOWED_CHILD_TYPES)

# -----------------------------------------------------------------------------
# Entity taxonomy
# Used in: extract prompt (entities[].type)
# -----------------------------------------------------------------------------

ENTITY_TYPES = ", ".join(ENTITY_TAXONOMY)

# -----------------------------------------------------------------------------
# Structured field enums
# Used in: extract prompt (quality, privacy, evidence, tooling fields)
# -----------------------------------------------------------------------------

CONFIDENCE_ENUM = ", ".join(get_args(Confidence))
VISIBILITY_ENUM = ", ".join(get_args(Visibility))
CLAIM_STATE_ENUM = ", ".join(get_args(ClaimState))
EVIDENCE_TYPE_ENUM = ", ".join(get_args(EvidenceType))
TOOL_TYPE_ENUM = ", ".join(get_args(ToolType))