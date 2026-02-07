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
    PurchaseCreditsRequest,
    LedgerEntryResponse,
    BioResponse,
    BioCreateUpdate,
    ExperienceCardResponse,
    CardFamilyResponse,
)
from src.domain import PersonSchema, ExperienceCardV1Schema
from src.serializers import experience_card_to_response, experience_card_to_v1_schema, experience_card_child_to_response
from src.services.me import me_service
from src.services.experience_card import experience_card_service

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


@router.get("/profile-v1", response_model=PersonSchema)
async def get_profile_v1(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current user profile in domain v1 schema (Person)."""
    return await me_service.get_profile_v1(db, current_user)


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


@router.post("/credits/purchase", response_model=CreditsResponse)
async def purchase_credits(
    body: PurchaseCreditsRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.purchase_credits(db, current_user.id, body)


@router.get("/credits/ledger", response_model=list[LedgerEntryResponse])
async def get_credits_ledger(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_credits_ledger(db, current_user.id)


@router.get("/experience-cards", response_model=list[ExperienceCardResponse])
async def list_my_experience_cards(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cards = await experience_card_service.list_cards(db, current_user.id)
    return [experience_card_to_response(c) for c in cards]


@router.get("/experience-card-families", response_model=list[CardFamilyResponse])
async def list_my_experience_card_families(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List saved experience cards with their children grouped by parent."""
    families = await experience_card_service.list_card_families(db, current_user.id)
    return [
        CardFamilyResponse(
            parent=experience_card_to_response(parent),
            children=[experience_card_child_to_response(c) for c in children],
        )
        for parent, children in families
    ]


@router.get("/experience-cards-v1", response_model=list[ExperienceCardV1Schema])
async def list_my_experience_cards_v1(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's experience cards in domain v1 schema (Experience Card v1)."""
    cards = await experience_card_service.list_cards(db, current_user.id)
    return [experience_card_to_v1_schema(c) for c in cards]
