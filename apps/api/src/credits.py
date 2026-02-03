from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import CreditWallet, CreditLedger, IdempotencyKey


async def get_balance(db: AsyncSession, person_id: str) -> int:
    result = await db.execute(select(CreditWallet).where(CreditWallet.person_id == person_id))
    w = result.scalar_one_or_none()
    return w.balance if w else 0


async def deduct_credits(
    db: AsyncSession,
    person_id: str,
    amount: int,
    reason: str,
    reference_type: str | None = None,
    reference_id: str | None = None,
) -> bool:
    result = await db.execute(
        select(CreditWallet)
        .where(CreditWallet.person_id == person_id)
        .with_for_update()
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        return False
    if wallet.balance < amount:
        return False
    wallet.balance -= amount
    new_balance = wallet.balance
    ledger = CreditLedger(
        person_id=person_id,
        amount=-amount,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        balance_after=new_balance,
    )
    db.add(wallet)
    db.add(ledger)
    await db.flush()
    return True


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
