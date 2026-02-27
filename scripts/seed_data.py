#!/usr/bin/env python3
"""
Seed script to populate the database with sample experience data via API calls.
Make sure the API is running on http://localhost:8000 before running this script.
"""

import asyncio
import json
import sys

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


API_BASE_URL = "http://localhost:8000"

# Sample experience data based on the provided design
EXPERIENCE_SAMPLES = [
    {
        "title": "Sales and Partnerships Manager",
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
        "company": "Epic&Focus Company",
        "location": "Mumbai",
        "domain": "photography",
        "sub_domain": "all",
        "summary": "Generated ₹15 lakh in sales within two months while managing the admin panel, mediated collaborations with other studios, secured city-wide coverage across Mumbai, and established partnerships in every major area.",
        "children": [
            {
                "title": "Admin Panel Management",
                "category": "RESPONSIBILITIES",
                "description": "Managed the admin panel concurrently with sales activities photography company two months",
            },
            {
                "title": "Studio Collaborations",
                "category": "COLLABORATIONS",
                "description": "Mediated collaborations between the company and other studios photography company two months",
            },
            {
                "title": "Sales Achievement",
                "category": "METRICS",
                "description": "Generated ₹15 lakh in sales within two months photography company two months",
            },
            {
                "title": "City-wide Coverage & Partnerships",
                "category": "ACHIEVEMENTS",
                "description": "Secured coverage across all of Mumbai and established partnerships in every major area photography company two months",
            },
        ],
    },
    {
        "title": "Product Manager",
        "start_date": "2023-06-01",
        "end_date": "2023-12-31",
        "company": "TechStartup Inc",
        "location": "Bangalore",
        "domain": "technology",
        "sub_domain": "saas",
        "summary": "Led product strategy and roadmap for SaaS platform with 50K+ users. Increased feature adoption by 40% and improved user retention by 25% through data-driven decisions.",
        "children": [
            {
                "title": "Product Roadmap Leadership",
                "category": "RESPONSIBILITIES",
                "description": "Created and executed quarterly product roadmaps that increased team velocity by 35%",
            },
            {
                "title": "Cross-functional Collaboration",
                "category": "COLLABORATIONS",
                "description": "Worked with engineering, design, and marketing teams to deliver 8 major features on schedule",
            },
            {
                "title": "User Growth",
                "category": "METRICS",
                "description": "Increased product adoption from 30K to 50K users (67% growth) in 6 months",
            },
            {
                "title": "Retention Improvement",
                "category": "ACHIEVEMENTS",
                "description": "Improved 30-day retention rate from 60% to 75% through onboarding improvements",
            },
        ],
    },
    {
        "title": "Software Engineer",
        "start_date": "2022-01-15",
        "end_date": "2023-05-30",
        "company": "WebSolutions Ltd",
        "location": "Delhi",
        "domain": "software",
        "sub_domain": "backend",
        "summary": "Built and maintained backend infrastructure serving 1M+ daily active users. Optimized database queries reducing API latency by 60% and improved system reliability to 99.99% uptime.",
        "children": [
            {
                "title": "Backend Infrastructure",
                "category": "RESPONSIBILITIES",
                "description": "Designed and implemented microservices architecture handling 10K requests/second",
            },
            {
                "title": "Team Code Review",
                "category": "COLLABORATIONS",
                "description": "Led code reviews and mentored 3 junior engineers improving code quality by 45%",
            },
            {
                "title": "Performance Optimization",
                "category": "METRICS",
                "description": "Reduced API latency from 500ms to 200ms through query optimization and caching",
            },
            {
                "title": "System Reliability",
                "category": "ACHIEVEMENTS",
                "description": "Achieved 99.99% uptime through monitoring, alerting, and automated failover systems",
            },
        ],
    },
]


async def seed_data():
    """Seed the database with sample experience data via API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Connecting to API at {API_BASE_URL}...")
        
        for i, experience in enumerate(EXPERIENCE_SAMPLES, 1):
            print(f"\n[{i}/{len(EXPERIENCE_SAMPLES)}] Creating experience: {experience['title']}")
            
            try:
                # Create experience card
                card_data = {
                    "title": experience["title"],
                    "start_date": experience["start_date"],
                    "end_date": experience["end_date"],
                    "company": experience["company"],
                    "location": experience["location"],
                    "domain": experience["domain"],
                    "sub_domain": experience["sub_domain"],
                    "summary": experience["summary"],
                }
                
                response = await client.post(
                    f"{API_BASE_URL}/builder/cards",
                    json=card_data,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code != 201:
                    print(f"  ❌ Failed to create card: {response.status_code}")
                    print(f"     Response: {response.text}")
                    continue
                
                card_response = response.json()
                card_id = card_response.get("id")
                print(f"  ✓ Card created with ID: {card_id}")
                
                # Create child elements (responsibilities, metrics, etc.)
                for j, child in enumerate(experience["children"], 1):
                    child_data = {
                        "title": child["title"],
                        "category": child["category"],
                        "description": child["description"],
                    }
                    
                    child_response = await client.post(
                        f"{API_BASE_URL}/builder/cards/{card_id}/children",
                        json=child_data,
                        headers={"Content-Type": "application/json"},
                    )
                    
                    if child_response.status_code == 201:
                        print(f"    ✓ Added {child['category']}: {child['title']}")
                    else:
                        print(f"    ❌ Failed to add child: {child_response.status_code}")
                
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                continue
        
        print("\n✅ Seed data completed!")


if __name__ == "__main__":
    try:
        asyncio.run(seed_data())
    except KeyboardInterrupt:
        print("\n\nSeed cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)
