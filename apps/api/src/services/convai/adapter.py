"""
Adapter: bridge Vapi chat messages to our clarify pipeline.

Receives OpenAI-format messages, maintains session state, runs detect/clarify/draft,
returns the assistant reply text for TTS.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.experience import (
    detect_experiences,
    run_draft_single,
    clarify_experience_interactive,
    DEFAULT_MAX_PARENT_CLARIFY,
    DEFAULT_MAX_CHILD_CLARIFY,
)
from src.services.experience import experience_card_service, apply_card_patch, embed_experience_cards
from src.schemas import ExperienceCardPatch, ExperienceCardChildPatch
from .session import ConvaiSessionState, get_session

logger = logging.getLogger(__name__)


async def _translate_to_english_async(text: str) -> str:
    """Pass-through (no translation)."""
    return text


def _parse_choice_input(text: str, options: list[dict]) -> str | None:
    """
    Parse user's voice response to choose_focus (e.g. "1", "first", "the Google one").
    Returns parent_id (str) or None if unparseable.
    """
    if not text or not options:
        return None
    t = text.strip().lower()
    # Direct index: "1", "2", "one", "two", "first", "second"
    ordinals = {"first": 1, "second": 2, "third": 3, "1st": 1, "2nd": 2, "3rd": 3}
    for i, opt in enumerate(options):
        idx = i + 1
        pid = opt.get("parent_id")
        label = (opt.get("label") or "").lower()
        if str(idx) == t or str(pid) == t:
            return str(pid)
        if ordinals.get(t) == idx:
            return str(pid)
        if t == "one" and idx == 1:
            return str(pid)
        if t == "two" and idx == 2:
            return str(pid)
        if label and label in t:
            return str(pid)
    # Try to extract a number
    match = re.search(r"\b([12])\b", t)
    if match:
        n = int(match.group(1))
        if 1 <= n <= len(options):
            return str(options[n - 1].get("parent_id"))
    return None


def _parent_merged_to_patch(merged: dict) -> ExperienceCardPatch:
    """Build patch from merged form (from builder router logic)."""
    from datetime import date

    intent_secondary = None
    if merged.get("intent_secondary_str") is not None:
        s = merged["intent_secondary_str"]
        if isinstance(s, str):
            intent_secondary = [x.strip() for x in s.split(",") if x.strip()]
        elif isinstance(s, list):
            intent_secondary = [str(x).strip() for x in s if str(x).strip()]

    def parse_date(v):
        if v is None:
            return None
        s = str(v).strip()[:10]
        if len(s) == 7 and s[4] == "-":
            s = f"{s}-01"
        try:
            return date.fromisoformat(s)
        except (ValueError, TypeError):
            return None

    return ExperienceCardPatch(
        title=merged.get("title") or None,
        summary=merged.get("summary") or None,
        normalized_role=merged.get("normalized_role") or None,
        domain=merged.get("domain") or None,
        sub_domain=merged.get("sub_domain") or None,
        company_name=merged.get("company_name") or None,
        company_type=merged.get("company_type") or None,
        location=merged.get("location") if isinstance(merged.get("location"), str) else None,
        employment_type=merged.get("employment_type") or None,
        start_date=parse_date(merged.get("start_date")),
        end_date=parse_date(merged.get("end_date")),
        is_current=merged.get("is_current") if isinstance(merged.get("is_current"), bool) else None,
        intent_primary=merged.get("intent_primary") or None,
        intent_secondary=intent_secondary,
        seniority_level=merged.get("seniority_level") or None,
    )


async def convai_chat_turn(
    conversation_id: str,
    user_id: str,
    messages: list[dict],
    db: AsyncSession,
    state: ConvaiSessionState,
) -> str:
    """
    Process one turn: extract latest user message, run pipeline, return assistant reply.
    """
    # Get latest user message
    user_content = ""
    for m in reversed(messages):
        role = (m.get("role") or "").strip().lower()
        content = (m.get("content") or "").strip()
        if role == "user" and content:
            user_content = content
            break

    # Build conversation_history from messages (for clarify)
    conv_history: list[dict] = []
    for m in messages:
        role = (m.get("role") or "").strip().lower()
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            conv_history.append({"role": role, "content": content})

    # Empty input: opening question
    if not user_content:
        return (
            "What's one experience you'd like to add? Tell me in your own words."
        )

    # Translate if needed
    english = await _translate_to_english_async(user_content)
    state.raw_experience_text = english or user_content

    if state.stage == "awaiting_experience":
        # Detect experiences
        try:
            detect = await detect_experiences(english or user_content)
        except Exception as e:
            logger.exception("detect_experiences failed: %s", e)
            return "I'm sorry, I couldn't process that. Could you tell me about one experience you'd like to add?"
        count = detect.get("count", 0) or 0
        experiences = detect.get("experiences") or []

        if count == 0 or not experiences:
            return (
                "I didn't quite get that—what role or place were you at, and what did you do there?"
            )

        if count == 1:
            # Extract single experience and start clarify
            try:
                draft_set_id, raw_exp_id, families = await run_draft_single(
                    db, user_id, english or user_content, 1, 1
                )
            except Exception as e:
                logger.exception("run_draft_single failed: %s", e)
                return "Can you tell me a bit more—like where you worked and roughly when?"
            if not families:
                return "Can you tell me a bit more—like where you worked and roughly when?"
            family = families[0]
            parent = family.get("parent") or {}
            state.card_family = family
            state.draft_set_id = draft_set_id
            state.raw_experience_id = raw_exp_id
            state.stage = "clarifying"
            state.asked_history = []
            summary = parent.get("summary") or parent.get("normalized_role") or parent.get("title") or "Your experience"
            first_clarify = await clarify_experience_interactive(
                raw_text=english or user_content,
                current_card=parent,
                card_type="parent",
                conversation_history=conv_history,
                card_family=family,
                asked_history_structured=[],
                max_parent=DEFAULT_MAX_PARENT_CLARIFY,
                max_child=DEFAULT_MAX_CHILD_CLARIFY,
            )
            q = first_clarify.get("clarifying_question")
            if first_clarify.get("asked_history_entry"):
                state.asked_history.append(first_clarify["asked_history_entry"])
            if first_clarify.get("canonical_family"):
                state.card_family = first_clarify["canonical_family"]
            return f"Here's what I understood: {summary}. {q or 'I have a few questions to get more detail.'}"

        # Multiple experiences: choose_focus
        state.detected_experiences = experiences
        state.stage = "awaiting_choice"
        options = [{"parent_id": str(e["index"]), "label": e.get("label", f"Experience {e['index']}")} for e in experiences]
        parts = ["I found multiple experiences. Which one do you want to add first?"]
        for i, o in enumerate(options):
            parts.append(f"{i + 1}. {o['label']}")
        parts.append("Say the number or the name.")
        return " ".join(parts)

    if state.stage == "awaiting_choice":
        options = [{"parent_id": str(e["index"]), "label": e.get("label", "")} for e in state.detected_experiences]
        choice = _parse_choice_input(user_content, options)
        if not choice:
            return "Which one would you like? Say 1, 2, or the name of the experience."
        idx = int(choice)
        state.focus_parent_id = choice
        state.stage = "clarifying"
        try:
            draft_set_id, raw_exp_id, families = await run_draft_single(
                db,
                user_id,
                state.raw_experience_text,
                idx,
                len(state.detected_experiences),
            )
        except Exception as e:
            logger.exception("run_draft_single (choice) failed: %s", e)
            return "I had trouble with that. Could you try again?"
        if not families:
            return "I couldn't extract that experience. Can you tell me more about it?"
        family = families[0]
        state.card_family = family
        state.draft_set_id = draft_set_id
        state.raw_experience_id = raw_exp_id
        state.asked_history = []
        parent = family.get("parent") or {}
        first_clarify = await clarify_experience_interactive(
            raw_text=state.raw_experience_text,
            current_card=parent,
            card_type="parent",
            conversation_history=conv_history,
            card_family=family,
            asked_history_structured=[],
            max_parent=DEFAULT_MAX_PARENT_CLARIFY,
            max_child=DEFAULT_MAX_CHILD_CLARIFY,
        )
        q = first_clarify.get("clarifying_question")
        if first_clarify.get("asked_history_entry"):
            state.asked_history.append(first_clarify["asked_history_entry"])
        if first_clarify.get("canonical_family"):
            state.card_family = first_clarify["canonical_family"]
        return q or "I have a few questions to get more detail."

    if state.stage == "clarifying":
        family = state.card_family or {"parent": {}, "children": []}
        parent = family.get("parent") or {}
        last_target = None
        if state.asked_history and state.asked_history[-1].get("role") == "user":
            for e in reversed(state.asked_history):
                if e.get("role") == "assistant" and e.get("kind") == "clarify_question":
                    last_target = {
                        "target_type": e.get("target_type"),
                        "target_field": e.get("target_field"),
                        "target_child_type": e.get("target_child_type"),
                    }
                    break

        result = await clarify_experience_interactive(
            raw_text=user_content,
            current_card=parent,
            card_type="parent",
            conversation_history=conv_history,
            card_family=family,
            asked_history_structured=state.asked_history,
            last_question_target=last_target,
            max_parent=DEFAULT_MAX_PARENT_CLARIFY,
            max_child=DEFAULT_MAX_CHILD_CLARIFY,
        )

        if result.get("asked_history_entry"):
            state.asked_history.append(result["asked_history_entry"])
        if result.get("canonical_family"):
            state.card_family = result["canonical_family"]

        # Persist filled fields if we have card_id
        filled = result.get("filled") or {}
        if filled:
            parent_merged = {**(parent or {}), **filled}
            card_id = (parent or {}).get("id")
            if card_id:
                card = await experience_card_service.get_card(db, card_id, user_id)
                if card:
                    patch = _parent_merged_to_patch(parent_merged)
                    apply_card_patch(card, patch)
                    await db.flush()
                    await embed_experience_cards(db, parents=[card], children=[])

        if result.get("should_stop"):
            state.stage = "card_ready"
            return (
                result.get("clarifying_question")
                or "Your experience card is ready. You can view it on the cards page and add more experiences anytime."
            )

        q = result.get("clarifying_question")
        if q:
            return q

        if result.get("action") == "choose_focus":
            state.stage = "awaiting_choice"
            state.detected_experiences = [{"index": int(o.get("parent_id", i)), "label": o.get("label", "")} for i, o in enumerate(result.get("options") or [])]
            return result.get("message") or "Which experience would you like to add?"

        return "What else would you like to add about this experience?"

    if state.stage == "card_ready":
        return "Your card is ready. Say 'add another experience' to create a new one, or you can view and edit your cards on the page."

    return "What would you like to add?"
