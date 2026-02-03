from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Person
from src.dependencies import get_current_user, get_db
from src.schemas import ContactDetailsResponse, PatchContactRequest
from src.services.me import me_service

router = APIRouter(prefix="/me", tags=["contact"])


@router.get("/contact", response_model=ContactDetailsResponse)
async def get_contact(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.get_contact(db, current_user.id)


@router.patch("/contact", response_model=ContactDetailsResponse)
async def patch_contact(
    body: PatchContactRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await me_service.patch_contact(db, current_user.id, body)
