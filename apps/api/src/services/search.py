"""Search service facade.

Business logic is split across:
- search pipeline: src.services.search_logic
- profile/public profile views: src.services.search_profile_view
- contact unlock: src.services.search_contact_unlock
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas import (
    SearchRequest,
    SearchResponse,
    PersonProfileResponse,
    PersonListResponse,
    PersonPublicProfileResponse,
    UnlockContactResponse,
)
from src.services.search_logic import run_search
from src.services.search_profile_view import (
    get_person_profile,
    list_people_for_discover,
    get_public_profile_impl,
)
from src.services.search_contact_unlock import unlock_contact


class SearchService:
    """Facade for search operations."""

    @staticmethod
    async def search(
        db: AsyncSession,
        searcher_id: str,
        body: SearchRequest,
        idempotency_key: str | None,
    ) -> SearchResponse:
        return await run_search(db, searcher_id, body, idempotency_key)

    @staticmethod
    async def get_profile(
        db: AsyncSession,
        searcher_id: str,
        person_id: str,
        search_id: str,
    ) -> PersonProfileResponse:
        return await get_person_profile(db, searcher_id, person_id, search_id)

    @staticmethod
    async def unlock(
        db: AsyncSession,
        searcher_id: str,
        person_id: str,
        search_id: str,
        idempotency_key: str | None,
    ) -> UnlockContactResponse:
        return await unlock_contact(db, searcher_id, person_id, search_id, idempotency_key)

    @staticmethod
    async def list_people(db: AsyncSession) -> PersonListResponse:
        return await list_people_for_discover(db)

    @staticmethod
    async def get_public_profile(db: AsyncSession, person_id: str) -> PersonPublicProfileResponse:
        return await get_public_profile_impl(db, person_id)


search_service = SearchService()
