"""
Lightweight validate/normalize step for live search parsing pipeline.

Runs after LLM cleanup → single extract. Deterministic post-processor that:
- Moves weak constraints from MUST → SHOULD (to avoid killing recall)
- Normalizes company/team/keyword tokens (strip, lowercase, dedupe)
- Enforces date formats (YYYY-MM-DD) and salary conversion to ₹/year
- Dedupes all list fields
- Enforces intent_primary enum (drops invalid values)
"""

import re
from datetime import datetime
from typing import Optional, get_args

from src.domain import Intent
from src.schemas.search import (
    ParsedConstraintsPayload,
    ParsedConstraintsMust,
    ParsedConstraintsShould,
    ParsedConstraintsExclude,
)

# Allow at most this many MUST list items before demoting rest to SHOULD (recall protection)
MAX_MUST_INTENT_PRIMARY = 2
MAX_MUST_COMPANY_NORM = 3
MAX_MUST_TEAM_NORM = 3
MAX_MUST_DOMAIN = 2
# Confidence below this: demote softer MUST lists (domain, sub_domain) to SHOULD
WEAK_CONFIDENCE_THRESHOLD = 0.5
MIN_ALLOWED_YEAR = 1900
# Allow near-future dates to avoid dropping valid in-progress ranges.
MAX_ALLOWED_YEAR_OFFSET = 1

_VALID_INTENT_PRIMARY = frozenset(get_args(Intent))


def _str_strip_or_none(s: Optional[str]) -> Optional[str]:
    if s is None or not isinstance(s, str):
        return s
    t = s.strip()
    return t if t else None


def _dedupe_list(items: list[str], normalize: bool = False) -> list[str]:
    """Dedupe preserving order. If normalize, strip and lowercase for key."""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if not s:
            continue
        key = s.lower() if normalize else s
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _normalize_date(s: Optional[str]) -> Optional[str]:
    """Return YYYY-MM-DD if parseable, else None. Accepts YYYY-MM-DD, YYYY-MM."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    max_year = datetime.utcnow().year + MAX_ALLOWED_YEAR_OFFSET
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.year < MIN_ALLOWED_YEAR or dt.year > max_year:
                return None
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Try year only
    if re.match(r"^\d{4}$", s):
        year = int(s)
        if year < MIN_ALLOWED_YEAR or year > max_year:
            return None
        return f"{s}-01-01"
    return None


def _normalize_salary_to_per_year(
    value: Optional[float],
    *,
    hint_per_month: bool = False,
) -> Optional[float]:
    """
    Ensure salary is in ₹/year. If hint_per_month or value looks like monthly (< 200_000),
    multiply by 12. Clamp to non-negative.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    # Heuristic: values < 200k are likely per-month (e.g. 50k/month)
    if hint_per_month or (v > 0 and v < 200_000):
        v = v * 12
    return v


def validate_and_normalize(payload: ParsedConstraintsPayload) -> ParsedConstraintsPayload:
    """
    Lightweight validate/normalize step for parsed search constraints.
    Call after ParsedConstraintsPayload.from_llm_dict(filters_raw).
    """
    must = payload.must
    should = payload.should
    exclude = payload.exclude
    confidence = max(0.0, min(1.0, payload.confidence_score))

    # ---- Dedupe and normalize list fields ----
    company_norm = _dedupe_list(list(must.company_norm or []), normalize=True)
    team_norm = _dedupe_list(list(must.team_norm or []), normalize=True)
    intent_primary_raw = list(must.intent_primary or [])
    intent_primary_valid = [x for x in intent_primary_raw if isinstance(x, str) and x.strip().lower() in _VALID_INTENT_PRIMARY]
    intent_primary = _dedupe_list([s.strip() for s in intent_primary_valid], normalize=True)
    domain = _dedupe_list(list(must.domain or []), normalize=False)
    sub_domain = _dedupe_list(list(must.sub_domain or []), normalize=False)
    employment_type = _dedupe_list(list(must.employment_type or []), normalize=False)
    seniority_level = _dedupe_list(list(must.seniority_level or []), normalize=False)

    # ---- Move weak constraints MUST → SHOULD ----
    # Intent: keep at most MAX_MUST_INTENT_PRIMARY in must; rest go to intent_secondary
    intent_to_must = intent_primary[:MAX_MUST_INTENT_PRIMARY]
    intent_to_should = intent_primary[MAX_MUST_INTENT_PRIMARY:]
    should_intent_secondary = _dedupe_list(
        list(should.intent_secondary or []) + intent_to_should,
        normalize=True,
    )

    # Company: keep at most MAX_MUST_COMPANY_NORM; rest as keywords for semantic boost
    company_to_must = company_norm[:MAX_MUST_COMPANY_NORM]
    company_to_should = company_norm[MAX_MUST_COMPANY_NORM:]
    should_keywords = _dedupe_list(
        list(should.keywords or []) + company_to_should,
        normalize=True,
    )

    # Team: keep at most MAX_MUST_TEAM_NORM; rest to keywords
    team_to_must = team_norm[:MAX_MUST_TEAM_NORM]
    team_to_should = team_norm[MAX_MUST_TEAM_NORM:]
    should_keywords = _dedupe_list(should_keywords + team_to_should, normalize=True)

    # Low confidence: demote domain/sub_domain from MUST to SHOULD (keywords)
    if confidence < WEAK_CONFIDENCE_THRESHOLD:
        domain_to_should = domain[MAX_MUST_DOMAIN:] if len(domain) > MAX_MUST_DOMAIN else []
        domain = domain[:MAX_MUST_DOMAIN]
        should_keywords = _dedupe_list(should_keywords + domain_to_should + list(sub_domain), normalize=True)
        sub_domain = []
    else:
        domain = domain[:MAX_MUST_DOMAIN]
        sub_domain = sub_domain[:2]

    # ---- Dates ----
    time_start = _normalize_date(must.time_start)
    time_end = _normalize_date(must.time_end)
    if time_start and time_end and time_start > time_end:
        time_start, time_end = time_end, time_start

    # ---- Salary: ensure ₹/year ----
    offer_salary = _normalize_salary_to_per_year(must.offer_salary_inr_per_year)

    # ---- Exclude: normalize and dedupe ----
    exclude_company = _dedupe_list(list(exclude.company_norm or []), normalize=True)
    exclude_keywords = _dedupe_list(list(exclude.keywords or []), normalize=True)

    # ---- Should: skills_or_tools and keywords dedupe ----
    skills_or_tools = _dedupe_list(list(should.skills_or_tools or []), normalize=True)
    search_phrases = _dedupe_list(list(payload.search_phrases or []), normalize=False)

    new_must = ParsedConstraintsMust(
        company_norm=company_to_must,
        team_norm=team_to_must,
        intent_primary=intent_to_must,
        domain=domain,
        sub_domain=sub_domain,
        employment_type=employment_type,
        seniority_level=seniority_level,
        location_text=_str_strip_or_none(must.location_text),
        city=_str_strip_or_none(must.city),
        country=_str_strip_or_none(must.country),
        time_start=time_start,
        time_end=time_end,
        is_current=must.is_current,
        open_to_work_only=must.open_to_work_only,
        offer_salary_inr_per_year=offer_salary,
    )
    new_should = ParsedConstraintsShould(
        skills_or_tools=skills_or_tools,
        keywords=should_keywords,
        intent_secondary=should_intent_secondary,
    )
    new_exclude = ParsedConstraintsExclude(
        company_norm=exclude_company,
        keywords=exclude_keywords,
    )

    return ParsedConstraintsPayload(
        query_original=payload.query_original or "",
        query_cleaned=payload.query_cleaned or "",
        must=new_must,
        should=new_should,
        exclude=new_exclude,
        search_phrases=search_phrases,
        query_embedding_text=(payload.query_embedding_text or "").strip(),
        confidence_score=confidence,
    )
