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
    UnlockedCardsResponse,
    SavedSearchesResponse,
)
from .search_logic import run_search, load_search_more, list_searches, delete_search
from .search_profile_view import (
    get_person_profile,
    list_people_for_discover,
    list_unlocked_cards_for_searcher,
    get_public_profile_impl,
)
from .search_contact_unlock import unlock_contact


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
    async def get_search_more(
        db: AsyncSession,
        searcher_id: str,
        search_id: str,
        offset: int,
        limit: int = 6,
        skip_credits: bool = False,
    ) -> list:
        """Fetch next batch of search results. Returns list of PersonSearchResult. When skip_credits=True (viewing from history), no credit deduction."""
        return await load_search_more(db, searcher_id, search_id, offset, limit, skip_credits)

    @staticmethod
    async def get_profile(
        db: AsyncSession,
        searcher_id: str,
        person_id: str,
        search_id: str | None = None,
    ) -> PersonProfileResponse:
        return await get_person_profile(db, searcher_id, person_id, search_id)

    @staticmethod
    async def unlock(
        db: AsyncSession,
        searcher_id: str,
        person_id: str,
        search_id: str | None,
        idempotency_key: str | None,
    ) -> UnlockContactResponse:
        return await unlock_contact(db, searcher_id, person_id, search_id, idempotency_key)

    @staticmethod
    async def list_people(db: AsyncSession) -> PersonListResponse:
        return await list_people_for_discover(db)

    @staticmethod
    async def list_unlocked_cards(db: AsyncSession, searcher_id: str) -> UnlockedCardsResponse:
        return await list_unlocked_cards_for_searcher(db, searcher_id)

    @staticmethod
    async def list_saved_searches(db: AsyncSession, searcher_id: str) -> SavedSearchesResponse:
        return await list_searches(db, searcher_id)

    @staticmethod
    async def list_search_history(db: AsyncSession, searcher_id: str, limit: int = 50) -> SavedSearchesResponse:
        """Alias for listing search history (kept under SavedSearchesResponse for backward compatibility)."""
        return await list_searches(db, searcher_id, limit=limit)

    @staticmethod
    async def delete_saved_search(db: AsyncSession, searcher_id: str, search_id: str) -> bool:
        """Delete a saved search. Returns True if deleted, False if not found."""
        return await delete_search(db, searcher_id, search_id)

    @staticmethod
    async def get_public_profile(db: AsyncSession, person_id: str) -> PersonPublicProfileResponse:
        return await get_public_profile_impl(db, person_id)


search_service = SearchService()
