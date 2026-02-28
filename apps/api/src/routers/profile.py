from fastapi import APIRouter, Depends, UploadFile, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person
from src.dependencies import get_current_user, get_db
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
    ExperienceCardResponse,
    CardFamilyResponse,
)
from src.domain import PersonSchema, ExperienceCardSchema
from src.serializers import experience_card_to_response, experience_card_to_schema, experience_card_child_to_response
from src.services.profile import profile_service
from src.services.experience import experience_card_service

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=PersonResponse)
async def get_me(
    current_user: Person = Depends(get_current_user),
):
    return await profile_service.get_current_user(current_user)


@router.patch("", response_model=PersonResponse)
async def patch_me(
    body: PatchProfileRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.patch_current_user(db, current_user, body)


@router.get("/profile-schema", response_model=PersonSchema)
async def get_profile_schema(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current user profile in Person schema."""
    return await profile_service.get_profile_schema(db, current_user)


@router.get("/visibility", response_model=VisibilitySettingsResponse)
async def get_visibility(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.get_visibility(db, current_user.id)


@router.patch("/visibility", response_model=VisibilitySettingsResponse)
async def patch_visibility(
    body: PatchVisibilityRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.patch_visibility(db, current_user.id, body)


@router.get("/bio", response_model=BioResponse)
async def get_bio(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.get_bio(db, current_user)


@router.put("/bio", response_model=BioResponse)
async def put_bio(
    body: BioCreateUpdate,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.put_bio(db, current_user, body)


@router.post("/bio/photo")
async def upload_bio_photo(
    file: UploadFile,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload profile photo; stored in DB. Frontend fetches via GET /me/bio/photo with Bearer auth."""
    await profile_service.upload_profile_photo(db, current_user, file)
    await db.commit()
    return {"profile_photo_url": "/me/bio/photo"}


@router.get("/bio/photo")
async def get_bio_photo(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve profile photo from DB. Requires Bearer auth."""
    photo = await profile_service.get_profile_photo_from_db(db, current_user.id)
    if not photo:
        raise HTTPException(status_code=404, detail="No profile photo")
    content, media_type = photo
    return Response(content=content, media_type=media_type)


@router.get("/credits", response_model=CreditsResponse)
async def get_credits(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.get_credits(db, current_user.id)


@router.post("/credits/purchase", response_model=CreditsResponse)
async def purchase_credits(
    body: PurchaseCreditsRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.purchase_credits(db, current_user.id, body)


@router.get("/credits/ledger", response_model=list[LedgerEntryResponse])
async def get_credits_ledger(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.get_credits_ledger(db, current_user.id)


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


@router.get("/experience-cards-schema", response_model=list[ExperienceCardSchema])
async def list_my_experience_cards_schema(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's experience cards in ExperienceCardSchema."""
    cards = await experience_card_service.list_cards(db, current_user.id)
    return [experience_card_to_schema(c) for c in cards]
