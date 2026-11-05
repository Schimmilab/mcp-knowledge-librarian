"""Tests for text extraction."""

import tempfile
from pathlib import Path

import pytest
from pypdf import PdfWriter, PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from mcp_knowledge_librarian.extractor import TextExtractor
from mcp_knowledge_librarian.models import DocumentMetadata, DocumentStatus


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def text_pdf(temp_dir):
    """Create a PDF with text content."""
    pdf_path = temp_dir / "text.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(100, 750, "This is a test document.")
    c.drawString(100, 730, "It contains multiple lines of text.")
    c.drawString(100, 710, "Scan detection requires more than fifty characters")
    c.drawString(100, 690, "per page on average, so this fixture provides them.")
    c.showPage()
    c.drawString(100, 750, "This is page two.")
    c.drawString(100, 730, "It also carries enough text to stay well above the")
    c.drawString(100, 710, "scan detection threshold of the extractor.")
    c.save()

    return pdf_path


@pytest.fixture
def blank_pdf(temp_dir):
    """Create a blank PDF (simulating a scan)."""
    pdf_path = temp_dir / "blank.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    return pdf_path


def create_metadata(pdf_path: Path, doc_id: str = "test123") -> DocumentMetadata:
    """Create test document metadata."""
    stat = pdf_path.stat()

    with open(pdf_path, "rb") as f:
        reader = PdfReader(f)
        page_count = len(reader.pages)

    return DocumentMetadata(
        id=doc_id,
        filename=pdf_path.name,
        path=str(pdf_path),
        size_bytes=stat.st_size,
        page_count=page_count,
    )


def test_extract_text_from_text_pdf(text_pdf):
    """Test text extraction from a text-based PDF."""
    extractor = TextExtractor(enable_ocr=False)
    metadata = create_metadata(text_pdf)

    chunks, is_scan = extractor.extract_text_from_document(metadata)

    assert not is_scan
    assert len(chunks) == 2  # Two pages
    assert "test document" in chunks[0].text.lower()
    assert "page two" in chunks[1].text.lower()


def test_detect_scanned_pdf(blank_pdf):
    """Test detection of scanned PDFs."""
    extractor = TextExtractor(enable_ocr=False)
    metadata = create_metadata(blank_pdf)

    chunks, is_scan = extractor.extract_text_from_document(metadata)

    assert is_scan
    assert len(chunks) == 0  # No text extracted


def test_chunk_creation():
    """Test fixed-size chunk creation."""
    extractor = TextExtractor()

    text = "This is a long text that should be split into multiple chunks. " * 10
    chunks = extractor.create_fixed_size_chunks(
        text=text,
        document_id="doc123",
        page_number=1,
        chunk_size=100,
        overlap=20,
    )

    assert len(chunks) > 1

    # Check overlap
    for i in range(len(chunks) - 1):
        # Chunks should overlap
        assert chunks[i].char_offset + chunks[i].char_length > chunks[i + 1].char_offset


def test_chunk_metadata():
    """Test chunk metadata correctness."""
    extractor = TextExtractor()

    text = "Short text"
    chunks = extractor.create_fixed_size_chunks(
        text=text,
        document_id="doc456",
        page_number=5,
        chunk_size=100,
        overlap=20,
    )

    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.document_id == "doc456"
    assert chunk.page_number == 5
    assert chunk.text == text
    assert chunk.char_offset == 0
    assert chunk.char_length == len(text)
    assert "doc456:page:5:chunk:0" in chunk.chunk_id
