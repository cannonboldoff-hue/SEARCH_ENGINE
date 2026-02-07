from typing import Optional

from pydantic import BaseModel, ConfigDict


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
    linkedin_url: Optional[str] = None  # from ContactDetails
    phone: Optional[str] = None  # from ContactDetails
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
    linkedin_url: Optional[str] = None  # sync to ContactDetails
    phone: Optional[str] = None  # sync to ContactDetails
