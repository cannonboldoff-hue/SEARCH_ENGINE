"""Shared model-to-response serializers."""

from typing import TYPE_CHECKING

from src.db.models import ExperienceCard, Person
from src.schemas import ExperienceCardResponse

if TYPE_CHECKING:
    from src.db.models import Bio, VisibilitySettings
from src.domain_schemas import (
    PersonSchema,
    LocationBasic,
    PersonVerification,
    PersonPrivacyDefaults,
    ExperienceCardV1Schema,
    LanguageField,
    TimeField,
    LocationWithConfidence,
    RoleItem,
    TopicItem,
    ToolingField,
    PrivacyField,
    QualityField,
    IndexField,
)


def experience_card_to_response(card: ExperienceCard) -> ExperienceCardResponse:
    """Map ExperienceCard model to ExperienceCardResponse."""
    return ExperienceCardResponse(
        id=card.id,
        person_id=card.person_id,
        raw_experience_id=card.raw_experience_id,
        status=card.status,
        human_edited=getattr(card, "human_edited", False),
        locked=getattr(card, "locked", False),
        title=card.title,
        context=card.context,
        constraints=card.constraints,
        decisions=card.decisions,
        outcome=card.outcome,
        tags=card.tags or [],
        company=card.company,
        team=card.team,
        role_title=card.role_title,
        time_range=card.time_range,
        location=card.location,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def person_to_person_schema(
    person: Person,
    *,
    bio: "Bio | None" = None,
    visibility_settings: "VisibilitySettings | None" = None,
) -> PersonSchema:
    """Map Person + optional Bio + optional VisibilitySettings to PersonSchema (domain v1)."""
    from src.db.models import Bio, VisibilitySettings  # avoid circular import

    location = LocationBasic(
        city=bio.current_city if bio else None,
        region=None,
        country=None,
    )
    verification = PersonVerification(status="unverified", methods=[])
    default_visibility = "private"
    if visibility_settings:
        if getattr(visibility_settings, "open_to_work", False) or getattr(
            visibility_settings, "open_to_contact", False
        ):
            default_visibility = "searchable"
    privacy_defaults = PersonPrivacyDefaults(default_visibility=default_visibility)
    updated = getattr(person, "updated_at", None) or person.created_at
    return PersonSchema(
        person_id=person.id,
        username=person.email or "",
        display_name=person.display_name or "",
        photo_url=bio.profile_photo_url if bio else None,
        bio=None,
        location=location,
        verification=verification,
        privacy_defaults=privacy_defaults,
        created_at=person.created_at,
        updated_at=updated,
    )


def experience_card_to_v1_schema(card: ExperienceCard) -> ExperienceCardV1Schema:
    """Map ExperienceCard model to ExperienceCardV1Schema (domain v1). Fills defaults for missing fields."""
    language = LanguageField(raw_text=None, confidence="medium")
    time = TimeField(
        start=None,
        end=None,
        ongoing=None,
        text=card.time_range,
        confidence="medium",
    )
    location = LocationWithConfidence(
        city=card.location,
        region=None,
        country=None,
        text=card.location,
        confidence="medium",
    )
    roles = []
    if card.role_title:
        roles.append(RoleItem(label=card.role_title, seniority=None, confidence="medium"))
    topics = [TopicItem(label=t, raw=None, confidence="medium") for t in (card.tags or [])]
    privacy = PrivacyField(visibility="profile_only", sensitive=False)
    quality = QualityField(
        overall_confidence="medium",
        claim_state="self_claim",
        needs_clarification=False,
        clarifying_question=None,
    )
    updated = getattr(card, "updated_at", None) or card.created_at
    return ExperienceCardV1Schema(
        id=card.id,
        person_id=card.person_id,
        created_by=card.person_id,
        version=1,
        edited_at=card.updated_at,
        parent_id=None,
        depth=0,
        relation_type=None,
        intent="other",
        headline=card.title or "",
        summary=(card.context or "")[:500] or (card.outcome or "")[:500] or "",
        raw_text=card.context or card.outcome or "",
        language=language,
        time=time,
        location=location,
        roles=roles,
        actions=[],
        topics=topics,
        entities=[],
        tooling=ToolingField(),
        outcomes=[],
        evidence=[],
        privacy=privacy,
        quality=quality,
        index=IndexField(),
        created_at=card.created_at,
        updated_at=updated,
    )
