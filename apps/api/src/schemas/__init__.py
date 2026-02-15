"""Pydantic request/response schemas. Re-exported for backward compatibility."""

from src.schemas.auth import SignupRequest, LoginRequest, TokenResponse
from src.schemas.profile import (
    PersonResponse,
    PatchProfileRequest,
    VisibilitySettingsResponse,
    PatchVisibilityRequest,
)
from src.schemas.bio import PastCompanyItem, BioResponse, BioCreateUpdate
from src.schemas.contact import ContactDetailsResponse, PatchContactRequest
from src.schemas.credits import CreditsResponse, PurchaseCreditsRequest, LedgerEntryResponse
from src.schemas.builder import (
    RawExperienceCreate,
    RawExperienceResponse,
    RewriteTextResponse,
    TranslateTextResponse,
    CardFamilyV1Response,
    DraftSetV1Response,
    FillFromTextRequest,
    FillFromTextResponse,
    CommitDraftSetRequest,
    ExperienceCardCreate,
    ExperienceCardPatch,
    ExperienceCardResponse,
    ExperienceCardChildPatch,
    ExperienceCardChildResponse,
    CardFamilyResponse,
)
from src.schemas.search import (
    SearchRequest,
    PersonSearchResult,
    SearchResponse,
    PersonProfileResponse,
    UnlockContactRequest,
    UnlockContactResponse,
)
from src.schemas.discover import (
    PersonListItem,
    PersonListResponse,
    PersonPublicProfileResponse,
)

__all__ = [
    "SignupRequest",
    "LoginRequest",
    "TokenResponse",
    "PersonResponse",
    "PatchProfileRequest",
    "VisibilitySettingsResponse",
    "PatchVisibilityRequest",
    "PastCompanyItem",
    "BioResponse",
    "BioCreateUpdate",
    "ContactDetailsResponse",
    "PatchContactRequest",
    "CreditsResponse",
    "PurchaseCreditsRequest",
    "LedgerEntryResponse",
    "RawExperienceCreate",
    "RawExperienceResponse",
    "RewriteTextResponse",
    "TranslateTextResponse",
    "CardFamilyV1Response",
    "DraftSetV1Response",
    "FillFromTextRequest",
    "FillFromTextResponse",
    "CommitDraftSetRequest",
    "ExperienceCardCreate",
    "ExperienceCardPatch",
    "ExperienceCardResponse",
    "ExperienceCardChildPatch",
    "ExperienceCardChildResponse",
    "CardFamilyResponse",
    "SearchRequest",
    "PersonSearchResult",
    "SearchResponse",
    "PersonProfileResponse",
    "UnlockContactRequest",
    "UnlockContactResponse",
    "PersonListItem",
    "PersonListResponse",
    "PersonPublicProfileResponse",
]
