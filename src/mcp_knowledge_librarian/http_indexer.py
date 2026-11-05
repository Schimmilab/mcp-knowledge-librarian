"""Extended IndexManager that can generate HTTP URLs for results."""

from typing import Optional

from .indexer import IndexManager
from .models import SearchQuery, SearchResult


class HTTPIndexManager(IndexManager):
    """Index manager that generates HTTP URLs for search results."""

    def __init__(
        self,
        index_path: str,
        enable_semantic: bool = False,
        http_base_url: Optional[str] = None,
    ):
        """
        Initialize the HTTP-aware index manager.

        Args:
            index_path: Path to store the index
            enable_semantic: Whether to enable semantic search
            http_base_url: Base URL for HTTP server (e.g., "http://localhost:8765")
        """
        super().__init__(index_path, enable_semantic)
        self.http_base_url = http_base_url

    def search(
        self, query: SearchQuery, keyword_weight: float = 0.5
    ) -> list[SearchResult]:
        """
        Search the index and return results with HTTP URLs if configured.

        Args:
            query: Search query
            keyword_weight: Weight for keyword search (0.0-1.0)

        Returns:
            List of search results
        """
        results = super().search(query, keyword_weight)

        # If HTTP base URL is configured, replace file:// URLs with HTTP URLs
        if self.http_base_url:
            for result in results:
                # Extract document_id from the file:// URL
                # (it's stored as the document_id field anyway)
                result.document_path = (
                    f"{self.http_base_url}/pdf/{result.document_id}?page={result.page_number}"
                )

        return results
