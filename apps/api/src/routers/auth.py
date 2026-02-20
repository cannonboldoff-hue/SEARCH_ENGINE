from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import get_settings, limiter
from src.dependencies import get_db
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
from src.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


@router.post("/signup", response_model=SignupResponse)
@limiter.limit(_settings.auth_signup_rate_limit)
async def signup(
    request: Request,
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.signup(db, body)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(_settings.auth_login_rate_limit)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.login(db, body)


@router.post("/verify-email", response_model=VerifyEmailResponse)
@limiter.limit(_settings.auth_verify_rate_limit)
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.verify_email(db, body)


@router.post("/verify-email/resend", response_model=ResendVerificationResponse)
@limiter.limit(_settings.auth_verify_rate_limit)
async def resend_verify_email(
    request: Request,
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.resend_verification_email(db, body)
