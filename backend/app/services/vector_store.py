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

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# HuggingFace Inference API endpoint for the same model
HF_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/{MODEL_NAME}"


class VectorStoreService:
    def __init__(self):
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        self.model = None  # Lazy load to conserve startup RAM
        self._embedding_mode = None  # Will be set by _get_model: "local", "hf_api", or "hash"
        self.index: Optional[faiss.IndexFlatIP] = None
        self.metadata: List[Dict[str, Any]] = []
        self._load_or_create_index()

    def _get_model(self):
        """
        Determines embedding mode in order of preference:
        1. VECTOR_STORE_MODE=hf_api → HuggingFace Inference API (free, no download, real embeddings)
        2. VECTOR_STORE_MODE=auto → tries HF API if token available, else local with 15s timeout, else hash
        3. VECTOR_STORE_MODE=hash → instant hash vectorizer (no API calls, no downloads)
        """
        if self.model is None:
            store_mode = (settings.VECTOR_STORE_MODE or os.environ.get("VECTOR_STORE_MODE", "auto")).lower().strip()
            hf_token = settings.HF_API_TOKEN or os.environ.get("HF_API_TOKEN", "")

            # ── Mode: hash (instant, no network) ────────────────────────────
            if store_mode == "hash":
                print("[Vector Store] VECTOR_STORE_MODE=hash → using instant hash vectorizer.", flush=True)
                self.model = "fallback"
                self._embedding_mode = "hash"
                return self.model

            # ── Mode: hf_api (explicit) or auto with HF token ───────────────
            if store_mode == "hf_api" or (store_mode == "auto" and hf_token):
                if hf_token:
                    # Quick connectivity check — detect DNS/network issues immediately
                    if self._check_hf_api_connectivity(hf_token):
                        print(f"[Vector Store] Using HuggingFace Inference API for embeddings (model: {MODEL_NAME}).", flush=True)
                        self.model = "hf_api"
                        self._embedding_mode = "hf_api"
                        return self.model
                    else:
                        print("[Vector Store] HF API unreachable (DNS/network issue). Using hash vectorizer.", flush=True)
                        self.model = "fallback"
                        self._embedding_mode = "hash"
                        return self.model
                else:
                    print("[Vector Store] VECTOR_STORE_MODE=hf_api but HF_API_TOKEN not set. Falling back to hash.", flush=True)
                    self.model = "fallback"
                    self._embedding_mode = "hash"
                    return self.model

            # ── Mode: auto (try local SentenceTransformer with 15s timeout) ─
            try:
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

                def _load_model():
                    from sentence_transformers import SentenceTransformer
                    return SentenceTransformer(MODEL_NAME)

                print("[Vector Store] Loading SentenceTransformer model (15s timeout)...", flush=True)
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_load_model)
                    self.model = future.result(timeout=15.0)
                self._embedding_mode = "local"
                print("[Vector Store] SentenceTransformer loaded successfully.", flush=True)

            except Exception as e:
                timeout_msg = "TIMED OUT" if "TimeoutError" in type(e).__name__ or "timeout" in str(e).lower() else f"failed ({e})"
                print(f"[Vector Store] SentenceTransformer {timeout_msg}. Using hash vectorizer.", flush=True)
                self.model = "fallback"
                self._embedding_mode = "hash"

        return self.model

    def _check_hf_api_connectivity(self, hf_token: str) -> bool:
        """Quick connectivity check to HuggingFace API. Returns False if DNS/network is broken."""
        try:
            response = httpx.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": "test", "options": {"wait_for_model": False}},
                timeout=5.0,
            )
            # Any HTTP response (even 503 model loading) means network is reachable
            return True
        except (httpx.ConnectError, OSError) as e:
            print(f"[Vector Store] HF API connectivity check failed: {e}", flush=True)
            return False
        except httpx.TimeoutException:
            # Timeout is OK — server is reachable but slow
            return True
        except Exception as e:
            print(f"[Vector Store] HF API connectivity check error: {e}", flush=True)
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
        use_hash_fallback = False  # Flag to skip all remaining HF API calls

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # If we already detected an unrecoverable error, skip straight to hash
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
                        # DNS/network failure — skip ALL remaining batches immediately
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
        """Routes to the appropriate embedding backend based on current mode."""
        model = self._get_model()

        # HuggingFace Inference API path
        if self._embedding_mode == "hf_api":
            try:
                return self._hf_api_encode(texts)
            except Exception as exc:
                print(f"[Vector Store] HF API encode failed ({exc}). Falling back to hash.", flush=True)
                return self._hash_encode(texts)

        # Local SentenceTransformer path
        if model not in ("fallback", "hf_api"):
            try:
                embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                return embeddings.astype(np.float32)
            except Exception as exc:
                print(f"[Vector Store Warning] Model encode failed ({exc}). Using hash vectorizer fallback.")

        # Hash vectorizer fallback
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


# Global singleton instance
vector_store = VectorStoreService()
