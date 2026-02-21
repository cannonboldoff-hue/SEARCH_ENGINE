"""Profile view business logic for search results and public people pages."""

import asyncio

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person, PersonProfile, ExperienceCard, ExperienceCardChild, UnlockContact
from src.schemas import (
    PersonProfileResponse,
    PersonListItem,
    PersonListResponse,
    PersonPublicProfileResponse,
    UnlockedCardItem,
    UnlockedCardsResponse,
    CardFamilyResponse,
    BioResponse,
    ContactDetailsResponse,
    PastCompanyItem,
)
from src.serializers import experience_card_to_response
from .search_logic import _validate_search_session, _card_families_from_parents_and_children


async def get_person_profile(
    db: AsyncSession,
    searcher_id: str,
    person_id: str,
    search_id: str | None = None,
) -> PersonProfileResponse:
    """Load profile for person view; validate search context only when search_id is provided."""
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

    p_result, profile_result, cards_result, unlock_result = await asyncio.gather(
        db.execute(select(Person).where(Person.id == person_id)),
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(
            select(ExperienceCard).where(
                ExperienceCard.user_id == person_id,
                ExperienceCard.experience_card_visibility == True,
            ).order_by(ExperienceCard.created_at.desc())
        ),
        db.execute(unlock_stmt),
    )
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    profile = profile_result.scalar_one_or_none()
    cards = cards_result.scalars().all()

    contact = None
    open_to_work = profile.open_to_work if profile else False
    open_to_contact = profile.open_to_contact if profile else False
    if (open_to_work or open_to_contact) and unlock_result.scalar_one_or_none() and profile:
        contact = ContactDetailsResponse(
            email_visible=profile.email_visible,
            email=person.email if profile.email_visible else None,
            phone=profile.phone,
            linkedin_url=profile.linkedin_url,
            other=profile.other,
        )

    if open_to_work and profile:
        locs = profile.work_preferred_locations or []
        sal_min = profile.work_preferred_salary_min
    else:
        locs = []
        sal_min = None

    bio_resp = _bio_response_for_public(person, profile)
    card_families: list[CardFamilyResponse] = []
    if cards:
        children_result = await db.execute(
            select(ExperienceCardChild).where(
                ExperienceCardChild.parent_experience_id.in_([c.id for c in cards])
            )
        )
        children_list = children_result.scalars().all()
        card_families = _card_families_from_parents_and_children(cards, children_list)

    return PersonProfileResponse(
        id=person.id,
        display_name=person.display_name,
        open_to_work=open_to_work,
        open_to_contact=open_to_contact,
        work_preferred_locations=locs,
        work_preferred_salary_min=sal_min,
        experience_cards=[experience_card_to_response(c) for c in cards],
        card_families=card_families,
        bio=bio_resp,
        contact=contact,
    )


async def list_people_for_discover(db: AsyncSession) -> PersonListResponse:
    """List people who have at least one visible experience card."""
    subq = (
        select(ExperienceCard.person_id)
        .where(ExperienceCard.experience_card_visibility == True)
        .distinct()
    )
    people_ids_result = await db.execute(select(Person.id).where(Person.id.in_(subq)))
    person_ids = [str(r[0]) for r in people_ids_result.all()]
    if not person_ids:
        return PersonListResponse(people=[])

    async def get_people():
        r = await db.execute(select(Person).where(Person.id.in_(person_ids)))
        return {str(p.id): p for p in r.scalars().all()}

    async def get_profiles():
        r = await db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(person_ids)))
        return {str(p.person_id): p for p in r.scalars().all()}

    async def get_card_summaries():
        r = await db.execute(
            select(ExperienceCard.person_id, ExperienceCard.summary, ExperienceCard.created_at)
            .where(
                ExperienceCard.person_id.in_(person_ids),
                ExperienceCard.experience_card_visibility == True,
            )
            .order_by(ExperienceCard.person_id, ExperienceCard.created_at.desc())
        )
        return r.all()

    people, profiles, card_rows = await asyncio.gather(get_people(), get_profiles(), get_card_summaries())

    summaries_by_person: dict[str, list[str]] = {pid: [] for pid in person_ids}
    for row in card_rows:
        pid = str(row.person_id)
        if len(summaries_by_person[pid]) >= 5:
            continue
        summary = (row.summary or "").strip()
        if summary:
            summaries_by_person[pid].append(summary)

    people_list = [
        PersonListItem(
            id=pid,
            display_name=p.display_name,
            current_location=profiles[pid].current_city if pid in profiles else None,
            experience_summaries=summaries_by_person.get(pid, [])[:5],
        )
        for pid, p in people.items()
    ]
    return PersonListResponse(people=people_list)


async def list_unlocked_cards_for_searcher(
    db: AsyncSession,
    searcher_id: str,
) -> UnlockedCardsResponse:
    """List unique people unlocked by the searcher (latest unlock first)."""
    unlocks_result = await db.execute(
        select(UnlockContact)
        .where(UnlockContact.searcher_id == searcher_id)
        .order_by(UnlockContact.created_at.desc())
    )
    unlocks = unlocks_result.scalars().all()
    if not unlocks:
        return UnlockedCardsResponse(cards=[])

    unique_unlocks: list[UnlockContact] = []
    seen_person_ids: set[str] = set()
    for unlock in unlocks:
        person_id = str(unlock.target_person_id)
        if person_id in seen_person_ids:
            continue
        seen_person_ids.add(person_id)
        unique_unlocks.append(unlock)

    person_ids = [str(unlock.target_person_id) for unlock in unique_unlocks]

    async def get_people():
        result = await db.execute(select(Person).where(Person.id.in_(person_ids)))
        return {str(person.id): person for person in result.scalars().all()}

    async def get_profiles():
        result = await db.execute(select(PersonProfile).where(PersonProfile.person_id.in_(person_ids)))
        return {str(profile.person_id): profile for profile in result.scalars().all()}

    async def get_card_summaries():
        result = await db.execute(
            select(ExperienceCard.person_id, ExperienceCard.summary, ExperienceCard.created_at)
            .where(
                ExperienceCard.person_id.in_(person_ids),
                ExperienceCard.experience_card_visibility == True,
            )
            .order_by(ExperienceCard.person_id, ExperienceCard.created_at.desc())
        )
        return result.all()

    people_by_id, profiles_by_id, card_rows = await asyncio.gather(
        get_people(),
        get_profiles(),
        get_card_summaries(),
    )

    summaries_by_person: dict[str, list[str]] = {person_id: [] for person_id in person_ids}
    for row in card_rows:
        row_person_id = str(row.person_id)
        if len(summaries_by_person[row_person_id]) >= 5:
            continue
        summary = (row.summary or "").strip()
        if summary:
            summaries_by_person[row_person_id].append(summary)

    cards: list[UnlockedCardItem] = []
    for unlock in unique_unlocks:
        person_id = str(unlock.target_person_id)
        person = people_by_id.get(person_id)
        if not person:
            continue
        profile = profiles_by_id.get(person_id)
        cards.append(
            UnlockedCardItem(
                person_id=person_id,
                search_id=str(unlock.search_id),
                display_name=person.display_name,
                current_location=profile.current_city if profile else None,
                open_to_work=bool(profile.open_to_work) if profile else False,
                open_to_contact=bool(profile.open_to_contact) if profile else False,
                experience_summaries=summaries_by_person.get(person_id, [])[:5],
                unlocked_at=unlock.created_at,
            )
        )

    return UnlockedCardsResponse(cards=cards)


def _bio_response_for_public(person: Person, profile: PersonProfile | None) -> BioResponse:
    """Build BioResponse for public profile."""
    past: list[PastCompanyItem] = []
    if profile and profile.past_companies:
        for p in profile.past_companies:
            if isinstance(p, dict):
                past.append(
                    PastCompanyItem(
                        company_name=p.get("company_name", "") or "",
                        role=p.get("role"),
                        years=p.get("years"),
                    )
                )

    return BioResponse(
        first_name=profile.first_name if profile else None,
        last_name=profile.last_name if profile else None,
        date_of_birth=profile.date_of_birth if profile else None,
        current_city=profile.current_city if profile else None,
        profile_photo_url=profile.profile_photo_url if profile else None,
        school=profile.school if profile else None,
        college=profile.college if profile else None,
        current_company=profile.current_company if profile else None,
        past_companies=past or None,
        email=None,
        linkedin_url=profile.linkedin_url if profile else None,
        phone=profile.phone if profile else None,
        complete=bool(profile and (profile.school or "").strip() and (person.email or "").strip()),
    )


async def get_public_profile_impl(db: AsyncSession, person_id: str) -> PersonPublicProfileResponse:
    """Load public profile: full bio plus visible experience card families."""
    p_result = await db.execute(select(Person).where(Person.id == person_id))
    person = p_result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    profile_result, cards_result = await asyncio.gather(
        db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id)),
        db.execute(
            select(ExperienceCard).where(
                ExperienceCard.user_id == person_id,
                ExperienceCard.experience_card_visibility == True,
            ).order_by(ExperienceCard.created_at.desc())
        ),
    )
    profile = profile_result.scalar_one_or_none()
    bio_resp = _bio_response_for_public(person, profile)
    parents = cards_result.scalars().all()
    if not parents:
        return PersonPublicProfileResponse(
            id=person.id,
            display_name=person.display_name,
            bio=bio_resp,
            card_families=[],
        )

    children_result = await db.execute(
        select(ExperienceCardChild).where(
            ExperienceCardChild.parent_experience_id.in_([c.id for c in parents])
        )
    )
    children_list = children_result.scalars().all()
    card_families = _card_families_from_parents_and_children(parents, children_list)
    return PersonPublicProfileResponse(
        id=person.id,
        display_name=person.display_name,
        bio=bio_resp,
        card_families=card_families,
    )
