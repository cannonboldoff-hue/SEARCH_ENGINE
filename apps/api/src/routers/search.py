from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import get_settings, limiter
from src.db.models import Person
from src.dependencies import get_current_user, get_db
from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonSearchResult,
    PersonProfileResponse,
    PersonListResponse,
    PersonPublicProfileResponse,
    UnlockContactRequest,
    UnlockContactResponse,
    UnlockedCardsResponse,
    SavedSearchesResponse,
)
from src.services.search import search_service

router = APIRouter(tags=["search"])
_settings = get_settings()


@router.get("/people", response_model=PersonListResponse)
async def list_people(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List people for discover grid: name, location, top 5 experience titles."""
    return await search_service.list_people(db)


@router.get("/me/searches", response_model=SavedSearchesResponse)
async def list_saved_searches(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max number of searches to return (newest first)"),
):
    """List search history for the current user with result counts."""
    return await search_service.list_search_history(db, current_user.id, limit=limit)


@router.get("/me/unlocked-cards", response_model=UnlockedCardsResponse)
async def list_unlocked_cards(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all unique people whose contact details were unlocked by current user."""
    return await search_service.list_unlocked_cards(db, current_user.id)


@router.get("/people/{person_id}/profile", response_model=PersonPublicProfileResponse)
async def get_person_public_profile(
    person_id: str,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Public profile for person detail page: full bio + all experience card families (parent → children)."""
    return await search_service.get_public_profile(db, person_id)


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


class SearchMoreResponse(BaseModel):
    people: list[PersonSearchResult]


@router.get("/search/{search_id}/more", response_model=SearchMoreResponse)
async def search_more(
    search_id: str,
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(6, ge=1, le=24, description="Number of results to return (max 24 for viewing saved search history)"),
    history: bool = Query(False, description="When true, viewing from saved history - no credit deduction"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch more search results. Use offset=6 for second page, offset=12 for third, etc. When history=true, no credits are charged (results already unlocked)."""
    people = await search_service.get_search_more(
        db, current_user.id, search_id, offset=offset, limit=limit, skip_credits=history
    )
    return SearchMoreResponse(people=people)


@router.get("/people/{person_id}", response_model=PersonProfileResponse)
async def get_person(
    person_id: str,
    search_id: str | None = Query(None),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.get_profile(db, current_user.id, person_id, search_id)


@router.post("/people/{person_id}/unlock-contact", response_model=UnlockContactResponse)
@limiter.limit(_settings.unlock_rate_limit)
async def unlock_contact(
    request: Request,
    person_id: str,
    body: UnlockContactRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await search_service.unlock(db, current_user.id, person_id, body.search_id, idempotency_key)
