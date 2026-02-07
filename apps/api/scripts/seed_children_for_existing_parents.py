"""
Seed multiple child cards (with details) for existing parent experience cards.

Fetches experience cards that have fewer than --max-children children, calls the LLM
to generate 4-6 child cards with detailed value objects, and inserts only new
child_type entries (one child per type per parent by DB constraint).

Requires: OPENAI_API_KEY or CHAT_API_BASE_URL in .env.
Run from apps/api: python scripts/seed_children_for_existing_parents.py [--limit N] [--max-children M] [--delay D]
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.db.session import async_session
from src.db.models import ExperienceCard, ExperienceCardChild
from src.domain import ALLOWED_CHILD_TYPES
from src.providers import get_chat_provider, ChatServiceError, ChatRateLimitError

CHILD_TYPES_STR = ", ".join(ALLOWED_CHILD_TYPES)
DEFAULT_LIMIT = 50
DEFAULT_MAX_CHILDREN = 4
DEFAULT_DELAY_SEC = 2.0


def _repair_json_simple(text: str) -> str:
    text = re.sub(r",(\s*})", r"\1", text)
    text = re.sub(r",(\s*])", r"\1", text)
    return text


def _parse_json_from_llm(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_repair_json_simple(text))
    except json.JSONDecodeError:
        pass
    try:
        import json_repair
        return json_repair.loads(text)
    except Exception:
        pass
    raise json.JSONDecodeError("Invalid JSON", text, 0)


def normalize_child_value(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, str, int, float, bool)):
        return {"value": value}
    return {"value": str(value)}


def _build_children_prompt(
    title: str,
    company_name: str,
    normalized_role: str,
    summary: str,
    existing_child_types: list[str],
) -> str:
    existing_str = ", ".join(existing_child_types) if existing_child_types else "none"
    return f"""Generate 4-6 child cards for this work/education experience. Each child must have a DIFFERENT child_type from: {CHILD_TYPES_STR}. Skip these already present for this experience: {existing_str}.

Experience context:
- title: {title or "(none)"}
- company: {company_name or "(none)"}
- role: {normalized_role or "(none)"}
- summary: {summary or "(none)"}

For each child use a child_type not in the existing list. Each child has: child_type, label (short string), value (JSON object with rich details):
- skills: value with description, level (e.g. expert, advanced).
- tools: value with name, description, optionally category.
- metrics: value with metric, value/result, context.
- achievements: value with description, result, optionally timeframe.
- responsibilities: value with description, scope.
- collaborations: value with who, what, outcome.
- domain_knowledge: value with domain, description, depth.
- exposure: value with area, description, level.
- education: value with institution, degree_or_program, focus.
- certifications: value with name, issuer, year.

Output valid JSON only, no markdown:
{{ "children": [
  {{ "child_type": "skills", "label": "...", "value": {{ "description": "...", "level": "..." }} }},
  {{ "child_type": "tools", "label": "...", "value": {{ "name": "...", "description": "..." }} }}
  ... (4-6 children with different types and detailed value)
] }}"""


async def generate_children_for_parent(
    provider,
    card: ExperienceCard,
    existing_types: set[str],
    temperature: float = 0.8,
) -> list[dict]:
    """Return list of child dicts (child_type, label, value) for types not in existing_types."""
    prompt = _build_children_prompt(
        title=card.title or "",
        company_name=card.company_name or "",
        normalized_role=card.normalized_role or "",
        summary=card.summary or "",
        existing_child_types=sorted(existing_types),
    )
    response = await provider.chat(prompt, max_tokens=4000, temperature=temperature)
    data = _parse_json_from_llm(response)
    children = data.get("children") or []
    out = []
    for c in children:
        if not isinstance(c, dict):
            continue
        ct = (c.get("child_type") or "").strip().lower().replace("-", "_")
        if ct not in ALLOWED_CHILD_TYPES or ct in existing_types:
            continue
        existing_types.add(ct)
        out.append({"child_type": ct, "label": c.get("label") or ct, "value": c.get("value")})
    return out


async def seed_children_for_existing_parents(
    limit: int,
    max_children: int,
    delay_sec: float,
    temperature: float = 0.8,
):
    provider = get_chat_provider()
    async with async_session() as session:
        # Parents that already have >= max_children (we skip these)
        parents_with_enough = (
            select(ExperienceCardChild.parent_experience_id)
            .group_by(ExperienceCardChild.parent_experience_id)
            .having(func.count(ExperienceCardChild.id) >= max_children)
        )
        # Select cards that have fewer than max_children (or zero) children
        result = await session.execute(
            select(ExperienceCard)
            .where(ExperienceCard.id.not_in(parents_with_enough))
            .options(selectinload(ExperienceCard.children))
            .limit(limit)
        )
        cards = result.scalars().unique().all()
        processed = 0
        added_total = 0

        for card in cards:
            existing_types = {ch.child_type for ch in card.children}
            if len(existing_types) >= max_children:
                continue

            try:
                new_children = await generate_children_for_parent(
                    provider, card, set(existing_types), temperature
                )
            except (ChatRateLimitError, ChatServiceError) as e:
                logger.warning("LLM error for card %s: %s", card.id, e)
                if delay_sec > 0:
                    await asyncio.sleep(delay_sec * 2)
                continue
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Parse error for card %s: %s", card.id, e)
                continue

            for ch in new_children:
                session.add(
                    ExperienceCardChild(
                        parent_experience_id=card.id,
                        person_id=card.person_id,
                        child_type=ch["child_type"],
                        label=(ch.get("label") or ch["child_type"])[:255],
                        value=normalize_child_value(ch.get("value")),
                        confidence_score=0.85,
                        search_phrases=[ch.get("label") or ch["child_type"], ch["child_type"]],
                        search_document=str(normalize_child_value(ch.get("value")))[:2000],
                    )
                )
                added_total += 1

            if new_children:
                await session.commit()
                processed += 1
                logger.info(
                    "Card %s (%s): added %s children (total now %s)",
                    card.id,
                    card.title or card.normalized_role,
                    len(new_children),
                    len(existing_types) + len(new_children),
                )

            if delay_sec > 0:
                await asyncio.sleep(delay_sec)

        logger.info("Done. Processed %s parents, added %s child cards.", processed, added_total)


def main():
    parser = argparse.ArgumentParser(
        description="Add multiple child cards with details to existing experience cards."
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Max parent cards to process (default {DEFAULT_LIMIT})")
    parser.add_argument("--max-children", type=int, default=DEFAULT_MAX_CHILDREN,
                        help=f"Only add to parents with fewer than this many children (default {DEFAULT_MAX_CHILDREN})")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SEC,
                        help=f"Seconds between LLM calls (default {DEFAULT_DELAY_SEC})")
    parser.add_argument("--temperature", type=float, default=0.8, help="LLM temperature")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)

    try:
        asyncio.run(
            seed_children_for_existing_parents(
                args.limit,
                args.max_children,
                args.delay,
                args.temperature,
            )
        )
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(0)
    except RuntimeError as e:
        if "not configured" in str(e).lower() or "chat" in str(e).lower():
            logger.error("LLM not configured. Set OPENAI_API_KEY or CHAT_API_BASE_URL in apps/api/.env")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
