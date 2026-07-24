import sys
import json
from pathlib import Path

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env", override=True)

import app.config as config_module
config_module.settings = config_module.Settings()

from sqlalchemy import select
from app.database import SessionLocal
from app.models.competitor import Competitor
from app.services.vector_store import vector_store
from app.services.llm import generate_rag_answer


def main():
    db = SessionLocal()
    try:
        github = db.scalars(select(Competitor).where(Competitor.name == "GitHub")).first()
        supabase = db.scalars(select(Competitor).where(Competitor.name == "Supabase")).first()

        print("=========================================================================")
        print("PHASE 4 STOP GATE VERIFICATION: RAG CHAT & CITATION TEST SUITE")
        print("=========================================================================\n")

        test_cases = [
            {
                "label": "Test Case 1: Grounded Pricing Question (GitHub)",
                "competitor": github,
                "question": "What are the pricing tiers and plans for GitHub?",
            },
            {
                "label": "Test Case 2: Grounded Feature & Price Question (Supabase)",
                "competitor": supabase,
                "question": "What is the price of the Supabase Pro plan and what is included in it?",
            },
            {
                "label": "Test Case 3: Out-of-Context Negative Test (Strict Boundaries)",
                "competitor": github,
                "question": "Does GitHub offer automated cryptocurrency stock trading software?",
            },
        ]

        for case in test_cases:
            print(f"-------------------------------------------------------------------------")
            print(f"{case['label']}")
            print(f"Competitor : {case['competitor'].name if case['competitor'] else 'Global'}")
            print(f"Question   : '{case['question']}'\n")

            comp_id_str = str(case['competitor'].id) if case['competitor'] else None

            # Retrieve vector chunks
            chunks = vector_store.search(
                query=case['question'],
                competitor_id=comp_id_str,
                top_k=4,
            )

            # Generate RAG answer
            answer, citations = generate_rag_answer(case['question'], chunks)

            print("--- CITED SNAPSHOT DATES & SOURCES ---")
            if citations:
                for c in citations:
                    print(f"  • Date: {c['fetched_at']} | Source: {c['source_type']} | ID: {c['snapshot_id']}")
            else:
                print("  • No relevant snapshots found in vector store.")

            print("\n--- GROUNDED ANSWER ---")
            print(f"{answer}\n")

        print("=========================================================================")
        print("PHASE 4 RAG CHAT STOP GATE VERIFICATION COMPLETE")
        print("=========================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    main()
