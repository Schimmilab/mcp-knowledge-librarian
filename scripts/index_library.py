#!/usr/bin/env python3
"""Script to index the PDF library."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.server import KnowledgeLibrarianServer


async def main():
    """Index the library."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    print("Initializing server...")
    server = KnowledgeLibrarianServer(config_path)

    print("Starting indexing process...")
    print("This may take a while depending on the number of PDFs...\n")

    # Call the index_documents method directly
    result = await server._index_documents(force_reindex=False)

    print("\n" + "="*60)
    print("Indexing complete!")
    print("="*60)
    for item in result:
        print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
