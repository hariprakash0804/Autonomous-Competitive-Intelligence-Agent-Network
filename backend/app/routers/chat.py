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
    chat_history: Optional[List[Dict[str, Any]]] = None
    image_url: Optional[str] = None
    media_filename: Optional[str] = None
    media_type: Optional[str] = None  # "image" | "document" | "pdf" | "text"
    media_content: Optional[str] = None  # Extracted text content from attached document


@router.post("/")
def chat_query(
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    RAG Endpoint: Retrieves top-k FAISS vector chunks for a competitor,
    enforces prompt context boundaries, and returns the grounded answer
    plus cited snapshot timestamps.
    Supports Conversation Memory (chat history), Image Attachments, and Document Attachments.
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

    # Generate grounded RAG answer with Chat Memory, Image, and Document Context
    answer, cited_snapshots = generate_rag_answer(
        question=payload.question,
        retrieved_chunks=retrieved_chunks,
        chat_history=payload.chat_history,
        image_url=payload.image_url,
        media_filename=payload.media_filename,
        media_type=payload.media_type,
        media_content=payload.media_content,
    )

    return {
        "question": payload.question,
        "competitor_id": comp_id_str,
        "answer": answer,
        "cited_snapshots": cited_snapshots,
        "media_attached": bool(payload.image_url or payload.media_filename or payload.media_content),
    }


@router.get("/faiss-status")
def get_faiss_status(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Diagnostic Endpoint: Returns live FAISS vector store statistics on Render:
    - Total indexed vectors count
    - Active embedding mode & dimension
    - Distribution of chunks by source type
    - Recent chunk previews
    """
    total_vectors = vector_store.index.ntotal if vector_store.index is not None else 0
    active_dim = vector_store.index.d if vector_store.index is not None else 0
    embedding_mode = getattr(vector_store, "_embedding_mode", "unknown")

    competitor_counts: Dict[str, int] = {}
    source_type_counts: Dict[str, int] = {}

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
