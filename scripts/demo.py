#!/usr/bin/env python3
"""Demo script for the knowledge librarian."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.catalog import PDFCatalog
from mcp_knowledge_librarian.extractor import TextExtractor
from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import SearchQuery


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_section(text: str):
    """Print a formatted section."""
    print("\n" + "-" * 70)
    print(f"  {text}")
    print("-" * 70 + "\n")


async def demo_index():
    """Demo: Index documents."""
    print_header("DEMO: Indexing PDF Library")

    # Initialize components
    catalog = PDFCatalog()
    extractor = TextExtractor(enable_ocr=False)
    indexer = IndexManager(index_path=".index", enable_semantic=False)

    # Scan library
    print_section("Scanning demo_library/")
    documents = catalog.scan_directories(["demo_library"])
    print(f"Found {len(documents)} PDF documents")

    for doc in documents:
        print(f"  - {doc.filename} ({doc.page_count} pages)")

    # Check for duplicates
    duplicates = catalog.find_duplicates()
    if duplicates:
        print(f"\n⚠️  Found {len(duplicates)} sets of duplicates")
    else:
        print("\n✓ No duplicates found")

    # Index documents
    print_section("Indexing Documents")
    stats = {"indexed": 0, "ocr_required": 0, "errors": 0}

    for doc in documents:
        try:
            print(f"Processing {doc.filename}...", end=" ")
            chunks, is_scan = extractor.extract_text_from_document(doc)
            indexer.index_document(doc, chunks, is_scan)

            if doc.status.value == "indexed":
                stats["indexed"] += 1
                print(f"✓ Indexed ({len(chunks)} chunks)")
            elif doc.status.value == "ocr_required":
                stats["ocr_required"] += 1
                print("⚠️  OCR required")
            else:
                stats["errors"] += 1
                print("✗ Error")

        except Exception as e:
            stats["errors"] += 1
            print(f"✗ Error: {e}")

    # Summary
    print_section("Indexing Summary")
    print(f"Indexed:      {stats['indexed']}")
    print(f"OCR required: {stats['ocr_required']}")
    print(f"Errors:       {stats['errors']}")

    # Get statistics
    index_stats = indexer.get_statistics()
    print(f"\nTotal documents in index: {index_stats['total_documents']}")
    print(f"Total text chunks:        {index_stats['total_chunks']}")


async def demo_search():
    """Demo: Search documents."""
    print_header("DEMO: Searching PDF Library")

    # Initialize indexer
    indexer = IndexManager(index_path=".index", enable_semantic=False)

    # Check if index exists
    stats = indexer.get_statistics()
    if stats["total_documents"] == 0:
        print("❌ No documents in index. Run 'python scripts/demo.py index' first.")
        return

    print(f"Index contains {stats['total_documents']} documents with {stats['total_chunks']} chunks\n")

    # Demo queries
    queries = [
        "neural networks",
        "machine learning applications",
        "python programming",
        "data science workflow",
        "hypothesis testing",
    ]

    for query_text in queries:
        print_section(f'Search: "{query_text}"')

        query = SearchQuery(query=query_text, max_results=3, min_score=0.0)
        results = indexer.search(query, keyword_weight=0.7)

        if not results:
            print("No results found.")
            continue

        print(f"Found {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {result.document_path}")
            print(f"   Page {result.page_number} | Score: {result.score:.4f}")
            print(f"   {result.snippet}")
            print()

            # Show full chunk for first result
            if i == 1:
                print("   Full context:")
                chunk = indexer.get_chunk(result.chunk_id)
                if chunk:
                    preview = chunk.text[:300] + "..." if len(chunk.text) > 300 else chunk.text
                    print(f"   {preview}")
                print()


async def demo_metadata():
    """Demo: Document metadata."""
    print_header("DEMO: Document Metadata")

    indexer = IndexManager(index_path=".index", enable_semantic=False)
    documents = indexer.list_documents()

    if not documents:
        print("❌ No documents in index.")
        return

    print(f"Found {len(documents)} documents:\n")

    for doc in documents:
        print(f"Filename: {doc.filename}")
        print(f"Path:     {doc.path}")
        print(f"Pages:    {doc.page_count}")
        print(f"Status:   {doc.status.value}")
        print(f"Scan:     {doc.is_scan}")
        if doc.title:
            print(f"Title:    {doc.title}")
        print()


async def main():
    """Main demo entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/demo.py [index|search|metadata]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "index":
        await demo_index()
    elif command == "search":
        await demo_search()
    elif command == "metadata":
        await demo_metadata()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: index, search, metadata")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
