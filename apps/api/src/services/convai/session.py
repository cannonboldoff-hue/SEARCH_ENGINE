"""
In-memory session store for ElevenLabs ConvAI conversations.

Maps conversation_id -> (user_id, ConvaiSessionState).
For production with multiple instances, use Redis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# conversation_id -> (user_id: str, state: ConvaiSessionState)
_sessions: dict[str, tuple[str, "ConvaiSessionState"]] = {}


@dataclass
class ConvaiSessionState:
    """State for one voice conversation (clarify flow)."""

    # Accumulated raw experience text (user's initial + follow-ups)
    raw_experience_text: str = ""

    # Clarify flow stage
    stage: str = "awaiting_experience"  # awaiting_experience | awaiting_choice | clarifying | card_ready

    # Detected experiences (from detect_experiences)
    detected_experiences: list[dict] = field(default_factory=list)

    # User's chosen focus (experience index as string, e.g. "1")
    focus_parent_id: str | None = None

    # Current card family (parent + children) for clarify
    card_family: dict = field(default_factory=dict)

    # Structured clarify history (role, kind, target_type, target_field, text, etc.)
    asked_history: list[dict] = field(default_factory=list)

    # Draft set / raw experience IDs (for run_draft_single)
    draft_set_id: str | None = None
    raw_experience_id: str | None = None


def create_session(conversation_id: str, user_id: str) -> ConvaiSessionState:
    """Create a new session for this conversation."""
    state = ConvaiSessionState()
    _sessions[conversation_id] = (user_id, state)
    logger.info("ConvAI session created: conversation_id=%s user_id=%s", conversation_id, user_id)
    return state


def get_session(conversation_id: str) -> tuple[str, ConvaiSessionState] | None:
    """Get (user_id, state) for a conversation, or None."""
    return _sessions.get(conversation_id)


def delete_session(conversation_id: str) -> None:
    """Remove a session."""
    if conversation_id in _sessions:
        del _sessions[conversation_id]
        logger.info("ConvAI session deleted: conversation_id=%s", conversation_id)
