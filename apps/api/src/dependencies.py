from typing import Annotated, AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.session import async_session
from src.db.models import Person, ExperienceCard, ExperienceCardChild
from src.auth import decode_access_token
from src.services.experience_card import experience_card_service

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Person:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await db.execute(select(Person).where(Person.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_experience_card_or_404(
    card_id: str,
    current_user: Annotated[Person, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExperienceCard:
    """Load experience card by id for current user or raise 404. Requires route path param card_id."""
    card = await experience_card_service.get_card(db, card_id, current_user.id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )
    return card


async def get_experience_card_child_or_404(
    child_id: str,
    current_user: Annotated[Person, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExperienceCardChild:
    """Load experience card child by id for current user or raise 404. Requires route path param child_id."""
    result = await db.execute(
        select(ExperienceCardChild).where(
            ExperienceCardChild.id == child_id,
            ExperienceCardChild.person_id == current_user.id,
        )
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child card not found",
        )
    return child


