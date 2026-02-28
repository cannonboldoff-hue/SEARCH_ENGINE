"""
Vapi AI integration.

Bridges the clarify flow to OpenAI-compatible chat format for Vapi custom LLM.
"""

from .adapter import convai_chat_turn
from .session import (
    ConvaiSessionState,
    create_session,
    get_session,
    delete_session,
)

__all__ = [
    "convai_chat_turn",
    "ConvaiSessionState",
    "create_session",
    "get_session",
    "delete_session",
]
