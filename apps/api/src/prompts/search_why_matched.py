"""Prompt for LLM-generated search match explanations."""

import json
from typing import Any


def get_why_matched_prompt(
    query_original: str,
    query_cleaned: str,
    must: dict[str, Any],
    should: dict[str, Any],
    people_evidence: list[dict[str, Any]],
) -> str:
    payload = {
        "query_original": query_original or "",
        "query_cleaned": query_cleaned or query_original or "",
        "must": must or {},
        "should": should or {},
        "people": people_evidence or [],
    }
    payload_json = json.dumps(payload, ensure_ascii=True)
    return f"""You are a search result explanation engine.

Task:
- Explain why each person was shown for the query.
- Use only the provided evidence.

Return ONLY valid JSON with this exact schema:
{{
  "people": [
    {{
      "person_id": "string",
      "why_matched": ["string", "string", "string"]
    }}
  ]
}}

Rules:
1) Keep each reason short (max 120 chars).
2) Return 1-3 reasons per person.
3) Mention concrete overlap with query constraints when possible (skills, domain, company, time, location, availability).
4) Do not invent facts not present in input.
5) Do not include markdown, bullets, or prose outside JSON.

Input JSON:
{payload_json}
"""
