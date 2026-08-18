import uuid
import faiss
import pytest
from app.services.vector_store import VectorStoreService, UNIFIED_EMBED_DIM


def test_vector_store_hash_mode_and_search(tmp_path):
    vs = VectorStoreService()
    vs.model = "fallback"
    vs._embedding_mode = "hash"
    vs._active_dim = UNIFIED_EMBED_DIM
    vs.index = faiss.IndexFlatIP(UNIFIED_EMBED_DIM)
    vs.metadata = []

    comp_id_1 = str(uuid.uuid4())
    comp_id_2 = str(uuid.uuid4())

    # Add chunk for Competitor 1
    vs.add_snapshot_chunks(
        snapshot_id=str(uuid.uuid4()),
        competitor_id=comp_id_1,
        source_type="PRICING",
        text="Stripe payments processing enterprise billing tier $29 monthly",
        fetched_at="2026-08-18T00:00:00Z",
        defer_save=True,
    )

    # Add chunk for Competitor 2
    vs.add_snapshot_chunks(
        snapshot_id=str(uuid.uuid4()),
        competitor_id=comp_id_2,
        source_type="NEWS",
        text="Linear launches project management updates and keyboard shortcuts",
        fetched_at="2026-08-18T00:00:00Z",
        defer_save=True,
    )

    # Search isolated to Competitor 1
    results = vs.search(
        query="payments billing tier",
        competitor_id=comp_id_1,
        allowed_competitor_ids=[comp_id_1],
        top_k=5,
    )
    assert len(results) >= 1
    assert all(r["competitor_id"] == comp_id_1 for r in results)

    # Search with multi-tenant filtering (excluding Competitor 2)
    filtered = vs.search(
        query="project management",
        allowed_competitor_ids=[comp_id_1],  # Only allowed to see comp 1
        top_k=5,
    )
    assert not any(r["competitor_id"] == comp_id_2 for r in filtered)


def test_faiss_status_endpoint(client):
    response = client.get("/faiss-status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "total_vectors" in data
    assert "embedding_dimension" in data
