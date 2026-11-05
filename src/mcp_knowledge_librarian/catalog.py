"""PDF cataloging and metadata extraction."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

from .models import DocumentMetadata, DocumentStatus

logger = logging.getLogger(__name__)


class PDFCatalog:
    """Handles PDF discovery, cataloging, and metadata extraction."""

    def __init__(self):
        """Initialize the catalog."""
        self.documents: dict[str, DocumentMetadata] = {}
        # Identical files share a hash and overwrite each other in
        # self.documents, so duplicate paths are tracked separately.
        self._paths_by_hash: dict[str, list[str]] = {}

    def scan_directories(self, paths: list[str | Path]) -> list[DocumentMetadata]:
        """
        Scan directories recursively for PDF files.

        Args:
            paths: List of directory paths to scan

        Returns:
            List of discovered document metadata
        """
        discovered = []

        for path_str in paths:
            path = Path(path_str).expanduser().resolve()
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue

            if not path.is_dir():
                logger.warning(f"Path is not a directory: {path}")
                continue

            logger.info(f"Scanning directory: {path}")
            for pdf_path in path.rglob("*.pdf"):
                if pdf_path.is_file():
                    try:
                        metadata = self.extract_metadata(pdf_path)
                        discovered.append(metadata)
                        self.documents[metadata.id] = metadata
                        paths = self._paths_by_hash.setdefault(metadata.id, [])
                        if str(pdf_path) not in paths:
                            paths.append(str(pdf_path))
                        logger.info(f"Cataloged: {pdf_path.name} (ID: {metadata.id})")
                    except Exception as e:
                        logger.error(f"Failed to catalog {pdf_path}: {e}")

        logger.info(f"Discovered {len(discovered)} PDF documents")
        return discovered

    def discover_files(
        self, paths: list[str | Path]
    ) -> list[tuple[Path, int, float]]:
        """Discover PDF files with stat info only — no file reads.

        On cloud mounts (OneDrive/Google Drive) content reads force a
        download; stat() works on placeholder metadata alone.

        Returns:
            List of (path, size_bytes, mtime) tuples
        """
        discovered = []
        for path_str in paths:
            path = Path(path_str).expanduser().resolve()
            if not path.is_dir():
                logger.warning(f"Path is not a directory: {path}")
                continue
            for pdf_path in path.rglob("*.pdf"):
                try:
                    stat = pdf_path.stat()
                    discovered.append((pdf_path, stat.st_size, stat.st_mtime))
                except OSError as e:
                    logger.warning(f"Cannot stat {pdf_path}: {e}")
        logger.info(f"Discovered {len(discovered)} PDF files")
        return discovered

    @staticmethod
    def select_changed(
        discovered: list[tuple[Path, int, float]],
        known_states: dict[str, tuple[int, float | None]],
    ) -> list[tuple[Path, int, float]]:
        """Filter to files that are new or changed vs. the known index state.

        Documents migrated from the legacy index have no stored mtime; for
        those, a size match counts as unchanged so the first incremental run
        does not re-extract the whole library.
        """
        changed = []
        for pdf_path, size, mtime in discovered:
            known = known_states.get(str(pdf_path))
            if known is None:
                changed.append((pdf_path, size, mtime))
                continue
            known_size, known_mtime = known
            if known_size != size:
                changed.append((pdf_path, size, mtime))
            elif known_mtime is not None and abs(known_mtime - mtime) > 1e-6:
                changed.append((pdf_path, size, mtime))
        return changed

    def extract_metadata(self, pdf_path: Path) -> DocumentMetadata:
        """
        Extract metadata from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Document metadata

        Raises:
            Exception: If metadata extraction fails
        """
        try:
            # Calculate file hash for ID and duplicate detection
            file_hash = self._calculate_hash(pdf_path)

            # Get file stats
            stat = pdf_path.stat()
            size_bytes = stat.st_size
            mtime = stat.st_mtime

            # Read PDF metadata
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)
                page_count = len(reader.pages)

                # Extract metadata if available
                info = reader.metadata
                title = self._meta_str(info, "/Title")
                author = self._meta_str(info, "/Author")

                # Parse dates
                creation_date = None
                modification_date = None

                if info:
                    creation_date = self._parse_pdf_date(info.get("/CreationDate"))
                    modification_date = self._parse_pdf_date(info.get("/ModDate"))

            return DocumentMetadata(
                id=file_hash,
                filename=pdf_path.name,
                path=str(pdf_path),
                size_bytes=size_bytes,
                mtime=mtime,
                page_count=page_count,
                title=title,
                author=author,
                creation_date=creation_date,
                modification_date=modification_date,
                status=DocumentStatus.PENDING,
            )

        except Exception as e:
            logger.error(f"Failed to extract metadata from {pdf_path}: {e}")
            raise

    @staticmethod
    def _meta_str(info, key: str) -> Optional[str]:
        """Read a PDF info entry as string, resolving IndirectObject refs."""
        if not info:
            return None
        value = info.get(key)
        if value is None:
            return None
        try:
            if hasattr(value, "get_object"):
                value = value.get_object()
            text = str(value).strip()
            return text or None
        except Exception:
            return None

    def _calculate_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hex digest of the file hash
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse PDF date string to datetime.

        PDF dates are in format: D:YYYYMMDDHHmmSSOHH'mm

        Args:
            date_str: PDF date string

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        try:
            # Remove D: prefix and timezone info for simplicity
            date_str = date_str.replace("D:", "").split("+")[0].split("-")[0].split("Z")[0]

            # Parse up to seconds
            if len(date_str) >= 14:
                return datetime.strptime(date_str[:14], "%Y%m%d%H%M%S")
            elif len(date_str) >= 8:
                return datetime.strptime(date_str[:8], "%Y%m%d")
        except Exception as e:
            logger.debug(f"Failed to parse PDF date '{date_str}': {e}")

        return None

    def get_document(self, document_id: str) -> Optional[DocumentMetadata]:
        """
        Get document metadata by ID.

        Args:
            document_id: Document ID

        Returns:
            Document metadata or None if not found
        """
        return self.documents.get(document_id)

    def find_duplicates(self) -> dict[str, list[str]]:
        """
        Find duplicate documents based on hash.

        Returns:
            Dictionary mapping hash to list of file paths
        """
        duplicates = {
            k: list(v) for k, v in self._paths_by_hash.items() if len(v) > 1
        }

        if duplicates:
            logger.info(f"Found {len(duplicates)} sets of duplicate documents")

        return duplicates
