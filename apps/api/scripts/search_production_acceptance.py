"""
Acceptance checks for run_search production correctness fixes.

Covers:
A) concurrent idempotency requests charge exactly one credit
B) rollback safety when an exception happens after deduct_credits
C) run_search does not use asyncio.gather() with the same AsyncSession
D) lexical bonus is restricted to vector candidate person_ids (Option B)

Run:
  cd apps/api && uv run python scripts/search_production_acceptance.py
"""

import asyncio
import inspect
import logging
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

_app_api = Path(__file__).resolve().parent.parent
if str(_app_api) not in sys.path:
    sys.path.insert(0, str(_app_api))

from fastapi import HTTPException
from sqlalchemy import select

from src.db.models import Person, PersonProfile
from src.db.session import async_session
from src.schemas import SearchRequest
from src.services.credits import get_balance
from src.services.search import run_search
import src.services.search as search_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CANDIDATE_QUERIES = [
    "software engineer",
    "quant strategy worked for 30 days then failed, wrote postmortem",
    "vendor ops reduced delays 4 days to 2 days",
    "pune 2024 python whatsapp order tracker deployed 6 shops",
]


async def _pick_searcher_id(min_balance: int = 20) -> str | None:
    async with async_session() as db:
        result = await db.execute(
            select(Person.id)
            .join(PersonProfile, PersonProfile.person_id == Person.id)
            .where(PersonProfile.balance >= min_balance)
            .limit(1)
        )
        row = result.first()
        return str(row[0]) if row else None


async def _run_once(searcher_id: str, query: str, idempotency_key: str | None):
    async with async_session() as db:
        try:
            resp = await run_search(db, searcher_id, SearchRequest(query=query), idempotency_key)
            await db.commit()
            return ("ok", resp)
        except HTTPException as e:
            await db.rollback()
            return ("http", e.status_code, str(e.detail))
        except Exception as e:
            await db.rollback()
            return ("err", repr(e))


async def _pick_query_with_results(searcher_id: str) -> str | None:
    for q in CANDIDATE_QUERIES:
        status = await _run_once(searcher_id, q, None)
        if status[0] == "ok" and status[1].people:
            return q
    return None


async def _balance(searcher_id: str) -> int:
    async with async_session() as db:
        return await get_balance(db, searcher_id)


async def test_a_concurrent_idempotency(searcher_id: str, query: str) -> tuple[bool, str]:
    before = await _balance(searcher_id)
    key = f"search-prod-{uuid.uuid4()}"

    r1, r2 = await asyncio.gather(
        _run_once(searcher_id, query, key),
        _run_once(searcher_id, query, key),
    )

    after = await _balance(searcher_id)
    charged = before - after

    if any(r[0] == "err" for r in (r1, r2)):
        return False, f"unexpected error responses: {r1}, {r2}"

    ok_count = sum(1 for r in (r1, r2) if r[0] == "ok")
    in_progress_count = sum(1 for r in (r1, r2) if r[0] == "http" and r[1] == 409)
    if ok_count < 1:
        return False, f"expected at least one successful response, got: {r1}, {r2}"
    if charged != 1:
        return False, f"expected exactly one credit charged, got delta={charged} for responses: {r1}, {r2}"
    if ok_count == 1 and in_progress_count == 0:
        return False, f"second request should be 409 in-progress or stored 200, got: {r1}, {r2}"

    return True, f"charged={charged}, responses={r1[0]}/{r2[0]}"


async def test_b_rollback_after_deduct(searcher_id: str, query: str) -> tuple[bool, str]:
    before = await _balance(searcher_id)
    async with async_session() as db:
        try:
            with patch("src.services.search.SearchResult", side_effect=RuntimeError("forced insert failure")):
                await run_search(db, searcher_id, SearchRequest(query=query), None)
            await db.rollback()
            return False, "expected RuntimeError but run_search succeeded"
        except RuntimeError:
            await db.rollback()
        except HTTPException as e:
            await db.rollback()
            return False, f"unexpected HTTPException: {e.status_code} {e.detail}"
        except Exception as e:
            await db.rollback()
            return False, f"unexpected exception type: {repr(e)}"

    after = await _balance(searcher_id)
    if after != before:
        return False, f"balance changed despite rollback (before={before}, after={after})"
    return True, f"balance unchanged at {after}"


def test_c_no_gather_in_run_search() -> tuple[bool, str]:
    src = inspect.getsource(search_service.run_search)
    if "asyncio.gather" in src:
        return False, "run_search still contains asyncio.gather"
    return True, "run_search has no asyncio.gather"


def test_d_lexical_restricted_to_vector_candidates() -> tuple[bool, str]:
    src = inspect.getsource(search_service.run_search)
    expected_snippet = "for pid in all_person_ids if pid in lexical_scores"
    if expected_snippet not in src:
        return False, "did not find lexical filtering to all_person_ids"
    return True, "lexical scores filtered to all_person_ids"


async def main() -> None:
    searcher_id = await _pick_searcher_id()
    if not searcher_id:
        logger.error("No searcher with sufficient balance found; cannot run integration checks A/B.")
        sys.exit(1)

    query = await _pick_query_with_results(searcher_id)
    if not query:
        logger.error("Could not find a query that returns non-empty results; cannot run A/B reliably.")
        sys.exit(1)

    passed = 0
    failed = 0

    ok, msg = await test_a_concurrent_idempotency(searcher_id, query)
    if ok:
        logger.info("PASS A: %s", msg)
        passed += 1
    else:
        logger.error("FAIL A: %s", msg)
        failed += 1

    ok, msg = await test_b_rollback_after_deduct(searcher_id, query)
    if ok:
        logger.info("PASS B: %s", msg)
        passed += 1
    else:
        logger.error("FAIL B: %s", msg)
        failed += 1

    ok, msg = test_c_no_gather_in_run_search()
    if ok:
        logger.info("PASS C: %s", msg)
        passed += 1
    else:
        logger.error("FAIL C: %s", msg)
        failed += 1

    ok, msg = test_d_lexical_restricted_to_vector_candidates()
    if ok:
        logger.info("PASS D: %s", msg)
        passed += 1
    else:
        logger.error("FAIL D: %s", msg)
        failed += 1

    logger.info("Acceptance complete: passed=%s failed=%s", passed, failed)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
