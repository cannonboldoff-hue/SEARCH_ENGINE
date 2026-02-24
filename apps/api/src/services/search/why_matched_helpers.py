"""Helpers for search why_matched: payload building, sanitization, validation, fallback.

Ensures short, grounded, deduplicated reasons; no raw labels/headlines leaked to UI.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
WHY_REASON_MAX_LEN = 150
WHY_REASON_MAX_WORDS = 15
WHY_REASON_MAX_ITEMS = 3
EVIDENCE_SNIPPET_MAX_LEN = 150
EVIDENCE_STRING_MAX_LEN = 200

# Generic prefixes to strip from LLM output
WHY_GENERIC_PREFIXES = (
    "why this card was shown:",
    "why shown:",
    "match reason:",
    "reason:",
    "because",
    "this person was shown because",
    "matched because",
)


# -----------------------------------------------------------------------------
# Sanitization and dedupe
# -----------------------------------------------------------------------------
def sanitize_text_for_llm(text: str) -> str:
    """Normalize text for LLM payload: whitespace, repeated punctuation."""
    if not text or not isinstance(text, str):
        return ""
    s = " ".join(text.split()).strip()
    # Collapse repeated punctuation (e.g. "!!" -> "!", "---" -> "-")
    s = re.sub(r"([!?.,;:])\1+", r"\1", s)
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def dedupe_strings_preserve_order(items: list[str]) -> list[str]:
    """Remove empty, null, and near-duplicate strings; preserve order."""
    if not items:
        return []
    seen_normalized: set[str] = set()
    out: list[str] = []
    for x in (items or []):
        if x is None:
            continue
        s = sanitize_text_for_llm(str(x))
        if not s:
            continue
        key = s.lower().strip()
        if key in seen_normalized:
            continue
        # Optional: drop if very similar to an existing (substring)
        if any(key in prev or prev in key for prev in seen_normalized):
            continue
        seen_normalized.add(key)
        out.append(s)
    return out


def truncate_evidence(text: str, max_len: int = EVIDENCE_SNIPPET_MAX_LEN) -> str:
    """Truncate evidence string for payload; prefer word boundary."""
    if not text or not isinstance(text, str):
        return ""
    s = sanitize_text_for_llm(text)
    if len(s) <= max_len:
        return s
    cut = s[: max_len + 1].rsplit(maxsplit=1)
    return (cut[0] if cut else s[:max_len]).strip()


def truncate_reason_to_max_words(text: str, max_words: int = WHY_REASON_MAX_WORDS) -> str:
    """Truncate a reason string to at most max_words. Preserves word boundaries."""
    if not text or not isinstance(text, str):
        return ""
    s = sanitize_text_for_llm(text)
    if not s:
        return ""
    words = s.split()
    if len(words) <= max_words:
        return s
    return " ".join(words[:max_words]).strip()


# -----------------------------------------------------------------------------
# Compact evidence payload per person (deduped, no redundant parent/child copy)
# -----------------------------------------------------------------------------
def _compact_text(value: Any, max_len: int) -> str | None:
    if value is None:
        return None
    txt = sanitize_text_for_llm(str(value))
    if not txt:
        return None
    return txt[:max_len] if len(txt) > max_len else txt


def _compact_list(values: list[Any] | None, max_len: int, max_items: int) -> list[str]:
    out: list[str] = []
    for v in (values or [])[:max_items]:
        c = _compact_text(v, max_len)
        if c:
            out.append(c)
    return dedupe_strings_preserve_order(out)


def _child_display_fields(child: Any) -> dict[str, Any]:
    """Get display fields from ExperienceCardChild (label + value dict)."""
    value = getattr(child, "value", None) or {}
    if not isinstance(value, dict):
        value = {}
    label = getattr(child, "label", None)
    headline = value.get("headline") if isinstance(value.get("headline"), str) else None
    summary = value.get("summary") if isinstance(value.get("summary"), str) else None
    title = label or headline or ""
    return {
        "title": _compact_text(title, 100),
        "summary": _compact_text(summary, EVIDENCE_SNIPPET_MAX_LEN),
        "tags": _compact_list(value.get("tags"), 40, 5) if isinstance(value.get("tags"), list) else [],
    }


def build_match_explanation_payload(
    query_context: dict[str, Any],
    people_evidence_raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a compact, deduped evidence payload per person for the LLM.

    - query_context: { "query_original", "query_cleaned", "must", "should" } (serializable)
    - people_evidence_raw: list of dicts with person_id, matched_parent_cards, matched_child_cards
      (e.g. from _build_person_why_evidence before dedupe).

    Returns list of per-person payloads with evidence deduped and string lengths capped.
    Avoids sending parent title + child label + search_document repeating the same fact.
    """
    cleaned: list[dict[str, Any]] = []
    for pe in people_evidence_raw or []:
        person_id = str(pe.get("person_id") or "").strip()
        if not person_id:
            continue
        parents = pe.get("matched_parent_cards") or []
        children = pe.get("matched_child_cards") or []

        # Track all text snippets globally to dedupe parent/child overlap
        seen_snippets: set[str] = set()

        def _should_include(text: str | None) -> bool:
            """Check if text is new (not duplicate/substring of existing)."""
            if not text:
                return False
            key = text.lower().strip()
            if not key:
                return False
            # Exact duplicate check
            if key in seen_snippets:
                return False
            # Substring overlap check (avoid near-duplicates)
            for existing in seen_snippets:
                if key in existing or existing in key:
                    return False
            seen_snippets.add(key)
            return True

        # Process parents
        parent_evidence: list[dict[str, Any]] = []
        for p in parents[:2]:
            if not isinstance(p, dict):
                continue
            title = _compact_text(p.get("title"), 100)
            company = _compact_text(p.get("company_name"), 90)
            location = _compact_text(p.get("location"), 80)
            summary = _compact_text(p.get("summary"), EVIDENCE_SNIPPET_MAX_LEN)
            phrases = p.get("search_phrases")
            sim = p.get("similarity")
            start_date = p.get("start_date")
            end_date = p.get("end_date")
            
            # Only include if not duplicate
            clean_title = title if _should_include(title) else None
            clean_summary = summary if _should_include(summary) else None
            
            # Dedupe skills/phrases
            clean_phrases: list[str] = []
            if phrases and isinstance(phrases, list):
                for ph in phrases[:5]:
                    ph_compact = _compact_text(ph, 60)
                    if _should_include(ph_compact):
                        clean_phrases.append(ph_compact)
            
            parent_evidence.append({
                "headline": clean_title,
                "summary": truncate_evidence(clean_summary or "", EVIDENCE_SNIPPET_MAX_LEN) or None,
                "company": company,
                "location": location,
                "time": _compact_text(f"{start_date or ''}–{end_date or ''}".strip("–"), 40) or None,
                "skills": clean_phrases[:4],
                "similarity": round(float(sim), 4) if sim is not None else None,
            })

        # Process children
        child_evidence: list[dict[str, Any]] = []
        for c in children[:2]:
            if isinstance(c, dict):
                title = _compact_text(c.get("title") or c.get("headline"), 100)
                summary = _compact_text(c.get("summary") or c.get("context"), EVIDENCE_SNIPPET_MAX_LEN)
                tags = c.get("tags")
                phrases = c.get("search_phrases")
                sim = c.get("similarity")
            else:
                cf = _child_display_fields(c)
                title = cf.get("title")
                summary = cf.get("summary")
                tags = cf.get("tags")
                phrases = getattr(c, "search_phrases", None)
                sim = getattr(c, "similarity", None)
            
            # Only include if not already seen in parents
            clean_title = title if _should_include(title) else None
            clean_summary = summary if _should_include(summary) else None
            
            # Dedupe child tags/phrases
            clean_tags: list[str] = []
            for tag_source in [tags, phrases]:
                if tag_source and isinstance(tag_source, list):
                    for t in tag_source[:4]:
                        t_compact = _compact_text(t, 50)
                        if _should_include(t_compact):
                            clean_tags.append(t_compact)
                            if len(clean_tags) >= 4:
                                break
                if len(clean_tags) >= 4:
                    break
            
            child_evidence.append({
                "headline": clean_title,
                "summary": truncate_evidence(clean_summary or "", EVIDENCE_SNIPPET_MAX_LEN) or None,
                "skills": clean_tags,
                "similarity": round(float(sim), 4) if sim is not None else None,
            })

        # Collect non-null skills across all evidence
        skills_merged: list[str] = []
        for p in parent_evidence:
            skills_merged.extend(p.get("skills") or [])
        for c in child_evidence:
            skills_merged.extend(c.get("skills") or [])
        skills_merged = dedupe_strings_preserve_order(skills_merged)[:8]

        # Collect outcomes (summaries with metrics/results)
        outcomes: list[str] = []
        for p in parent_evidence:
            if p.get("summary"):
                outcomes.append(p["summary"])
        for c in child_evidence:
            if c.get("summary"):
                outcomes.append(c["summary"])
        outcomes = dedupe_strings_preserve_order(outcomes)[:5]

        # Build final compact evidence object
        payload = {
            "person_id": person_id,
            "query_context": query_context,
            "evidence": {
                "headline": (parent_evidence[0].get("headline") if parent_evidence else None) or 
                            (child_evidence[0].get("headline") if child_evidence else None),
                "summary": (parent_evidence[0].get("summary") if parent_evidence else None) or 
                           (child_evidence[0].get("summary") if child_evidence else None),
                "skills": skills_merged,
                "tools": skills_merged[:5],  # Alias for prompt compatibility
                "domain": parent_evidence[0].get("headline") if parent_evidence else None,
                "outcomes": outcomes,
                "company": parent_evidence[0].get("company") if parent_evidence else None,
                "location": parent_evidence[0].get("location") if parent_evidence else None,
                "time": parent_evidence[0].get("time") if parent_evidence else None,
                "child_evidence": [
                    {
                        "headline": ce.get("headline"), 
                        "summary": ce.get("summary"), 
                        "skills": ce.get("skills") or []
                    }
                    for ce in child_evidence
                    if ce.get("headline") or ce.get("summary")  # Only include if has content
                ],
            },
        }
        # Drop None/empty values for smaller payload
        payload["evidence"] = {
            k: v for k, v in payload["evidence"].items() 
            if v is not None and v != [] and v != ""
        }
        cleaned.append(payload)
    return cleaned


# -----------------------------------------------------------------------------
# Post-LLM validation and cleanup
# -----------------------------------------------------------------------------
def clean_why_reason(reason: str) -> str | None:
    """Clean a single why_matched reason: strip generic prefixes, enforce length, reject junk.
    
    Returns None if reason is invalid/low-quality.
    """
    if not reason or not isinstance(reason, str):
        return None
    s = sanitize_text_for_llm(reason)
    if not s:
        return None
    
    # Strip generic meta-prefixes
    lower = s.lower()
    for prefix in WHY_GENERIC_PREFIXES:
        if lower.startswith(prefix):
            s = s[len(prefix) :].strip()
            s = sanitize_text_for_llm(s)
            lower = s.lower()
            break
    
    # Enforce max length with word boundary truncation
    if len(s) > WHY_REASON_MAX_LEN:
        s = s[: WHY_REASON_MAX_LEN + 1].rsplit(maxsplit=1)[0] or s[:WHY_REASON_MAX_LEN]
    s = s.strip()
    # Enforce max 12 words
    s = truncate_reason_to_max_words(s, WHY_REASON_MAX_WORDS)
    s = s.strip()
    
    if not s or len(s) < 3:
        return None
    
    # Reject obvious junk patterns
    words = s.split()
    
    # 1) Same word repeated 3+ times (e.g., "sales sales sales")
    if len(words) >= 3 and len(set(w.lower() for w in words)) == 1:
        return None
    
    # 2) Very generic/vague reasons (too short or single word)
    if len(words) == 1 and len(s) < 10:
        return None
    
    # 3) All words are the same repeated (e.g., "experience experience experience in tech")
    word_counts = {}
    for w in words:
        word_counts[w.lower()] = word_counts.get(w.lower(), 0) + 1
    max_word_count = max(word_counts.values()) if word_counts else 0
    if len(words) >= 3 and max_word_count >= len(words) - 1:
        # Most words are duplicates
        return None
    
    # 4) Reject if it looks like a raw label (all caps or title case spam)
    if s.isupper() and len(words) <= 3:
        return None
    
    # 5) Reject obvious markdown artifacts
    if s.startswith(("-", "*", "•", "#")) or s.endswith((":", "...")):
        s = s.lstrip("-*•#").rstrip(":.")
        s = sanitize_text_for_llm(s)
        if not s or len(s) < 3:
            return None
    
    return s if s else None


def validate_why_matched_output(parsed: dict[str, Any]) -> tuple[dict[str, list[str]], int]:
    """Validate and clean LLM JSON output. Returns (person_id -> reasons, fallback_count)."""
    fallback_count = 0
    result: dict[str, list[str]] = {}
    people = parsed.get("people")
    if not isinstance(people, list):
        return {}, 0
    for item in people:
        if not isinstance(item, dict):
            continue
        person_id = str(item.get("person_id") or "").strip()
        if not person_id:
            continue
        raw_reasons = item.get("why_matched")
        if not isinstance(raw_reasons, (list, tuple)):
            raw_reasons = []
        cleaned: list[str] = []
        seen: set[str] = set()
        for r in raw_reasons:
            reason = clean_why_reason(str(r))
            if not reason:
                continue
            key = reason.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(reason)
            if len(cleaned) >= WHY_REASON_MAX_ITEMS:
                break
        if not cleaned:
            fallback_count += 1
        result[person_id] = cleaned[:WHY_REASON_MAX_ITEMS]
    return result, fallback_count


# -----------------------------------------------------------------------------
# Deterministic fallback reason builder
# -----------------------------------------------------------------------------
def fallback_build_why_matched(
    person_evidence: dict[str, Any],
    query_context: dict[str, Any],
) -> list[str]:
    """Build 1–3 short, clean reasons from cleaned evidence when LLM fails or returns invalid.
    
    Generates natural, compressed reasons without verbose prefixes like "Location match:" or "Skills/domain:".
    Prioritizes: explicit query constraints > skills/tools > outcomes > domain/summary.
    """
    reasons: list[str] = []
    evidence = person_evidence.get("evidence") or {}
    must = (query_context.get("must") or {})
    should = (query_context.get("should") or {})

    def _cap_reason(r: str | None) -> str | None:
        """Cap reason to max chars and max words; return None if empty."""
        if not r:
            return None
        r = truncate_evidence(r, WHY_REASON_MAX_LEN)
        r = truncate_reason_to_max_words(r, WHY_REASON_MAX_WORDS)
        return r.strip() or None

    # Helper to build natural location phrase
    def _build_location_reason() -> str | None:
        loc = evidence.get("location")
        company = evidence.get("company")
        if not loc:
            return None
        if company:
            return _cap_reason(f"{company} in {loc}")
        return _cap_reason(f"Based in {loc}")

    # Helper to build natural time reason
    def _build_time_reason() -> str | None:
        time_range = evidence.get("time")
        headline = evidence.get("headline") or evidence.get("domain")
        if not time_range:
            return None
        if headline:
            return _cap_reason(f"{headline} during {time_range}")
        return _cap_reason(f"Experience during {time_range}")

    # Helper to build natural skills reason
    def _build_skills_reason() -> str | None:
        skills = evidence.get("skills") or evidence.get("tools") or []
        if not skills:
            return None
        if len(skills) == 1:
            headline = evidence.get("headline") or evidence.get("domain")
            if headline:
                return _cap_reason(f"{headline} with {skills[0]}")
            return _cap_reason(f"Experience with {skills[0]}")
        # Multiple skills: just list them naturally
        skill_str = ", ".join(skills[:3])
        return _cap_reason(skill_str)

    # 1) Explicit query filters matched (location, company, time)
    loc = (must.get("location_text") or must.get("city") or must.get("country") or "").strip()
    if loc and evidence.get("location"):
        r = _build_location_reason()
        if r and r not in reasons:
            reasons.append(r)
    
    time_start = must.get("time_start")
    time_end = must.get("time_end")
    if (time_start or time_end) and evidence.get("time"):
        r = _build_time_reason()
        if r and r not in reasons:
            reasons.append(r)

    # 2) Skills/tools overlap
    if len(reasons) < WHY_REASON_MAX_ITEMS:
        r = _build_skills_reason()
        if r and r not in reasons:
            reasons.append(r)

    # 3) Outcomes/metrics (most specific evidence, prioritize first)
    outcomes = evidence.get("outcomes") or []
    for o in outcomes[:2]:
        if len(reasons) >= WHY_REASON_MAX_ITEMS:
            break
        r = _cap_reason(str(o))
        if r and r not in reasons:
            reasons.append(r)

    # 4) Domain/work-type (general fallback)
    if len(reasons) < WHY_REASON_MAX_ITEMS:
        domain = evidence.get("domain") or evidence.get("headline")
        if domain:
            r = _cap_reason(str(domain))
            if r and r not in reasons:
                reasons.append(r)

    # 5) Child evidence (if still need more reasons)
    child_evidence = evidence.get("child_evidence") or []
    for ce in child_evidence[:1]:
        if len(reasons) >= WHY_REASON_MAX_ITEMS:
            break
        h = ce.get("headline") or ce.get("summary")
        if h:
            r = _cap_reason(str(h))
            if r and r not in reasons:
                reasons.append(r)

    # Final dedupe and return
    return dedupe_strings_preserve_order(reasons)[:WHY_REASON_MAX_ITEMS]
