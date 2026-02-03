"""Shared model-to-response serializers."""

from src.db.models import ExperienceCard
from src.schemas import ExperienceCardResponse


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
        created_at=card.created_at,
        updated_at=card.updated_at,
    )
