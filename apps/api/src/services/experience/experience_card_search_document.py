"""
Single source of truth for the text used to embed experience cards (parents and children).

This "search document" is stored on ExperienceCard.search_document and
ExperienceCardChild.search_document, and is used for:
  - Vector embedding (semantic search)
  - Full-text search (tsvector)

Callers:
  - experience_card_embedding: when building inputs for the embedding API
  - experience_card: when applying patches (to keep search_document in sync)
  - experience_card_pipeline: when persisting new cards (builds from V1Card; see card_to_*_fields)
"""

from src.db.models import ExperienceCard, ExperienceCardChild


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

    Used when: re-embedding after patch, or when card.search_document is not set.
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
    Build the searchable/embedding text for a child card from its label and value dict.

    Used when: re-embedding after patch (child.value is the dimension container).
    Returns None if the resulting text would be empty.
    """
    if not isinstance(value, dict):
        return None
    time_text = None
    if isinstance(value.get("time"), dict):
        time_text = value["time"].get("text")
    location_text = None
    if isinstance(value.get("location"), dict):
        location_text = value["location"].get("text")
    tags = value.get("tags") if isinstance(value.get("tags"), list) else []
    tags_str = " ".join(str(t).strip() for t in tags[:10] if str(t).strip())
    parts = [
        label or "",
        str(value.get("headline") or ""),
        str(value.get("summary") or ""),
        str(value.get("company") or ""),
        str(location_text or ""),
        str(time_text or ""),
        tags_str,
    ]
    doc = " ".join(p.strip() for p in parts if p and str(p).strip()).strip()
    return doc or None


def get_child_search_document(child: ExperienceCardChild) -> str:
    """
    Return the search document for a child card (stored or derived from value).
    """
    stored = (child.search_document or "").strip()
    if stored:
        return stored
    value = child.value if isinstance(child.value, dict) else {}
    return (build_child_search_document_from_value(child.label, value) or "").strip()
