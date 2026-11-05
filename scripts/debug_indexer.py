#!/usr/bin/env python3
"""Debug the indexer state."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.server import KnowledgeLibrarianServer
from mcp_knowledge_librarian.catalog import PDFCatalog
import asyncio


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    print("🔍 Debugging Indexer State\n")
    print("=" * 60)

    # Initialize server
    print("\n1️⃣ Loading server configuration...")
    server = KnowledgeLibrarianServer(config_path)

    # Check config
    print("\n2️⃣ Background indexing configuration:")
    bg_config = server.config.get("background_indexing", {})
    print(f"   Enabled: {bg_config.get('enabled', False)}")
    print(f"   Scan interval: {bg_config.get('scan_interval', 'N/A')}s")
    print(f"   Batch size: {bg_config.get('batch_size', 'N/A')}")
    print(f"   Index on startup: {bg_config.get('index_on_startup', False)}")

    # Check current index stats
    print("\n3️⃣ Current index statistics:")
    stats = server.indexer.get_statistics()
    print(f"   Total documents: {stats.get('total_documents', 0)}")
    print(f"   Total chunks: {stats.get('total_chunks', 0)}")

    # Scan directories
    print("\n4️⃣ Scanning directories for PDFs...")
    library_paths = server.config["library_paths"]
    print(f"   Library paths: {library_paths}")

    catalog = PDFCatalog()
    print("   Scanning (this may take a moment)...")
    documents = catalog.scan_directories(library_paths)
    print(f"   Found {len(documents)} PDF documents")

    # Check which are not indexed
    print("\n5️⃣ Checking indexing status...")
    not_indexed = []
    indexed = []

    for metadata in documents:
        existing = server.indexer.get_document_metadata(metadata.id)
        if not existing or existing.status.value == "error":
            not_indexed.append(metadata)
        else:
            indexed.append(metadata)

    print(f"   ✅ Already indexed: {len(indexed)}")
    print(f"   ⏳ Not yet indexed: {len(not_indexed)}")

    if not_indexed:
        print("\n   First 10 pending documents:")
        for i, doc in enumerate(not_indexed[:10], 1):
            print(f"      {i}. {doc.filename}")

    # Check if background task would find them
    print("\n6️⃣ Simulating background indexer logic...")
    pending = []
    for metadata in documents:
        existing = server.indexer.get_document_metadata(metadata.id)
        if not existing or existing.status.value == "error":
            pending.append(metadata)

    print(f"   Background indexer would find: {len(pending)} documents")

    print("\n" + "=" * 60)
    print("✅ Debug complete!")


if __name__ == "__main__":
    asyncio.run(main())
