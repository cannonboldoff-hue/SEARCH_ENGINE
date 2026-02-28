"""
Experience-card clarify logic (stateless).

This module holds the rules and validation for the clarify conversation:
canonical card shape, plan validation, fallbacks, and merging patches.
It does NOT call the LLM or DB; the actual flow (planner/question/apply LLM
and conversation orchestration) lives in pipeline.

Concepts:
- Canonical normalizer: one card shape for all clarify logic.
- Planner contract: ask | autofill | stop + target_type/target_field/target_child_type.
- Backend guardrail: validate plan, fallback if invalid.
- Question writer / answer applier are LLM steps in the pipeline; this module
  provides merge_patch_into_card_family, normalize_after_patch, etc.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Canonical shape and allowed targets
# -----------------------------------------------------------------------------

PARENT_TARGET_FIELDS: tuple[str, ...] = (
    "headline",
    "role",
    "summary",
    "company_name",
    "team",
    "time",
    "location",
    "location.is_remote",
    "domain",
    "sub_domain",
    "intent_primary",
    "seniority_level",
    "employment_type",
    "company_type",
)

PARENT_PRIORITY: tuple[str, ...] = (
    "headline",
    "role",
    "summary",
    "company_name",
    "time",
    "location",
    "domain",
    "intent_primary",
)

CHILD_TARGET_FIELDS: tuple[str, ...] = (
    "skills",
    "tools",
    "responsibilities",
    "achievements",
    "metrics",
    "collaborations",
    "domain_knowledge",
    "exposure",
    "education",
    "certifications",
)

CHILD_PRIORITY: tuple[str, ...] = (
    "metrics",
    "tools",
    "achievements",
    "responsibilities",
    "collaborations",
    "domain_knowledge",
    "exposure",
    "education",
    "certifications",
)

DEFAULT_MAX_PARENT_CLARIFY = 2
DEFAULT_MAX_CHILD_CLARIFY = 2

# When multiple experiences exist and no focus selected, show this message.
CHOOSE_FOCUS_MESSAGE = (
    "I found multiple experiences in what you shared. We'll build one card first—which one do you want to add?"
)

# Patterns that indicate generic onboarding/discovery questions (BANNED in post-extraction clarify).
GENERIC_QUESTION_PATTERNS = (
    "something cool you've built",
    "something cool you built",
    "tell me more about your experience",
    "what did you work on",
    "can you share more",
    "share more about",
    "tell me about",
    "what would you like to add",
    "describe your experience",
    "tell me about a",
    "what's one experience",
    "anything else you want to add",
    "what experience",
    "like to add",
    "want to add",
)


def _get_str(d: dict, *keys: str) -> Optional[str]:
    v = None
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _get_list(d: dict, key: str) -> list:
    v = d.get(key)
    if isinstance(v, list):
        return v
    return []


def _get_dict(d: dict, key: str) -> dict:
    v = d.get(key)
    if isinstance(v, dict):
        return v
    return {}


def normalize_card_family_for_clarify(card_family: dict) -> dict:
    """
    Normalize any card family (API response or pipeline shape) into one canonical
    nested shape for clarify. Legacy flat keys (start_date, end_date,
    location string) are merged into time/location objects.
    """
    parent_raw = card_family.get("parent") or {}
    children_raw = _get_list(card_family, "children")

    # --- Parent canonical ---
    p = dict(parent_raw)
    # headline / title
    headline = _get_str(p, "headline", "title")
    if not headline:
        headline = _get_str(p, "normalized_role") or None
    p["headline"] = headline
    if "title" not in p or not p["title"]:
        p["title"] = headline
    # role from roles[0] or normalized_role
    if not p.get("normalized_role") and _get_list(p, "roles"):
        r0 = p["roles"][0]
        if isinstance(r0, dict) and r0.get("label"):
            p["normalized_role"] = r0.get("label")
        elif isinstance(r0, str):
            p["normalized_role"] = r0
    p["role"] = p.get("normalized_role")
    # summary
    p["summary"] = _get_str(p, "summary", "context") or ""
    # company / team
    p["company_name"] = _get_str(p, "company_name", "company", "organization")
    p["team"] = _get_str(p, "team")
    p["domain"] = _get_str(p, "domain")
    p["sub_domain"] = _get_str(p, "sub_domain")
    p["intent_primary"] = _get_str(p, "intent_primary", "intent")
    # time: nested
    time_in = _get_dict(p, "time")
    if not time_in.get("start") and p.get("start_date"):
        time_in["start"] = p["start_date"] if isinstance(p["start_date"], str) else None
    if not time_in.get("end") and p.get("end_date"):
        time_in["end"] = p["end_date"] if isinstance(p["end_date"], str) else None
    if time_in.get("ongoing") is None and p.get("is_current") is not None:
        time_in["ongoing"] = bool(p["is_current"])
    if not time_in.get("text") and (p.get("time_range") or p.get("time_text")):
        time_in["text"] = _get_str(p, "time_range", "time_text")
    p["time"] = time_in
    # location: nested
    loc_in = _get_dict(p, "location")
    if isinstance(loc_in.get("text"), str):
        pass
    elif _get_str(p, "location"):
        loc_in["text"] = _get_str(p, "location")
    if not loc_in.get("city") and p.get("city"):
        loc_in["city"] = p.get("city")
    if not loc_in.get("country") and p.get("country"):
        loc_in["country"] = p.get("country")
    p["location"] = loc_in
    # arrays
    p["roles"] = _get_list(p, "roles")
    p["actions"] = _get_list(p, "actions")
    p["outcomes"] = _get_list(p, "outcomes")
    if not p.get("tooling") and (p.get("tooling") is None):
        p["tooling"] = {"tools": _get_list(_get_dict(p, "tooling"), "tools")}
    else:
        tooling = _get_dict(p, "tooling")
        if "tools" not in tooling:
            tooling["tools"] = _get_list(tooling, "tools")
        p["tooling"] = tooling

    # --- Children canonical ---
    from src.services.experience.child_value import get_child_label

    children: list[dict] = []
    for c in children_raw:
        if not isinstance(c, dict):
            continue
        child = dict(c)
        child_type = _get_str(child, "child_type", "relation_type") or "skills"
        child["child_type"] = child_type
        value = _get_dict(child, "value")
        child["label"] = _get_str(child, "label", "title") or get_child_label(value or {}, child_type)
        if not value:
            value = {"raw_text": None, "items": []}
        if "items" not in value or not isinstance(value.get("items"), list):
            value["items"] = []
        child["value"] = value
        children.append(child)

    return {"parent": p, "children": children}


def is_parent_good_enough(canonical_parent: dict) -> bool:
    """
    Parent is good enough when every applicable field has a value, has been asked,
    or has been set to null as inapplicable. Does NOT stop early based on minimum fields.
    Returns True only when no high-value fields remain unresolved.
    """
    # A field is considered resolved if it has a non-empty value OR is explicitly null
    # (null means inapplicable). We check the fields that are always applicable.
    has_headline_or_role = bool(
        _get_str(canonical_parent, "headline", "title") or _get_str(canonical_parent, "role", "normalized_role")
    )
    has_summary = bool(_get_str(canonical_parent, "summary"))
    time_obj = _get_dict(canonical_parent, "time")
    has_time = bool(
        time_obj.get("start") or time_obj.get("end") or time_obj.get("text") or time_obj.get("ongoing") is True
    )
    has_domain = bool(_get_str(canonical_parent, "domain"))
    has_intent = bool(_get_str(canonical_parent, "intent_primary", "intent"))
    # company_name may be null (inapplicable for freelance/self-employed) — treat explicit null as resolved
    company_name_key_present = "company_name" in canonical_parent or "company" in canonical_parent
    has_company_resolved = company_name_key_present  # null or value both count as resolved
    # All core fields must be resolved
    return bool(
        has_headline_or_role
        and has_summary
        and has_time
        and has_domain
        and has_intent
        and has_company_resolved
    )


def compute_missing_fields(canonical_family: dict) -> dict[str, list[str]]:
    """Return { 'parent': [field, ...], 'child': [child_type, ...] } for empty/missing high-value fields."""
    missing_parent: list[str] = []
    p = canonical_family.get("parent") or {}
    if not _get_str(p, "headline", "title") and not _get_str(p, "role", "normalized_role"):
        missing_parent.append("headline")
    if not _get_str(p, "summary"):
        missing_parent.append("summary")
    if not _get_str(p, "company_name", "company"):
        missing_parent.append("company_name")
    time_obj = _get_dict(p, "time")
    if not (time_obj.get("start") or time_obj.get("end") or time_obj.get("text") or time_obj.get("ongoing") is True):
        missing_parent.append("time")
    loc_obj = _get_dict(p, "location")
    if not (loc_obj.get("city") or loc_obj.get("country") or loc_obj.get("text")):
        missing_parent.append("location")
    if not _get_str(p, "domain"):
        missing_parent.append("domain")
    if not _get_str(p, "intent_primary", "intent"):
        missing_parent.append("intent_primary")

    missing_child: list[str] = []
    for c in _get_list(canonical_family, "children"):
        if not isinstance(c, dict):
            continue
        ct = _get_str(c, "child_type") or "skills"
        value = _get_dict(c, "value")
        items = value.get("items") if isinstance(value.get("items"), list) else []
        has_items = bool(items and any(
            (isinstance(it, dict) and (it.get("title") or it.get("subtitle") or "").strip())
            for it in items
        ))
        if not has_items and ct in CHILD_TARGET_FIELDS:
            missing_child.append(ct)
    seen = set()
    missing_child_dedup = [x for x in CHILD_PRIORITY if x in missing_child and not (seen.add(x) or False)]
    seen.clear()
    for x in missing_child:
        if x not in seen:
            seen.add(x)
            if x not in missing_child_dedup:
                missing_child_dedup.append(x)

    return {"parent": missing_parent, "child": missing_child_dedup}


# -----------------------------------------------------------------------------
# Planner output and validated plan
# -----------------------------------------------------------------------------

@dataclass
class ClarifyPlan:
    """Raw or validated plan from planner."""
    action: Literal["ask", "autofill", "stop", "choose_focus"]
    target_type: Optional[Literal["parent", "child"]] = None
    target_field: Optional[str] = None
    target_child_type: Optional[str] = None
    reason: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    autofill_patch: Optional[dict] = None
    focus_parent_id: Optional[str] = None
    message: Optional[str] = None
    options: Optional[list[dict]] = None


def build_choose_focus_options(card_families: list[dict]) -> list[dict]:
    """Build options list for choose_focus from multiple card families. Each option: parent_id, label."""
    options: list[dict] = []
    for i, family in enumerate(card_families):
        parent = family.get("parent") or {}
        pid = _get_str(parent, "id")
        if not pid:
            pid = str(i + 1)
        label = _get_str(parent, "headline", "title", "normalized_role")
        if not label:
            label = _get_str(parent, "summary")
        if not label:
            label = _get_str(parent, "company_name", "company")
        if not label:
            label = f"Experience {i + 1}"
        if len(label) > 80:
            label = label[:77] + "..."
        options.append({"parent_id": pid, "label": label})
    return options


def is_question_generic_onboarding(question: str) -> bool:
    """Return True if the question is a generic discovery/onboarding prompt (BANNED in post-extraction)."""
    if not question or not question.strip():
        return True
    q = question.strip().lower()
    for pattern in GENERIC_QUESTION_PATTERNS:
        if pattern in q:
            return True
    return False


def _parse_planner_json(data: dict) -> Optional[ClarifyPlan]:
    if not isinstance(data, dict):
        return None
    action = (data.get("action") or "").strip().lower()
    if action not in ("ask", "autofill", "stop", "choose_focus"):
        return None
    target_type = (data.get("target_type") or "").strip().lower() or None
    if target_type and target_type not in ("parent", "child"):
        target_type = None
    target_field = (data.get("target_field") or "").strip() or None
    target_child_type = (data.get("target_child_type") or "").strip() or None
    reason = (data.get("reason") or "").strip()
    confidence = (data.get("confidence") or "medium").strip().lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"
    autofill_patch = data.get("autofill_patch") if isinstance(data.get("autofill_patch"), dict) else None
    focus_parent_id = (data.get("focus_parent_id") or "").strip() or None
    message = (data.get("message") or "").strip() or None
    options_raw = data.get("options")
    options = None
    if isinstance(options_raw, list):
        options = []
        for o in options_raw:
            if isinstance(o, dict) and o.get("parent_id") is not None:
                options.append({"parent_id": str(o["parent_id"]), "label": str(o.get("label") or o["parent_id"])[:80]})
    return ClarifyPlan(
        action=action,
        target_type=target_type or None,
        target_field=target_field,
        target_child_type=target_child_type,
        reason=reason,
        confidence=confidence,
        autofill_patch=autofill_patch,
        focus_parent_id=focus_parent_id,
        message=message,
        options=options,
    )


def validate_clarify_plan(
    plan: Optional[ClarifyPlan],
    canonical_family: dict,
    asked_history: list[dict],
    *,
    parent_asked_count: int = 0,
    child_asked_count: int = 0,
    max_parent: int = DEFAULT_MAX_PARENT_CLARIFY,
    max_child: int = DEFAULT_MAX_CHILD_CLARIFY,
) -> tuple[ClarifyPlan, bool]:
    """Validate planner output. Returns (validated_plan, used_fallback)."""
    used_fallback = False
    if not plan or plan.action not in ("ask", "autofill", "stop"):
        used_fallback = True
        plan = fallback_clarify_plan(
            canonical_family, asked_history,
            parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
            max_parent=max_parent, max_child=max_child,
        )
        return plan, used_fallback
    if plan.action == "choose_focus":
        used_fallback = True
        plan = fallback_clarify_plan(
            canonical_family, asked_history,
            parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
            max_parent=max_parent, max_child=max_child,
        )
        return plan, used_fallback

    parent = canonical_family.get("parent") or {}
    missing = compute_missing_fields(canonical_family)
    parent_ok = is_parent_good_enough(parent)

    if plan.action == "stop":
        if parent_ok or parent_asked_count >= max_parent:
            return plan, used_fallback
        used_fallback = True
        plan = fallback_clarify_plan(
            canonical_family, asked_history,
            parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
            max_parent=max_parent, max_child=max_child,
        )
        return plan, used_fallback

    if plan.action == "autofill":
        if plan.target_type == "parent" and plan.target_field and plan.target_field in PARENT_TARGET_FIELDS:
            if plan.autofill_patch and _patch_only_touches_target(plan.autofill_patch, plan.target_field, "parent"):
                if plan.target_field == "time":
                    time_patch = plan.autofill_patch.get("time") if isinstance(plan.autofill_patch.get("time"), dict) else {}
                    if not (time_patch.get("start") or time_patch.get("end") or time_patch.get("text") or time_patch.get("ongoing") is True):
                        logger.warning("validate_clarify_plan: rejected invalid time autofill patch: %s", time_patch)
                        used_fallback = True
                        plan = fallback_clarify_plan(
                            canonical_family, asked_history,
                            parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                            max_parent=max_parent, max_child=max_child,
                        )
                        return plan, used_fallback
                if _field_already_filled(parent, plan.target_field):
                    logger.warning("validate_clarify_plan: field %s already filled, rejecting autofill", plan.target_field)
                    used_fallback = True
                    plan = fallback_clarify_plan(
                        canonical_family, asked_history,
                        parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                        max_parent=max_parent, max_child=max_child,
                    )
                    return plan, used_fallback
                return plan, used_fallback
        if plan.target_type == "child" and plan.target_child_type and plan.target_child_type in CHILD_TARGET_FIELDS:
            if plan.autofill_patch and _patch_only_touches_child_target(plan.autofill_patch, plan.target_child_type):
                return plan, used_fallback
        used_fallback = True
        plan = fallback_clarify_plan(
            canonical_family, asked_history,
            parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
            max_parent=max_parent, max_child=max_child,
        )
        return plan, used_fallback

    if plan.target_type == "parent":
        if plan.target_field not in PARENT_TARGET_FIELDS and plan.target_field != "location.is_remote":
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if _field_already_asked(asked_history, "parent", plan.target_field, None):
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if _field_already_filled(parent, plan.target_field):
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if parent_asked_count >= max_parent:
            used_fallback = True
            plan = ClarifyPlan(action="stop", reason="Max parent questions reached", confidence="high")
            return plan, used_fallback
        return plan, used_fallback

    if plan.target_type == "child":
        if not parent_ok and parent_asked_count < max_parent:
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if plan.target_child_type not in CHILD_TARGET_FIELDS:
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if _field_already_asked(asked_history, "child", plan.target_field or plan.target_child_type, plan.target_child_type):
            used_fallback = True
            plan = fallback_clarify_plan(
                canonical_family, asked_history,
                parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
                max_parent=max_parent, max_child=max_child,
            )
            return plan, used_fallback
        if child_asked_count >= max_child:
            used_fallback = True
            plan = ClarifyPlan(action="stop", reason="Max child questions reached", confidence="high")
            return plan, used_fallback
        return plan, used_fallback

    used_fallback = True
    plan = fallback_clarify_plan(
        canonical_family, asked_history,
        parent_asked_count=parent_asked_count, child_asked_count=child_asked_count,
        max_parent=max_parent, max_child=max_child,
    )
    return plan, used_fallback


def _field_already_asked(
    asked_history: list[dict],
    target_type: str,
    target_field: Optional[str],
    target_child_type: Optional[str],
) -> bool:
    for msg in asked_history:
        if msg.get("role") != "assistant" or msg.get("kind") != "clarify_question":
            continue
        if msg.get("target_type") != target_type:
            continue
        if target_type == "parent" and msg.get("target_field") == target_field:
            return True
        if target_type == "child" and msg.get("target_child_type") == target_child_type:
            return True
    return False


def _field_already_filled(parent: dict, target_field: Optional[str]) -> bool:
    if not target_field:
        return True
    if target_field == "headline":
        return bool(_get_str(parent, "headline", "title"))
    if target_field == "role":
        return bool(_get_str(parent, "role", "normalized_role"))
    if target_field == "summary":
        return bool(_get_str(parent, "summary"))
    if target_field == "company_name":
        return bool(_get_str(parent, "company_name", "company"))
    if target_field == "team":
        return bool(_get_str(parent, "team"))
    if target_field == "time":
        t = _get_dict(parent, "time")
        return bool(t.get("start") or t.get("end") or t.get("text") or t.get("ongoing") is True)
    if target_field == "location":
        loc = _get_dict(parent, "location")
        return bool(loc.get("city") or loc.get("country") or loc.get("text"))
    if target_field == "location.is_remote":
        loc = _get_dict(parent, "location")
        return loc.get("is_remote") is not None
    if target_field in ("domain", "sub_domain", "intent_primary", "seniority_level", "employment_type", "company_type"):
        return bool(_get_str(parent, target_field))
    return False


def _patch_only_touches_target(patch: dict, target_field: str, target_type: str) -> bool:
    allowed_top_level = {target_field}
    if target_field == "time":
        allowed_top_level = {"time", "start_date", "end_date", "is_current", "time_text", "time_range"}
    elif target_field == "location":
        allowed_top_level = {"location", "city", "country"}
    for key in patch:
        if key not in allowed_top_level:
            return False
    return True


def _patch_only_touches_child_target(patch: dict, target_child_type: str) -> bool:
    if "value" in patch:
        return True
    if "children" in patch and isinstance(patch["children"], list):
        return True
    return len(patch) <= 1


def fallback_clarify_plan(
    canonical_family: dict,
    asked_history: list[dict],
    *,
    parent_asked_count: int = 0,
    child_asked_count: int = 0,
    max_parent: int = DEFAULT_MAX_PARENT_CLARIFY,
    max_child: int = DEFAULT_MAX_CHILD_CLARIFY,
) -> ClarifyPlan:
    """Deterministic fallback: pick next missing parent field, or child, or stop."""
    parent = canonical_family.get("parent") or {}
    missing = compute_missing_fields(canonical_family)
    parent_ok = is_parent_good_enough(parent)

    if parent_asked_count >= max_parent and (parent_ok or child_asked_count >= max_child):
        return ClarifyPlan(action="stop", reason="Limits reached", confidence="high")

    if parent_asked_count < max_parent:
        for field_name in PARENT_PRIORITY:
            if field_name not in (missing.get("parent") or []):
                continue
            if _field_already_asked(asked_history, "parent", field_name, None):
                continue
            if _field_already_filled(parent, field_name):
                continue
            return ClarifyPlan(
                action="ask", target_type="parent", target_field=field_name,
                reason=f"Fallback: next missing parent field {field_name}", confidence="high",
            )

    if child_asked_count >= max_child:
        return ClarifyPlan(action="stop", reason="Max child questions", confidence="high")
    for ct in CHILD_PRIORITY:
        if ct not in missing.get("child", []):
            continue
        if _field_already_asked(asked_history, "child", ct, ct):
            continue
        return ClarifyPlan(
            action="ask", target_type="child", target_field=ct, target_child_type=ct,
            reason=f"Fallback: next missing child {ct}", confidence="high",
        )
    return ClarifyPlan(action="stop", reason="No more missing fields", confidence="high")


def should_stop_clarify(
    plan: ClarifyPlan,
    canonical_family: dict,
    parent_asked_count: int,
    child_asked_count: int,
    max_parent: int,
    max_child: int,
) -> tuple[bool, Optional[str]]:
    """Returns (should_stop, stop_reason)."""
    if plan.action == "stop":
        return True, plan.reason or "Planner chose stop"
    if plan.action == "ask":
        parent = canonical_family.get("parent") or {}
        if plan.target_type == "parent" and parent_asked_count >= max_parent:
            return True, "Max parent questions reached"
        if plan.target_type == "child" and child_asked_count >= max_child:
            return True, "Max child questions reached"
    return False, None


def merge_patch_into_card_family(canonical_family: dict, patch: dict, plan: ClarifyPlan) -> dict:
    """Merge a patch into canonical family."""
    out = json.loads(json.dumps(canonical_family))
    parent = out.get("parent") or {}
    children = list(out.get("children") or [])

    if plan.target_type == "parent":
        for k, v in patch.items():
            if k == "time" and isinstance(v, dict):
                parent["time"] = {**(parent.get("time") or {}), **v}
            elif k == "location" and isinstance(v, dict):
                parent["location"] = {**(parent.get("location") or {}), **v}
            else:
                parent[k] = v
        out["parent"] = parent
        return out

    if plan.target_type == "child" and plan.target_child_type:
        patch_val = patch.get("value") or patch
        if "value" in patch or "items" in patch_val:
            found = False
            for c in children:
                if (c.get("child_type") or c.get("relation_type")) == plan.target_child_type:
                    v = c.get("value") or {}
                    new_items = patch_val.get("items") if isinstance(patch_val.get("items"), list) else []
                    if new_items:
                        from .child_value import merge_child_items, normalize_child_items
                        existing = v.get("items") if isinstance(v.get("items"), list) else []
                        v["items"] = merge_child_items(
                            normalize_child_items(existing) if existing else [],
                            normalize_child_items(new_items),
                        )
                    if patch_val.get("raw_text") is not None:
                        v["raw_text"] = patch_val.get("raw_text")
                    c["value"] = v
                    found = True
                    break
            if not found:
                children.append({
                    "child_type": plan.target_child_type,
                    "value": patch_val if isinstance(patch_val, dict) else {"raw_text": None, "items": []},
                })
        elif "children" in patch and isinstance(patch["children"], list):
            for new_c in patch["children"]:
                if isinstance(new_c, dict):
                    children.append(new_c)
        out["children"] = children
        return out

    return out


def normalize_after_patch(canonical_family: dict) -> dict:
    """Normalize dates, trim strings, dedupe arrays after merge."""
    out = json.loads(json.dumps(canonical_family))
    parent = out.get("parent") or {}
    time_obj = parent.get("time") or {}
    if isinstance(time_obj.get("start"), str) and len(time_obj["start"]) > 10:
        time_obj["start"] = time_obj["start"][:10]
    if isinstance(time_obj.get("end"), str) and len(time_obj["end"]) > 10:
        time_obj["end"] = time_obj["end"][:10]
    parent["time"] = time_obj
    for k in ("headline", "title", "summary", "company_name", "team", "domain", "sub_domain", "intent_primary"):
        if isinstance(parent.get(k), str):
            parent[k] = parent[k].strip()
    out["parent"] = parent
    return out


def canonical_parent_to_flat_response(canonical_parent: dict) -> dict:
    """Convert canonical parent to flat shape for API response."""
    flat = dict(canonical_parent)
    time_obj = _get_dict(canonical_parent, "time")
    flat["start_date"] = time_obj.get("start")
    flat["end_date"] = time_obj.get("end")
    flat["is_current"] = time_obj.get("ongoing")
    flat["time_text"] = time_obj.get("text")
    flat["time_range"] = time_obj.get("text")
    loc = _get_dict(canonical_parent, "location")
    flat["location"] = loc.get("text") or (", ".join(filter(None, [loc.get("city"), loc.get("country")])))
    flat["company_name"] = flat.get("company_name") or flat.get("company")
    flat["normalized_role"] = flat.get("normalized_role") or flat.get("role")
    return flat
