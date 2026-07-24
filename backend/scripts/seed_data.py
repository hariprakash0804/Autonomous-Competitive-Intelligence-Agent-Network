import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.database import SessionLocal
from app.models.user import User
from app.models.competitor import Competitor
from app.dependencies.auth import hash_password

SEED_USER_EMAIL = "admin@example.com"
SEED_USER_PASS = "admin123456"

COMPETITORS_DATA = [
    {
        "name": "GitHub",
        "pricing_url": "https://github.com/pricing",
        "review_urls": ["https://github.com/about"],
        "news_keywords": ["https://github.blog/"],
    },
    {
        "name": "Supabase",
        "pricing_url": "https://supabase.com/pricing",
        "review_urls": ["https://supabase.com/docs"],
        "news_keywords": ["https://supabase.com/blog"],
    },
    {
        "name": "Python Software Foundation",
        "pricing_url": "https://www.python.org/psf/donations/",
        "review_urls": ["https://www.python.org/about/"],
        "news_keywords": ["https://www.python.org/blogs/"],
    },
    {
        "name": "JS-Shell Target (Stale Test)",
        "pricing_url": "https://client.schwab.com/",  # Real HTTP 200 JS-shell SPA page matching 'enable javascript'
        "review_urls": ["https://httpbin.org/status/500"], # Will trigger status 500 -> is_stale=True
        "news_keywords": ["https://httpbin.org/bytes/10"],  # Extremely short content -> is_stale=True
    },
]


def seed_database():
    db = SessionLocal()
    try:
        # Check or create seed user
        user = db.scalars(select(User).where(User.email == SEED_USER_EMAIL)).first()
        if not user:
            user = User(
                email=SEED_USER_EMAIL,
                hashed_password=hash_password(SEED_USER_PASS),
                name="Admin User",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created seed user: {user.email} (ID: {user.id})")
        else:
            print(f"Using existing seed user: {user.email} (ID: {user.id})")

        # Seed competitors
        created_count = 0
        for comp_data in COMPETITORS_DATA:
            existing = db.scalars(
                select(Competitor).where(
                    Competitor.user_id == user.id,
                    Competitor.name == comp_data["name"],
                )
            ).first()

            if not existing:
                comp = Competitor(
                    user_id=user.id,
                    name=comp_data["name"],
                    pricing_url=comp_data["pricing_url"],
                    review_urls=comp_data["review_urls"],
                    news_keywords=comp_data["news_keywords"],
                )
                db.add(comp)
                created_count += 1
                print(f"Added competitor: {comp_data['name']}")
            else:
                # Update URLs in case seed updated
                existing.pricing_url = comp_data["pricing_url"]
                existing.review_urls = comp_data["review_urls"]
                existing.news_keywords = comp_data["news_keywords"]
                print(f"Updated competitor: {comp_data['name']} (ID: {existing.id})")

        db.commit()
        print(f"Seeding finished. Synchronized {len(COMPETITORS_DATA)} competitors.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
