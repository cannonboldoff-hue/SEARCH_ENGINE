from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.dependencies import get_db
from src.db.models import Person, VisibilitySettings, ContactDetails, CreditWallet, CreditLedger
from src.auth import hash_password, verify_password, create_access_token
from src.schemas import SignupRequest, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    person = Person(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(person)
    await db.flush()
    db.add(VisibilitySettings(person_id=person.id))
    db.add(ContactDetails(person_id=person.id))
    wallet = CreditWallet(person_id=person.id, balance=1000)
    db.add(wallet)
    await db.flush()
    db.add(CreditLedger(person_id=person.id, amount=1000, reason="signup", balance_after=1000))
    await db.commit()
    await db.refresh(person)
    token = create_access_token(subject=str(person.id))
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.email == body.email))
    person = result.scalar_one_or_none()
    if not person or not verify_password(body.password, person.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(subject=str(person.id))
    return TokenResponse(access_token=token)
