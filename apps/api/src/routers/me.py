from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person
from src.dependencies import get_current_user, get_db
from src.schemas import (
    PersonResponse,
    PatchMeRequest,
    VisibilitySettingsResponse,
    PatchVisibilityRequest,
    CreditsResponse,
    LedgerEntryResponse,
    BioResponse,
    BioCreateUpdate,
)
from src.services.me import me_service

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=PersonResponse)
async def get_me(
    current_user: Person = Depends(get_current_user),
):
    return await me_service.get_me(current_user)


@router.patch("", response_model=PersonResponse)
async def patch_me(
    body: PatchMeRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.patch_me(db, current_user, body)


@router.get("/visibility", response_model=VisibilitySettingsResponse)
async def get_visibility(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_visibility(db, current_user.id)


@router.patch("/visibility", response_model=VisibilitySettingsResponse)
async def patch_visibility(
    body: PatchVisibilityRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.patch_visibility(db, current_user.id, body)


@router.get("/bio", response_model=BioResponse)
async def get_bio(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_bio(db, current_user)


@router.put("/bio", response_model=BioResponse)
async def put_bio(
    body: BioCreateUpdate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.put_bio(db, current_user, body)


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_credits(db, current_user.id)


@router.get("/credits/ledger", response_model=list[LedgerEntryResponse])
async def get_credits_ledger(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_credits_ledger(db, current_user.id)
