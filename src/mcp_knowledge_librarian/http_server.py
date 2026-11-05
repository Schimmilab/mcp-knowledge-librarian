"""HTTP server module for PDF preview and browsing."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from aiohttp import web
import html as _html

from .indexer import IndexManager
from .models import SearchQuery

logger = logging.getLogger(__name__)


class PDFPreviewServer:
    """HTTP server for serving PDFs with page navigation."""

    def __init__(self, index_manager: IndexManager, host: str = "127.0.0.1", port: int = 8765):
        """
        Initialize the PDF preview server.

        Args:
            index_manager: Index manager instance
            host: Host to bind to
            port: Port to listen on
        """
        self.indexer = index_manager
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._setup_routes()

    def _setup_routes(self):
        """Set up HTTP routes."""
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/pdf/{document_id}", self.handle_pdf)
        self.app.router.add_get("/search", self.handle_search)

    async def handle_index(self, request: web.Request) -> web.Response:
        """Handle index page."""
        documents = self.indexer.list_documents()

        html = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Library</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; }
        .document { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; background: #f9f9f9; }
        .document h3 { margin: 0 0 10px 0; }
        .document p { margin: 5px 0; color: #666; }
        .document a { color: #0066cc; text-decoration: none; }
        .document a:hover { text-decoration: underline; }
        .status { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
        .status-indexed { background: #d4edda; color: #155724; }
        .status-ocr_required { background: #fff3cd; color: #856404; }
        .status-error { background: #f8d7da; color: #721c24; }
        .search-box { margin: 20px 0; padding: 20px; background: #f0f0f0; border-radius: 8px; }
        .search-box input { width: 60%; padding: 10px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; }
        .search-box button { padding: 10px 20px; font-size: 16px; border: none; background: #0066cc; color: white; border-radius: 4px; cursor: pointer; }
        .search-box button:hover { background: #0052a3; }
    </style>
</head>
<body>
    <h1>📚 PDF Library</h1>

    <div class="search-box">
        <form action="/search" method="get">
            <input type="text" name="q" placeholder="Search documents..." required>
            <button type="submit">Search</button>
        </form>
    </div>

    <h2>Documents ({total})</h2>
""".format(total=len(documents))

        for doc in sorted(documents, key=lambda d: d.filename):
            status_class = f"status-{doc.status.value}"
            html += f"""
    <div class="document">
        <h3><a href="/pdf/{doc.id}">{_html.escape(doc.title or doc.filename)}</a></h3>
        <p><strong>File:</strong> {_html.escape(doc.filename)}</p>
        <p><strong>Pages:</strong> {doc.page_count} | <span class="status {status_class}">{doc.status.value}</span></p>
        {f'<p><strong>Author:</strong> {_html.escape(doc.author)}</p>' if doc.author else ''}
        <p><a href="/pdf/{doc.id}">Open PDF</a></p>
    </div>
"""

        html += """
</body>
</html>
"""
        return web.Response(text=html, content_type="text/html")

    async def handle_pdf(self, request: web.Request) -> web.Response:
        """Handle PDF viewing."""
        document_id = request.match_info["document_id"]
        page = int(request.query.get("page", 1))

        metadata = self.indexer.get_document_metadata(document_id)
        if not metadata:
            return web.Response(text="Document not found", status=404)

        pdf_path = Path(metadata.path)
        if not pdf_path.exists():
            return web.Response(text="PDF file not found", status=404)

        # Serve PDF with page fragment
        with open(pdf_path, "rb") as f:
            pdf_data = f.read()

        headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": f'inline; filename="{metadata.filename}"',
        }

        # Add page navigation hint for browsers
        if page > 1:
            headers["Content-Location"] = f"/pdf/{document_id}#page={page}"

        return web.Response(body=pdf_data, headers=headers)

    async def handle_search(self, request: web.Request) -> web.Response:
        """Handle search requests."""
        query = request.query.get("q", "")

        if not query:
            return web.Response(text="No query provided", status=400)

        search_query = SearchQuery(query=query, max_results=50, min_score=0.1)
        results = self.indexer.search(search_query)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Search: {_html.escape(query)}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px; max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #333; }}
        .result {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 8px; background: #f9f9f9; }}
        .result h3 {{ margin: 0 0 10px 0; }}
        .result p {{ margin: 5px 0; color: #666; }}
        .result a {{ color: #0066cc; text-decoration: none; }}
        .result a:hover {{ text-decoration: underline; }}
        .snippet {{ background: #fff; padding: 10px; border-left: 3px solid #0066cc; margin: 10px 0; font-family: monospace; white-space: pre-wrap; }}
        .score {{ color: #888; font-size: 14px; }}
        .back {{ display: inline-block; margin: 20px 0; color: #0066cc; text-decoration: none; }}
        .back:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <a class="back" href="/">← Back to Library</a>
    <h1>Search Results: "{_html.escape(query)}"</h1>
    <p>Found {len(results)} results</p>
"""

        for result in results:
            html += f"""
    <div class="result">
        <h3><a href="/pdf/{result.document_id}?page={result.page_number}">{_html.escape(result.document_title or "Untitled")}</a></h3>
        <p>Page {result.page_number} | <span class="score">Score: {result.score:.3f}</span></p>
        <div class="snippet">{_html.escape(result.snippet)}</div>
        <p><a href="/pdf/{result.document_id}?page={result.page_number}">Open PDF at page {result.page_number}</a></p>
    </div>
"""

        if not results:
            html += '<p style="color: #888;">No results found. Try different search terms.</p>'

        html += """
</body>
</html>
"""
        return web.Response(text=html, content_type="text/html")

    async def start(self):
        """Start the server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"HTTP server started at http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("HTTP server stopped")
