"""
Seed visibility settings for all existing people.
Populates: open_to_work, open_to_contact, work_preferred_locations, work_preferred_salary_min (minimum salary needed).

Run from repo root or apps/api:
  uv run python apps/api/scripts/seed_visibility.py
  or: cd apps/api && uv run python scripts/seed_visibility.py
"""
import asyncio
import logging
import random
import sys
from pathlib import Path

# Ensure apps/api is on path so "src" resolves (run from repo root or apps/api)
_app_api = Path(__file__).resolve().parent.parent
if str(_app_api) not in sys.path:
    sys.path.insert(0, str(_app_api))

from sqlalchemy import select
from src.db.session import async_session
from src.db.models import Person, PersonProfile

logger = logging.getLogger(__name__)

# Major Indian cities for work preferred locations
INDIA_MAJOR_CITIES = [
    "Bangalore",
    "Mumbai",
    "Delhi",
    "Hyderabad",
    "Chennai",
    "Pune",
    "Kolkata",
    "Ahmedabad",
    "Noida",
    "Gurgaon",
    "Jaipur",
    "Lucknow",
    "Kochi",
    "Chandigarh",
]

# Salary range in ₹/year (LPA * 100_000)
SALARY_MIN_LPA = 5
SALARY_MAX_LPA = 50

# Distribution: majority Open to work, some Open to contact, few No contact
OPEN_TO_WORK_WEIGHT = 0.70
OPEN_TO_CONTACT_WEIGHT = 0.25
NO_CONTACT_WEIGHT = 0.05


def random_visibility_mode() -> str:
    """Return 'open_to_work' | 'open_to_contact' | 'no_contact'."""
    r = random.random()
    if r < OPEN_TO_WORK_WEIGHT:
        return "open_to_work"
    if r < OPEN_TO_WORK_WEIGHT + OPEN_TO_CONTACT_WEIGHT:
        return "open_to_contact"
    return "no_contact"


async def run_seed_visibility() -> None:
    async with async_session() as session:
        result = await session.execute(select(Person.id))
        person_ids = [row[0] for row in result.fetchall()]

        if not person_ids:
            logger.warning("No people in database. Nothing to seed.")
            return

        # Load existing profiles (visibility lives in person_profiles)
        profile_result = await session.execute(
            select(PersonProfile).where(PersonProfile.person_id.in_(person_ids))
        )
        existing_by_person = {p.person_id: p for p in profile_result.scalars().all()}

        created = 0
        updated = 0

        for person_id in person_ids:
            profile = existing_by_person.get(person_id)
            mode = random_visibility_mode()

            if profile is None:
                profile = PersonProfile(person_id=person_id)
                session.add(profile)
                await session.flush()
                created += 1
            else:
                updated += 1

            if mode == "open_to_work":
                num_cities = random.randint(5, min(10, len(INDIA_MAJOR_CITIES)))
                profile.open_to_work = True
                profile.open_to_contact = False
                profile.work_preferred_locations = random.sample(INDIA_MAJOR_CITIES, num_cities)
                salary_min_lpa = random.uniform(SALARY_MIN_LPA, SALARY_MAX_LPA)
                profile.work_preferred_salary_min = round(salary_min_lpa * 100_000, 2)
            elif mode == "open_to_contact":
                profile.open_to_work = False
                profile.open_to_contact = True
                profile.work_preferred_locations = []
                profile.work_preferred_salary_min = None
            else:
                profile.open_to_work = False
                profile.open_to_contact = False
                profile.work_preferred_locations = []
                profile.work_preferred_salary_min = None

        await session.commit()
        logger.info(
            "Visibility seed done. People=%s, created=%s, updated=%s",
            len(person_ids),
            created,
            updated,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_seed_visibility())


if __name__ == "__main__":
    main()
