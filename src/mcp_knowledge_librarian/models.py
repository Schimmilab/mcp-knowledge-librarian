"""Data models for the knowledge librarian."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    INDEXED = "indexed"
    OCR_REQUIRED = "ocr_required"
    ERROR = "error"


class DocumentMetadata(BaseModel):
    """Metadata for a PDF document."""

    id: str = Field(description="Unique document identifier (hash)")
    filename: str = Field(description="Original filename")
    path: str = Field(description="Full path to the document")
    size_bytes: int = Field(description="File size in bytes")
    mtime: Optional[float] = Field(
        default=None, description="File modification time (st_mtime) at index time"
    )
    page_count: int = Field(description="Number of pages")
    title: Optional[str] = Field(default=None, description="Document title from metadata")
    author: Optional[str] = Field(default=None, description="Document author from metadata")
    creation_date: Optional[datetime] = Field(
        default=None, description="Document creation date from metadata"
    )
    modification_date: Optional[datetime] = Field(
        default=None, description="Document modification date from metadata"
    )
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING, description="Processing status"
    )
    indexed_at: Optional[datetime] = Field(default=None, description="When document was indexed")
    error_message: Optional[str] = Field(
        default=None, description="Error message if processing failed"
    )
    is_scan: bool = Field(default=False, description="Whether document appears to be a scan")


class TextChunk(BaseModel):
    """A chunk of text extracted from a document."""

    chunk_id: str = Field(description="Unique chunk identifier")
    document_id: str = Field(description="Parent document ID")
    page_number: int = Field(description="Page number (1-indexed)")
    text: str = Field(description="Extracted text content")
    char_offset: int = Field(description="Character offset within the page")
    char_length: int = Field(description="Length of text in characters")


class SearchResult(BaseModel):
    """A search result with citation information."""

    document_id: str = Field(description="Document ID")
    document_path: str = Field(description="Path to the document")
    document_title: Optional[str] = Field(default=None, description="Document title")
    page_number: int = Field(description="Page number where text was found")
    snippet: str = Field(description="Text snippet with context")
    score: float = Field(description="Relevance score (0.0-1.0)")
    chunk_id: str = Field(description="Chunk ID for reference")


class SearchQuery(BaseModel):
    """Search query parameters."""

    query: str = Field(description="Search query text")
    max_results: int = Field(default=20, description="Maximum number of results")
    min_score: float = Field(default=0.1, description="Minimum relevance score")
    document_id: Optional[str] = Field(
        default=None, description="Limit search to specific document"
    )
