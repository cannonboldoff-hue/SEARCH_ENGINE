#!/usr/bin/env python3
"""
Seed script to populate the database with sample experience data.
Run this script after starting the API.
"""

import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add the API to the path
api_path = Path(__file__).parent.parent / "apps" / "api"
sys.path.insert(0, str(api_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.db.models import Person, PersonProfile, ExperienceCard, ExperienceCardChild
from src.db.session import Base
from src.core.config import get_settings


async def seed_data():
    """Seed the database with sample experience data."""
    settings = get_settings()
    
    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create demo user
        demo_user = Person(
            email="demo@example.com",
            hashed_password="$2b$12$dummyhash",  # Dummy hash, not used since auth is disabled
            display_name="Demo User",
            email_verified_at=datetime.now(timezone.utc),
        )
        session.add(demo_user)
        await session.flush()
        
        # Create profile for demo user
        profile = PersonProfile(
            person_id=demo_user.id,
            first_name="Demo",
            last_name="User",
            current_city="Mumbai",
            school="St. Xavier's College",
            college="IIT Bombay",
            current_company="Epic&Focus Company",
            open_to_work=True,
            work_preferred_locations=["Mumbai", "Delhi", "Bangalore"],
            open_to_contact=True,
            email_visible=True,
            linkedin_url="https://linkedin.com/in/demouser",
            balance=5000,
        )
        session.add(profile)
        await session.flush()
        
        # Sample experience 1: Sales and Partnerships Manager
        exp1 = ExperienceCard(
            person_id=demo_user.id,
            title="Sales and Partnerships Manager",
            normalized_role="sales and partnerships manager",
            domain="Sales",
            domain_norm="sales",
            sub_domain="Business Development",
            sub_domain_norm="business development",
            company_name="Epic&Focus Company",
            company_norm="epicfocus company",
            company_type="Photography Company",
            team="Sales & Partnerships",
            team_norm="sales partnerships",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            is_current=False,
            location="Mumbai",
            city="Mumbai",
            country="India",
            is_remote=False,
            employment_type="Full-time",
            summary="Generated ₹15 lakh in sales within two months while managing the admin panel, mediated collaborations with other studios, secured city-wide coverage across Mumbai, and established partnerships in every major area.",
            raw_text="Sales and Partnerships Manager at Epic&Focus Company (Jan 2024 - Mar 2024) in Mumbai. Generated ₹15 lakh in sales within two months while managing the admin panel, mediated collaborations with other studios, secured city-wide coverage across Mumbai, and established partnerships in every major area.",
            intent_primary="Business Growth",
            intent_secondary=["Leadership", "Partnerships", "Revenue Generation"],
            seniority_level="Senior",
            confidence_score=0.95,
            experience_card_visibility=True,
            search_phrases=["sales", "partnerships", "business development", "sales management", "revenue generation"],
            search_document="Sales and Partnerships Manager - Epic&Focus Company - Mumbai - Sales, Business Development - Generated ₹15 lakh in sales, managed admin panel, studio collaborations, city-wide coverage, established partnerships",
        )
        session.add(exp1)
        await session.flush()
        
        # Child card 1.1: Admin Panel Management (Responsibility)
        child1_1 = ExperienceCardChild(
            parent_experience_id=exp1.id,
            person_id=demo_user.id,
            child_type="RESPONSIBILITY",
            label="Admin Panel Management",
            value={
                "title": "Admin Panel Management",
                "description": "Managed the admin panel concurrently with sales activities",
                "impact": "Ensured smooth operations across photography company for two months",
            },
            confidence_score=0.92,
            search_phrases=["admin", "panel management", "operations"],
            search_document="Admin Panel Management - Managed the admin panel concurrently with sales activities",
        )
        session.add(child1_1)
        
        # Child card 1.2: Studio Collaborations (Collaboration)
        child1_2 = ExperienceCardChild(
            parent_experience_id=exp1.id,
            person_id=demo_user.id,
            child_type="COLLABORATION",
            label="Studio Collaborations",
            value={
                "title": "Studio Collaborations",
                "description": "Mediated collaborations between the company and other studios",
                "partner_count": 5,
            },
            confidence_score=0.88,
            search_phrases=["collaboration", "partnerships", "studios"],
            search_document="Studio Collaborations - Mediated collaborations between the company and other studios",
        )
        session.add(child1_2)
        
        # Child card 1.3: Sales Achievement (Metric)
        child1_3 = ExperienceCardChild(
            parent_experience_id=exp1.id,
            person_id=demo_user.id,
            child_type="METRIC",
            label="Sales Achievement",
            value={
                "metric": "Revenue Generated",
                "value": "₹15 lakh",
                "duration": "Two months",
                "currency": "INR",
            },
            confidence_score=0.98,
            search_phrases=["sales", "revenue", "15 lakh", "achievement"],
            search_document="Sales Achievement - Generated ₹15 lakh in sales within two months",
        )
        session.add(child1_3)
        
        # Child card 1.4: Geographic Coverage (Achievement)
        child1_4 = ExperienceCardChild(
            parent_experience_id=exp1.id,
            person_id=demo_user.id,
            child_type="ACHIEVEMENT",
            label="City-wide Coverage & Partnerships",
            value={
                "title": "City-wide Coverage & Partnerships",
                "description": "Secured coverage across all of Mumbai and established partnerships in every major area",
                "scope": "city-wide",
                "location": "Mumbai",
            },
            confidence_score=0.94,
            search_phrases=["partnerships", "coverage", "Mumbai", "expansion"],
            search_document="City-wide Coverage & Partnerships - Secured coverage across all of Mumbai and established partnerships",
        )
        session.add(child1_4)
        
        # Sample experience 2: Software Engineer
        exp2 = ExperienceCard(
            person_id=demo_user.id,
            title="Senior Software Engineer",
            normalized_role="senior software engineer",
            domain="Technology",
            domain_norm="technology",
            sub_domain="Backend Development",
            sub_domain_norm="backend development",
            company_name="TechCorp Solutions",
            company_norm="techcorp solutions",
            company_type="Software Company",
            team="Platform Engineering",
            team_norm="platform engineering",
            start_date=date(2023, 3, 15),
            end_date=date(2024, 1, 1),
            is_current=False,
            location="Bangalore",
            city="Bangalore",
            country="India",
            is_remote=True,
            employment_type="Full-time",
            summary="Led development of microservices architecture serving 1M+ users, mentored junior engineers, and improved API performance by 40% through optimization.",
            raw_text="Senior Software Engineer at TechCorp Solutions (Mar 2023 - Jan 2024) in Bangalore. Led development of microservices architecture serving 1M+ users, mentored junior engineers, and improved API performance by 40% through optimization.",
            intent_primary="Technical Leadership",
            intent_secondary=["Backend Development", "Performance Optimization", "Team Leadership"],
            seniority_level="Senior",
            confidence_score=0.96,
            experience_card_visibility=True,
            search_phrases=["backend", "software engineer", "microservices", "architecture", "performance"],
            search_document="Senior Software Engineer - TechCorp Solutions - Bangalore - Backend Development - Microservices, API optimization, team mentorship",
        )
        session.add(exp2)
        await session.flush()
        
        # Child card 2.1: Microservices Architecture
        child2_1 = ExperienceCardChild(
            parent_experience_id=exp2.id,
            person_id=demo_user.id,
            child_type="RESPONSIBILITY",
            label="Microservices Architecture",
            value={
                "title": "Microservices Architecture Development",
                "description": "Designed and led development of scalable microservices architecture",
                "scale": "1M+ users",
            },
            confidence_score=0.97,
            search_phrases=["microservices", "architecture", "scale"],
            search_document="Microservices Architecture - Designed and led development serving 1M+ users",
        )
        session.add(child2_1)
        
        # Child card 2.2: Performance Improvement Metric
        child2_2 = ExperienceCardChild(
            parent_experience_id=exp2.id,
            person_id=demo_user.id,
            child_type="METRIC",
            label="API Performance Improvement",
            value={
                "metric": "Performance Improvement",
                "improvement": "40%",
                "focus_area": "API Optimization",
            },
            confidence_score=0.95,
            search_phrases=["performance", "optimization", "api"],
            search_document="API Performance Improvement - Improved API performance by 40% through optimization",
        )
        session.add(child2_2)
        
        # Child card 2.3: Team Leadership
        child2_3 = ExperienceCardChild(
            parent_experience_id=exp2.id,
            person_id=demo_user.id,
            child_type="RESPONSIBILITY",
            label="Team Mentorship",
            value={
                "title": "Team Mentorship and Leadership",
                "description": "Mentored junior engineers and led platform engineering team",
                "team_size": 5,
            },
            confidence_score=0.90,
            search_phrases=["mentorship", "leadership", "team"],
            search_document="Team Mentorship - Mentored junior engineers on platform engineering",
        )
        session.add(child2_3)
        
        # Sample experience 3: Product Manager
        exp3 = ExperienceCard(
            person_id=demo_user.id,
            title="Product Manager",
            normalized_role="product manager",
            domain="Product",
            domain_norm="product",
            sub_domain="Product Strategy",
            sub_domain_norm="product strategy",
            company_name="InnovateTech Inc",
            company_norm="innovatetech inc",
            company_type="SaaS Company",
            team="Product",
            team_norm="product",
            start_date=date(2022, 6, 1),
            end_date=date(2023, 3, 1),
            is_current=False,
            location="Mumbai",
            city="Mumbai",
            country="India",
            is_remote=False,
            employment_type="Full-time",
            summary="Launched 3 major product features reaching 50K+ users, managed cross-functional teams, and increased user engagement by 35%.",
            raw_text="Product Manager at InnovateTech Inc (Jun 2022 - Mar 2023) in Mumbai. Launched 3 major product features reaching 50K+ users, managed cross-functional teams, and increased user engagement by 35%.",
            intent_primary="Product Growth",
            intent_secondary=["User Engagement", "Feature Development", "Cross-functional Leadership"],
            seniority_level="Mid",
            confidence_score=0.93,
            experience_card_visibility=True,
            search_phrases=["product manager", "product strategy", "user engagement", "feature launch"],
            search_document="Product Manager - InnovateTech Inc - Mumbai - Product Strategy - 3 major features, 50K+ users, 35% engagement increase",
        )
        session.add(exp3)
        await session.flush()
        
        # Child card 3.1: Product Launches
        child3_1 = ExperienceCardChild(
            parent_experience_id=exp3.id,
            person_id=demo_user.id,
            child_type="METRIC",
            label="Product Features Launched",
            value={
                "metric": "Features Launched",
                "count": 3,
                "user_reach": "50K+",
            },
            confidence_score=0.96,
            search_phrases=["product", "features", "launch", "users"],
            search_document="Product Features Launched - Launched 3 major product features reaching 50K+ users",
        )
        session.add(child3_1)
        
        # Child card 3.2: Engagement Growth
        child3_2 = ExperienceCardChild(
            parent_experience_id=exp3.id,
            person_id=demo_user.id,
            child_type="METRIC",
            label="User Engagement Growth",
            value={
                "metric": "Engagement Increase",
                "percentage": "35%",
                "period": "9 months",
            },
            confidence_score=0.94,
            search_phrases=["engagement", "growth", "users"],
            search_document="User Engagement Growth - Increased user engagement by 35%",
        )
        session.add(child3_2)
        
        # Commit all changes
        await session.commit()
        print("✓ Seed data created successfully!")
        print(f"  - Created demo user: {demo_user.email}")
        print(f"  - Created 3 sample experience cards with children")
        print(f"  - Demo user ID: {demo_user.id}")


async def main():
    try:
        await seed_data()
    except Exception as e:
        print(f"✗ Error seeding data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
