"""
Single source of truth for the text used to embed experience cards (parents and children).

For parents: build_parent_search_document() derives text from card fields (no stored column).
For children: get_child_search_document() derives text from child.value (items, raw_text).
Used for: vector embedding (semantic search) and full-text search (tsvector).

Callers:
  - embedding: when building inputs for the embedding API
  - pipeline: when persisting new cards (builds from Card; see card_to_*_fields)
"""

from src.db.models import ExperienceCard, ExperienceCardChild
from src.services.experience.child_value import get_child_label


def _format_date_range(card: ExperienceCard) -> str:
    """Format start/end dates for inclusion in search document."""
    if card.start_date and card.end_date:
        return f"{card.start_date} - {card.end_date}"
    if card.start_date:
        return str(card.start_date)
    if card.end_date:
        return str(card.end_date)
    return ""


def build_parent_search_document(card: ExperienceCard) -> str:
    """
    Build the searchable/embedding text for a parent experience card.

    Used for: embedding input and lexical FTS (derived from card fields).
    """
    parts = [
        card.title or "",
        card.normalized_role or "",
        card.domain or "",
        card.sub_domain or "",
        card.company_name or "",
        card.company_type or "",
        card.location or "",
        card.employment_type or "",
        card.summary or "",
        card.raw_text or "",
        card.intent_primary or "",
        " ".join(card.intent_secondary or []),
        card.seniority_level or "",
        _format_date_range(card),
        "current" if card.is_current else "",
    ]
    return " ".join(filter(None, parts))


def build_child_search_document_from_value(label: str | None, value: dict) -> str | None:
    """
    Build the searchable/embedding text for a child card from label and value.
    Value: { raw_text, items[] }.
    """
    if not isinstance(value, dict):
        return None
    parts = [
        label or "",
        str(value.get("raw_text") or ""),
    ]
    items = value.get("items") if isinstance(value.get("items"), list) else []
    for it in items[:20]:
        if isinstance(it, dict):
            parts.append(str(it.get("title") or it.get("subtitle") or ""))
            parts.append(str(it.get("description") or it.get("sub_summary") or ""))
    doc = " ".join(p.strip() for p in parts if p and str(p).strip()).strip()
    return doc or None


def get_child_search_document(child: ExperienceCardChild) -> str:
    """
    Return the search document for a child card (derived from value).
    """
    value = child.value if isinstance(child.value, dict) else {}
    label = get_child_label(value, getattr(child, "child_type", "") or "")
    return (build_child_search_document_from_value(label, value) or "").strip()
