"""Prompt for LLM-generated search match explanations.

Uses a grounded, domain-agnostic prompt that forces compression (not copying),
dedupes parent/child overlap, and forbids raw labels/prose. Output is strict JSON only.
"""

import json
from typing import Any


def get_why_matched_prompt(
    query_original: str,
    query_cleaned: str,
    must: dict[str, Any],
    should: dict[str, Any],
    people_evidence: list[dict[str, Any]],
) -> str:
    """Build prompt for why_matched explanation. Expects people_evidence to be
    the cleaned payload from build_match_explanation_payload (compact, deduped)."""
    query_context = {
        "query_original": query_original or "",
        "query_cleaned": query_cleaned or query_original or "",
        "must": must or {},
        "should": should or {},
    }
    # Send only person_id + evidence per person to reduce tokens
    people_payload = [
        {"person_id": p.get("person_id"), "evidence": p.get("evidence") or {}}
        for p in (people_evidence or [])
    ]
    payload = {"query_context": query_context, "people": people_payload}
    payload_json = json.dumps(payload, ensure_ascii=True)

    return f"""You are a grounded match-explanation engine.

TASK
Generate short, clear reasons explaining why each person matched a search query.

You MUST use only the evidence provided in the input.
You MUST compress and summarize noisy evidence into clean reasons.
Do NOT copy raw labels/headlines verbatim when they are repetitive, duplicated, or poorly formatted.

OUTPUT (STRICT)
Return ONLY valid JSON with this exact schema:
{
  "people": [
    {
      "person_id": "string",
      "why_matched": ["string", "string", "string"]
    }
  ]
}

GLOBAL RULES (STRICT)
1) Return 1-3 reasons per person.
2) Each reason must be <= 150 characters.
3) Each reason must be a clean human-readable phrase/sentence fragment.
4) Do NOT invent facts not present in the input.
5) Do NOT include markdown, bullet symbols, comments, or prose outside JSON.
6) Do NOT include field names (e.g., "headline:", "summary:", "skills:") in the output.
7) Do NOT copy long raw text; summarize it.
8) Do NOT repeat the same fact across multiple reasons.
9) If evidence is weak/noisy, return 1 cautious reason using only clearly supported facts.

EVIDENCE STRUCTURE
Each person has:
- Parent evidence: headline, summary, company, location, time
- child_evidence[]: each child has child_type ("metrics", "achievements", "tools", "skills", "responsibilities", etc.), titles[], descriptions[]
- outcomes[]: parent summaries + all child item titles + descriptions

Use child_type to interpret content: skills/tools child types contain skill names; metrics/achievements contain outcomes; etc.

WHAT TO PRIORITIZE IN REASONS
Prefer the strongest overlaps with the query, in this order:
1) Hard constraints / explicit filters (role, company, team, location, time, availability, salary)
2) Skills, tools, methods (from child_evidence where child_type is "skills" or "tools")
3) Domain / type of work
4) Outcomes, metrics, achievements (from child_evidence where child_type is "metrics" or "achievements", or from outcomes[])
5) Supporting context (from child_evidence titles/descriptions)

QUERY-RELEVANCE RULES (CRITICAL)
- When the query contains specific terms (e.g., "products sold", "100+ products", "revenue", "sales"), you MUST prefer outcomes that directly match those terms.
- Example: Query "Sold 100+ products under 3 months" + evidence ["₹15 lakh sales", "Efficiency boost", "200+ products sold"] → prefer "200+ products sold" or "Sold 200+ products in 2 months" because they directly match "products sold"; do NOT lead with "₹15 lakh sales" or "Efficiency boost".
- Among multiple outcomes/metrics, rank by overlap with query keywords: the more query terms an outcome contains, the higher it should appear in reasons.

DEDUPLICATION RULES
- If the same concept appears in parent and child evidence, mention it only once.
- If labels/headlines repeat words (e.g., "Sales Manager Sales Manager"), rewrite cleanly.
- Ignore duplicate or near-duplicate evidence snippets.

NORMALIZATION RULES
- Prefer normalized facts when both raw + normalized forms exist.
- Keep currency/metrics concise (e.g., "₹15L sales in 2 months").
- Keep time/location concise (e.g., "Mumbai", "3 years", "2022-2024").
- If multiple facts are available, choose the most search-relevant ones.

STYLE RULES
- Be specific, not generic.
- Good: "Quant research in crypto using Python and backtesting"
- Good: "Mumbai studio partnerships with ₹15L sales in 2 months"
- Good: "Ops + automation work with vendor/process ownership"
- Bad: "Why this card was shown: ..."
- Bad: "Sales Manager Sales Manager..."
- Bad: "Matched because of experience"

ROBUSTNESS RULES
- Some evidence may be incomplete, duplicated, or noisy.
- Some fields may be missing.
- Some people may match mostly via parent evidence, others via child evidence.
Handle all cases gracefully and still return valid JSON.

INPUT JSON
{payload_json}
"""