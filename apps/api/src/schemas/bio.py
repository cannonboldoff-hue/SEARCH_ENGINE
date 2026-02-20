import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


PHONE_ALLOWED_CHARS_REGEX = re.compile(r"^\+?[0-9().\-\s]+$")


class PastCompanyItem(BaseModel):
    company_name: str
    role: Optional[str] = None
    years: Optional[str] = None


class BioResponse(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    current_city: Optional[str] = None
    profile_photo_url: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    current_company: Optional[str] = None
    past_companies: Optional[list[PastCompanyItem]] = None
    email: Optional[str] = None  # from Person, for display
    linkedin_url: Optional[str] = None  # from PersonProfile
    phone: Optional[str] = None  # from PersonProfile
    complete: bool = False

    model_config = ConfigDict(from_attributes=True)


class BioCreateUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    current_city: Optional[str] = None
    profile_photo_url: Optional[str] = None
    school: Optional[str] = None
    college: Optional[str] = None
    current_company: Optional[str] = None
    past_companies: Optional[list[PastCompanyItem]] = None
    email: Optional[str] = None  # sync to Person.email if provided
    linkedin_url: Optional[str] = None  # sync to PersonProfile
    phone: str  # sync to PersonProfile

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("Phone number is required")
        if not PHONE_ALLOWED_CHARS_REGEX.fullmatch(normalized):
            raise ValueError("Phone number contains invalid characters")
        digits = re.sub(r"\D", "", normalized)
        if len(digits) < 10 or len(digits) > 15:
            raise ValueError("Enter a valid phone number (10-15 digits)")
        return normalized
