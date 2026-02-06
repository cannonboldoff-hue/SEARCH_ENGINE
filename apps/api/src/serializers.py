"""Shared model-to-response serializers."""

from typing import TYPE_CHECKING, get_args

from src.db.models import ExperienceCard, ExperienceCardChild, Person
from src.schemas import ExperienceCardResponse, ExperienceCardChildResponse

if TYPE_CHECKING:
    from src.db.models import Bio, VisibilitySettings
from src.domain import (
    PersonSchema,
    LocationBasic,
    PersonVerification,
    PersonPrivacyDefaults,
    ExperienceCardV1Schema,
    Intent,
    LanguageField,
    TimeField,
    LocationWithConfidence,
    RoleItem,
    ToolingField,
    PrivacyField,
    QualityField,
    IndexField,
)


def experience_card_to_response(card: ExperienceCard) -> ExperienceCardResponse:
    """Map ExperienceCard model to ExperienceCardResponse."""
    return ExperienceCardResponse(
        id=card.id,
        user_id=card.user_id,
        title=card.title,
        normalized_role=card.normalized_role,
        domain=card.domain,
        sub_domain=card.sub_domain,
        company_name=card.company_name,
        company_type=card.company_type,
        start_date=card.start_date,
        end_date=card.end_date,
        is_current=card.is_current,
        location=card.location,
        employment_type=card.employment_type,
        summary=card.summary,
        raw_text=card.raw_text,
        intent_primary=card.intent_primary,
        intent_secondary=card.intent_secondary or [],
        seniority_level=card.seniority_level,
        confidence_score=card.confidence_score,
        visibility=card.visibility,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def experience_card_child_to_response(child: ExperienceCardChild) -> ExperienceCardChildResponse:
    """Map ExperienceCardChild model to ExperienceCardChildResponse (draft-v1 compatible DTO)."""
    value = child.value if isinstance(child.value, dict) else {}
    time_obj = value.get("time") if isinstance(value.get("time"), dict) else {}
    location_obj = value.get("location") if isinstance(value.get("location"), dict) else {}
    tags = value.get("tags") if isinstance(value.get("tags"), list) else []
    topics = value.get("topics") if isinstance(value.get("topics"), list) else [{"label": t} for t in tags]

    title = child.label or (value.get("headline") if isinstance(value.get("headline"), str) else "") or ""
    summary = (value.get("summary") if isinstance(value.get("summary"), str) else "") or ""

    return ExperienceCardChildResponse(
        id=child.id,
        title=title,
        context=summary,
        tags=[str(t) for t in tags if str(t).strip()],
        headline=title,
        summary=summary,
        topics=topics if isinstance(topics, list) else [],
        time_range=time_obj.get("text"),
        role_title=None,
        company=value.get("company"),
        location=location_obj.get("text"),
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
    """Map ExperienceCard (parent) to ExperienceCardV1Schema (domain v1). Uses stored intent if valid Intent else 'other'."""
    language = LanguageField(raw_text=None, confidence="medium")
    time = TimeField(
        start=card.start_date.isoformat() if card.start_date else None,
        end=card.end_date.isoformat() if card.end_date else None,
        ongoing=card.is_current,
        text=None,
        confidence="medium",
    )
    location = LocationWithConfidence(
        city=None,
        region=None,
        country=None,
        text=card.location,
        confidence="medium",
    )
    roles = []
    if card.normalized_role:
        roles.append(RoleItem(label=card.normalized_role, seniority=card.seniority_level, confidence="medium"))
    topics = []
    privacy = PrivacyField(visibility="profile_only", sensitive=False)
    quality = QualityField(
        overall_confidence="medium",
        claim_state="self_claim",
        needs_clarification=False,
        clarifying_question=None,
    )
    updated = getattr(card, "updated_at", None) or card.created_at
    valid_intents = get_args(Intent)
    intent: Intent = card.intent_primary if (card.intent_primary and card.intent_primary in valid_intents) else "other"
    return ExperienceCardV1Schema(
        id=card.id,
        person_id=card.user_id,
        created_by=card.user_id,
        version=1,
        edited_at=card.updated_at,
        parent_id=None,
        depth=0,
        relation_type=None,
        intent=intent,
        headline=card.title or "",
        summary=(card.summary or "")[:500],
        raw_text=card.raw_text or "",
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
