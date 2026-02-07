"""Auth (signup, login) business logic."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core import hash_password, verify_password, create_access_token
from src.db.models import Person, VisibilitySettings, ContactDetails, CreditWallet, CreditLedger
from src.schemas import SignupRequest, LoginRequest, TokenResponse

SIGNUP_CREDITS = 1000


async def signup(db: AsyncSession, body: SignupRequest) -> TokenResponse:
    """Register a new user and return a token. Raises HTTPException if email already registered."""
    result = await db.execute(select(Person).where(Person.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    person = Person(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(person)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    db.add(VisibilitySettings(person_id=person.id))
    db.add(ContactDetails(person_id=person.id))
    wallet = CreditWallet(person_id=person.id, balance=SIGNUP_CREDITS)
    db.add(wallet)
    await db.flush()
    db.add(
        CreditLedger(
            person_id=person.id,
            amount=SIGNUP_CREDITS,
            reason="signup",
            balance_after=SIGNUP_CREDITS,
        )
    )
    await db.refresh(person)
    token = create_access_token(subject=str(person.id))
    return TokenResponse(access_token=token)


async def login(db: AsyncSession, body: LoginRequest) -> TokenResponse:
    """Authenticate and return a token. Raises HTTPException if invalid credentials."""
    result = await db.execute(select(Person).where(Person.email == body.email))
    person = result.scalar_one_or_none()
    if not person or not verify_password(body.password, person.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(subject=str(person.id))
    return TokenResponse(access_token=token)


class AuthService:
    """Facade for auth operations."""

    @staticmethod
    async def signup(db: AsyncSession, body: SignupRequest) -> TokenResponse:
        return await signup(db, body)

    @staticmethod
    async def login(db: AsyncSession, body: LoginRequest) -> TokenResponse:
        return await login(db, body)


auth_service = AuthService()
