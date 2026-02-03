"""Me (profile, visibility, bio, credits, contact) business logic."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Person, VisibilitySettings, CreditWallet, CreditLedger, Bio, ContactDetails
from src.schemas import (
    PersonResponse,
    PatchMeRequest,
    VisibilitySettingsResponse,
    PatchVisibilityRequest,
    CreditsResponse,
    LedgerEntryResponse,
    BioResponse,
    BioCreateUpdate,
    PastCompanyItem,
    ContactDetailsResponse,
    PatchContactRequest,
)


def _past_companies_to_items(past: list | None) -> list[PastCompanyItem]:
    if not past or not isinstance(past, list):
        return []
    return [
        PastCompanyItem(
            company_name=p.get("company_name", ""),
            role=p.get("role"),
            years=p.get("years"),
        )
        for p in past
        if isinstance(p, dict)
    ]


def _person_response(person: Person) -> PersonResponse:
    return PersonResponse(
        id=person.id,
        email=person.email,
        display_name=person.display_name,
        created_at=person.created_at,
    )


async def get_profile(person: Person) -> PersonResponse:
    return _person_response(person)


async def update_profile(db: AsyncSession, person: Person, body: PatchMeRequest) -> PersonResponse:
    if body.display_name is not None:
        person.display_name = body.display_name
    return _person_response(person)


async def get_visibility(db: AsyncSession, person_id: str) -> VisibilitySettingsResponse:
    result = await db.execute(
        select(VisibilitySettings).where(VisibilitySettings.person_id == person_id)
    )
    vis = result.scalar_one_or_none()
    if not vis:
        raise HTTPException(status_code=404, detail="Visibility settings not found")
    return VisibilitySettingsResponse(
        open_to_work=vis.open_to_work,
        work_preferred_locations=vis.work_preferred_locations or [],
        work_preferred_salary_min=vis.work_preferred_salary_min,
        work_preferred_salary_max=vis.work_preferred_salary_max,
        open_to_contact=vis.open_to_contact,
        contact_preferred_salary_min=vis.contact_preferred_salary_min,
        contact_preferred_salary_max=vis.contact_preferred_salary_max,
    )


async def patch_visibility(
    db: AsyncSession,
    person_id: str,
    body: PatchVisibilityRequest,
) -> VisibilitySettingsResponse:
    result = await db.execute(
        select(VisibilitySettings).where(VisibilitySettings.person_id == person_id)
    )
    vis = result.scalar_one_or_none()
    if not vis:
        vis = VisibilitySettings(person_id=person_id)
        db.add(vis)
        await db.flush()
    if body.open_to_work is not None:
        vis.open_to_work = body.open_to_work
    if body.work_preferred_locations is not None:
        vis.work_preferred_locations = body.work_preferred_locations
    if body.work_preferred_salary_min is not None:
        vis.work_preferred_salary_min = body.work_preferred_salary_min
    if body.work_preferred_salary_max is not None:
        vis.work_preferred_salary_max = body.work_preferred_salary_max
    if body.open_to_contact is not None:
        vis.open_to_contact = body.open_to_contact
    if body.contact_preferred_salary_min is not None:
        vis.contact_preferred_salary_min = body.contact_preferred_salary_min
    if body.contact_preferred_salary_max is not None:
        vis.contact_preferred_salary_max = body.contact_preferred_salary_max
    return VisibilitySettingsResponse(
        open_to_work=vis.open_to_work,
        work_preferred_locations=vis.work_preferred_locations or [],
        work_preferred_salary_min=vis.work_preferred_salary_min,
        work_preferred_salary_max=vis.work_preferred_salary_max,
        open_to_contact=vis.open_to_contact,
        contact_preferred_salary_min=vis.contact_preferred_salary_min,
        contact_preferred_salary_max=vis.contact_preferred_salary_max,
    )


async def get_bio_response(db: AsyncSession, person: Person) -> BioResponse:
    result = await db.execute(select(Bio).where(Bio.person_id == person.id))
    bio = result.scalar_one_or_none()
    contact_result = await db.execute(
        select(ContactDetails).where(ContactDetails.person_id == person.id)
    )
    contact = contact_result.scalar_one_or_none()
    past = _past_companies_to_items(bio.past_companies if bio else None)
    complete = bool(
        bio
        and (bio.school or "").strip()
        and (person.email or "").strip()
    )
    return BioResponse(
        first_name=bio.first_name if bio else None,
        last_name=bio.last_name if bio else None,
        date_of_birth=bio.date_of_birth if bio else None,
        current_city=bio.current_city if bio else None,
        profile_photo_url=bio.profile_photo_url if bio else None,
        school=bio.school if bio else None,
        college=bio.college if bio else None,
        current_company=bio.current_company if bio else None,
        past_companies=past,
        email=person.email,
        linkedin_url=contact.linkedin_url if contact else None,
        phone=contact.phone if contact else None,
        complete=complete,
    )


async def update_bio(
    db: AsyncSession,
    person: Person,
    body: BioCreateUpdate,
) -> BioResponse:
    result = await db.execute(select(Bio).where(Bio.person_id == person.id))
    bio = result.scalar_one_or_none()
    if not bio:
        bio = Bio(person_id=person.id)
        db.add(bio)
        await db.flush()
    if body.first_name is not None:
        bio.first_name = body.first_name
    if body.last_name is not None:
        bio.last_name = body.last_name
    if body.date_of_birth is not None:
        bio.date_of_birth = body.date_of_birth
    if body.current_city is not None:
        bio.current_city = body.current_city
    if body.profile_photo_url is not None:
        bio.profile_photo_url = body.profile_photo_url
    if body.school is not None:
        bio.school = body.school
    if body.college is not None:
        bio.college = body.college
    if body.current_company is not None:
        bio.current_company = body.current_company
    if body.past_companies is not None:
        bio.past_companies = [
            {"company_name": p.company_name, "role": p.role, "years": p.years}
            for p in body.past_companies
        ]
    if body.email is not None and body.email.strip():
        person.email = body.email.strip()
        db.add(person)
    if body.first_name is not None or body.last_name is not None:
        parts = [bio.first_name or "", bio.last_name or ""]
        person.display_name = " ".join(parts).strip() or person.display_name
        db.add(person)
    contact_result = await db.execute(
        select(ContactDetails).where(ContactDetails.person_id == person.id)
    )
    contact = contact_result.scalar_one_or_none()
    if body.linkedin_url is not None or body.phone is not None:
        if not contact:
            contact = ContactDetails(person_id=person.id)
            db.add(contact)
            await db.flush()
        if body.linkedin_url is not None:
            contact.linkedin_url = body.linkedin_url
        if body.phone is not None:
            contact.phone = body.phone
    past = _past_companies_to_items(bio.past_companies)
    complete = bool((bio.school or "").strip() and (person.email or "").strip())
    return BioResponse(
        first_name=bio.first_name,
        last_name=bio.last_name,
        date_of_birth=bio.date_of_birth,
        current_city=bio.current_city,
        profile_photo_url=bio.profile_photo_url,
        school=bio.school,
        college=bio.college,
        current_company=bio.current_company,
        past_companies=past,
        email=person.email,
        linkedin_url=contact.linkedin_url if contact else None,
        phone=contact.phone if contact else None,
        complete=complete,
    )


async def get_credits(db: AsyncSession, person_id: str) -> CreditsResponse:
    result = await db.execute(select(CreditWallet).where(CreditWallet.person_id == person_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        return CreditsResponse(balance=0)
    return CreditsResponse(balance=wallet.balance)


async def get_credits_ledger(db: AsyncSession, person_id: str) -> list[LedgerEntryResponse]:
    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.person_id == person_id)
        .order_by(CreditLedger.created_at.desc())
    )
    entries = result.scalars().all()
    return [
        LedgerEntryResponse(
            id=e.id,
            amount=e.amount,
            reason=e.reason,
            reference_type=e.reference_type,
            reference_id=str(e.reference_id) if e.reference_id else None,
            balance_after=e.balance_after,
            created_at=e.created_at,
        )
        for e in entries
    ]


def _contact_response(c: ContactDetails | None) -> ContactDetailsResponse:
    if not c:
        return ContactDetailsResponse(
            email_visible=True,
            phone=None,
            linkedin_url=None,
            other=None,
        )
    return ContactDetailsResponse(
        email_visible=c.email_visible,
        phone=c.phone,
        linkedin_url=c.linkedin_url,
        other=c.other,
    )


async def get_contact_response(db: AsyncSession, person_id: str) -> ContactDetailsResponse:
    result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
    contact = result.scalar_one_or_none()
    return _contact_response(contact)


async def update_contact(
    db: AsyncSession,
    person_id: str,
    body: PatchContactRequest,
) -> ContactDetailsResponse:
    result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == person_id))
    contact = result.scalar_one_or_none()
    if not contact:
        contact = ContactDetails(person_id=person_id)
        db.add(contact)
        await db.flush()
    if body.email_visible is not None:
        contact.email_visible = body.email_visible
    if body.phone is not None:
        contact.phone = body.phone
    if body.linkedin_url is not None:
        contact.linkedin_url = body.linkedin_url
    if body.other is not None:
        contact.other = body.other
    return _contact_response(contact)


class MeService:
    """Facade for me (profile, visibility, bio, credits, contact) operations."""

    @staticmethod
    async def get_me(person: Person) -> PersonResponse:
        return await get_profile(person)

    @staticmethod
    async def patch_me(db: AsyncSession, person: Person, body: PatchMeRequest) -> PersonResponse:
        return await update_profile(db, person, body)

    @staticmethod
    async def get_visibility(db: AsyncSession, person_id: str) -> VisibilitySettingsResponse:
        return await get_visibility(db, person_id)

    @staticmethod
    async def patch_visibility(
        db: AsyncSession,
        person_id: str,
        body: PatchVisibilityRequest,
    ) -> VisibilitySettingsResponse:
        return await patch_visibility(db, person_id, body)

    @staticmethod
    async def get_bio(db: AsyncSession, person: Person) -> BioResponse:
        return await get_bio_response(db, person)

    @staticmethod
    async def put_bio(
        db: AsyncSession,
        person: Person,
        body: BioCreateUpdate,
    ) -> BioResponse:
        return await update_bio(db, person, body)

    @staticmethod
    async def get_credits(db: AsyncSession, person_id: str) -> CreditsResponse:
        return await get_credits(db, person_id)

    @staticmethod
    async def get_credits_ledger(db: AsyncSession, person_id: str) -> list[LedgerEntryResponse]:
        return await get_credits_ledger(db, person_id)

    @staticmethod
    async def get_contact(db: AsyncSession, person_id: str) -> ContactDetailsResponse:
        return await get_contact_response(db, person_id)

    @staticmethod
    async def patch_contact(
        db: AsyncSession,
        person_id: str,
        body: PatchContactRequest,
    ) -> ContactDetailsResponse:
        return await update_contact(db, person_id, body)


me_service = MeService()
