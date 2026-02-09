from typing import Optional

from pydantic import BaseModel


class ContactDetailsResponse(BaseModel):
    email_visible: bool
    email: Optional[str] = None  # actual email when unlocked and email_visible
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    other: Optional[str] = None


class PatchContactRequest(BaseModel):
    email_visible: Optional[bool] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    other: Optional[str] = None
