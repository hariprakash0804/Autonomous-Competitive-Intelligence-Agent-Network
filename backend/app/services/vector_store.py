import os
import json
import uuid
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx
import faiss
import numpy as np

from app.config import settings

INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "faiss_data"
INDEX_FILE = INDEX_DIR / "index.faiss"
METADATA_FILE = INDEX_DIR / "metadata.json"
DIM_FILE = INDEX_DIR / "dim.json"

# Primary: OpenRouter free embedding model
OPENROUTER_EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
OPENROUTER_EMBED_DIM = 2048
OPENROUTER_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"

# Fallback: HuggingFace Inference API
HF_MODEL_NAME = "all-MiniLM-L6-v2"
HF_EMBEDDING_DIM = 384
HF_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/{HF_MODEL_NAME}"

# Default dimension (set dynamically based on active embedding mode)
EMBEDDING_DIM = OPENROUTER_EMBED_DIM


class VectorStoreService:
    def __init__(self):
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        self.model = None  # Lazy load to conserve startup RAM
        self._embedding_mode = None  # Will be set by _get_model: "openrouter", "hf_api", "local", or "hash"
        self._active_dim = OPENROUTER_EMBED_DIM  # Active embedding dimension
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_create_index()

    def _get_model(self):
        """
        Determines embedding mode in order of preference:
        1. OpenRouter embedding API (nvidia/llama-nemotron-embed-vl-1b-v2:free) — if LLM_API_KEY is set
        2. HuggingFace Inference API (all-MiniLM-L6-v2) — if HF_API_TOKEN is set
        3. Local SentenceTransformer — if installable within 15s
        4. Hash vectorizer fallback — instant, no API calls
        """
        if self.model is None:
            store_mode = (settings.VECTOR_STORE_MODE or os.environ.get("VECTOR_STORE_MODE", "auto")).lower().strip()
            openrouter_key = settings.LLM_API_KEY or os.environ.get("LLM_API_KEY", "")
            hf_token = settings.HF_API_TOKEN or os.environ.get("HF_API_TOKEN", "")

            # ── Mode: hash (instant, no network) ────────────────────────────
            if store_mode == "hash":
                print("[Vector Store] VECTOR_STORE_MODE=hash → using instant hash vectorizer.", flush=True)
                self.model = "fallback"
                self._embedding_mode = "hash"
                self._active_dim = OPENROUTER_EMBED_DIM
                return self.model

            # ── Priority 1: OpenRouter Embedding API (free, 2048-dim) ────────
            if openrouter_key and store_mode in ("auto", "openrouter"):
                if self._check_openrouter_embed_connectivity(openrouter_key):
                    print(f"[Vector Store] Using OpenRouter Embedding API (model: {OPENROUTER_EMBED_MODEL}, dim: {OPENROUTER_EMBED_DIM}).", flush=True)
                    self.model = "openrouter"
                    self._embedding_mode = "openrouter"
                    self._active_dim = OPENROUTER_EMBED_DIM
                    self._ensure_index_dimension(OPENROUTER_EMBED_DIM)
                    return self.model
                else:
                    print("[Vector Store] OpenRouter Embedding API unreachable. Trying fallbacks...", flush=True)

            # ── Priority 2: HuggingFace Inference API (free, 384-dim) ────────
            if hf_token and store_mode in ("auto", "hf_api"):
                if self._check_hf_api_connectivity(hf_token):
                    print(f"[Vector Store] Using HuggingFace Inference API for embeddings (model: {HF_MODEL_NAME}).", flush=True)
                    self.model = "hf_api"
                    self._embedding_mode = "hf_api"
                    self._active_dim = HF_EMBEDDING_DIM
                    self._ensure_index_dimension(HF_EMBEDDING_DIM)
                    return self.model
                else:
                    print("[Vector Store] HF API unreachable. Trying fallbacks...", flush=True)

            # ── Priority 3: Local SentenceTransformer (15s timeout) ──────────
            if store_mode == "auto":
                try:
                    from concurrent.futures import ThreadPoolExecutor

                    def _load_model():
                        from sentence_transformers import SentenceTransformer
                        return SentenceTransformer(HF_MODEL_NAME)

                    print("[Vector Store] Loading SentenceTransformer model (15s timeout)...", flush=True)
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_load_model)
                        self.model = future.result(timeout=15.0)
                    self._embedding_mode = "local"
                    self._active_dim = HF_EMBEDDING_DIM
                    self._ensure_index_dimension(HF_EMBEDDING_DIM)
                    print("[Vector Store] SentenceTransformer loaded successfully.", flush=True)
                    return self.model
                except Exception as e:
                    timeout_msg = "TIMED OUT" if "TimeoutError" in type(e).__name__ or "timeout" in str(e).lower() else f"failed ({e})"
                    print(f"[Vector Store] SentenceTransformer {timeout_msg}. Using hash vectorizer.", flush=True)

            # ── Priority 4: Hash vectorizer fallback ─────────────────────────
            print("[Vector Store] Using hash vectorizer fallback.", flush=True)
            self.model = "fallback"
            self._embedding_mode = "hash"
            self._active_dim = OPENROUTER_EMBED_DIM

        return self.model

    def _check_openrouter_embed_connectivity(self, api_key: str) -> bool:
        """Quick connectivity check to OpenRouter Embedding API."""
        try:
            response = httpx.post(
                OPENROUTER_EMBED_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": OPENROUTER_EMBED_MODEL, "input": ["connectivity test"]},
                timeout=8.0,
            )
            return response.status_code == 200 and "data" in response.json()
        except Exception as e:
            print(f"[Vector Store] OpenRouter embed connectivity check failed: {e}", flush=True)
            return False

    def _check_hf_api_connectivity(self, hf_token: str) -> bool:
        """Quick connectivity check to HuggingFace API."""
        try:
            response = httpx.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": "test", "options": {"wait_for_model": False}},
                timeout=5.0,
            )
            return True
        except Exception as e:
            print(f"[Vector Store] HF API connectivity check failed: {e}", flush=True)
            return False

    @staticmethod
    def _is_unrecoverable_error(exc: Exception) -> bool:
        """Detects DNS failures, connection refused, and other errors that won't resolve on retry."""
        err_msg = str(exc).lower()
        unrecoverable_patterns = [
            "no address associated with hostname",
            "name or service not known",
            "nodename nor servname provided",
            "getaddrinfo failed",
            "connection refused",
            "network is unreachable",
            "no route to host",
            "ssl: certificate_verify_failed",
        ]
        return any(pattern in err_msg for pattern in unrecoverable_patterns)

    def _openrouter_encode(self, texts: List[str]) -> np.ndarray:
        """
        Calls OpenRouter Embedding API (nvidia/llama-nemotron-embed-vl-1b-v2:free) for
        high-quality 2048-dim semantic embeddings. Batches texts in groups of 8.
        Falls back to hash vectorizer on unrecoverable errors.
        """
        api_key = settings.LLM_API_KEY or os.environ.get("LLM_API_KEY", "")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        all_embeddings = []
        batch_size = 8
        use_hash_fallback = False

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            if use_hash_fallback:
                hash_vecs = self._hash_encode(batch)
                all_embeddings.extend(hash_vecs)
                continue

            # Truncate to 512 chars per text for API efficiency
            batch_truncated = [t[:512] for t in batch]
            batch_succeeded = False

            for attempt in range(3):
                try:
                    response = httpx.post(
                        OPENROUTER_EMBED_URL,
                        headers=headers,
                        json={"model": OPENROUTER_EMBED_MODEL, "input": batch_truncated},
                        timeout=15.0,
                    )

                    if response.status_code == 429:
                        print("[Vector Store] OpenRouter embed rate limited, waiting 2s...", flush=True)
                        time.sleep(2.0)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    for item in data.get("data", []):
                        vec = np.array(item["embedding"], dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec /= norm
                        all_embeddings.append(vec)
                    batch_succeeded = True
                    break

                except Exception as exc:
                    if self._is_unrecoverable_error(exc):
                        print(f"[Vector Store] OpenRouter embed unrecoverable error: {exc}. Switching to hash.", flush=True)
                        use_hash_fallback = True
                        break
                    if attempt < 2:
                        print(f"[Vector Store] OpenRouter embed attempt {attempt + 1} failed: {exc}. Retrying...", flush=True)
                        time.sleep(1.0)
                    else:
                        print(f"[Vector Store] OpenRouter embed failed after 3 attempts: {exc}.", flush=True)

            if not batch_succeeded:
                hash_vecs = self._hash_encode(batch)
                all_embeddings.extend(hash_vecs)

        return np.array(all_embeddings, dtype=np.float32)

    def _hf_api_encode(self, texts: List[str]) -> np.ndarray:
        """
        Calls HuggingFace Inference API for real semantic embeddings.
        Detects unrecoverable errors (DNS, connection) on first failure
        and immediately falls back to hash for ALL remaining batches.
        """
        hf_token = settings.HF_API_TOKEN or os.environ.get("HF_API_TOKEN", "")
        headers = {"Authorization": f"Bearer {hf_token}"}

        all_embeddings = []
        batch_size = 16
        use_hash_fallback = False

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            if use_hash_fallback:
                hash_vecs = self._hash_encode(batch)
                all_embeddings.extend(hash_vecs)
                continue

            batch_truncated = [t[:512] for t in batch]
            batch_succeeded = False

            for attempt in range(3):
                try:
                    response = httpx.post(
                        HF_API_URL,
                        headers=headers,
                        json={"inputs": batch_truncated, "options": {"wait_for_model": True}},
                        timeout=15.0,
                    )

                    if response.status_code == 503:
                        wait = min(float(response.json().get("estimated_time", 5)), 10)
                        print(f"[Vector Store] HF API model loading, waiting {wait:.0f}s...", flush=True)
                        time.sleep(wait)
                        continue

                    if response.status_code == 429:
                        print("[Vector Store] HF API rate limited, waiting 2s...", flush=True)
                        time.sleep(2.0)
                        continue

                    response.raise_for_status()
                    embeddings_batch = response.json()

                    for emb in embeddings_batch:
                        vec = np.array(emb, dtype=np.float32)
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec /= norm
                        all_embeddings.append(vec)
                    batch_succeeded = True
                    break

                except Exception as exc:
                    if self._is_unrecoverable_error(exc):
                        print(f"[Vector Store] HF API unrecoverable error: {exc}. Switching to hash for all batches.", flush=True)
                        use_hash_fallback = True
                        break
                    if attempt < 2:
                        print(f"[Vector Store] HF API attempt {attempt + 1} failed: {exc}. Retrying...", flush=True)
                        time.sleep(1.0)
                    else:
                        print(f"[Vector Store] HF API failed after 3 attempts: {exc}.", flush=True)

            if not batch_succeeded:
                hash_vecs = self._hash_encode(batch)
                all_embeddings.extend(hash_vecs)

        return np.array(all_embeddings, dtype=np.float32)

    def _hash_encode(self, texts: List[str]) -> np.ndarray:
        """Lightweight normalized term hashing vectorizer using active dimension."""
        dim = self._active_dim
        vectors = []
        for text in texts:
            words = re.findall(r"\w+", text.lower())
            vec = np.zeros(dim, dtype=np.float32)
            for w in words:
                h = hash(w) % dim
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)

    def _encode_text(self, texts: List[str]) -> np.ndarray:
        """Routes to the appropriate embedding backend based on current mode."""
        model = self._get_model()

        # OpenRouter Embedding API path (primary)
        if self._embedding_mode == "openrouter":
            try:
                return self._openrouter_encode(texts)
            except Exception as exc:
                print(f"[Vector Store] OpenRouter encode failed ({exc}). Falling back to hash.", flush=True)
                return self._hash_encode(texts)

        # HuggingFace Inference API path
        if self._embedding_mode == "hf_api":
            try:
                return self._hf_api_encode(texts)
            except Exception as exc:
                print(f"[Vector Store] HF API encode failed ({exc}). Falling back to hash.", flush=True)
                return self._hash_encode(texts)

        # Local SentenceTransformer path
        if model not in ("fallback", "hf_api", "openrouter"):
            try:
                embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.astype(np.float32)
            except Exception as exc:
                print(f"[Vector Store Warning] Model encode failed ({exc}). Using hash vectorizer fallback.")

        # Hash vectorizer fallback
        return self._hash_encode(texts)

    def _ensure_index_dimension(self, required_dim: int):
        """Recreates FAISS index if current dimension doesn't match required dimension."""
        if self.index is not None and self.index.d == required_dim:
            return  # Dimension matches, no action needed

        if self.index is not None and self.index.d != required_dim:
            old_dim = self.index.d
            old_count = self.index.ntotal
            print(f"[Vector Store] FAISS dimension mismatch ({old_dim} → {required_dim}). Rebuilding index ({old_count} vectors discarded).", flush=True)
            self.index = faiss.IndexFlatIP(required_dim)
            self.metadata = []
            self._save_index()

    def _load_or_create_index(self):
        if INDEX_FILE.exists() and METADATA_FILE.exists():
            try:
                self.index = faiss.read_index(str(INDEX_FILE))
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                print(f"[Vector Store] Loaded FAISS index: {self.index.ntotal} vectors, dim={self.index.d}", flush=True)
                return
            except Exception as e:
                print(f"Warning: Failed to load FAISS index ({e}). Creating a new one.")

        self.index = faiss.IndexFlatIP(OPENROUTER_EMBED_DIM)
        self.metadata = []
        self._save_index()

    def _save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_FILE))
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2)

    def chunk_text(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
        """
        Two-strategy text chunker:
        1. Markdown section-aware: If text contains '## ' headings, split on headings
           so each chunk is one complete report section (preserving heading context).
        2. Paragraph-based fallback: For raw web pages, accumulate paragraphs up to
           chunk_size (1000 chars) with overlap for long single paragraphs.
        """
        if not text:
            return []

        # ── Strategy 1: Markdown section-aware chunking ──────────────────────
        if "## " in text:
            return self._chunk_by_sections(text, chunk_size)

        # ── Strategy 2: Paragraph-based fallback ─────────────────────────────
        return self._chunk_by_paragraphs(text, chunk_size, chunk_overlap)

    def _chunk_by_sections(self, text: str, max_chunk_size: int = 2000) -> List[str]:
        """
        Splits markdown text on '## ' headings. Each chunk contains one complete
        section with its heading. If a section exceeds max_chunk_size, it is
        further split by paragraphs within that section.
        Preamble text before the first '## ' heading is kept as a separate chunk.
        """
        chunks = []
        parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if len(part) <= max_chunk_size:
                chunks.append(part)
            else:
                # Section too large — sub-split by paragraphs within it
                sub_chunks = self._chunk_by_paragraphs(part, max_chunk_size, chunk_overlap=100)
                chunks.extend(sub_chunks)

        return [c for c in chunks if c.strip()]

    def _chunk_by_paragraphs(self, text: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> List[str]:
        """Accumulates paragraphs into chunks up to chunk_size. Long paragraphs are force-split with overlap."""
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
        defer_save: bool = False,
    ) -> int:
        """Adds text chunks to the FAISS index. Set defer_save=True to batch multiple additions before persisting."""
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

        if not defer_save:
            self._save_index()
        return len(chunks)

    def flush(self):
        """Persists the current in-memory FAISS index and metadata to disk. Call after batched add_snapshot_chunks(defer_save=True)."""
        self._save_index()

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

    def rehydrate_from_db(self):
        """
        Auto-Rehydration for Ephemeral Cloud Deployments (Render Free Tier):
        If FAISS index on disk is empty (0 vectors) after server restart,
        rehydrates FAISS vector embeddings from stored PostgreSQL snapshots & reports.
        """
        if self.index is not None and self.index.ntotal > 0:
            print(f"[FAISS Rehydration] FAISS index already has {self.index.ntotal} active vectors. Skipping rehydration.", flush=True)
            return

        print("[FAISS Rehydration] Empty FAISS index detected on startup. Rehydrating from PostgreSQL...", flush=True)
        try:
            from app.database import SessionLocal
            from app.models.snapshot import Snapshot
            from app.models.report import Report

            db = SessionLocal()
            try:
                # 1. Rehydrate Reports
                reports = db.query(Report).order_by(Report.generated_at.asc()).all()
                report_count = 0
                for r in reports:
                    if r.summary:
                        self.add_snapshot_chunks(
                            snapshot_id=str(r.id),
                            competitor_id=str(r.competitor_id),
                            source_type="executive_report",
                            fetched_at=r.generated_at.isoformat() if hasattr(r.generated_at, "isoformat") else str(r.generated_at),
                            text=r.summary,
                            defer_save=True,
                        )
                        report_count += 1

                # 2. Rehydrate Snapshots
                snapshots = db.query(Snapshot).order_by(Snapshot.fetched_at.asc()).all()
                snapshot_count = 0
                for s in snapshots:
                    if s.raw_content and not s.is_stale:
                        src_type = s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type)
                        self.add_snapshot_chunks(
                            snapshot_id=str(s.id),
                            competitor_id=str(s.competitor_id),
                            source_type=src_type,
                            fetched_at=s.fetched_at.isoformat() if hasattr(s.fetched_at, "isoformat") else str(s.fetched_at),
                            text=s.raw_content,
                            defer_save=True,
                        )
                        snapshot_count += 1

                if report_count > 0 or snapshot_count > 0:
                    self.flush()
                    print(f"[FAISS Rehydration] Complete! Re-indexed {report_count} reports and {snapshot_count} snapshots into FAISS (Total vectors: {self.index.ntotal}).", flush=True)
                else:
                    print("[FAISS Rehydration] No database snapshots/reports found to rehydrate.", flush=True)

            finally:
                db.close()
        except Exception as exc:
            print(f"[FAISS Rehydration Notice] {exc}", flush=True)


# Global singleton instance
vector_store = VectorStoreService()
