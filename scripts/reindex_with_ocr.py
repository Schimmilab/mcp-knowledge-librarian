#!/usr/bin/env python3
"""Re-index documents that require OCR."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path to import mcp_knowledge_librarian
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.catalog import PDFCatalog
from mcp_knowledge_librarian.extractor import TextExtractor
from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import DocumentStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def reindex_with_ocr(index_path: str = ".index", ocr_language: str = "eng"):
    """Re-index documents that require OCR."""

    # Initialize components with OCR enabled
    indexer = IndexManager(index_path=index_path, enable_semantic=False)
    extractor = TextExtractor(enable_ocr=True, ocr_language=ocr_language)

    # Find documents that need OCR
    ocr_required = [
        doc for doc in indexer.list_documents()
        if doc.status == DocumentStatus.OCR_REQUIRED
    ]

    if not ocr_required:
        logger.info("No documents require OCR")
        return

    logger.info(f"Found {len(ocr_required)} documents that require OCR")

    success_count = 0
    error_count = 0

    for doc in ocr_required:
        logger.info(f"Processing: {doc.filename}")

        try:
            # Extract text with OCR
            chunks, is_scan = extractor.extract_text_from_document(doc)

            # Re-index document
            indexer.index_document(doc, chunks, is_scan)

            if doc.status == DocumentStatus.INDEXED:
                logger.info(f"✓ Successfully indexed {doc.filename} ({len(chunks)} chunks)")
                success_count += 1
            else:
                logger.warning(f"⚠ Document {doc.filename} still has status: {doc.status}")
                error_count += 1

        except Exception as e:
            logger.error(f"✗ Failed to process {doc.filename}: {e}")
            error_count += 1

    logger.info(f"\n{'='*60}")
    logger.info(f"Re-indexing complete:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info(f"  Total:   {len(ocr_required)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Re-index documents with OCR")
    parser.add_argument(
        "--index-path",
        default=".index",
        help="Path to index directory (default: .index)",
    )
    parser.add_argument(
        "--language",
        default="eng",
        help="OCR language code (default: eng)",
    )

    args = parser.parse_args()

    asyncio.run(reindex_with_ocr(args.index_path, args.language))
