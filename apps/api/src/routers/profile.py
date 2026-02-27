import os

from fastapi import APIRouter, Depends, Request, UploadFile, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import create_photo_token, decode_access_token
from src.core.config import get_settings
from src.db.models import Person
from src.dependencies import get_current_user, get_current_user_optional, get_db
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
from src.domain import PersonSchema, ExperienceCardV1Schema
from src.serializers import experience_card_to_response, experience_card_to_v1_schema, experience_card_child_to_response
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


@router.get("/profile-v1", response_model=PersonSchema)
async def get_profile_v1(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current user profile in domain v1 schema (Person)."""
    return await profile_service.get_profile_v1(db, current_user)


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
    request: Request,
    file: UploadFile,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload profile photo; returns { profile_photo_url } with a signed token so <img> can load it."""
    settings = get_settings()
    base = (
        settings.api_public_url
        or os.environ.get("RENDER_EXTERNAL_URL")
        or str(request.base_url)
    ).rstrip("/")
    token = create_photo_token(str(current_user.id))
    photo_url = f"{base}/me/bio/photo?t={token}"
    await profile_service.upload_profile_photo(db, current_user, file, photo_url)
    await db.commit()
    return {"profile_photo_url": photo_url}


@router.get("/bio/photo")
async def get_bio_photo(
    request: Request,
    current_user: Person | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Serve profile photo from DB. Use ?t=TOKEN (from upload response) for <img>; otherwise requires auth."""
    person_id: str | None = None
    t = request.query_params.get("t")
    if t:
        person_id = decode_access_token(t)
    if not person_id and current_user:
        person_id = current_user.id
    if not person_id:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    photo = await profile_service.get_profile_photo_from_db(db, person_id)
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


@router.get("/experience-cards-v1", response_model=list[ExperienceCardV1Schema])
async def list_my_experience_cards_v1(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List current user's experience cards in domain v1 schema (Experience Card v1)."""
    cards = await experience_card_service.list_cards(db, current_user.id)
    return [experience_card_to_v1_schema(c) for c in cards]
