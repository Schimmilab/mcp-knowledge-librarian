"""One-time migration: metadata.pkl + chunks.pkl -> SQLite index.

Usage:
    python scripts/migrate_to_sqlite.py <old_index_dir> <new_index_dir>

Example:
    python scripts/migrate_to_sqlite.py \
        "/path/to/library/.index" \
        "$HOME/.cache/knowledge-librarian/index"
"""

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.indexer import IndexManager, _clean, _dt  # noqa: E402


def migrate(old_index_dir: str, new_index_dir: str) -> dict:
    old = Path(old_index_dir).expanduser()

    with open(old / "metadata.pkl", "rb") as f:
        documents = pickle.load(f)
    with open(old / "chunks.pkl", "rb") as f:
        chunks = pickle.load(f)

    manager = IndexManager(index_path=new_index_dir)
    conn = manager._conn

    with conn:
        for meta in documents.values():
            conn.execute(
                """INSERT OR REPLACE INTO documents
                   (id, filename, path, size_bytes, mtime, page_count, title,
                    author, creation_date, modification_date, status, is_scan,
                    indexed_at, error_message)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    meta.id, _clean(meta.filename), _clean(meta.path),
                    meta.size_bytes,
                    getattr(meta, "mtime", None), meta.page_count,
                    _clean(meta.title), _clean(meta.author),
                    _dt(meta.creation_date), _dt(meta.modification_date),
                    meta.status.value, int(meta.is_scan),
                    _dt(meta.indexed_at), _clean(meta.error_message),
                ),
            )
        for chunk in chunks.values():
            text = _clean(chunk.text)
            cur = conn.execute(
                """INSERT OR REPLACE INTO chunks
                   (chunk_id, document_id, page_number, text,
                    char_offset, char_length)
                   VALUES (?,?,?,?,?,?)""",
                (
                    chunk.chunk_id, chunk.document_id, chunk.page_number,
                    text, chunk.char_offset, chunk.char_length,
                ),
            )
            conn.execute(
                "INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)",
                (cur.lastrowid, text),
            )

    stats = {"documents": len(documents), "chunks": len(chunks)}
    print(f"Migrated {stats['documents']} documents, {stats['chunks']} chunks")
    print(f"New index: {manager.db_path}")
    manager.close()
    return stats


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    migrate(sys.argv[1], sys.argv[2])
