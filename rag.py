"""
RAG — Sprint 7
Embeddings locaux (paraphrase-multilingual-MiniLM-L12-v2, $0) + SQLite.
Index diff par mtime, recherche cosinus numpy, thread-safe.
"""

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import NamedTuple

import numpy as np

log = logging.getLogger(__name__)

_MODEL_NAME    = "paraphrase-multilingual-MiniLM-L12-v2"
_CHUNK_CHARS   = 1200   # ≈ 300 tokens
_OVERLAP_CHARS = 200    # ≈ 50 tokens overlap
_TOP_K         = 5
_MIN_SCORE     = 0.25   # seuil de pertinence minimum

_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_OPENAI_MODEL   = "text-embedding-3-small"

_encoder        = None
_encoder_lock   = threading.Lock()
_openai_client  = None
_openai_lock    = threading.Lock()


def _get_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    with _encoder_lock:
        if _encoder is None:
            from sentence_transformers import SentenceTransformer
            log.info(f"RAG : chargement du modèle {_MODEL_NAME}…")
            _encoder = SentenceTransformer(_MODEL_NAME)
            log.info("RAG : modèle prêt.")
    return _encoder


class SearchResult(NamedTuple):
    content:     str
    source_path: str
    score:       float


def chunk_text(text: str, chunk_chars: int = _CHUNK_CHARS, overlap: int = _OVERLAP_CHARS) -> list[str]:
    """Découpe un texte en chunks de ~chunk_chars caractères avec overlap."""
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        if start + chunk_chars >= len(text):
            tail = text[start:].strip()
            if tail:
                chunks.append(tail)
            break
        end = start + chunk_chars
        # Cherche un point de coupure naturel dans les 40% finaux du chunk
        best_break = end
        for sep in ("\n\n", "\n", ". ", " "):
            pos = text.rfind(sep, start + int(chunk_chars * 0.6), end)
            if pos > start:
                best_break = pos + len(sep)
                break
        chunk = text[start:best_break].strip()
        if chunk:
            chunks.append(chunk)
        start = max(start + 1, best_break - overlap)
    return chunks


def _get_openai_client():
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    with _openai_lock:
        if _openai_client is None:
            import openai as _openai_mod
            log.info(f"RAG : utilisation d'OpenAI embeddings ({_OPENAI_MODEL})")
            _openai_client = _openai_mod.OpenAI(api_key=_OPENAI_API_KEY)
    return _openai_client


def _embed(texts: list[str]) -> np.ndarray:
    """Encode une liste de textes en embeddings L2-normalisés."""
    if _OPENAI_API_KEY:
        try:
            resp = _get_openai_client().embeddings.create(model=_OPENAI_MODEL, input=texts)
            vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            return vecs / np.maximum(norms, 1e-10)
        except Exception as e:
            is_quota = (
                getattr(e, "status_code", None) == 429
                or "quota" in str(e).lower()
                or "rate_limit" in str(e).lower()
            )
            if is_quota:
                log.warning(f"RAG : quota OpenAI dépassé, fallback sentence-transformers. ({e})")
            else:
                raise
    return _get_encoder().encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )


class RAGIndex:
    def __init__(self, db_path: Path, memory_dir: Path):
        self.db_path    = db_path
        self.memory_dir = memory_dir
        self._lock      = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id          INTEGER PRIMARY KEY,
                    source_path TEXT    NOT NULL,
                    chunk_idx   INTEGER NOT NULL,
                    content     TEXT    NOT NULL,
                    embedding   BLOB    NOT NULL,
                    file_mtime  REAL    NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON chunks(source_path)")
            conn.commit()

    def _files_to_index(self) -> list[Path]:
        """Fichiers mémoire à indexer (hors soul.md et logs)."""
        targets: list[Path] = []
        for sub in ("projets", "concepts", "idees", "perso"):
            d = self.memory_dir / sub
            if d.exists():
                targets.extend(sorted(d.glob("*.md")))
        for fname in ("memory.md", "user.md", "jarvis_style.md"):
            p = self.memory_dir / fname
            if p.exists():
                targets.append(p)
        return targets

    def index_modified(self) -> None:
        """Réindexe uniquement les fichiers modifiés. Thread-safe, non bloquant."""
        with self._lock:
            try:
                files = self._files_to_index()
                with self._connect() as conn:
                    indexed: dict[str, float] = {
                        row[0]: row[1]
                        for row in conn.execute(
                            "SELECT source_path, MAX(file_mtime) FROM chunks GROUP BY source_path"
                        ).fetchall()
                    }
                    to_update = [
                        (p, p.stat().st_mtime)
                        for p in files
                        if str(p) not in indexed or indexed[str(p)] < p.stat().st_mtime
                    ]
                    if not to_update:
                        log.info("RAG : index à jour, aucun fichier modifié.")
                        return
                    log.info(f"RAG : réindexation de {len(to_update)} fichier(s)…")
                    for path, mtime in to_update:
                        text = path.read_text()
                        chunks = chunk_text(text)
                        if not chunks:
                            continue
                        embeddings = _embed(chunks)
                        conn.execute("DELETE FROM chunks WHERE source_path = ?", (str(path),))
                        conn.executemany(
                            "INSERT INTO chunks "
                            "(source_path, chunk_idx, content, embedding, file_mtime) "
                            "VALUES (?, ?, ?, ?, ?)",
                            [
                                (str(path), i, c, emb.astype(np.float32).tobytes(), mtime)
                                for i, (c, emb) in enumerate(zip(chunks, embeddings))
                            ],
                        )
                        log.info(f"RAG : {path.name} → {len(chunks)} chunk(s)")
                    conn.commit()
                log.info("RAG : indexation terminée.")
            except Exception as e:
                log.error(f"RAG index_modified : {e}")

    _SEARCH_LIMIT = 500  # max chunks chargés en RAM par recherche

    def search(self, query: str, top_k: int = _TOP_K) -> list[SearchResult]:
        """Embed la query et retourne les top_k chunks les plus similaires."""
        try:
            q_emb = _embed([query])[0]   # shape (dim,), normalisé
            with self._connect() as conn:
                total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                rows = conn.execute(
                    "SELECT source_path, content, embedding FROM chunks LIMIT ?",
                    (self._SEARCH_LIMIT,),
                ).fetchall()
            if not rows:
                return []
            if total > self._SEARCH_LIMIT:
                log.warning(f"RAG search : index tronqué à {self._SEARCH_LIMIT}/{total} chunks")
            matrix = np.stack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
            scores  = (matrix @ q_emb).flatten()
            top_idx = np.argsort(scores)[::-1][:top_k]
            results = [
                SearchResult(rows[i][1], rows[i][0], float(scores[i]))
                for i in top_idx
                if scores[i] >= _MIN_SCORE
            ]
            if results:
                score_summary = ", ".join(f"{r.score:.2f}" for r in results)
                log.info(f"RAG search : {len(results)} résultat(s) — scores [{score_summary}]")
            else:
                best = float(scores[np.argmax(scores)]) if len(scores) else 0.0
                log.info(f"RAG search : aucun résultat (seuil={_MIN_SCORE}, meilleur score={best:.2f})")
            return results
        except Exception as e:
            log.error(f"RAG search : {e}")
            return []

    def stats(self) -> dict:
        try:
            with self._connect() as conn:
                n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                n_files  = conn.execute(
                    "SELECT COUNT(DISTINCT source_path) FROM chunks"
                ).fetchone()[0]
            return {"chunks": n_chunks, "files": n_files}
        except Exception:
            return {"chunks": 0, "files": 0}


# ── Singleton ─────────────────────────────────────────────────────────────────

_rag: RAGIndex | None = None


def init_rag(db_path: Path, memory_dir: Path) -> RAGIndex:
    global _rag
    _rag = RAGIndex(db_path, memory_dir)
    return _rag


def get_rag() -> RAGIndex | None:
    return _rag


def format_search_results(results: list[SearchResult], memory_dir: Path) -> str:
    """Formate les résultats RAG pour injection dans le message utilisateur."""
    if not results:
        return "(Aucun résultat pertinent trouvé dans la mémoire.)"
    parts = []
    for r in results:
        try:
            rel = Path(r.source_path).relative_to(memory_dir.parent)
        except ValueError:
            rel = Path(r.source_path).name
        parts.append(f"[source: {rel} | score: {r.score:.2f}]\n{r.content}")
    return "\n\n---\n\n".join(parts)
