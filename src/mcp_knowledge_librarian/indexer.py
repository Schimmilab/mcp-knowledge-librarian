"""SQLite/FTS5-based index management.

Replaces the previous Whoosh + pickle implementation:
- no in-memory chunk cache (chunks.pkl was 318 MB, fully rewritten per document)
- BM25 full-text ranking via SQLite FTS5 (stdlib, zero extra dependencies)
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    DocumentMetadata,
    DocumentStatus,
    SearchQuery,
    SearchResult,
    TextChunk,
)

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime REAL,
    page_count INTEGER NOT NULL,
    title TEXT,
    author TEXT,
    creation_date TEXT,
    modification_date TEXT,
    status TEXT NOT NULL,
    is_scan INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(path);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_offset INTEGER NOT NULL,
    char_length INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL
);
"""


def _clean(value: Optional[str]) -> Optional[str]:
    """Strip lone surrogates (from broken PDF extraction) — invalid UTF-8
    that SQLite rejects."""
    if value is None:
        return None
    return value.encode("utf-8", "replace").decode("utf-8")


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class IndexManager:
    """Manages the document index backed by a single SQLite database."""

    def __init__(self, index_path: str, enable_semantic: bool = False):
        # enable_semantic kept for call compatibility; semantic search was a
        # placeholder and has been removed.
        self.index_path = Path(index_path).expanduser()
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.index_path / "librarian.db"

        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        logger.info(f"Index opened at {self.db_path}")

    # -- indexing ---------------------------------------------------------

    def index_document(
        self, metadata: DocumentMetadata, chunks: list[TextChunk], is_scan: bool
    ) -> None:
        """
        Index a document and its chunks, replacing any previous version.

        Args:
            metadata: Document metadata
            chunks: List of text chunks
            is_scan: Whether document is a scan
        """
        metadata.is_scan = is_scan
        metadata.indexed_at = datetime.now()

        if is_scan and len(chunks) == 0:
            metadata.status = DocumentStatus.OCR_REQUIRED
        elif len(chunks) > 0:
            metadata.status = DocumentStatus.INDEXED
        else:
            metadata.status = DocumentStatus.ERROR
            metadata.error_message = "No text content extracted"

        with self._conn:
            self._conn.execute(
                """INSERT INTO documents
                   (id, filename, path, size_bytes, mtime, page_count, title,
                    author, creation_date, modification_date, status, is_scan,
                    indexed_at, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     filename=excluded.filename, path=excluded.path,
                     size_bytes=excluded.size_bytes, mtime=excluded.mtime,
                     page_count=excluded.page_count, title=excluded.title,
                     author=excluded.author,
                     creation_date=excluded.creation_date,
                     modification_date=excluded.modification_date,
                     status=excluded.status, is_scan=excluded.is_scan,
                     indexed_at=excluded.indexed_at,
                     error_message=excluded.error_message""",
                (
                    metadata.id, _clean(metadata.filename), _clean(metadata.path),
                    metadata.size_bytes, metadata.mtime, metadata.page_count,
                    _clean(metadata.title), _clean(metadata.author),
                    _dt(metadata.creation_date), _dt(metadata.modification_date),
                    metadata.status.value, int(metadata.is_scan),
                    _dt(metadata.indexed_at), _clean(metadata.error_message),
                ),
            )

            # Replace existing chunks (remove old FTS rows first)
            old = self._conn.execute(
                "SELECT rowid, text FROM chunks WHERE document_id=?", (metadata.id,)
            ).fetchall()
            for row in old:
                self._conn.execute(
                    "INSERT INTO chunks_fts(chunks_fts, rowid, text) "
                    "VALUES('delete', ?, ?)",
                    (row["rowid"], row["text"]),
                )
            self._conn.execute(
                "DELETE FROM chunks WHERE document_id=?", (metadata.id,)
            )

            for chunk in chunks:
                text = _clean(chunk.text)
                cur = self._conn.execute(
                    """INSERT INTO chunks
                       (chunk_id, document_id, page_number, text,
                        char_offset, char_length)
                       VALUES (?,?,?,?,?,?)""",
                    (
                        chunk.chunk_id, chunk.document_id, chunk.page_number,
                        text, chunk.char_offset, chunk.char_length,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, text),
                )

        logger.info(
            f"Indexed document {metadata.filename} with {len(chunks)} chunks "
            f"(status: {metadata.status})"
        )

    # -- search -----------------------------------------------------------

    @staticmethod
    def _fts_query(query: str) -> str:
        # Quote each term so FTS5 operators/special chars in user input
        # cannot break the query syntax.
        terms = [t.replace('"', "") for t in query.split()]
        return " ".join(f'"{t}"' for t in terms if t)

    def search(
        self, query: SearchQuery, keyword_weight: float = 1.0
    ) -> list[SearchResult]:
        """
        Search the index using FTS5 BM25 ranking.

        Args:
            query: Search query
            keyword_weight: Unused, kept for call compatibility

        Returns:
            List of search results with scores normalized to 0..1
        """
        fts_query = self._fts_query(query.query)
        if not fts_query:
            return []

        sql = """
            SELECT c.chunk_id, c.document_id, c.page_number, c.text,
                   chunks_fts.rank AS rank,
                   d.path AS doc_path, d.title AS doc_title
            FROM chunks_fts
            JOIN chunks c ON c.rowid = chunks_fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE chunks_fts MATCH ?
        """
        params: list = [fts_query]
        if query.document_id:
            sql += " AND c.document_id = ?"
            params.append(query.document_id)
        sql += " ORDER BY rank LIMIT ?"
        params.append(query.max_results * 2)

        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f"Search failed for '{query.query}': {e}")
            return []

        if not rows:
            return []

        # FTS5 bm25 rank: negative, more negative = better. Normalize to 0..1.
        max_raw = max(-row["rank"] for row in rows) or 1.0
        results = []
        for row in rows:
            score = -row["rank"] / max_raw
            if score < query.min_score:
                continue
            results.append(
                SearchResult(
                    document_id=row["document_id"],
                    document_path=f"file://{row['doc_path']}#page={row['page_number']}",
                    document_title=row["doc_title"],
                    page_number=row["page_number"],
                    snippet=self._create_snippet(row["text"], query.query),
                    score=score,
                    chunk_id=row["chunk_id"],
                )
            )

        results = results[: query.max_results]
        logger.info(f"Search for '{query.query}' returned {len(results)} results")
        return results

    def _create_snippet(
        self, text: str, query: str, context_chars: int = 150, max_length: int = 500
    ) -> str:
        """Create a snippet with context around the first query term match."""
        query_terms = query.lower().split()

        best_pos = -1
        for term in query_terms:
            pos = text.lower().find(term)
            if pos != -1:
                best_pos = pos
                break

        if best_pos == -1:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        start = max(0, best_pos - context_chars)
        end = min(len(text), best_pos + len(query_terms[0]) + context_chars)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    # -- embeddings & semantic search -------------------------------------

    def store_embeddings(self, items: list) -> None:
        """Persist embeddings. items = list of (chunk_id, 1-D float32 ndarray).

        Stored as float16 BLOBs to halve size on disk and in RAM; retrieval
        upcasts to float32 for the dot product.
        """
        import numpy as np

        with self._conn:
            for chunk_id, vec in items:
                v = np.asarray(vec, dtype=np.float16)
                self._conn.execute(
                    "INSERT INTO chunk_embeddings (chunk_id, dim, vec) VALUES (?,?,?) "
                    "ON CONFLICT(chunk_id) DO UPDATE SET dim=excluded.dim, vec=excluded.vec",
                    (chunk_id, int(v.shape[0]), v.tobytes()),
                )
        self._emb_cache = None  # invalidate in-memory matrix

    def chunks_missing_embeddings(self, limit: int = 1000) -> list:
        """Return (chunk_id, text) for chunks that have no embedding yet."""
        rows = self._conn.execute(
            "SELECT c.chunk_id, c.text FROM chunks c "
            "LEFT JOIN chunk_embeddings e ON e.chunk_id = c.chunk_id "
            "WHERE e.chunk_id IS NULL LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["chunk_id"], r["text"]) for r in rows]

    def count_embeddings(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM chunk_embeddings"
        ).fetchone()[0]

    def _embedding_matrix(self):
        """Load all embeddings into memory: (ids, (N,dim) float32 matrix).

        Cached, but reloaded whenever the embedding count changes — so a
        long-running server picks up vectors written by a separate embedding
        batch (another process) without needing a restart.
        """
        import numpy as np

        n = self.count_embeddings()
        cache = getattr(self, "_emb_cache", None)
        if cache is not None and cache[0] == n:
            return cache[1], cache[2]
        rows = self._conn.execute(
            "SELECT chunk_id, vec FROM chunk_embeddings"
        ).fetchall()
        if not rows:
            self._emb_cache = (0, [], np.zeros((0, 0), dtype=np.float32))
            return self._emb_cache[1], self._emb_cache[2]
        ids = [r["chunk_id"] for r in rows]
        mat = np.stack(
            [np.frombuffer(r["vec"], dtype=np.float16).astype(np.float32) for r in rows]
        )
        self._emb_cache = (n, ids, mat)
        logger.info(f"Loaded {len(ids)} embeddings into memory {mat.shape}")
        return ids, mat

    def semantic_search(
        self, query_vec, max_results: int = 20, min_score: float = 0.0,
        document_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """Cosine-similarity search. Vectors are L2-normalized, so the dot
        product is the cosine similarity."""
        import numpy as np

        ids, mat = self._embedding_matrix()
        if not ids:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        sims = mat @ q
        k = min(len(ids), max(max_results * 4, max_results))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]

        results: list[SearchResult] = []
        for i in top:
            score = float(sims[i])
            if score < min_score:
                break  # sorted descending
            row = self._conn.execute(
                "SELECT c.chunk_id, c.document_id, c.page_number, c.text, "
                "d.path AS doc_path, d.title AS doc_title "
                "FROM chunks c JOIN documents d ON d.id=c.document_id "
                "WHERE c.chunk_id=?",
                (ids[i],),
            ).fetchone()
            if not row:
                continue
            if document_id and row["document_id"] != document_id:
                continue
            results.append(
                SearchResult(
                    document_id=row["document_id"],
                    document_path=f"file://{row['doc_path']}#page={row['page_number']}",
                    document_title=row["doc_title"],
                    page_number=row["page_number"],
                    snippet=self._create_snippet(row["text"], ""),
                    score=round(score, 4),
                    chunk_id=row["chunk_id"],
                )
            )
            if len(results) >= max_results:
                break
        return results

    @staticmethod
    def _rrf(rankings: list, k: int = 60) -> dict:
        """Reciprocal Rank Fusion: map chunk_id -> fused score."""
        scores: dict = {}
        for ranking in rankings:
            for rank, cid in enumerate(ranking):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
        return scores

    def hybrid_search(
        self, query: SearchQuery, query_vec, pool: int = 40
    ) -> list[SearchResult]:
        """Fuse BM25 and semantic rankings with Reciprocal Rank Fusion.

        `pool` is how many candidates each retriever contributes before fusion.
        The returned score is the RRF score normalized to 0..1.
        """
        bm25 = self.search(
            SearchQuery(query=query.query, max_results=pool, min_score=0.0,
                        document_id=query.document_id)
        )
        sem = self.semantic_search(
            query_vec, max_results=pool, min_score=0.0, document_id=query.document_id
        )
        by_id = {r.chunk_id: r for r in sem}
        by_id.update({r.chunk_id: r for r in bm25})  # prefer bm25 snippet if both

        scores = self._rrf(
            [[r.chunk_id for r in bm25], [r.chunk_id for r in sem]]
        )
        if not scores:
            return []
        ordered = sorted(scores, key=lambda c: scores[c], reverse=True)
        mx = max(scores.values())
        out = []
        for cid in ordered[: query.max_results]:
            r = by_id.get(cid)
            if r is not None:
                out.append(r.model_copy(update={"score": round(scores[cid] / mx, 4)}))
        return out

    # -- lookups ----------------------------------------------------------

    def _row_to_metadata(self, row: sqlite3.Row) -> DocumentMetadata:
        return DocumentMetadata(
            id=row["id"],
            filename=row["filename"],
            path=row["path"],
            size_bytes=row["size_bytes"],
            mtime=row["mtime"],
            page_count=row["page_count"],
            title=row["title"],
            author=row["author"],
            creation_date=_parse_dt(row["creation_date"]),
            modification_date=_parse_dt(row["modification_date"]),
            status=DocumentStatus(row["status"]),
            is_scan=bool(row["is_scan"]),
            indexed_at=_parse_dt(row["indexed_at"]),
            error_message=row["error_message"],
        )

    def get_document_metadata(self, document_id: str) -> Optional[DocumentMetadata]:
        row = self._conn.execute(
            "SELECT * FROM documents WHERE id=?", (document_id,)
        ).fetchone()
        return self._row_to_metadata(row) if row else None

    def get_chunk(self, chunk_id: str) -> Optional[TextChunk]:
        row = self._conn.execute(
            "SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()
        if not row:
            return None
        return TextChunk(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            page_number=row["page_number"],
            text=row["text"],
            char_offset=row["char_offset"],
            char_length=row["char_length"],
        )

    def list_documents(
        self, limit: int = 100, offset: int = 0
    ) -> list[DocumentMetadata]:
        rows = self._conn.execute(
            "SELECT * FROM documents ORDER BY filename LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_metadata(r) for r in rows]

    def count_documents(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def file_states(self) -> dict[str, tuple[int, Optional[float]]]:
        """Map of path -> (size_bytes, mtime) for incremental scanning."""
        rows = self._conn.execute(
            "SELECT path, size_bytes, mtime FROM documents WHERE status != 'error'"
        ).fetchall()
        return {r["path"]: (r["size_bytes"], r["mtime"]) for r in rows}

    def documents_with_status(self, status: DocumentStatus) -> list[DocumentMetadata]:
        rows = self._conn.execute(
            "SELECT * FROM documents WHERE status=?", (status.value,)
        ).fetchall()
        return [self._row_to_metadata(r) for r in rows]

    def get_statistics(self) -> dict:
        status_counts = {
            row["status"]: row["n"]
            for row in self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM documents GROUP BY status"
            )
        }
        total_chunks = self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        return {
            "total_documents": self.count_documents(),
            "total_chunks": total_chunks,
            "total_embeddings": self.count_embeddings(),
            "status_counts": status_counts,
            "index_path": str(self.index_path),
            "db_path": str(self.db_path),
        }

    def close(self) -> None:
        self._conn.close()
