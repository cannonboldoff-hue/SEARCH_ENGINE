from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Person, ContactDetails
from src.dependencies import get_current_user, get_db
from src.schemas import ContactDetailsResponse, PatchContactRequest

router = APIRouter(prefix="/me", tags=["contact"])


@router.get("/contact", response_model=ContactDetailsResponse)
async def get_contact(
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == current_user.id))
    contact = result.scalar_one_or_none()
    if not contact:
        return ContactDetailsResponse(
            email_visible=True,
            phone=None,
            linkedin_url=None,
            other=None,
        )
    return ContactDetailsResponse(
        email_visible=contact.email_visible,
        phone=contact.phone,
        linkedin_url=contact.linkedin_url,
        other=contact.other,
    )


@router.patch("/contact", response_model=ContactDetailsResponse)
async def patch_contact(
    body: PatchContactRequest,
    current_user: Person = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ContactDetails).where(ContactDetails.person_id == current_user.id))
    contact = result.scalar_one_or_none()
    if not contact:
        contact = ContactDetails(person_id=current_user.id)
        db.add(contact)
        await db.flush()
    if body.email_visible is not None:
        contact.email_visible = body.email_visible
    if body.phone is not None:
        contact.phone = body.phone
    if body.linkedin_url is not None:
        contact.linkedin_url = body.linkedin_url
    if body.other is not None:
        contact.other = body.other
    await db.commit()
    await db.refresh(contact)
    return ContactDetailsResponse(
        email_visible=contact.email_visible,
        phone=contact.phone,
        linkedin_url=contact.linkedin_url,
        other=contact.other,
    )
