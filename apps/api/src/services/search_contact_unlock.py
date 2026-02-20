"""Contact unlock business logic for search results."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import SEARCH_RESULT_EXPIRY_HOURS
from src.db.models import Person, PersonProfile, Search, UnlockContact
from src.schemas import ContactDetailsResponse, UnlockContactResponse
from src.services.credits import (
    get_balance,
    deduct_credits,
    get_idempotent_response,
    save_idempotent_response,
)
from src.services.search_logic import _validate_search_session


def unlock_endpoint(person_id: str) -> str:
    """Idempotency endpoint for unlock-contact."""
    return f"POST /people/{person_id}/unlock-contact"


def _contact_response(p: PersonProfile | None, person: Person | None = None) -> ContactDetailsResponse:
    """Build unlock-contact payload, hiding email when profile marks it private."""
    email_visible = p.email_visible if p else True
    return ContactDetailsResponse(
        email_visible=email_visible,
        email=(person.email if (person and email_visible) else None),
        phone=p.phone if p else None,
        linkedin_url=p.linkedin_url if p else None,
        other=p.other if p else None,
    )


async def unlock_contact(
    db: AsyncSession,
    searcher_id: str,
    person_id: str,
    search_id: str | None,
    idempotency_key: str | None,
) -> UnlockContactResponse:
    """Unlock contact for a person from search results or discover cards."""
    endpoint = unlock_endpoint(person_id)
    if idempotency_key:
        existing = await get_idempotent_response(db, idempotency_key, searcher_id, endpoint)
        if existing and existing.response_body:
            return UnlockContactResponse(**existing.response_body)

    if search_id:
        await _validate_search_session(db, searcher_id, search_id, person_id)

    unlock_stmt = select(UnlockContact).where(
        UnlockContact.searcher_id == searcher_id,
        UnlockContact.target_person_id == person_id,
    )
    if search_id:
        unlock_stmt = unlock_stmt.where(UnlockContact.search_id == search_id)
    else:
        unlock_stmt = unlock_stmt.order_by(UnlockContact.created_at.desc()).limit(1)

    profile_result, person_result, u_result = await asyncio.gather(
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(select(Person).where(Person.id == person_id)),
        db.execute(unlock_stmt),
    )
    profile = profile_result.scalar_one_or_none()
    person = person_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Person profile not found")
    if not (profile.open_to_work or profile.open_to_contact):
        raise HTTPException(status_code=403, detail="Person is not open to contact")

    if u_result.scalar_one_or_none():
        return UnlockContactResponse(unlocked=True, contact=_contact_response(profile, person))

    balance = await get_balance(db, searcher_id)
    if balance < 1:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    unlock_search_id = search_id
    if not unlock_search_id:
        discover_search = Search(
            searcher_id=searcher_id,
            query_text=f"discover_profile:{person_id}",
            parsed_constraints_json=None,
            filters={"source": "discover_profile"},
            extra={"source": "discover_profile"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SEARCH_RESULT_EXPIRY_HOURS),
        )
        db.add(discover_search)
        await db.flush()
        unlock_search_id = discover_search.id

    unlock = UnlockContact(
        searcher_id=searcher_id,
        target_person_id=person_id,
        search_id=unlock_search_id,
    )
    db.add(unlock)
    await db.flush()
    if not await deduct_credits(db, searcher_id, 1, "unlock_contact", "unlock_id", unlock.id):
        raise HTTPException(status_code=402, detail="Insufficient credits")

    resp = UnlockContactResponse(unlocked=True, contact=_contact_response(profile, person))
    if idempotency_key:
        await save_idempotent_response(
            db,
            idempotency_key,
            searcher_id,
            endpoint,
            200,
            resp.model_dump(mode="json"),
        )
    return resp
