"""Auth (signup, login) business logic."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from src.core import hash_password, verify_password, create_access_token, get_settings
from src.db.models import Person, PersonProfile, CreditLedger
from src.providers import get_email_provider, EmailConfigError, EmailServiceError
from src.schemas import (
    SignupRequest,
    SignupResponse,
    LoginRequest,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)

logger = logging.getLogger(__name__)

SIGNUP_CREDITS = 1000


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _send_verification_email(db: AsyncSession, person: Person) -> None:
    try:
        provider = get_email_provider()
    except EmailConfigError:
        logger.info("Email verification skipped; SendGrid not configured.")
        return

    settings = get_settings()
    token = str(secrets.randbelow(1_000_000)).zfill(6)
    now = datetime.now(timezone.utc)
    person.email_verification_token_hash = _hash_token(token)
    person.email_verification_expires_at = now + timedelta(minutes=settings.email_verify_expire_minutes)
    await db.flush()

    lines = [
        "Verify your email for CONXA.",
        f"Verification code: {token}",
        f"This code expires in {settings.email_verify_expire_minutes} minutes.",
    ]
    lines.append("If you did not request this, you can ignore this email.")
    text = "\n\n".join(lines)

    try:
        await provider.send_email(person.email, "Verify your email", text)
    except EmailServiceError:
        person.email_verification_token_hash = None
        person.email_verification_expires_at = None
        logger.warning("Failed to send verification email for person %s", person.id)


async def signup(db: AsyncSession, body: SignupRequest) -> SignupResponse:
    """Create a user account with email + password."""
    email = _normalize_email(body.email)
    display_name = body.display_name.strip() if body.display_name else None
    display_name = display_name or None

    existing = await db.execute(select(Person.id).where(func.lower(Person.email) == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    person = Person(
        email=email,
        hashed_password=hash_password(body.password),
        display_name=display_name,
    )
    db.add(person)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    db.add(PersonProfile(person_id=person.id, balance=SIGNUP_CREDITS))
    await db.flush()
    db.add(
        CreditLedger(
            person_id=person.id,
            amount=SIGNUP_CREDITS,
            reason="signup",
            balance_after=SIGNUP_CREDITS,
        )
    )
    await _send_verification_email(db, person)

    settings = get_settings()
    if settings.email_verification_required:
        return SignupResponse(email_verification_required=True)

    token = create_access_token(subject=str(person.id))
    return SignupResponse(
        access_token=token,
        email_verification_required=False,
    )


async def login(db: AsyncSession, body: LoginRequest) -> TokenResponse:
    """Authenticate and return a token. Raises HTTPException if invalid credentials."""
    email = _normalize_email(body.email)
    result = await db.execute(select(Person).where(func.lower(Person.email) == email))
    person = result.scalar_one_or_none()
    if not person or not verify_password(body.password, person.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    settings = get_settings()
    if settings.email_verification_required and not person.email_verified_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")
    token = create_access_token(subject=str(person.id))
    return TokenResponse(access_token=token)


async def verify_email(db: AsyncSession, body: VerifyEmailRequest) -> VerifyEmailResponse:
    email = _normalize_email(body.email)
    result = await db.execute(select(Person).where(func.lower(Person.email) == email))
    person = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not person:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
    if person.email_verified_at:
        return VerifyEmailResponse(verified=True)
    if not person.email_verification_token_hash or not person.email_verification_expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification code")
    if person.email_verification_expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one.",
        )
    if _hash_token(body.token) != person.email_verification_token_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please check and try again.",
        )

    person.email_verified_at = now
    person.email_verification_token_hash = None
    person.email_verification_expires_at = None
    return VerifyEmailResponse(verified=True)


async def resend_verification_email(db: AsyncSession, body: ResendVerificationRequest) -> ResendVerificationResponse:
    email = _normalize_email(body.email)
    result = await db.execute(select(Person).where(func.lower(Person.email) == email))
    person = result.scalar_one_or_none()

    if not person or person.email_verified_at:
        return ResendVerificationResponse(sent=True)

    await _send_verification_email(db, person)
    return ResendVerificationResponse(sent=True)


class AuthService:
    """Facade for auth operations."""

    @staticmethod
    async def signup(db: AsyncSession, body: SignupRequest) -> SignupResponse:
        return await signup(db, body)

    @staticmethod
    async def login(db: AsyncSession, body: LoginRequest) -> TokenResponse:
        return await login(db, body)

    @staticmethod
    async def verify_email(db: AsyncSession, body: VerifyEmailRequest) -> VerifyEmailResponse:
        return await verify_email(db, body)

    @staticmethod
    async def resend_verification_email(
        db: AsyncSession, body: ResendVerificationRequest
    ) -> ResendVerificationResponse:
        return await resend_verification_email(db, body)


auth_service = AuthService()
