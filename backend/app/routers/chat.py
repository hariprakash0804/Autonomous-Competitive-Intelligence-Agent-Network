import uuid
from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.competitor import Competitor
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
    enforces strict prompt context boundaries, and returns the grounded answer
    plus cited snapshot timestamps.
    """
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question cannot be empty")

    comp_id_str = None
    if payload.competitor_id:
        try:
            c_uuid = uuid.UUID(payload.competitor_id)
            competitor = db.get(Competitor, c_uuid)
            if not competitor or competitor.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
            comp_id_str = str(c_uuid)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid competitor UUID")

    # Retrieve top-4 FAISS chunks matching query
    retrieved_chunks = vector_store.search(
        query=payload.question,
        competitor_id=comp_id_str,
        top_k=4,
    )

    # Generate grounded RAG answer
    answer, cited_snapshots = generate_rag_answer(payload.question, retrieved_chunks)

    return {
        "question": payload.question,
        "competitor_id": comp_id_str,
        "answer": answer,
        "cited_snapshots": cited_snapshots,
    }
