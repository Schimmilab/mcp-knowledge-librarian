"""Tests for PDF cataloging."""

import hashlib
import tempfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from mcp_knowledge_librarian.catalog import PDFCatalog
from mcp_knowledge_librarian.models import DocumentStatus


@pytest.fixture
def temp_library():
    """Create a temporary library directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_pdf(temp_library):
    """Create a sample PDF file."""
    pdf_path = temp_library / "test.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    return pdf_path


def test_scan_empty_directory(temp_library):
    """Test scanning an empty directory."""
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_library])
    assert len(documents) == 0


def test_scan_with_pdf(temp_library, sample_pdf):
    """Test scanning a directory with a PDF."""
    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_library])

    assert len(documents) == 1
    assert documents[0].filename == "test.pdf"
    assert documents[0].page_count == 1
    assert documents[0].status == DocumentStatus.PENDING


def test_extract_metadata(sample_pdf):
    """Test metadata extraction."""
    catalog = PDFCatalog()
    metadata = catalog.extract_metadata(sample_pdf)

    assert metadata.filename == "test.pdf"
    assert metadata.path == str(sample_pdf)
    assert metadata.page_count == 1
    assert metadata.size_bytes > 0
    assert len(metadata.id) == 64  # SHA256 hex digest


def test_duplicate_detection(temp_library, sample_pdf):
    """Test duplicate detection."""
    # Create a copy of the PDF
    pdf_copy = temp_library / "copy.pdf"
    pdf_copy.write_bytes(sample_pdf.read_bytes())

    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_library])

    assert len(documents) == 2

    duplicates = catalog.find_duplicates()
    assert len(duplicates) == 1
    assert len(list(duplicates.values())[0]) == 2


def test_hash_calculation(sample_pdf):
    """Test file hash calculation."""
    catalog = PDFCatalog()

    # Calculate hash twice - should be identical
    hash1 = catalog._calculate_hash(sample_pdf)
    hash2 = catalog._calculate_hash(sample_pdf)

    assert hash1 == hash2
    assert len(hash1) == 64


def test_recursive_scan(temp_library):
    """Test recursive directory scanning."""
    # Create nested structure
    subdir = temp_library / "subdir"
    subdir.mkdir()

    # Create PDFs in different directories
    pdf1 = temp_library / "pdf1.pdf"
    pdf2 = subdir / "pdf2.pdf"

    for pdf_path in [pdf1, pdf2]:
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(pdf_path, "wb") as f:
            writer.write(f)

    catalog = PDFCatalog()
    documents = catalog.scan_directories([temp_library])

    assert len(documents) == 2
    filenames = {doc.filename for doc in documents}
    assert filenames == {"pdf1.pdf", "pdf2.pdf"}
