"""
Child card value schema and normalization.

Canonical child value shape:
  {
    "raw_text": "string|null",
    "items": [
      { "title": "string", "description": "string|null" }
    ]
  }

Helpers: normalize_child_items, dedupe_child_items, normalize_child_value.
"""

from __future__ import annotations

from typing import Any


def _trim(s: Any) -> str | None:
    """Return trimmed string or None if empty."""
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def normalize_child_items(items: Any) -> list[dict]:
    """
    Normalize and clean items array. Each item must have title.
    - Drop items with missing/empty title
    - description may be null
    - Trim whitespace
    - Backward compat: subtitle → title, sub_summary → description
    """
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Prefer new keys; fall back to old keys for backward compat
        title = _trim(
            item.get("title")
            or item.get("subtitle")
            or item.get("label")
            or item.get("text")
        )
        if not title:
            continue
        description = _trim(
            item.get("description")
            or item.get("sub_summary")
            or item.get("summary")
        )
        out.append({
            "title": title,
            "description": description,
        })
    return out


def dedupe_child_items(items: list[dict]) -> list[dict]:
    """
    Deduplicate items by (title, description) pair.
    Keeps first occurrence.
    """
    seen: set[tuple[str, str | None]] = set()
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        description = item.get("description")
        description_norm = (description or "").strip() or None
        key = (title, description_norm)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def normalize_child_value(value: Any) -> dict | None:
    """
    Normalize child value to canonical shape { raw_text, items[] }.
    Returns None if no items and no raw_text.
    """
    if value is None or not isinstance(value, dict):
        return None

    items_raw = value.get("items")
    items = dedupe_child_items(normalize_child_items(items_raw)) if isinstance(items_raw, list) else []

    raw_text = _trim(value.get("raw_text"))

    # If no items and no raw_text, drop child
    if not items and not raw_text:
        return None

    return {
        "raw_text": raw_text,
        "items": items,
    }


def merge_child_items(a: list[dict], b: list[dict]) -> list[dict]:
    """Merge two item lists and dedupe. Preserves order (a first, then b)."""
    combined = list(a) + list(b)
    return dedupe_child_items(normalize_child_items(combined))


def is_child_value_empty(value: Any) -> bool:
    """True if value has no meaningful content (no items, no raw_text)."""
    norm = normalize_child_value(value)
    return norm is None or (not norm.get("items") and not norm.get("raw_text"))


def get_child_label(value: Any, child_type: str = "") -> str:
    """
    Derive display label/title from child value.
    Uses: first item title, legacy value.headline (migration 028 backfill), or child_type.
    """
    if not isinstance(value, dict):
        return child_type or ""
    items = value.get("items")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        t = _trim(items[0].get("title") or items[0].get("subtitle"))
        if t:
            return t
    # Legacy: migration 028 backfilled label into value.headline for rows with no items
    headline = _trim(value.get("headline"))
    if headline:
        return headline
    return child_type or ""
