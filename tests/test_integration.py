"""Integration tests for the complete workflow."""

import tempfile
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from mcp_knowledge_librarian.catalog import PDFCatalog
from mcp_knowledge_librarian.extractor import TextExtractor
from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import SearchQuery


@pytest.fixture
def temp_env():
    """Create a temporary environment with library and index."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        library_dir = tmpdir / "library"
        library_dir.mkdir()
        index_dir = tmpdir / "index"
        index_dir.mkdir()

        yield {
            "root": tmpdir,
            "library": library_dir,
            "index": index_dir,
        }


@pytest.fixture
def sample_documents(temp_env):
    """Create sample PDF documents."""
    docs = []

    # Document 1: Machine Learning
    doc1 = temp_env["library"] / "ml_guide.pdf"
    c = canvas.Canvas(str(doc1), pagesize=letter)
    c.drawString(100, 750, "Machine Learning Guide")
    c.drawString(100, 730, "Machine learning is a subset of artificial intelligence.")
    c.drawString(100, 710, "It focuses on training algorithms to learn from data.")
    c.showPage()
    c.drawString(100, 750, "Neural networks are a key technique in machine learning.")
    c.save()
    docs.append(doc1)

    # Document 2: Data Science
    doc2 = temp_env["library"] / "data_science.pdf"
    c = canvas.Canvas(str(doc2), pagesize=letter)
    c.drawString(100, 750, "Introduction to Data Science")
    c.drawString(100, 730, "Data science combines statistics and computer science.")
    c.drawString(100, 710, "It involves analyzing large datasets to extract insights.")
    c.save()
    docs.append(doc2)

    # Document 3: Python Programming
    doc3 = temp_env["library"] / "python.pdf"
    c = canvas.Canvas(str(doc3), pagesize=letter)
    c.drawString(100, 750, "Python Programming Basics")
    c.drawString(100, 730, "Python is a popular programming language.")
    c.drawString(100, 710, "It is widely used in data science and machine learning.")
    c.save()
    docs.append(doc3)

    return docs


def test_end_to_end_workflow(temp_env, sample_documents):
    """Test complete workflow: catalog -> extract -> index -> search."""
    # 1. Catalog documents
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_env["library"]])

    assert len(documents) == 3
    assert all(doc.page_count > 0 for doc in documents)

    # 2. Extract text
    extractor = TextExtractor(enable_ocr=False)
    all_chunks = {}

    for doc in documents:
        chunks, is_scan = extractor.extract_text_from_document(doc)
        assert not is_scan
        assert len(chunks) > 0
        all_chunks[doc.id] = chunks

    # 3. Index documents
    indexer = IndexManager(
        index_path=str(temp_env["index"]),
        enable_semantic=False,
    )

    for doc in documents:
        chunks = all_chunks[doc.id]
        is_scan = False
        indexer.index_document(doc, chunks, is_scan)

    # 4. Search
    query = SearchQuery(query="machine learning", max_results=10, min_score=0.0)
    results = indexer.search(query)

    # Should find results in ML guide and Python doc
    assert len(results) > 0
    assert any("ml_guide" in r.document_path for r in results)

    # Check citation information
    for result in results:
        assert result.document_path
        assert result.page_number > 0
        assert result.snippet
        assert "machine learning" in result.snippet.lower()
        assert result.chunk_id


def test_snippet_retrieval(temp_env, sample_documents):
    """Test retrieving full snippet by chunk ID."""
    # Setup
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_env["library"]])

    extractor = TextExtractor(enable_ocr=False)
    indexer = IndexManager(index_path=str(temp_env["index"]), enable_semantic=False)

    for doc in documents:
        chunks, is_scan = extractor.extract_text_from_document(doc)
        indexer.index_document(doc, chunks, is_scan)

    # Search
    query = SearchQuery(query="data science", max_results=5)
    results = indexer.search(query)

    assert len(results) > 0

    # Get snippet
    chunk_id = results[0].chunk_id
    chunk = indexer.get_chunk(chunk_id)

    assert chunk is not None
    assert chunk.chunk_id == chunk_id
    assert "data science" in chunk.text.lower()


def test_document_metadata_retrieval(temp_env, sample_documents):
    """Test retrieving document metadata."""
    # Setup
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_env["library"]])

    indexer = IndexManager(index_path=str(temp_env["index"]), enable_semantic=False)
    extractor = TextExtractor(enable_ocr=False)

    for doc in documents:
        chunks, is_scan = extractor.extract_text_from_document(doc)
        indexer.index_document(doc, chunks, is_scan)

    # Retrieve metadata
    doc_id = documents[0].id
    metadata = indexer.get_document_metadata(doc_id)

    assert metadata is not None
    assert metadata.id == doc_id
    assert metadata.filename
    assert metadata.path
    assert metadata.page_count > 0
    assert metadata.status.value in ["indexed", "ocr_required"]


def test_persistence(temp_env, sample_documents):
    """Test that index persists across restarts."""
    # Initial indexing
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_env["library"]])

    extractor = TextExtractor(enable_ocr=False)
    indexer1 = IndexManager(index_path=str(temp_env["index"]), enable_semantic=False)

    for doc in documents:
        chunks, is_scan = extractor.extract_text_from_document(doc)
        indexer1.index_document(doc, chunks, is_scan)

    doc_count1 = len(indexer1.list_documents())

    # Create new indexer (simulating restart)
    indexer2 = IndexManager(index_path=str(temp_env["index"]), enable_semantic=False)

    # Should have same documents
    doc_count2 = len(indexer2.list_documents())
    assert doc_count1 == doc_count2

    # Should be able to search
    query = SearchQuery(query="python", max_results=10)
    results = indexer2.search(query)
    assert len(results) > 0


def test_statistics(temp_env, sample_documents):
    """Test index statistics."""
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_env["library"]])

    extractor = TextExtractor(enable_ocr=False)
    indexer = IndexManager(index_path=str(temp_env["index"]), enable_semantic=False)

    for doc in documents:
        chunks, is_scan = extractor.extract_text_from_document(doc)
        indexer.index_document(doc, chunks, is_scan)

    stats = indexer.get_statistics()

    assert stats["total_documents"] == len(documents)
    assert stats["total_chunks"] > 0
    assert "status_counts" in stats
    assert "indexed" in stats["status_counts"]
