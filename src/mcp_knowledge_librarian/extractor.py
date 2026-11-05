"""Text extraction from PDF documents."""

import logging
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentMetadata, TextChunk

logger = logging.getLogger(__name__)


class TextExtractor:
    """Handles text extraction from PDF documents."""

    def __init__(self, enable_ocr: bool = False, ocr_language: str = "eng"):
        """
        Initialize the text extractor.

        Args:
            enable_ocr: Whether to enable OCR for scanned documents
            ocr_language: Tesseract language code
        """
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language

        if enable_ocr:
            try:
                import pytesseract

                self.pytesseract = pytesseract
                logger.info("OCR enabled")
            except ImportError:
                logger.warning("pytesseract not available, OCR will be disabled")
                self.enable_ocr = False
                self.pytesseract = None
        else:
            self.pytesseract = None

    def extract_text_from_document(
        self, metadata: DocumentMetadata
    ) -> tuple[list[TextChunk], bool]:
        """
        Extract text from a PDF document.

        Args:
            metadata: Document metadata

        Returns:
            Tuple of (list of text chunks, is_scan flag)
        """
        pdf_path = Path(metadata.path)
        chunks = []
        is_scan = False

        try:
            with open(pdf_path, "rb") as f:
                reader = PdfReader(f)

                # Check if document is likely a scan
                is_scan = self._is_scanned_pdf(reader)

                if is_scan and not self.enable_ocr:
                    logger.info(f"Document {metadata.filename} appears to be a scan (OCR disabled)")
                    return chunks, is_scan

                # Scans: render each page to an image and OCR it (full-page
                # rendering via pdf2image — pypdf's page.images only yields
                # embedded raster XObjects, which misses most real scans).
                if is_scan and self.enable_ocr:
                    return self._ocr_scanned_pdf(metadata, len(reader.pages)), is_scan

                # Text PDFs: extract embedded text per page
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        text = page.extract_text()

                        if text and text.strip():
                            chunk = TextChunk(
                                chunk_id=f"{metadata.id}:page:{page_num}",
                                document_id=metadata.id,
                                page_number=page_num,
                                text=text,
                                char_offset=0,
                                char_length=len(text),
                            )
                            chunks.append(chunk)

                    except Exception as e:
                        logger.error(
                            f"Failed to extract text from page {page_num} of {metadata.filename}: {e}"
                        )

            logger.info(
                f"Extracted {len(chunks)} text chunks from {metadata.filename} "
                f"(scan: {is_scan})"
            )

        except Exception as e:
            logger.error(f"Failed to extract text from {metadata.filename}: {e}")
            raise

        return chunks, is_scan

    def _is_scanned_pdf(self, reader: PdfReader, sample_pages: int = 3) -> bool:
        """
        Detect if a PDF is likely a scanned document.

        Args:
            reader: PDF reader instance
            sample_pages: Number of pages to sample

        Returns:
            True if document appears to be a scan
        """
        total_pages = len(reader.pages)
        pages_to_check = min(sample_pages, total_pages)

        text_chars = 0
        for i in range(pages_to_check):
            try:
                text = reader.pages[i].extract_text()
                text_chars += len(text.strip())
            except Exception:
                pass

        # If average text per page is very low, likely a scan
        avg_chars_per_page = text_chars / pages_to_check if pages_to_check > 0 else 0

        # Threshold: less than 50 characters per page suggests a scan
        is_scan = avg_chars_per_page < 50

        logger.debug(
            f"Scan detection: {avg_chars_per_page:.1f} chars/page "
            f"(threshold: 50) -> {'scan' if is_scan else 'text'}"
        )

        return is_scan

    def _ocr_scanned_pdf(
        self, metadata: DocumentMetadata, total_pages: int, dpi: int = 200, batch: int = 8
    ) -> list[TextChunk]:
        """
        OCR a scanned PDF by rendering each page to a full-page image.

        Pages are rendered in batches (via pdf2image/poppler) to keep memory
        bounded on large documents, then run through Tesseract.

        Args:
            metadata: Document metadata
            total_pages: Number of pages in the PDF
            dpi: Rendering resolution
            batch: Pages rendered per pdf2image call

        Returns:
            List of text chunks (one per page that yielded text)
        """
        if not self.enable_ocr or not self.pytesseract:
            return []

        from pdf2image import convert_from_path  # optional dependency (ocr extra)

        chunks: list[TextChunk] = []
        for start in range(1, total_pages + 1, batch):
            end = min(start + batch - 1, total_pages)
            try:
                images = convert_from_path(
                    metadata.path, dpi=dpi, first_page=start, last_page=end
                )
            except Exception as e:
                logger.error(
                    f"Render failed for {metadata.filename} pages {start}-{end}: {e}"
                )
                continue

            for offset, img in enumerate(images):
                page_num = start + offset
                try:
                    text = self.pytesseract.image_to_string(img, lang=self.ocr_language)
                except Exception as e:
                    logger.warning(f"OCR failed on page {page_num} of {metadata.filename}: {e}")
                    continue

                if text and text.strip():
                    chunks.append(
                        TextChunk(
                            chunk_id=f"{metadata.id}:page:{page_num}",
                            document_id=metadata.id,
                            page_number=page_num,
                            text=text,
                            char_offset=0,
                            char_length=len(text),
                        )
                    )

        logger.info(f"OCR extracted {len(chunks)} pages from {metadata.filename}")
        return chunks

    def create_fixed_size_chunks(
        self, text: str, document_id: str, page_number: int, chunk_size: int, overlap: int
    ) -> list[TextChunk]:
        """
        Split text into fixed-size chunks with overlap.

        Args:
            text: Text to chunk
            document_id: Parent document ID
            page_number: Page number
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks in characters

        Returns:
            List of text chunks
        """
        chunks = []
        text_length = len(text)

        start = 0
        chunk_num = 0

        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk_text = text[start:end]

            if chunk_text.strip():
                chunk = TextChunk(
                    chunk_id=f"{document_id}:page:{page_number}:chunk:{chunk_num}",
                    document_id=document_id,
                    page_number=page_number,
                    text=chunk_text,
                    char_offset=start,
                    char_length=len(chunk_text),
                )
                chunks.append(chunk)
                chunk_num += 1

            # Move start position
            start = end if start + chunk_size >= text_length else start + chunk_size - overlap

        return chunks
