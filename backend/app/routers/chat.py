import uuid
from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.competitor import Competitor
from app.models.report import Report
from app.models.snapshot import Snapshot
from app.services.vector_store import vector_store
from app.services.llm import generate_rag_answer

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    competitor_id: Optional[str] = None
    question: str


@router.post("/")
def chat_query(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    RAG Endpoint: Retrieves top-k FAISS vector chunks for a competitor,
    enforces prompt context boundaries, and returns the grounded answer
    plus cited snapshot timestamps. Falls back to DB reports & snapshots if FAISS is unindexed.
    """
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")

    comp_id_str = None
    target_competitor = None
    if payload.competitor_id:
        try:
            c_uuid = uuid.UUID(payload.competitor_id)
            target_competitor = db.get(Competitor, c_uuid)
            if not target_competitor or target_competitor.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
            comp_id_str = str(c_uuid)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid competitor UUID")

    # Retrieve top-6 FAISS chunks matching query (section-aware chunks for coherent context)
    retrieved_chunks = vector_store.search(
        query=payload.question,
        competitor_id=comp_id_str,
        top_k=6,
    )

    # Context enrichment: If FAISS index has 0 chunks for this competitor, query DB reports/snapshots
    if not retrieved_chunks and target_competitor:
        reports = db.query(Report).filter(Report.competitor_id == target_competitor.id).order_by(Report.generated_at.desc()).all()
        snapshots = db.query(Snapshot).filter(Snapshot.competitor_id == target_competitor.id).order_by(Snapshot.fetched_at.desc()).all()

        fallback_texts = []
        if reports:
            for r in reports[:2]:
                if r.summary:
                    fallback_texts.append(f"Executive Analysis Report for {target_competitor.name}:\n{r.summary}")
        if snapshots:
            for s in snapshots[:3]:
                if s.raw_content:
                    fallback_texts.append(f"Snapshot ({s.source_type.value if hasattr(s.source_type, 'value') else s.source_type} fetched {s.fetched_at}):\n{s.raw_content[:1500]}")

        # If no reports or snapshots exist yet, construct target profile intelligence context
        if not fallback_texts:
            fallback_texts.append(
                f"Competitor Target Profile: {target_competitor.name}\n"
                f"Domain: {target_competitor.domain or 'N/A'}\n"
                f"Pricing Page URL: {target_competitor.pricing_url or 'N/A'}\n"
                f"Company URL: {target_competitor.company_url or 'N/A'}\n"
                f"Tracked Keywords: {', '.join(target_competitor.news_keywords or [target_competitor.name])}"
            )

        for idx, text in enumerate(fallback_texts):
            retrieved_chunks.append({
                "snapshot_id": f"DB-RECORD-{idx+1}",
                "fetched_at": str(target_competitor.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(target_competitor.created_at, "strftime") else target_competitor.created_at),
                "source_type": "database_intelligence",
                "chunk_text": text,
            })

    # Generate grounded RAG answer
    answer, cited_snapshots = generate_rag_answer(payload.question, retrieved_chunks)

    return {
        "question": payload.question,
        "competitor_id": comp_id_str,
        "answer": answer,
        "cited_snapshots": cited_snapshots,
    }
