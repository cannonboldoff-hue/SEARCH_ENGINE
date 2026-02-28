"""Profile (visibility, bio, credits, contact) business logic."""

from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.db.models import Person, PersonProfile, CreditLedger
from src.services.credits import add_credits as add_credits_to_wallet
from src.serializers import person_to_person_schema
from src.domain import PersonSchema
from src.schemas import (
    PersonResponse,
    PatchProfileRequest,
    VisibilitySettingsResponse,
    PatchVisibilityRequest,
    CreditsResponse,
    PurchaseCreditsRequest,
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


async def _get_profile_schema_response(db: AsyncSession, person: Person) -> PersonSchema:
    """Return current user as PersonSchema."""
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person.id))
    profile = result.scalar_one_or_none()
    return person_to_person_schema(person, profile=profile)


async def update_profile(db: AsyncSession, person: Person, body: PatchProfileRequest) -> PersonResponse:
    if body.display_name is not None:
        person.display_name = body.display_name
    return _person_response(person)


async def _get_visibility(db: AsyncSession, person_id: str) -> VisibilitySettingsResponse:
    result = await db.execute(
        select(PersonProfile).where(PersonProfile.person_id == person_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return VisibilitySettingsResponse(
        open_to_work=profile.open_to_work,
        work_preferred_locations=profile.work_preferred_locations or [],
        work_preferred_salary_min=profile.work_preferred_salary_min,
        open_to_contact=profile.open_to_contact,
    )


async def _patch_visibility(
    db: AsyncSession,
    person_id: str,
    body: PatchVisibilityRequest,
) -> VisibilitySettingsResponse:
    result = await db.execute(
        select(PersonProfile).where(PersonProfile.person_id == person_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = PersonProfile(person_id=person_id)
        db.add(profile)
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent request created the profile; re-load it.
            await db.rollback()
            result = await db.execute(
                select(PersonProfile).where(PersonProfile.person_id == person_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                raise
    if body.open_to_work is not None:
        profile.open_to_work = body.open_to_work
    if body.work_preferred_locations is not None:
        profile.work_preferred_locations = body.work_preferred_locations
    if body.work_preferred_salary_min is not None:
        profile.work_preferred_salary_min = body.work_preferred_salary_min
    if body.open_to_contact is not None:
        profile.open_to_contact = body.open_to_contact
    return VisibilitySettingsResponse(
        open_to_work=profile.open_to_work,
        work_preferred_locations=profile.work_preferred_locations or [],
        work_preferred_salary_min=profile.work_preferred_salary_min,
        open_to_contact=profile.open_to_contact,
    )


async def upload_profile_photo(
    db: AsyncSession,
    person: Person,
    file: UploadFile,
) -> None:
    """Save uploaded image to DB (profile_photo, profile_photo_media_type)."""
    allowed = ("image/jpeg", "image/png", "image/gif", "image/webp")
    media_type = (file.content_type or "").strip().lower()
    if media_type and media_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, or WebP images are allowed")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="Image must be under 5MB")
    if not media_type:
        media_type = "image/jpeg"
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = PersonProfile(person_id=person.id)
        db.add(profile)
        await db.flush()
    profile.profile_photo = content
    profile.profile_photo_media_type = media_type
    profile.profile_photo_url = "/me/bio/photo"  # Sentinel: blob exists, frontend fetches with Bearer


async def get_profile_photo_from_db(
    db: AsyncSession,
    person_id: str,
) -> tuple[bytes, str] | None:
    """Return (image_bytes, media_type) for the profile photo if stored in DB, else None."""
    result = await db.execute(
        select(PersonProfile.profile_photo, PersonProfile.profile_photo_media_type).where(
            PersonProfile.person_id == person_id
        )
    )
    row = result.one_or_none()
    if not row or row[0] is None:
        return None
    media_type = (row[1] or "image/jpeg").strip() or "image/jpeg"
    return (bytes(row[0]), media_type)


async def get_bio_response(db: AsyncSession, person: Person) -> BioResponse:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person.id))
    profile = result.scalar_one_or_none()
    past = _past_companies_to_items(profile.past_companies if profile else None)
    complete = bool(
        profile
        and (profile.school or "").strip()
        and (person.email or "").strip()
    )
    has_photo = profile is not None and profile.profile_photo is not None
    return BioResponse(
        first_name=profile.first_name if profile else None,
        last_name=profile.last_name if profile else None,
        date_of_birth=profile.date_of_birth if profile else None,
        current_city=profile.current_city if profile else None,
        profile_photo_url="/me/bio/photo" if has_photo else None,
        school=profile.school if profile else None,
        college=profile.college if profile else None,
        current_company=profile.current_company if profile else None,
        past_companies=past,
        email=person.email,
        linkedin_url=profile.linkedin_url if profile else None,
        phone=profile.phone if profile else None,
        complete=complete,
    )


async def update_bio(
    db: AsyncSession,
    person: Person,
    body: BioCreateUpdate,
) -> BioResponse:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = PersonProfile(person_id=person.id)
        db.add(profile)
        await db.flush()
    if body.first_name is not None:
        profile.first_name = body.first_name
    if body.last_name is not None:
        profile.last_name = body.last_name
    if body.date_of_birth is not None:
        profile.date_of_birth = body.date_of_birth
    if body.current_city is not None:
        profile.current_city = body.current_city
    # profile_photo_url in body is ignored; upload sets it via /me/bio/photo endpoint
    if body.school is not None:
        profile.school = body.school
    if body.college is not None:
        profile.college = body.college
    if body.current_company is not None:
        profile.current_company = body.current_company
    if body.past_companies is not None:
        profile.past_companies = [
            {"company_name": p.company_name, "role": p.role, "years": p.years}
            for p in body.past_companies
        ]
    if body.email is not None and body.email.strip():
        new_email = body.email.strip()
        if new_email != person.email:
            existing = await db.execute(
                select(Person).where(Person.email == new_email, Person.id != person.id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")
            person.email = new_email
            db.add(person)
    if body.first_name is not None or body.last_name is not None:
        parts = [profile.first_name or "", profile.last_name or ""]
        person.display_name = " ".join(parts).strip() or person.display_name
        db.add(person)
    if body.linkedin_url is not None:
        profile.linkedin_url = body.linkedin_url
    if body.phone is not None:
        profile.phone = body.phone
    past = _past_companies_to_items(profile.past_companies)
    complete = bool((profile.school or "").strip() and (person.email or "").strip())
    has_photo = profile.profile_photo is not None
    return BioResponse(
        first_name=profile.first_name,
        last_name=profile.last_name,
        date_of_birth=profile.date_of_birth,
        current_city=profile.current_city,
        profile_photo_url="/me/bio/photo" if has_photo else None,
        school=profile.school,
        college=profile.college,
        current_company=profile.current_company,
        past_companies=past,
        email=person.email,
        linkedin_url=profile.linkedin_url,
        phone=profile.phone,
        complete=complete,
    )


async def _get_credits(db: AsyncSession, person_id: str) -> CreditsResponse:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return CreditsResponse(balance=0)
    return CreditsResponse(balance=profile.balance)


async def _purchase_credits(
    db: AsyncSession,
    person_id: str,
    body: PurchaseCreditsRequest,
) -> CreditsResponse:
    if body.credits < 1:
        raise HTTPException(status_code=400, detail="credits must be at least 1")
    if body.credits > 100_000:
        raise HTTPException(status_code=400, detail="credits per purchase limited to 100,000")
    new_balance = await add_credits_to_wallet(db, person_id, body.credits, reason="purchase")
    return CreditsResponse(balance=new_balance)


async def _get_credits_ledger(db: AsyncSession, person_id: str) -> list[LedgerEntryResponse]:
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


def _contact_response(p: PersonProfile | None) -> ContactDetailsResponse:
    if not p:
        return ContactDetailsResponse(
            email_visible=True,
            phone=None,
            linkedin_url=None,
            other=None,
        )
    return ContactDetailsResponse(
        email_visible=p.email_visible,
        phone=p.phone,
        linkedin_url=p.linkedin_url,
        other=p.other,
    )


async def get_contact_response(db: AsyncSession, person_id: str) -> ContactDetailsResponse:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id))
    profile = result.scalar_one_or_none()
    return _contact_response(profile)


async def update_contact(
    db: AsyncSession,
    person_id: str,
    body: PatchContactRequest,
) -> ContactDetailsResponse:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = PersonProfile(person_id=person_id)
        db.add(profile)
        await db.flush()
    if body.email_visible is not None:
        profile.email_visible = body.email_visible
    if body.phone is not None:
        profile.phone = body.phone
    if body.linkedin_url is not None:
        profile.linkedin_url = body.linkedin_url
    if body.other is not None:
        profile.other = body.other
    return _contact_response(profile)


class ProfileService:
    """Facade for profile (visibility, bio, credits, contact) operations."""

    @staticmethod
    async def get_current_user(person: Person) -> PersonResponse:
        return await get_profile(person)

    @staticmethod
    async def get_profile_schema(db: AsyncSession, person: Person) -> PersonSchema:
        return await _get_profile_schema_response(db, person)

    @staticmethod
    async def patch_current_user(db: AsyncSession, person: Person, body: PatchProfileRequest) -> PersonResponse:
        return await update_profile(db, person, body)

    @staticmethod
    async def get_visibility(db: AsyncSession, person_id: str) -> VisibilitySettingsResponse:
        return await _get_visibility(db, person_id)

    @staticmethod
    async def patch_visibility(
        db: AsyncSession,
        person_id: str,
        body: PatchVisibilityRequest,
    ) -> VisibilitySettingsResponse:
        return await _patch_visibility(db, person_id, body)

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

    upload_profile_photo = staticmethod(upload_profile_photo)
    get_profile_photo_from_db = staticmethod(get_profile_photo_from_db)

    @staticmethod
    async def get_credits(db: AsyncSession, person_id: str) -> CreditsResponse:
        return await _get_credits(db, person_id)

    @staticmethod
    async def purchase_credits(
        db: AsyncSession,
        person_id: str,
        body: PurchaseCreditsRequest,
    ) -> CreditsResponse:
        return await _purchase_credits(db, person_id, body)

    @staticmethod
    async def get_credits_ledger(db: AsyncSession, person_id: str) -> list[LedgerEntryResponse]:
        return await _get_credits_ledger(db, person_id)

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


profile_service = ProfileService()
