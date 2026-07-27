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
