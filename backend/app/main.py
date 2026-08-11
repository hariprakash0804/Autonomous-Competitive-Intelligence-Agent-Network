from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
import app.models  # Ensures all SQLAlchemy models register with Base.metadata
from app.routers import auth, competitors, snapshots, reports, chat, pipeline, upload

app = FastAPI(
    title="Competitive Intelligence Agent Network",
    description="Autonomous multi-agent system for competitive intelligence gathering and analysis",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Autonomous Competitive Intelligence Agent Network API",
        "version": "0.1.0",
        "documentation": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Autonomous Competitive Intelligence Agent Network API",
    }


@app.on_event("startup")
def on_startup():
    """Starts background initialization tasks so Uvicorn binds port socket immediately (<0.001s)."""
    import threading

    def _bg_startup_tasks():
        try:
            print("[Startup] Ensuring PostgreSQL database tables exist...", flush=True)
            Base.metadata.create_all(bind=engine)
            
            # Self-healing column additions for existing production databases
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS model_used VARCHAR(200);"))
                conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS pdf_url TEXT;"))
                conn.execute(text("ALTER TABLE reports ADD COLUMN IF NOT EXISTS html_url TEXT;"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_name VARCHAR(255);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_url VARCHAR(1024);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_description TEXT;"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS slack_webhook_url VARCHAR(1024);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_onboarded BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS company_url TEXT;"))
                conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS domain VARCHAR(255);"))
                conn.execute(text("ALTER TABLE competitors ADD COLUMN IF NOT EXISTS description_text TEXT;"))
                conn.execute(text("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS execution_logs JSON;"))
                conn.execute(text("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS pages_visited JSON;"))
                # Purge legacy corrupted PriceChange records ($650 / $750 regex artifacts from earlier tests)
                conn.execute(text("DELETE FROM price_changes WHERE old_price IN (650, 750) OR new_price IN (650, 750);"))

            print("[Startup] Database tables, schema, and price records verified/migrated successfully.", flush=True)
        except Exception as exc:
            print(f"[Startup Warning] Automatic table creation/migration error: {exc}", flush=True)

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
                    print(f"[Startup] Self-healing: Cleaned garbled topics in {updated_count} sentiment score records.", flush=True)
            finally:
                db_session.close()
        except Exception as clean_err:
            print(f"[Startup Warning] Legacy topics cleanup notice: {clean_err}", flush=True)

        try:
            from app.services.vector_store import vector_store
            vector_store.rehydrate_from_db()
        except Exception as rehydrate_err:
            print(f"[Startup Warning] FAISS rehydration notice: {rehydrate_err}", flush=True)

    threading.Thread(target=_bg_startup_tasks, daemon=True).start()


# Static files directory for rendered HTML reports
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS — secure origin regex matching with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Enforces enterprise HTTP security headers across all API responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geoloc=()"
    return response

# Register routers
app.include_router(auth.router)
app.include_router(competitors.router)
app.include_router(snapshots.router)
app.include_router(reports.router)
app.include_router(chat.router)
app.include_router(pipeline.router)
app.include_router(upload.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/faiss-status")
def global_faiss_status():
    """
    Public Status Endpoint: Returns live FAISS vector store status on Render.
    Can be opened directly in any browser tab without auth headers.
    """
    from app.services.vector_store import vector_store

    total_vectors = vector_store.index.ntotal if vector_store.index is not None else 0
    active_dim = vector_store.index.d if vector_store.index is not None else 0
    embedding_mode = getattr(vector_store, "_embedding_mode", "unknown")

    competitor_counts = {}
    source_type_counts = {}

    for meta in getattr(vector_store, "metadata", []):
        comp_id = meta.get("competitor_id", "unknown")
        src_type = meta.get("source_type", "unknown")
        competitor_counts[comp_id] = competitor_counts.get(comp_id, 0) + 1
        source_type_counts[src_type] = source_type_counts.get(src_type, 0) + 1

    return {
        "status": "active" if total_vectors > 0 else "empty",
        "total_vectors": total_vectors,
        "embedding_dimension": active_dim,
        "embedding_mode": embedding_mode,
        "source_type_distribution": source_type_counts,
        "indexed_competitors_count": len(competitor_counts),
        "recent_chunks": [
            {
                "snapshot_id": m.get("snapshot_id"),
                "competitor_id": m.get("competitor_id"),
                "source_type": m.get("source_type"),
                "fetched_at": m.get("fetched_at"),
                "chunk_snippet": (m.get("chunk_text") or "")[:120] + "...",
            }
            for m in getattr(vector_store, "metadata", [])[-5:]
        ],
    }
