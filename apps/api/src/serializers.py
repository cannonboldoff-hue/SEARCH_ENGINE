"""Shared model-to-response serializers."""

from typing import TYPE_CHECKING, get_args

from src.db.models import ExperienceCard, ExperienceCardChild, Person
from src.schemas import ExperienceCardResponse, ExperienceCardChildResponse, ChildValueItem
from src.services.experience.child_value import normalize_child_value

if TYPE_CHECKING:
    from src.db.models import PersonProfile
from src.domain import (
    PersonSchema,
    LocationBasic,
    PersonVerification,
    PersonPrivacyDefaults,
    ExperienceCardSchema,
    Intent,
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
        experience_card_visibility=card.experience_card_visibility,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def experience_card_child_to_response(child: ExperienceCardChild) -> ExperienceCardChildResponse:
    """Map ExperienceCardChild model to ExperienceCardChildResponse."""
    raw_value = child.value if isinstance(child.value, dict) else {}
    value_norm = normalize_child_value(raw_value)
    items_raw = (value_norm or {}).get("items") or []
    items = [
        ChildValueItem(title=it.get("title", ""), description=it.get("description"))
        for it in items_raw
        if isinstance(it, dict) and it.get("title")
    ]
    child_type = getattr(child, "child_type", None) or ""

    return ExperienceCardChildResponse(
        id=child.id,
        parent_experience_id=child.parent_experience_id,
        child_type=child_type,
        items=items,
    )


def person_to_person_schema(
    person: Person,
    *,
    profile: "PersonProfile | None" = None,
) -> PersonSchema:
    """Map Person + optional PersonProfile to PersonSchema (domain v1)."""
    from src.db.models import PersonProfile  # avoid circular import

    location = LocationBasic(
        city=profile.current_city if profile else None,
        region=None,
        country=None,
    )
    verification = PersonVerification(status="unverified", methods=[])
    default_visibility = "private"
    if profile:
        if getattr(profile, "open_to_work", False) or getattr(profile, "open_to_contact", False):
            default_visibility = "searchable"
    privacy_defaults = PersonPrivacyDefaults(default_visibility=default_visibility)
    updated = getattr(person, "updated_at", None) or person.created_at
    return PersonSchema(
        person_id=person.id,
        username=person.email or "",
        display_name=person.display_name or "",
        photo_url="/me/bio/photo" if (profile and profile.profile_photo is not None) else None,
        bio=None,
        location=location,
        verification=verification,
        privacy_defaults=privacy_defaults,
        created_at=person.created_at,
        updated_at=updated,
    )


def experience_card_to_schema(card: ExperienceCard) -> ExperienceCardSchema:
    """Map ExperienceCard (parent) to ExperienceCardSchema."""
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
    return ExperienceCardSchema(
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
        time=time,
        location=location,
        roles=roles,
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
