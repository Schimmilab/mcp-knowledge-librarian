"""Tests for the SQLite-based IndexManager."""

import pytest

from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import (
    DocumentMetadata,
    DocumentStatus,
    SearchQuery,
    TextChunk,
)


@pytest.fixture
def manager(tmp_path):
    return IndexManager(index_path=str(tmp_path / "index"))


def make_doc(doc_id="doc1", path="/lib/a.pdf"):
    return DocumentMetadata(
        id=doc_id,
        filename="a.pdf",
        path=path,
        size_bytes=1234,
        mtime=1700000000.0,
        page_count=2,
        title="Fermentation Basics",
        author="Test Author",
        status=DocumentStatus.PENDING,
    )


def make_chunks(doc_id="doc1"):
    return [
        TextChunk(
            chunk_id=f"{doc_id}:page:1",
            document_id=doc_id,
            page_number=1,
            text="Sauerkraut fermentation requires salt and time.",
            char_offset=0,
            char_length=47,
        ),
        TextChunk(
            chunk_id=f"{doc_id}:page:2",
            document_id=doc_id,
            page_number=2,
            text="Kombucha needs a SCOBY culture and sweet tea.",
            char_offset=0,
            char_length=45,
        ),
    ]


def test_index_and_get_metadata(manager):
    doc = make_doc()
    manager.index_document(doc, make_chunks(), is_scan=False)

    loaded = manager.get_document_metadata("doc1")
    assert loaded is not None
    assert loaded.status == DocumentStatus.INDEXED
    assert loaded.title == "Fermentation Basics"
    assert loaded.mtime == 1700000000.0


def test_search_finds_chunk(manager):
    manager.index_document(make_doc(), make_chunks(), is_scan=False)

    results = manager.search(SearchQuery(query="sauerkraut", min_score=0.0))
    assert len(results) == 1
    assert results[0].chunk_id == "doc1:page:1"
    assert results[0].page_number == 1
    assert 0.0 < results[0].score <= 1.0


def test_search_document_filter(manager):
    manager.index_document(make_doc("doc1", "/lib/a.pdf"), make_chunks("doc1"), False)
    manager.index_document(make_doc("doc2", "/lib/b.pdf"), make_chunks("doc2"), False)

    results = manager.search(
        SearchQuery(query="kombucha", min_score=0.0, document_id="doc2")
    )
    assert len(results) == 1
    assert results[0].document_id == "doc2"


def test_get_chunk(manager):
    manager.index_document(make_doc(), make_chunks(), is_scan=False)

    chunk = manager.get_chunk("doc1:page:2")
    assert chunk is not None
    assert "SCOBY" in chunk.text
    assert manager.get_chunk("nope") is None


def test_reindex_replaces_chunks(manager):
    doc = make_doc()
    manager.index_document(doc, make_chunks(), is_scan=False)
    manager.index_document(doc, make_chunks()[:1], is_scan=False)

    assert manager.get_chunk("doc1:page:2") is None
    stats = manager.get_statistics()
    assert stats["total_chunks"] == 1


def test_scan_without_chunks_marks_ocr_required(manager):
    doc = make_doc()
    manager.index_document(doc, [], is_scan=True)
    loaded = manager.get_document_metadata("doc1")
    assert loaded.status == DocumentStatus.OCR_REQUIRED


def test_list_documents_pagination(manager):
    for i in range(5):
        manager.index_document(
            make_doc(f"doc{i}", f"/lib/{i}.pdf"), make_chunks(f"doc{i}"), False
        )
    page = manager.list_documents(limit=2, offset=2)
    assert len(page) == 2
    assert manager.count_documents() == 5


def test_file_states(manager):
    manager.index_document(make_doc(), make_chunks(), is_scan=False)
    states = manager.file_states()
    assert states["/lib/a.pdf"] == (1234, 1700000000.0)


def test_fts_query_sanitizes_special_chars(manager):
    manager.index_document(make_doc(), make_chunks(), is_scan=False)
    # FTS5 operators in user input must not raise
    results = manager.search(SearchQuery(query='salt AND "time" (NEAR', min_score=0.0))
    assert isinstance(results, list)


def test_surrogates_in_text_are_sanitized(manager):
    # Broken PDF extraction can produce lone surrogates, which SQLite
    # rejects as invalid UTF-8. They must be replaced, not crash indexing.
    doc = make_doc()
    chunk = TextChunk(
        chunk_id="doc1:page:1",
        document_id="doc1",
        page_number=1,
        text="broken \udbc0 surrogate text",
        char_offset=0,
        char_length=24,
    )
    manager.index_document(doc, [chunk], is_scan=False)
    stored = manager.get_chunk("doc1:page:1")
    assert "surrogate text" in stored.text


def test_statistics(manager):
    manager.index_document(make_doc(), make_chunks(), is_scan=False)
    stats = manager.get_statistics()
    assert stats["total_documents"] == 1
    assert stats["total_chunks"] == 2
    assert stats["status_counts"]["indexed"] == 1
