#!/usr/bin/env python3
"""Monitor the indexing progress."""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_knowledge_librarian.server import KnowledgeLibrarianServer


async def get_stats(server):
    """Get current statistics."""
    # Force refresh by reloading metadata and chunks from disk
    server.indexer.documents = server.indexer._load_metadata()
    server.indexer.chunks = server.indexer._load_chunks()
    stats = server.indexer.get_statistics()
    return stats


async def monitor():
    """Monitor indexing progress."""
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"

    print("🔍 Knowledge Librarian - Indexing Monitor")
    print("=" * 60)

    server = KnowledgeLibrarianServer(config_path)

    # Count total PDFs
    print("\n📊 Counting total PDFs in library...")
    import subprocess
    result = subprocess.run(
        ['find', server.config['library_paths'][0],
         '-name', '*.pdf', '-type', 'f'],
        capture_output=True,
        text=True
    )
    total_pdfs = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

    print(f"   Total PDFs found: {total_pdfs}")

    # Get initial stats
    prev_stats = await get_stats(server)
    prev_count = prev_stats['total_documents']
    start_time = time.time()

    print("\n📈 Monitoring indexing progress...")
    print("   Press Ctrl+C to stop\n")

    try:
        while True:
            stats = await get_stats(server)

            indexed = stats.get('total_documents', 0)
            chunks = stats.get('total_chunks', 0)
            by_status = stats.get('by_status', {})

            # Calculate progress
            progress = (indexed / total_pdfs * 100) if total_pdfs > 0 else 0
            remaining = total_pdfs - indexed

            # Calculate speed
            elapsed = time.time() - start_time
            if elapsed > 0:
                docs_per_sec = (indexed - prev_count) / elapsed
                if docs_per_sec > 0:
                    eta_seconds = remaining / docs_per_sec
                    eta_hours = int(eta_seconds // 3600)
                    eta_mins = int((eta_seconds % 3600) // 60)
                    eta_str = f"{eta_hours}h {eta_mins}m"
                else:
                    eta_str = "calculating..."
            else:
                docs_per_sec = 0
                eta_str = "calculating..."

            # Clear screen (simple version)
            print("\033[2J\033[H", end="")

            print("🔍 Knowledge Librarian - Indexing Monitor")
            print("=" * 60)
            print(f"\n📚 Total PDFs in library:     {total_pdfs}")
            print(f"✅ Documents indexed:         {indexed} ({progress:.1f}%)")
            print(f"📄 Text chunks extracted:     {chunks:,}")
            print(f"⏳ Remaining documents:       {remaining}")
            print(f"⚡ Speed:                     {docs_per_sec:.2f} docs/sec")
            print(f"🕐 Estimated time remaining:  {eta_str}")

            print(f"\n📊 Status breakdown:")
            for status, count in by_status.items():
                print(f"   {status:15s}: {count:5d}")

            # Progress bar
            bar_width = 50
            filled = int(bar_width * progress / 100)
            bar = "█" * filled + "░" * (bar_width - filled)
            print(f"\n[{bar}] {progress:.1f}%")

            print("\n💡 Tip: The background indexer runs every 5 minutes")
            print("   Next scan in: ~", end="")

            # Wait 10 seconds before next update
            await asyncio.sleep(10)

    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped")
        print(f"   Final count: {indexed}/{total_pdfs} documents indexed")


if __name__ == "__main__":
    asyncio.run(monitor())
