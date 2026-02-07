"""Credit wallet, ledger, and idempotency key operations."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import PersonProfile, CreditLedger, IdempotencyKey


async def get_balance(db: AsyncSession, person_id: str) -> int:
    result = await db.execute(select(PersonProfile).where(PersonProfile.person_id == person_id))
    p = result.scalar_one_or_none()
    return p.balance if p else 0


async def deduct_credits(
    db: AsyncSession,
    person_id: str,
    amount: int,
    reason: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> bool:
    result = await db.execute(
        select(PersonProfile)
        .where(PersonProfile.person_id == person_id)
        .with_for_update()
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return False
    if profile.balance < amount:
        return False
    profile.balance -= amount
    new_balance = profile.balance
    ledger = CreditLedger(
        person_id=person_id,
        amount=-amount,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        balance_after=new_balance,
    )
    db.add(profile)
    db.add(ledger)
    await db.flush()
    return True


async def add_credits(
    db: AsyncSession,
    person_id: str,
    amount: int,
    reason: str = "purchase",
) -> int:
    """Add credits to profile balance. Returns new balance."""
    result = await db.execute(
        select(PersonProfile)
        .where(PersonProfile.person_id == person_id)
        .with_for_update()
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = PersonProfile(person_id=person_id, balance=0)
        db.add(profile)
        await db.flush()
    profile.balance += amount
    new_balance = profile.balance
    ledger = CreditLedger(
        person_id=person_id,
        amount=amount,
        reason=reason,
        reference_type=None,
        reference_id=None,
        balance_after=new_balance,
    )
    db.add(ledger)
    await db.flush()
    return new_balance


async def get_idempotent_response(db: AsyncSession, key: str, person_id: str, endpoint: str):
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.person_id == person_id,
            IdempotencyKey.endpoint == endpoint,
        )
    )
    row = result.scalar_one_or_none()
    return row


async def save_idempotent_response(
    db: AsyncSession,
    key: str,
    person_id: str,
    endpoint: str,
    response_status: int,
    response_body: dict,
):
    row = IdempotencyKey(
        key=key,
        person_id=person_id,
        endpoint=endpoint,
        response_status=response_status,
        response_body=response_body,
    )
    db.add(row)
    await db.flush()
