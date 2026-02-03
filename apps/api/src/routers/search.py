from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import Person
from src.dependencies import get_current_user, get_db
from src.schemas import SearchRequest, SearchResponse, PersonProfileResponse, UnlockContactResponse
from src.limiter import limiter
from src.services.search import search_service

router = APIRouter(tags=["search"])
_settings = get_settings()


@router.post("/search", response_model=SearchResponse)
@limiter.limit(_settings.search_rate_limit)
async def search(
    request: Request,
    body: SearchRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.search(db, current_user.id, body, idempotency_key)


@router.get("/people/{person_id}", response_model=PersonProfileResponse)
async def get_person(
    person_id: str,
    search_id: str | None = Query(None),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not search_id:
        raise HTTPException(status_code=400, detail="search_id required to view profile")
    return await search_service.get_profile(db, current_user.id, person_id, search_id)


@router.post("/people/{person_id}/unlock-contact", response_model=UnlockContactResponse)
@limiter.limit(_settings.unlock_rate_limit)
async def unlock_contact(
    request: Request,
    person_id: str,
    search_id: str = Query(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.unlock(db, current_user.id, person_id, search_id, idempotency_key)
