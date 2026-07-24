import os
import json
import uuid
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import faiss
import numpy as np

INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "faiss_data"
INDEX_FILE = INDEX_DIR / "index.faiss"
METADATA_FILE = INDEX_DIR / "metadata.json"

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class VectorStoreService:
    def __init__(self):
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        self.model = None  # Lazy load to conserve startup RAM
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_create_index()

    def _get_model(self):
        """Lazy loads SentenceTransformer to keep startup RAM under 150MB."""
        if self.model is None:
            try:
                print("[Vector Store] Lazy loading SentenceTransformer model...")
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(MODEL_NAME)
            except Exception as e:
                print(f"[Vector Store Warning] Failed to load SentenceTransformer ({e}). Using lightweight hash vectorizer fallback.")
                self.model = "fallback"
        return self.model

    def _hash_encode(self, texts: List[str]) -> np.ndarray:
        """Lightweight 384-dim normalized term hashing vectorizer for ultra-low RAM footprint (<10MB RAM)."""
        vectors = []
        for text in texts:
            words = re.findall(r"\w+", text.lower())
            vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
            for w in words:
                h = hash(w) % EMBEDDING_DIM
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)

    def _encode_text(self, texts: List[str]) -> np.ndarray:
        model = self._get_model()
        if model != "fallback":
            try:
                embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.astype(np.float32)
            except Exception as exc:
                print(f"[Vector Store Warning] Model encode failed ({exc}). Using hash vectorizer fallback.")
        return self._hash_encode(texts)

    def _load_or_create_index(self):
        if INDEX_FILE.exists() and METADATA_FILE.exists():
            try:
                self.index = faiss.read_index(str(INDEX_FILE))
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                return
            except Exception as e:
                print(f"Warning: Failed to load FAISS index ({e}). Creating a new one.")

        self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
        self.metadata = []
        self._save_index()

    def _save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_FILE))
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)

    def chunk_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        if not text:
            return []
        
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = f"{current_chunk}\n\n{para}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                if len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size - chunk_overlap):
                        chunks.append(para[i : i + chunk_size])
                    current_chunk = ""
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def add_snapshot_chunks(
        self,
        snapshot_id: str,
        competitor_id: str,
        source_type: str,
        fetched_at: str,
        text: str,
    ) -> int:
        chunks = self.chunk_text(text)
        if not chunks:
            return 0

        embeddings = self._encode_text(chunks)
        self.index.add(embeddings)

        for i, chunk in enumerate(chunks):
            meta = {
                "chunk_id": str(uuid.uuid4()),
                "snapshot_id": snapshot_id,
                "competitor_id": competitor_id,
                "source_type": source_type,
                "fetched_at": fetched_at,
                "chunk_text": chunk,
            }
            self.metadata.append(meta)

        self._save_index()
        return len(chunks)

    def search(
        self,
        query: str,
        competitor_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        if not query or self.index is None or self.index.ntotal == 0:
            return []

        query_vec = self._encode_text([query])

        search_k = min(top_k * 5 if competitor_id else top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = self.metadata[idx]
            if competitor_id and meta.get("competitor_id") != str(competitor_id):
                continue
            
            res = dict(meta)
            res["similarity_score"] = float(score)
            results.append(res)
            if len(results) >= top_k:
                break

        return results


# Global singleton instance
vector_store = VectorStoreService()
