from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Person, VisibilitySettings, CreditWallet, CreditLedger
from src.dependencies import get_current_user, get_db
from src.schemas import (
    PersonResponse,
    PatchMeRequest,
    VisibilitySettingsResponse,
    PatchVisibilityRequest,
    CreditsResponse,
    LedgerEntryResponse,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=PersonResponse)
async def get_me(
    current_user: Person = Depends(get_current_user),
):
    return PersonResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at,
    )


@router.patch("", response_model=PersonResponse)
async def patch_me(
    body: PatchMeRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return PersonResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=current_user.created_at,
    )


@router.get("/visibility", response_model=VisibilitySettingsResponse)
async def get_visibility(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VisibilitySettings).where(VisibilitySettings.person_id == current_user.id)
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


@router.patch("/visibility", response_model=VisibilitySettingsResponse)
async def patch_visibility(
    body: PatchVisibilityRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VisibilitySettings).where(VisibilitySettings.person_id == current_user.id)
    )
    vis = result.scalar_one_or_none()
    if not vis:
        vis = VisibilitySettings(person_id=current_user.id)
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
    await db.commit()
    await db.refresh(vis)
    return VisibilitySettingsResponse(
        open_to_work=vis.open_to_work,
        work_preferred_locations=vis.work_preferred_locations or [],
        work_preferred_salary_min=vis.work_preferred_salary_min,
        work_preferred_salary_max=vis.work_preferred_salary_max,
        open_to_contact=vis.open_to_contact,
        contact_preferred_salary_min=vis.contact_preferred_salary_min,
        contact_preferred_salary_max=vis.contact_preferred_salary_max,
    )


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CreditWallet).where(CreditWallet.person_id == current_user.id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        return CreditsResponse(balance=1000)
    return CreditsResponse(balance=wallet.balance)


@router.get("/credits/ledger", response_model=list[LedgerEntryResponse])
async def get_credits_ledger(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditLedger).where(CreditLedger.person_id == current_user.id).order_by(CreditLedger.created_at.desc())
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
