"""
Seed the database with 100 users (tech, non-tech, business) and at least 5 experience cards each.
Run from apps/api: uv run python scripts/seed_db.py
"""
import asyncio
import logging
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure src is importable when run from repo root or apps/api
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

from src.core import hash_password
from src.db.session import async_session
from src.db.models import (
    Person,
    Bio,
    VisibilitySettings,
    ContactDetails,
    CreditWallet,
    CreditLedger,
    ExperienceCard,
    ExperienceCardChild,
)
from src.domain import ALLOWED_CHILD_TYPES

SEED_PASSWORD = "SeedPassword123!"
NUM_USERS = 100
MIN_CARDS_PER_USER = 5
MAX_CARDS_PER_USER = 8
SIGNUP_CREDITS = 1000

# Background mix: tech, non-tech, business
BACKGROUNDS = ["tech", "non_tech", "business"]
BACKGROUND_WEIGHTS = [0.4, 0.35, 0.25]  # 40 tech, 35 non-tech, 25 business

# First names (mixed)
FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Avery",
    "Jamie", "Quinn", "Reese", "Skyler", "Parker", "Blake", "Cameron", "Drew",
    "Emma", "Liam", "Olivia", "Noah", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "William", "Mia", "James", "Charlotte", "Benjamin", "Amelia",
    "Lucas", "Harper", "Henry", "Evelyn", "Alexander", "Abigail", "Sebastian",
    "Emily", "Jack", "Ella", "Aiden", "Scarlett", "Owen", "Grace", "Samuel",
    "Chloe", "Matthew", "Victoria", "Joseph", "Riley", "Levi", "Aria",
    "Mateo", "Lily", "David", "Aubrey", "John", "Zoey", "Wyatt", "Penelope",
    "Luke", "Lillian", "Gabriel", "Addison", "Anthony", "Layla", "Isaac",
    "Natalie", "Dylan", "Camila", "Leo", "Hannah", "Lincoln", "Brooklyn",
    "Jaxon", "Zoe", "Asher", "Nora", "Christopher", "Leah", "Josiah", "Savannah",
]

# Last names
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
    "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera",
]

# Tech roles, companies, domains
TECH_ROLES = [
    "Software Engineer", "Senior Software Engineer", "Staff Engineer", "Tech Lead",
    "Product Manager", "Engineering Manager", "Data Scientist", "ML Engineer",
    "DevOps Engineer", "Backend Developer", "Frontend Developer", "Full Stack Developer",
    "Solutions Architect", "Security Engineer", "QA Engineer", "Platform Engineer",
]
TECH_COMPANIES = [
    "Google", "Meta", "Amazon", "Microsoft", "Apple", "Netflix", "Stripe", "Spotify",
    "Airbnb", "Uber", "Lyft", "Slack", "Notion", "Figma", "Vercel", "OpenAI",
    "TechStart Inc", "CloudNine Software", "DataDriven Labs", "DevOps Pro",
]
TECH_DOMAINS = ["Software Development", "Data Engineering", "Cloud Infrastructure", "Machine Learning", "Product Management", "DevOps", "Security", "Mobile Development"]

# Non-tech roles, companies, domains
NONTECH_ROLES = [
    "Teacher", "Senior Teacher", "Curriculum Designer", "School Counselor",
    "Registered Nurse", "Clinical Nurse", "Healthcare Coordinator", "Therapist",
    "Graphic Designer", "UX Designer", "Content Writer", "Editor", "Journalist",
    "Research Assistant", "Lab Technician", "Social Worker", "Policy Analyst",
]
NONTECH_COMPANIES = [
    "City Public Schools", "State University", "General Hospital", "Community Health",
    "Design Studio Co", "Publishing House", "Local Newspaper", "Nonprofit Foundation",
    "Research Institute", "Museum of Arts", "Public Library", "City Council",
]
NONTECH_DOMAINS = ["Education", "Healthcare", "Design", "Media", "Research", "Nonprofit", "Public Sector", "Creative Arts"]

# Business roles, companies, domains
BUSINESS_ROLES = [
    "Financial Analyst", "Investment Banker", "Accountant", "CFO", "Controller",
    "Marketing Manager", "Brand Director", "Growth Lead", "Digital Marketing Specialist",
    "Management Consultant", "Strategy Consultant", "Business Analyst", "Project Manager",
    "Sales Representative", "Account Executive", "Sales Manager", "Business Development",
]
BUSINESS_COMPANIES = [
    "Goldman Sachs", "McKinsey", "Deloitte", "PwC", "KPMG", "Accenture", "BCG",
    "Procter & Gamble", "Unilever", "Salesforce", "HubSpot", "Adobe", "Oracle",
    "Enterprise Corp", "Global Consulting Group", "Growth Partners", "Venture Sales Inc",
]
BUSINESS_DOMAINS = ["Finance", "Consulting", "Marketing", "Sales", "Strategy", "Operations", "Accounting", "Investment"]

# Employment types and locations
EMPLOYMENT_TYPES = ["full_time", "part_time", "contract", "internship", "freelance"]
LOCATIONS = [
    "San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX", "Boston, MA",
    "Chicago, IL", "Denver, CO", "Remote", "London, UK", "Berlin, Germany", "Toronto, Canada",
]
INTENTS = ["work", "education", "project", "business", "research", "achievement", "learning", "other"]
SENIORITY_LEVELS = ["entry", "mid", "senior", "lead", "executive"]


def random_date_in_range(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(0, delta)))


def generate_messy_raw_text(role: str, company: str, background: str, start: date, end: date) -> str:
    """Generate realistic, messy raw text for experience cards."""
    templates = {
        "tech": [
            f"So I worked as a {role} @ {company} starting in {start.strftime('%B %Y')} until {end.strftime('%B %Y')}... it was pretty intense! Basically I was responsible for building out the backend systems and working on microservices architecture. Did a ton of Python/Django work, some React on the frontend. Also got deep into AWS - setting up EC2 instances, RDS databases, S3 buckets for file storage. Had to deal with a lot of legacy code which was... challenging lol. But managed to refactor the entire user authentication system and improved performance by like 40%. Worked closely with the product team and designers to ship new features. Oh and I mentored 2 junior devs which was actually really rewarding. There were some rough patches - like when the production database went down during Black Friday and we had to work 18 hour days to fix it. But overall learned SO much about scalable systems.",
            f"My time at {company} as {role} was from {start.year} to {end.year}. Main focus was on data pipeline development using Apache Spark and Kafka. Built real-time analytics dashboards in Tableau, wrote tons of SQL queries for reporting. The data was MESSY - had to clean up years of inconsistent database schemas. Implemented ETL processes that reduced data processing time from 6 hours to 45 minutes. Also did machine learning stuff - built recommendation engines using scikit-learn and TensorFlow. Presented findings to C-suite executives quarterly. Team was small but super collaborative.",
            f"{role} position at {company} {start.year}-{end.year}. Wow what a ride! Started on the mobile team doing iOS development in Swift, then moved to full-stack when they needed help with the web platform. Built features end-to-end from database design to UI implementation. Used Node.js/Express for APIs, PostgreSQL for data storage, deployed everything on Docker containers. Had to learn GraphQL on the fly which was tough but worth it. Collaborated with UX designers using Figma, participated in daily standups and sprint planning. Shipped 15+ major features during my tenure. The codebase was a bit of a mess when I started - no tests, inconsistent coding standards, deployment was manual (!!) but by the time I left we had a proper CI/CD pipeline and 80% test coverage.",
            f"Working as {role} at {company} from {start.strftime('%m/%Y')} to {end.strftime('%m/%Y')} was honestly one of the most challenging but rewarding experiences of my career so far. I joined when the company was going through a major digital transformation - they were moving from monolithic architecture to microservices and my job was basically to help architect and implement this transition. Started with legacy .NET applications and gradually migrated everything to containerized services using Docker and Kubernetes. Had to learn SO MUCH on the job - never worked with k8s before! Also implemented monitoring and alerting using Prometheus and Grafana. The team was great - really collaborative culture with proper code reviews and knowledge sharing sessions. Did some really cool stuff with event-driven architecture using Apache Kafka for real-time data streaming.",
            f"Been working as a {role} @ {company} since {start.strftime('%B %Y')} (left in {end.strftime('%B %Y')}). Main focus was on improving the data infrastructure - when I started, data scientists were spending 80% of their time just cleaning and preparing data instead of actually doing analysis! Built automated ETL pipelines using Apache Airflow and Python to ingest data from multiple sources - APIs, databases, flat files, you name it. Also set up a proper data warehouse using Snowflake and created self-service analytics dashboards in Looker. The impact was huge - reduced time-to-insight from weeks to hours for most analysis. Worked closely with the ML team to put models into production using MLflow and Docker. Oh and I became the go-to person for anything SQL related lol - helped optimize queries that were taking 45 minutes down to under 2 minutes."
        ],
        "non_tech": [
            f"Worked as {role} at {company} from {start.strftime('%m/%Y')} to {end.strftime('%m/%Y')}. My main responsibilities included curriculum development for grades 6-8, classroom management for 25-30 students per class, and parent-teacher conferences. I redesigned the science curriculum to include more hands-on experiments which really improved student engagement - test scores went up 25%! Also organized the annual science fair, managed a budget of $5000 for supplies, and coordinated with other teachers for interdisciplinary projects. Had to deal with some challenging behavioral issues but developed strong relationships with students and families.",
            f"My role as {role} at {company} ({start.year} - {end.year}) involved direct patient care for 12-15 patients per shift in the cardiac unit. Administered medications, monitored vital signs, coordinated with doctors and specialists for treatment plans. Had to be really detail-oriented with documentation - everything gets audited! Worked 12-hour shifts including nights and weekends. Also trained new nurses and nursing students. Dealt with some really tough cases but it's incredibly rewarding when you see patients recover. Became certified in ACLS and BLS during my time there.",
            f"Creative work as {role} at {company} {start.year} to {end.year}. Mainly focused on brand identity design for healthcare and tech clients. Used Adobe Creative Suite daily - Illustrator, Photoshop, InDesign. Created logos, marketing materials, website mockups, and social media graphics. Worked directly with clients to understand their vision and brand guidelines. Had to manage multiple projects simultaneously with tight deadlines. Presented design concepts and iterated based on feedback. Also did some photography for product shoots and events. One of my favorite projects was rebranding a local hospital - created a whole new visual identity that made healthcare feel more approachable and less intimidating. The logo I designed is still being used 3 years later!",
            f"My experience as {role} at {company} ({start.strftime('%Y')}-{end.strftime('%Y')}) was incredibly fulfilling but also exhausting at times. Managing 28 middle schoolers is no joke! Had to develop creative lesson plans that would keep them engaged - did lots of hands-on experiments and group projects. The science fair I organized became a huge hit with parents and administration. Also had to deal with behavioral issues, parent conferences, IEP meetings, grading papers until midnight sometimes... But seeing that lightbulb moment when a student finally gets a concept? Priceless. I also started an after-school coding club which grew from 5 kids to 25 by the end of the year. Taught them basic Python and Scratch programming.",
            f"Nursing at {company} as {role} from {start.year} to {end.year} was the most intense and meaningful work I've ever done. 12-hour shifts in the cardiac ICU, dealing with life-and-death situations daily. Had to be incredibly detail-oriented with medication administration - double and triple checking everything because there's zero margin for error. Worked with amazing doctors and nurse practitioners, learned so much about advanced cardiac procedures. The hardest part was definitely losing patients despite our best efforts, but the joy of seeing someone recover and go home to their family made it all worthwhile. During COVID it was especially tough - PPE shortages, working overtime, seeing colleagues get sick. But our team really came together and supported each other through it all."
        ],
        "business": [
            f"Financial Analyst role at {company} from {start.strftime('%B %Y')} through {end.strftime('%B %Y')}. Primarily worked on quarterly financial reporting, budget planning, and variance analysis. Built Excel models for revenue forecasting and expense tracking - became the Excel wizard of the team lol. Prepared presentations for senior management using PowerPoint and Tableau. Analyzed P&L statements, balance sheets, cash flow statements. Had to work closely with accounting team to ensure data accuracy. During busy season (month-end close) it was pretty stressful with long hours but learned so much about the business.",
            f"My experience as {role} at {company} ({start.year}-{end.year}) focused on B2B sales in the SaaS space. Managed a territory covering the Northeast region with about 50 key accounts. Used Salesforce religiously for pipeline management and reporting. Cold calling, email outreach, attending trade shows and networking events. Built relationships with C-level executives and IT decision makers. Consistently hit quota - 120% in 2022, 115% in 2023. Also collaborated with marketing team on lead generation campaigns and product demos.",
            f"Strategy consulting at {company} as {role} {start.year} to {end.year}. Worked with Fortune 500 clients on operational improvement and digital transformation projects. Conducted market research, competitive analysis, stakeholder interviews. Created detailed project plans and recommendations using frameworks like McKinsey 7S and Porter's Five Forces. Spent lots of time in Excel building financial models and PowerPoint creating client presentations. Travel was intense - basically lived out of hotels for 3 years. But got exposure to so many different industries and business challenges. One project I'm particularly proud of was helping a manufacturing client reduce their supply chain costs by 22% through process optimization and vendor consolidation.",
            f"My time as {role} at {company} ({start.strftime('%B %Y')} - {end.strftime('%B %Y')}) was a masterclass in corporate finance. Worked on quarterly earnings reports, annual budgets, variance analysis, you name it. Excel became my best friend - built some seriously complex models for revenue forecasting and sensitivity analysis. Had to present to the CFO and board of directors quarterly which was nerve-wracking at first but I got good at distilling complex financial data into clear, actionable insights. Also worked on M&A due diligence for 3 acquisitions during my tenure. The hours were long during month-end close but learned SO much about how businesses actually work from a financial perspective.",
            f"Sales role at {company} as {role} {start.year} to {end.year} in the enterprise SaaS space. My territory was the Northeast - about 40 key accounts ranging from mid-market to Fortune 1000. Salesforce was my second home for pipeline management and forecasting. Did a lot of cold outreach, LinkedIn prospecting, trade show networking. The sales cycle was typically 6-9 months for enterprise deals so relationship building was crucial. Had some amazing wins - closed a $1.2M deal with a major retailer that took 14 months of nurturing! Also some painful losses where I thought I had it in the bag but got beat by a competitor at the last minute. Hit 118% of quota in my best year. The team culture was super competitive but supportive - we all helped each other out."
        ]
    }
    
    return random.choice(templates.get(background, templates["tech"]))


def generate_child_card_data(parent_id: str, person_id: str, child_type: str, background: str) -> dict:
    """Generate detailed child card data based on type and background."""
    
    child_data_templates = {
        "skills": {
            "tech": [
                {"Python": "Advanced - 5+ years experience with Django, Flask, FastAPI. Built microservices, APIs, data pipelines"},
                {"JavaScript": "Expert - React, Node.js, TypeScript. Frontend and backend development"},
                {"AWS": "Intermediate - EC2, S3, RDS, Lambda. Cloud architecture and deployment"},
                {"SQL": "Advanced - PostgreSQL, MySQL. Complex queries, optimization, database design"},
                {"Docker": "Intermediate - Containerization, deployment, orchestration with Kubernetes"}
            ],
            "non_tech": [
                {"Curriculum Development": "Expert - Designed STEM curriculum for middle school, aligned with state standards"},
                {"Classroom Management": "Advanced - 30+ students, behavior modification techniques, positive reinforcement"},
                {"Patient Care": "Expert - Cardiac unit experience, medication administration, vital signs monitoring"},
                {"Adobe Creative Suite": "Advanced - Illustrator, Photoshop, InDesign for brand design projects"},
                {"Communication": "Expert - Parent conferences, patient families, client presentations"}
            ],
            "business": [
                {"Financial Modeling": "Expert - Excel, DCF analysis, revenue forecasting, scenario planning"},
                {"Salesforce": "Advanced - Pipeline management, reporting, automation workflows"},
                {"Market Research": "Intermediate - Competitive analysis, customer interviews, survey design"},
                {"PowerPoint": "Expert - Executive presentations, data visualization, storytelling"},
                {"Negotiation": "Advanced - Contract terms, pricing discussions, partnership deals"}
            ]
        },
        "tools": {
            "tech": [
                {"VS Code": "Primary IDE for Python and JavaScript development"},
                {"Git": "Version control, branching strategies, code reviews"},
                {"Jira": "Project management, bug tracking, sprint planning"},
                {"Postman": "API testing and documentation"},
                {"Terraform": "Infrastructure as code for AWS deployments"}
            ],
            "non_tech": [
                {"SmartBoard": "Interactive whiteboard for engaging classroom lessons"},
                {"Epic EMR": "Electronic medical records system for patient documentation"},
                {"Figma": "Design collaboration and prototyping tool"},
                {"Google Classroom": "Online learning platform and assignment management"},
                {"Zoom": "Virtual meetings and online classes during COVID"}
            ],
            "business": [
                {"Excel": "Advanced formulas, pivot tables, macros, financial modeling"},
                {"Tableau": "Data visualization and business intelligence dashboards"},
                {"Salesforce": "CRM system for lead and opportunity management"},
                {"SAP": "Enterprise resource planning for financial data"},
                {"Bloomberg Terminal": "Financial data and market analysis"}
            ]
        },
        "responsibilities": {
            "tech": [
                "Led development of user authentication microservice handling 100k+ daily logins",
                "Mentored 3 junior developers through code reviews and pair programming sessions",
                "Architected data pipeline processing 50GB+ daily using Apache Spark and Kafka",
                "Maintained 99.9% uptime for critical customer-facing APIs through monitoring and optimization",
                "Collaborated with product managers to define technical requirements for new features"
            ],
            "non_tech": [
                "Managed classroom of 28 7th grade students with diverse learning needs and backgrounds",
                "Provided direct nursing care for 12-15 cardiac patients per 12-hour shift",
                "Developed brand identity designs for 20+ clients across healthcare and technology sectors",
                "Created engaging lesson plans incorporating hands-on experiments and group activities",
                "Coordinated with multidisciplinary team including doctors, therapists, and social workers"
            ],
            "business": [
                "Prepared monthly financial reports for executive leadership team and board of directors",
                "Managed $2.5M territory covering Northeast region with 45 key enterprise accounts",
                "Led strategic consulting engagements for Fortune 500 clients in manufacturing and retail",
                "Developed pricing models and competitive analysis for new product launches",
                "Conducted stakeholder interviews and market research for digital transformation projects"
            ]
        },
        "achievements": {
            "tech": [
                "Reduced API response time by 60% through database query optimization and caching",
                "Led migration to microservices architecture serving 500k+ monthly active users",
                "Open source contributor to popular Python libraries with 1000+ GitHub stars",
                "Implemented CI/CD pipeline reducing deployment time from 2 hours to 15 minutes",
                "Built machine learning model achieving 85% accuracy for fraud detection"
            ],
            "non_tech": [
                "Increased student test scores by 25% through innovative hands-on science curriculum",
                "Reduced patient readmission rates by 18% through improved discharge planning",
                "Won 'Design of the Year' award for healthcare brand identity project",
                "Organized school-wide science fair with 200+ student participants and 15 judges",
                "Certified in Advanced Cardiac Life Support (ACLS) and Basic Life Support (BLS)"
            ],
            "business": [
                "Exceeded sales quota by 120% in 2022 and 115% in 2023, ranking #3 in region",
                "Identified $2.8M in cost savings through operational efficiency improvements",
                "Led digital transformation project resulting in 35% improvement in customer satisfaction",
                "Built financial model that accurately predicted quarterly revenue within 2% margin",
                "Negotiated $5M strategic partnership deal with key technology vendor"
            ]
        },
        "metrics": {
            "tech": [
                {"API Response Time": "Improved from 2.3s to 0.9s average response time"},
                {"Code Coverage": "Increased test coverage from 45% to 89% across all services"},
                {"System Uptime": "Maintained 99.95% uptime for production systems"},
                {"User Growth": "Supported platform scaling from 50k to 500k monthly active users"},
                {"Deploy Frequency": "Increased from weekly to daily deployments with zero downtime"}
            ],
            "non_tech": [
                {"Student Achievement": "25% increase in standardized test scores over 2 years"},
                {"Patient Satisfaction": "Consistently scored 4.8/5.0 on patient care surveys"},
                {"Project Completion": "Delivered 18 design projects on time and under budget"},
                {"Class Size": "Successfully managed classrooms of 25-30 students"},
                {"Readmission Rate": "Reduced cardiac unit readmissions from 12% to 8%"}
            ],
            "business": [
                {"Revenue Growth": "$2.5M territory grew to $3.8M over 18 months (52% increase)"},
                {"Cost Savings": "Identified and implemented $2.8M in operational efficiencies"},
                {"Client Retention": "Maintained 95% client retention rate across portfolio"},
                {"Forecast Accuracy": "Financial models achieved 98% accuracy for quarterly projections"},
                {"Deal Closure": "Converted 23% of qualified leads to closed deals"}
            ]
        }
    }
    
    data_pool = child_data_templates.get(child_type, {}).get(background, [])
    if not data_pool:
        # Fallback generic data
        data_pool = ["Generic experience item", "Standard responsibility", "Basic achievement"]
    
    if isinstance(data_pool[0], dict):
        # Skills or tools format
        selected = random.choice(data_pool)
        skill_name, description = list(selected.items())[0]
        return {
            "parent_experience_id": parent_id,
            "person_id": person_id,
            "child_type": child_type,
            "label": skill_name,
            "value": {"description": description, "level": random.choice(["Beginner", "Intermediate", "Advanced", "Expert"])},
            "confidence_score": round(random.uniform(0.75, 0.95), 2),
            "search_phrases": [skill_name, child_type],
            "search_document": f"{skill_name}: {description}"
        }
    elif isinstance(data_pool[0], str):
        # Responsibilities, achievements format
        selected = random.choice(data_pool)
        return {
            "parent_experience_id": parent_id,
            "person_id": person_id,
            "child_type": child_type,
            "label": selected[:100] + "..." if len(selected) > 100 else selected,
            "value": {"description": selected, "impact": random.choice(["High", "Medium", "Significant"])},
            "confidence_score": round(random.uniform(0.8, 0.98), 2),
            "search_phrases": [child_type],
            "search_document": selected
        }
    else:
        # Metrics format
        selected = random.choice(data_pool)
        metric_name, value = list(selected.items())[0]
        return {
            "parent_experience_id": parent_id,
            "person_id": person_id,
            "child_type": child_type,
            "label": metric_name,
            "value": {"metric": metric_name, "result": value, "measurement_period": "Annual"},
            "confidence_score": round(random.uniform(0.85, 0.99), 2),
            "search_phrases": [metric_name, "metrics", child_type],
            "search_document": f"{metric_name}: {value}"
        }


def generate_experience_cards_with_children(person_id: str, background: str, count: int) -> tuple[list[dict], list[dict]]:
    """Generate parent experience cards and their children with detailed, messy raw text."""
    parent_cards = []
    child_cards = []
    
    if background == "tech":
        roles, companies, domains = TECH_ROLES, TECH_COMPANIES, TECH_DOMAINS
    elif background == "non_tech":
        roles, companies, domains = NONTECH_ROLES, NONTECH_COMPANIES, NONTECH_DOMAINS
    else:
        roles, companies, domains = BUSINESS_ROLES, BUSINESS_COMPANIES, BUSINESS_DOMAINS

    used_pairs: set[tuple[str, str]] = set()
    for _ in range(count):
        role = random.choice(roles)
        company = random.choice(companies)
        if (role, company) in used_pairs and len(used_pairs) < len(roles) * len(companies) // 2:
            role = random.choice(roles)
            company = random.choice(companies)
        used_pairs.add((role, company))

        start = random_date_in_range(date(2015, 1, 1), date(2022, 6, 1))
        end = random_date_in_range(start + timedelta(days=180), date(2025, 12, 31))
        is_current = random.random() < 0.3

        domain = random.choice(domains)
        sub_domain = f"{domain} - {random.choice(['Core', 'Operations', 'Strategy', 'Delivery'])}" if random.random() < 0.5 else None
        
        # Generate messy, detailed raw text
        messy_raw_text = generate_messy_raw_text(role, company, background, start, end)
        
        summary = f"Delivered impact in {domain} at {company}. Focused on {role} responsibilities with cross-functional collaboration and measurable results."
        search_doc = f"{role} {company} {domain} {summary} {messy_raw_text[:200]}..."
        search_phrases = [role, company, domain] + ([sub_domain] if sub_domain else [])

        # Create parent card with temporary ID (we'll get real ID after insert)
        parent_card = {
            "person_id": person_id,
            "title": f"{role} at {company}",
            "normalized_role": role,
            "domain": domain,
            "sub_domain": sub_domain,
            "company_name": company,
            "company_type": random.choice(["startup", "enterprise", "nonprofit", "government", "agency", "corporate"]),
            "start_date": start,
            "end_date": end,
            "is_current": is_current,
            "location": random.choice(LOCATIONS),
            "employment_type": random.choice(EMPLOYMENT_TYPES),
            "summary": summary,
            "raw_text": messy_raw_text,  # Much more detailed and messy!
            "intent_primary": random.choice(INTENTS),
            "intent_secondary": [],
            "seniority_level": random.choice(SENIORITY_LEVELS),
            "confidence_score": round(random.uniform(0.7, 1.0), 2),
            "visibility": True,
            "search_phrases": search_phrases,
            "search_document": search_doc,
            "_temp_children": []  # We'll populate this and remove before DB insert
        }
        
        # Generate 2-4 child cards for each parent
        num_children = random.randint(2, 4)
        selected_child_types = random.sample(list(ALLOWED_CHILD_TYPES), min(num_children, len(ALLOWED_CHILD_TYPES)))
        
        for child_type in selected_child_types:
            child_card = generate_child_card_data("PLACEHOLDER", person_id, child_type, background)
            parent_card["_temp_children"].append(child_card)
        
        parent_cards.append(parent_card)
    
    return parent_cards, child_cards


async def run_seed():
    hashed = hash_password(SEED_PASSWORD)
    async with async_session() as session:
        for i in range(NUM_USERS):
            background = random.choices(BACKGROUNDS, weights=BACKGROUND_WEIGHTS)[0]
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            display_name = f"{first} {last}"
            email = f"seed.user{i+1}.{background}@example.com"

            person = Person(
                email=email,
                hashed_password=hashed,
                display_name=display_name,
            )
            session.add(person)
            await session.flush()

            session.add(VisibilitySettings(person_id=person.id))
            session.add(ContactDetails(person_id=person.id))
            wallet = CreditWallet(person_id=person.id, balance=SIGNUP_CREDITS)
            session.add(wallet)
            await session.flush()
            session.add(
                CreditLedger(
                    person_id=person.id,
                    amount=SIGNUP_CREDITS,
                    reason="signup",
                    balance_after=SIGNUP_CREDITS,
                )
            )

            bio = Bio(
                person_id=person.id,
                first_name=first,
                last_name=last,
                current_city=random.choice(LOCATIONS).split(",")[0] if random.random() < 0.7 else None,
                current_company=random.choice(
                    TECH_COMPANIES + NONTECH_COMPANIES + BUSINESS_COMPANIES
                ) if random.random() < 0.6 else None,
            )
            session.add(bio)

            # Generate experience cards with children
            num_cards = random.randint(MIN_CARDS_PER_USER, MAX_CARDS_PER_USER)
            parent_cards, _ = generate_experience_cards_with_children(str(person.id), background, num_cards)
            
            # Insert parent cards first
            for parent_data in parent_cards:
                temp_children = parent_data.pop("_temp_children")  # Remove temp children data
                parent_card = ExperienceCard(**parent_data)
                session.add(parent_card)
                await session.flush()  # Get the actual parent ID
                
                # Now insert children with real parent ID
                for child_data in temp_children:
                    child_data["parent_experience_id"] = str(parent_card.id)
                    session.add(ExperienceCardChild(**child_data))

            if (i + 1) % 20 == 0:
                logger.info("Progress: seeded %s/%s users", i + 1, NUM_USERS)
                await session.commit()

        await session.commit()

    total_parent_cards = NUM_USERS * (MIN_CARDS_PER_USER + MAX_CARDS_PER_USER) // 2  # Average
    total_child_cards = total_parent_cards * 3  # Average 3 children per parent

    logger.info("Done. Seeded %s users with detailed experience data", NUM_USERS)
    logger.info("  Parent cards: %s-%s per user (~%s total)", MIN_CARDS_PER_USER, MAX_CARDS_PER_USER, total_parent_cards)
    logger.info("  Child cards: 2-4 per parent (~%s total)", total_child_cards)
    logger.info("  Password for all seed users: %s", SEED_PASSWORD)
    logger.info("  Example logins: seed.user1.tech@example.com, seed.user25.non_tech@example.com, seed.user50.business@example.com")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Starting template seed: %s users, %s-%s cards per user", NUM_USERS, MIN_CARDS_PER_USER, MAX_CARDS_PER_USER)
    asyncio.run(run_seed())
