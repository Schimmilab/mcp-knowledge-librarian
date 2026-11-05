"""Tests for the pickle -> SQLite migration."""

import pickle

from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import (
    DocumentMetadata,
    DocumentStatus,
    TextChunk,
)

from scripts.migrate_to_sqlite import migrate


def test_migrate_pickles(tmp_path):
    old_index = tmp_path / "old"
    old_index.mkdir()

    doc = DocumentMetadata(
        id="doc1",
        filename="a.pdf",
        path="/lib/a.pdf",
        size_bytes=100,
        page_count=1,
        status=DocumentStatus.INDEXED,
    )
    chunk = TextChunk(
        chunk_id="doc1:page:1",
        document_id="doc1",
        page_number=1,
        text="hello migration world",
        char_offset=0,
        char_length=21,
    )
    with open(old_index / "metadata.pkl", "wb") as f:
        pickle.dump({"doc1": doc}, f)
    with open(old_index / "chunks.pkl", "wb") as f:
        pickle.dump({"doc1:page:1": chunk}, f)

    new_index = tmp_path / "new"
    stats = migrate(str(old_index), str(new_index))

    assert stats == {"documents": 1, "chunks": 1}

    manager = IndexManager(index_path=str(new_index))
    assert manager.get_document_metadata("doc1") is not None
    assert manager.get_chunk("doc1:page:1").text == "hello migration world"
