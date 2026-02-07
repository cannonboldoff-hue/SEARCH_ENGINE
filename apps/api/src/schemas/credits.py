from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreditsResponse(BaseModel):
    balance: int


class PurchaseCreditsRequest(BaseModel):
    credits: int


class LedgerEntryResponse(BaseModel):
    id: str
    amount: int
    reason: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    balance_after: Optional[int] = None
    created_at: datetime
