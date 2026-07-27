from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
import app.models  # Ensures all SQLAlchemy models register with Base.metadata
from app.routers import auth, competitors, snapshots, reports, chat, pipeline

app = FastAPI(
    title="Competitive Intelligence Agent Network",
    description="Autonomous multi-agent system for competitive intelligence gathering and analysis",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup():
    """Ensures PostgreSQL database tables exist and schema migrations are applied automatically on startup."""
    try:
        print("[Startup] Ensuring PostgreSQL database tables exist...")
        Base.metadata.create_all(bind=engine)
        
        # Self-healing column additions for existing production databases
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS model_used VARCHAR(200);"))
            conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS pdf_url TEXT;"))
            conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS html_url TEXT;"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);"))
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_url VARCHAR(1024);"))
            conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS company_url TEXT;"))
            conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS domain VARCHAR(255);"))

        # Self-healing cleanup for legacy garbled topics in sentiment_scores
        try:
            from app.database import SessionLocal
            from app.models.sentiment_score import SentimentScore
            from app.services.sentiment import _is_valid_topic_word, STOP_WORDS
            db_session = SessionLocal()
            try:
                scores = db_session.query(SentimentScore).all()
                updated_count = 0
                for s in scores:
                    if s.topics:
                        clean_t = [
                            t for t in s.topics
                            if t and t.lower() not in STOP_WORDS and _is_valid_topic_word(t)
                        ]
                        if not clean_t:
                            clean_t = ["overview", "features", "pricing", "platform"]
                        if clean_t != s.topics:
                            s.topics = clean_t
                            updated_count += 1
                if updated_count > 0:
                    db_session.commit()
                    print(f"[Startup] Self-healing: Cleaned garbled topics in {updated_count} sentiment score records.")
            finally:
                db_session.close()
        except Exception as clean_err:
            print(f"[Startup Warning] Legacy topics cleanup notice: {clean_err}")

        print("[Startup] Database tables and schema verified/migrated successfully.")
    except Exception as exc:
        print(f"[Startup Warning] Automatic table creation/migration error: {exc}")


# Static files directory for rendered HTML reports
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS — allow all origins for production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(competitors.router)
app.include_router(snapshots.router)
app.include_router(reports.router)
app.include_router(chat.router)
app.include_router(pipeline.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
