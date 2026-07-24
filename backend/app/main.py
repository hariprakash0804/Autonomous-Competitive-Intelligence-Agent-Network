from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import auth, competitors, snapshots, reports, chat, pipeline

app = FastAPI(
    title="Competitive Intelligence Agent Network",
    description="Autonomous multi-agent system for competitive intelligence gathering and analysis",
    version="0.1.0",
)

# Static files directory for rendered HTML reports
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
