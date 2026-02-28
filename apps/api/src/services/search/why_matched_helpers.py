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
    """Get display fields from ExperienceCardChild.

    Returns raw_text, titles[], and descriptions[] from the child's value.
    Shape mirrors ExperienceCardChild.value: { raw_text, items: [{ title, description }] }.
    """
    value = getattr(child, "value", None) or {}
    if not isinstance(value, dict):
        value = {}

    raw_text = value.get("raw_text")
    items = value.get("items") or []

    titles: list[str] = []
    descriptions: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = (it.get("title") or "").strip()
        d = (it.get("description") or "").strip()
        if t:
            titles.append(t)
        if d:
            descriptions.append(d)

    return {
        "raw_text": _compact_text(raw_text, 500) if raw_text else None,
        "titles": titles,
        "descriptions": descriptions,
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
            sim = p.get("similarity")
            start_date = p.get("start_date")
            end_date = p.get("end_date")

            clean_title = title if _should_include(title) else None
            clean_summary = summary if _should_include(summary) else None

            parent_evidence.append({
                "headline": clean_title,
                "summary": truncate_evidence(clean_summary or "", EVIDENCE_SNIPPET_MAX_LEN) or None,
                "company": company,
                "location": location,
                "time": _compact_text(f"{start_date or ''}–{end_date or ''}".strip("–"), 40) or None,
                "skills": [],
                "similarity": round(float(sim), 4) if sim is not None else None,
            })

        # Process children — child_type + titles and descriptions from value.items[]
        child_evidence: list[dict[str, Any]] = []
        for c in children[:2]:
            if isinstance(c, dict):
                raw_titles = c.get("titles") or []
                raw_descriptions = c.get("descriptions") or []
                child_type = _compact_text(c.get("child_type"), 40) or None
            else:
                cf = _child_display_fields(c)
                raw_titles = cf.get("titles") or []
                raw_descriptions = cf.get("descriptions") or []
                child_type = _compact_text(getattr(c, "child_type", None), 40) or None

            titles: list[str] = []
            descriptions: list[str] = []
            for t in raw_titles:
                ct = _compact_text(t, 100)
                if ct and _should_include(ct):
                    titles.append(ct)
            for d in raw_descriptions:
                cd = _compact_text(d, 150)
                if cd and _should_include(cd):
                    descriptions.append(cd)

            if child_type or titles or descriptions:
                child_evidence.append({
                    "child_type": child_type,
                    "titles": titles,
                    "descriptions": descriptions,
                })

        # outcomes: child item titles and descriptions only
        # (parent summary is already in evidence.summary; no child summary field exists)
        outcomes: list[str] = []
        for c in child_evidence:
            for t in (c.get("titles") or []):
                outcomes.append(t)
            for d in (c.get("descriptions") or []):
                outcomes.append(d)
        outcomes = dedupe_strings_preserve_order(outcomes)[:6]

        # domain: broad category from query must.domain list (e.g. "Engineering", "Finance")
        must_domains = (query_context.get("must") or {}).get("domain") or []
        domain = _compact_text(must_domains[0], 80) if must_domains else None

        # Build final compact evidence object
        payload = {
            "person_id": person_id,
            "query_context": query_context,
            "evidence": {
                "headline": parent_evidence[0].get("headline") if parent_evidence else None,
                "summary": parent_evidence[0].get("summary") if parent_evidence else None,
                "domain": domain,
                "outcomes": outcomes,
                "company": parent_evidence[0].get("company") if parent_evidence else None,
                "location": parent_evidence[0].get("location") if parent_evidence else None,
                "time": parent_evidence[0].get("time") if parent_evidence else None,
                "child_evidence": [
                    {
                        "child_type": ce.get("child_type"),
                        "titles": ce.get("titles") or [],
                        "descriptions": ce.get("descriptions") or [],
                    }
                    for ce in child_evidence
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


def _extract_query_terms(query: str) -> set[str]:
    """Extract meaningful query terms for matching (e.g. 'products', 'sold' from 'Sold 100+ products')."""
    if not query or not isinstance(query, str):
        return set()
    words = re.findall(r"\b\w+\b", query.lower())
    stop = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with", "by", "under"}
    return {w for w in words if len(w) >= 2 and w not in stop}


def _company_matches_query(evidence_company: str | None, must_company_norm: list[str]) -> bool:
    """True when evidence company satisfies the query's company filter (e.g. Epic&Focus matches epic & focus)."""
    if not evidence_company or not must_company_norm:
        return False
    company_lower = evidence_company.lower()
    for cn in must_company_norm:
        if not cn:
            continue
        # Split "epic & focus" or "epic, focus" into terms
        terms = re.findall(r"\w+", cn.lower())
        if terms and all(t in company_lower for t in terms):
            return True
    return False


def boost_query_matching_reasons(
    why_matched_by_person: dict[str, list[str]],
    cleaned_payloads: list[dict[str, Any]],
    query_original: str,
) -> dict[str, list[str]]:
    """Ensure at least one reason mentions outcomes or company that directly match query terms.
    When the LLM omits query-relevant evidence (e.g. '200+ products sold' for query 'Sold 100+ products',
    or 'Epic&Focus' for query 'works in Epic&Focus'), prepend the best-matching evidence as the first reason."""
    terms = _extract_query_terms(query_original or "")
    by_person = {str(p.get("person_id") or ""): p for p in (cleaned_payloads or []) if p.get("person_id")}
    out = dict(why_matched_by_person)

    for person_id, reasons in list(out.items()):
        payload = by_person.get(str(person_id))
        if not payload:
            continue
        evidence = payload.get("evidence") or {}
        query_context = payload.get("query_context") or {}
        must_cn = (query_context.get("must") or {}).get("company_norm") or []
        company = evidence.get("company")
        outcomes = evidence.get("outcomes") or []

        # Company boost: when query has company filter and evidence.company matches, ensure it's mentioned
        if must_cn and company and _company_matches_query(company, must_cn):
            reasons_lower = " ".join((r or "").lower() for r in (reasons or []))
            company_lower = company.lower()
            if company_lower not in reasons_lower:
                capped = truncate_evidence(f"Experience at {company}", WHY_REASON_MAX_LEN)
                capped = truncate_reason_to_max_words(capped, WHY_REASON_MAX_WORDS).strip()
                if capped and len(capped) >= 5:
                    existing = [r for r in (reasons or []) if (r or "").lower() != capped.lower()]
                    out[person_id] = [capped] + existing[: WHY_REASON_MAX_ITEMS - 1]
                continue

        if not outcomes:
            continue

        # Find the best outcome by query-term overlap
        best_outcome = None
        best_score = 0
        for o in outcomes:
            o_lower = (str(o) or "").lower()
            score = sum(1 for t in terms if t in o_lower)
            if score > best_score:
                best_score = score
                best_outcome = o

        if best_score < 1 or not best_outcome:
            continue

        # Only skip if the best outcome's own terms are already well-represented in reasons
        best_outcome_lower = best_outcome.lower()
        best_outcome_terms = {t for t in terms if t in best_outcome_lower}
        reasons_lower = " ".join((r or "").lower() for r in (reasons or []))
        if best_outcome_terms and all(t in reasons_lower for t in best_outcome_terms):
            continue

        capped = truncate_evidence(str(best_outcome), WHY_REASON_MAX_LEN)
        capped = truncate_reason_to_max_words(capped, WHY_REASON_MAX_WORDS)
        capped = capped.strip()
        if capped and len(capped) >= 5:
            existing = [r for r in (reasons or []) if (r or "").lower() != capped.lower()]
            new_reasons = [capped] + existing[: WHY_REASON_MAX_ITEMS - 1]
            out[person_id] = new_reasons[:WHY_REASON_MAX_ITEMS]

    return out


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
    must_cn = must.get("company_norm") or []
    ev_company = evidence.get("company")
    if must_cn and ev_company and _company_matches_query(ev_company, must_cn):
        r = _cap_reason(f"Experience at {ev_company}")
        if r and r not in reasons:
            reasons.append(r)
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

    # 5) Child evidence titles and descriptions (if still need more reasons)
    child_evidence_list = evidence.get("child_evidence") or []
    for ce in child_evidence_list[:2]:
        if len(reasons) >= WHY_REASON_MAX_ITEMS:
            break
        for d in (ce.get("descriptions") or [])[:2]:
            if len(reasons) >= WHY_REASON_MAX_ITEMS:
                break
            r = _cap_reason(str(d))
            if r and r not in reasons:
                reasons.append(r)
        for t in (ce.get("titles") or [])[:2]:
            if len(reasons) >= WHY_REASON_MAX_ITEMS:
                break
            r = _cap_reason(str(t))
            if r and r not in reasons:
                reasons.append(r)

    # Final dedupe and return
    return dedupe_strings_preserve_order(reasons)[:WHY_REASON_MAX_ITEMS]
