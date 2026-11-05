"""MCP server implementation for the knowledge librarian."""

import asyncio
import json
import logging
from typing import Any, Optional

import yaml
from mcp.server import Server
from mcp.types import Tool, TextContent

from .catalog import PDFCatalog
from .extractor import TextExtractor
from .indexer import IndexManager
from .models import DocumentStatus, SearchQuery

logger = logging.getLogger(__name__)


def _json(data) -> str:
    """Compact JSON — tool output lands in the LLM context window."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


class KnowledgeLibrarianServer:
    """MCP server for PDF knowledge library management."""

    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize the server.

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Configure logging
        logging.basicConfig(
            level=self.config["logging"]["level"],
            format=self.config["logging"]["format"],
        )

        # Initialize components
        self.catalog = PDFCatalog()
        self.extractor = TextExtractor(
            enable_ocr=self.config["extraction"]["enable_ocr"],
            ocr_language=self.config["extraction"]["ocr_language"],
        )
        self.indexer = IndexManager(index_path=self.config["index_path"])

        # Semantic search config (embedding model loaded lazily on first use)
        search_cfg = self.config.get("search", {})
        self.enable_semantic = search_cfg.get("enable_semantic", False)
        self.enable_rerank = search_cfg.get("enable_rerank", False)
        self._embedding_model_name = search_cfg.get(
            "embedding_model", "intfloat/multilingual-e5-small"
        )
        self._rerank_model_name = search_cfg.get(
            "rerank_model", "BAAI/bge-reranker-v2-m3"
        )
        # Cap on how many hybrid candidates the (slow) cross-encoder rescores.
        self._rerank_pool = search_cfg.get("rerank_pool", 25)
        self._embedder = None
        self._reranker = None

        # Create MCP server
        self.server = Server("mcp-knowledge-librarian")

        # Background indexing state
        self._indexing_task: Optional[asyncio.Task] = None
        self._indexing_active = False

        # HTTP server state
        self._http_server: Optional[Any] = None
        self._http_server_task: Optional[asyncio.Task] = None

        # Register tools
        self._register_tools()

    def _register_tools(self):
        """Register MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="list_documents",
                    description="List indexed documents (paginated)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Max documents to return",
                                "default": 50,
                            },
                            "offset": {
                                "type": "integer",
                                "description": "Offset for pagination",
                                "default": 0,
                            },
                        },
                    },
                ),
                Tool(
                    name="index_documents",
                    description="Scan library paths and index all PDF documents",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "force_reindex": {
                                "type": "boolean",
                                "description": "Force reindexing of already indexed documents",
                                "default": False,
                            }
                        },
                    },
                ),
                Tool(
                    name="search",
                    description="Search for documents by keyword or semantic query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query text",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 20,
                            },
                            "min_score": {
                                "type": "number",
                                "description": "Minimum relevance score (0.0-1.0)",
                                "default": 0.1,
                            },
                            "document_id": {
                                "type": "string",
                                "description": "Limit search to specific document ID",
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="get_snippet",
                    description="Get a text snippet from a specific document and page",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chunk_id": {
                                "type": "string",
                                "description": "Chunk ID from search results",
                            }
                        },
                        "required": ["chunk_id"],
                    },
                ),
                Tool(
                    name="get_document_metadata",
                    description="Get metadata for a specific document",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "Document ID",
                            }
                        },
                        "required": ["document_id"],
                    },
                ),
                Tool(
                    name="get_statistics",
                    description="Get index statistics and health information",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="reindex_with_ocr",
                    description="Re-index documents that require OCR (scanned PDFs)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ocr_language": {
                                "type": "string",
                                "description": "OCR language code (e.g., 'eng', 'deu', 'fra')",
                                "default": "eng",
                            }
                        },
                    },
                ),
                Tool(
                    name="start_http_server",
                    description="Start HTTP preview server for browsing PDFs (bound to 127.0.0.1 only, no authentication)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "port": {
                                "type": "integer",
                                "description": "Port to listen on",
                                "default": 8765,
                            }
                        },
                    },
                ),
                Tool(
                    name="stop_http_server",
                    description="Stop the HTTP preview server",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> list[TextContent]:
            """Handle tool calls."""
            try:
                if name == "list_documents":
                    return await self._list_documents(
                        limit=arguments.get("limit", 50),
                        offset=arguments.get("offset", 0),
                    )
                elif name == "index_documents":
                    return await self._index_documents(
                        arguments.get("force_reindex", False)
                    )
                elif name == "search":
                    return await self._search(
                        query=arguments["query"],
                        max_results=arguments.get("max_results", 20),
                        min_score=arguments.get("min_score", 0.1),
                        document_id=arguments.get("document_id"),
                    )
                elif name == "get_snippet":
                    return await self._get_snippet(arguments["chunk_id"])
                elif name == "get_document_metadata":
                    return await self._get_document_metadata(arguments["document_id"])
                elif name == "get_statistics":
                    return await self._get_statistics()
                elif name == "reindex_with_ocr":
                    return await self._reindex_with_ocr(
                        arguments.get("ocr_language", "eng")
                    )
                elif name == "start_http_server":
                    # Security: never let a tool call choose the bind address. The preview server has
                    # no authentication and serves full PDFs; a prompt-injected "0.0.0.0" would expose
                    # the whole library to the network. Loopback only.
                    return await self._start_http_server(
                        host="127.0.0.1",
                        port=arguments.get("port", 8765),
                    )
                elif name == "stop_http_server":
                    return await self._stop_http_server()
                else:
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps({"error": f"Unknown tool: {name}"}),
                        )
                    ]
            except Exception as e:
                logger.error(f"Tool call failed: {e}", exc_info=True)
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": str(e)}),
                    )
                ]

    async def _list_documents(self, limit: int, offset: int) -> list[TextContent]:
        """List indexed documents, paginated."""
        documents = self.indexer.list_documents(limit=limit, offset=offset)

        result = {
            "total_documents": self.indexer.count_documents(),
            "limit": limit,
            "offset": offset,
            "documents": [
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "title": doc.title,
                    "page_count": doc.page_count,
                    "status": doc.status.value,
                }
                for doc in documents
            ],
        }

        return [TextContent(type="text", text=_json(result))]

    async def _index_documents(self, force_reindex: bool) -> list[TextContent]:
        """Index new/changed documents in library paths (incremental)."""
        results = {
            "discovered": 0,
            "indexed": 0,
            "unchanged": 0,
            "errors": 0,
            "ocr_required": 0,
            "details": [],
        }

        library_paths = self.config["library_paths"]
        discovered = self.catalog.discover_files(library_paths)
        results["discovered"] = len(discovered)

        if force_reindex:
            pending = discovered
        else:
            pending = self.catalog.select_changed(
                discovered, self.indexer.file_states()
            )
        results["unchanged"] = len(discovered) - len(pending)

        for pdf_path, _, _ in pending:
            try:
                metadata = self.catalog.extract_metadata(pdf_path)
                chunks, is_scan = self.extractor.extract_text_from_document(metadata)
                self.indexer.index_document(metadata, chunks, is_scan)

                if metadata.status.value == "indexed":
                    results["indexed"] += 1
                elif metadata.status.value == "ocr_required":
                    results["ocr_required"] += 1
                else:
                    results["errors"] += 1

                results["details"].append(
                    {
                        "filename": metadata.filename,
                        "status": metadata.status.value,
                        "chunks": len(chunks),
                    }
                )

            except Exception as e:
                results["errors"] += 1
                results["details"].append(
                    {
                        "filename": pdf_path.name,
                        "status": "error",
                        "error": str(e),
                    }
                )
                logger.error(f"Failed to index {pdf_path.name}: {e}")

        # Cap detail list so tool output stays token-friendly
        if len(results["details"]) > 50:
            results["details"] = results["details"][:50]
            results["details_truncated"] = True

        return [TextContent(type="text", text=_json(results))]

    @property
    def embedder(self):
        """Lazily load the embedding model (only when semantic search is used)."""
        if self._embedder is None:
            from .embeddings import EmbeddingModel

            self._embedder = EmbeddingModel(self._embedding_model_name)
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from .reranker import Reranker

            self._reranker = Reranker(self._rerank_model_name)
        return self._reranker

    async def _search(
        self,
        query: str,
        max_results: int,
        min_score: float,
        document_id: str | None,
    ) -> list[TextContent]:
        """Search for documents.

        Uses hybrid BM25 + semantic retrieval when semantic search is enabled
        and embeddings exist; otherwise falls back to pure BM25.
        """
        search_query = SearchQuery(
            query=query,
            max_results=max_results,
            min_score=min_score,
            document_id=document_id,
        )

        if self.enable_semantic and self.indexer.count_embeddings() > 0:
            query_vec = self.embedder.encode_query(query)
            if self.enable_rerank:
                # Retrieve a bounded pool, then let the cross-encoder pick the top.
                # Capped because the cross-encoder is slow (~3 pairs/s on MPS).
                pool_size = max(self._rerank_pool, max_results)
                cand_query = search_query.model_copy(
                    update={"max_results": pool_size}
                )
                candidates = self.indexer.hybrid_search(cand_query, query_vec)
                results = self.reranker.rerank(query, candidates, top_k=max_results)
                mode = "hybrid+rerank"
            else:
                results = self.indexer.hybrid_search(search_query, query_vec)
                mode = "hybrid"
        else:
            results = self.indexer.search(search_query)
            mode = "bm25"

        result = {
            "query": query,
            "mode": mode,
            "total_results": len(results),
            "results": [
                {
                    "document_id": r.document_id,
                    "document_path": r.document_path,
                    "document_title": r.document_title,
                    "page_number": r.page_number,
                    "snippet": r.snippet,
                    "score": round(r.score, 4),
                    "chunk_id": r.chunk_id,
                }
                for r in results
            ],
        }

        return [TextContent(type="text", text=_json(result))]

    async def _get_snippet(self, chunk_id: str) -> list[TextContent]:
        """Get a text snippet by chunk ID."""
        chunk = self.indexer.get_chunk(chunk_id)

        if not chunk:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": "Chunk not found"}),
                )
            ]

        metadata = self.indexer.get_document_metadata(chunk.document_id)

        result = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "document_path": metadata.path if metadata else None,
            "document_title": metadata.title if metadata else None,
            "page_number": chunk.page_number,
            "text": chunk.text,
            "char_offset": chunk.char_offset,
            "char_length": chunk.char_length,
        }

        return [TextContent(type="text", text=_json(result))]

    async def _get_document_metadata(self, document_id: str) -> list[TextContent]:
        """Get document metadata."""
        metadata = self.indexer.get_document_metadata(document_id)

        if not metadata:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": "Document not found"}),
                )
            ]

        result = {
            "id": metadata.id,
            "filename": metadata.filename,
            "path": metadata.path,
            "size_bytes": metadata.size_bytes,
            "page_count": metadata.page_count,
            "title": metadata.title,
            "author": metadata.author,
            "creation_date": metadata.creation_date.isoformat()
            if metadata.creation_date
            else None,
            "modification_date": metadata.modification_date.isoformat()
            if metadata.modification_date
            else None,
            "status": metadata.status.value,
            "is_scan": metadata.is_scan,
            "indexed_at": metadata.indexed_at.isoformat() if metadata.indexed_at else None,
            "error_message": metadata.error_message,
        }

        return [TextContent(type="text", text=_json(result))]

    async def _get_statistics(self) -> list[TextContent]:
        """Get index statistics."""
        stats = self.indexer.get_statistics()

        # Add HTTP server status
        stats["http_server"] = {
            "running": self._http_server is not None,
            "url": f"http://{getattr(self._http_server, 'host', 'N/A')}:{getattr(self._http_server, 'port', 'N/A')}" if self._http_server else None,
        }

        return [TextContent(type="text", text=_json(stats))]

    async def _reindex_with_ocr(self, ocr_language: str) -> list[TextContent]:
        """Re-index documents that require OCR."""
        # Find documents that need OCR
        ocr_required = self.indexer.documents_with_status(DocumentStatus.OCR_REQUIRED)

        if not ocr_required:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "no_documents",
                        "message": "No documents require OCR",
                    }),
                )
            ]

        logger.info(f"Starting OCR re-indexing for {len(ocr_required)} documents")

        # Create OCR-enabled extractor
        extractor = TextExtractor(enable_ocr=True, ocr_language=ocr_language)

        results = {
            "total": len(ocr_required),
            "success": 0,
            "errors": 0,
            "details": [],
        }

        for doc in ocr_required:
            try:
                logger.info(f"Processing: {doc.filename}")

                # Extract text with OCR
                chunks, is_scan = extractor.extract_text_from_document(doc)

                # Re-index document
                self.indexer.index_document(doc, chunks, is_scan)

                if doc.status == DocumentStatus.INDEXED:
                    logger.info(f"Successfully indexed {doc.filename} ({len(chunks)} chunks)")
                    results["success"] += 1
                    results["details"].append({
                        "filename": doc.filename,
                        "status": "success",
                        "chunks": len(chunks),
                    })
                else:
                    logger.warning(f"Document {doc.filename} status: {doc.status}")
                    results["errors"] += 1
                    results["details"].append({
                        "filename": doc.filename,
                        "status": "warning",
                        "message": f"Status: {doc.status}",
                    })

            except Exception as e:
                logger.error(f"Failed to process {doc.filename}: {e}")
                results["errors"] += 1
                results["details"].append({
                    "filename": doc.filename,
                    "status": "error",
                    "error": str(e),
                })

        return [TextContent(type="text", text=_json(results))]

    async def _start_http_server(self, host: str, port: int) -> list[TextContent]:
        """Start the HTTP preview server."""
        if self._http_server is not None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "already_running",
                        "url": f"http://{self._http_server.host}:{self._http_server.port}",
                    }),
                )
            ]

        try:
            from aiohttp import web

            # Create HTTP server instance
            from .http_server import PDFPreviewServer

            self._http_server = PDFPreviewServer(
                index_manager=self.indexer,
                host=host,
                port=port,
            )

            # Start server in background
            self._http_server_task = asyncio.create_task(
                self._http_server.start()
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            logger.info(f"HTTP server started at http://{host}:{port}")

            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "started",
                        "url": f"http://{host}:{port}",
                        "message": f"HTTP preview server is running. Open http://{host}:{port} in your browser.",
                    }),
                )
            ]

        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "error": str(e),
                    }),
                )
            ]

    async def _stop_http_server(self) -> list[TextContent]:
        """Stop the HTTP preview server."""
        if self._http_server is None:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "not_running",
                        "message": "HTTP server is not running",
                    }),
                )
            ]

        try:
            # Stop the server
            if self._http_server_task:
                self._http_server_task.cancel()
                try:
                    await self._http_server_task
                except asyncio.CancelledError:
                    pass

            await self._http_server.stop()

            logger.info("HTTP server stopped")

            self._http_server = None
            self._http_server_task = None

            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "stopped",
                        "message": "HTTP server stopped successfully",
                    }),
                )
            ]

        except Exception as e:
            logger.error(f"Failed to stop HTTP server: {e}")
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "error": str(e),
                    }),
                )
            ]

    async def _background_indexing_loop(self):
        """Background task that periodically indexes new documents."""
        config = self.config.get("background_indexing", {})
        scan_interval = config.get("scan_interval", 300)
        batch_size = config.get("batch_size", 50)

        logger.info("Background indexing started (interval: %ds, batch: %d)",
                   scan_interval, batch_size)

        while self._indexing_active:
            try:
                # Stat-only discovery — no content reads for unchanged files
                discovered = self.catalog.discover_files(self.config["library_paths"])
                pending = self.catalog.select_changed(
                    discovered, self.indexer.file_states()
                )

                if pending:
                    logger.info("Found %d new/failed documents to index", len(pending))

                    # Index in batches
                    for i in range(0, len(pending), batch_size):
                        if not self._indexing_active:
                            break

                        batch = pending[i:i + batch_size]
                        logger.info("Indexing batch %d-%d of %d",
                                   i + 1, min(i + batch_size, len(pending)), len(pending))

                        for pdf_path, _, _ in batch:
                            if not self._indexing_active:
                                break

                            try:
                                metadata = self.catalog.extract_metadata(pdf_path)
                                chunks, is_scan = self.extractor.extract_text_from_document(metadata)
                                self.indexer.index_document(metadata, chunks, is_scan)

                                if metadata.status.value == "indexed":
                                    logger.debug("Indexed: %s", metadata.filename)
                            except Exception as e:
                                logger.error("Failed to index %s: %s", pdf_path.name, e)

                        # Small delay between batches
                        await asyncio.sleep(1)
                else:
                    logger.debug("No new documents to index")

                # Wait for next scan interval
                await asyncio.sleep(scan_interval)

            except asyncio.CancelledError:
                logger.info("Background indexing cancelled")
                break
            except Exception as e:
                logger.error("Background indexing error: %s", e)
                await asyncio.sleep(60)  # Wait a bit before retrying

    def _start_background_indexing(self):
        """Start the background indexing task."""
        config = self.config.get("background_indexing", {})

        if not config.get("enabled", False):
            logger.info("Background indexing disabled in config")
            return

        if self._indexing_task is not None:
            logger.warning("Background indexing already running")
            return

        self._indexing_active = True
        self._indexing_task = asyncio.create_task(self._background_indexing_loop())
        logger.info("Background indexing task started")

    def _stop_background_indexing(self):
        """Stop the background indexing task."""
        if self._indexing_task is None:
            return

        logger.info("Stopping background indexing...")
        self._indexing_active = False
        self._indexing_task.cancel()
        self._indexing_task = None

    async def run(self):
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server

        try:
            async with stdio_server() as (read_stream, write_stream):
                # Start the server first (non-blocking)
                server_task = asyncio.create_task(
                    self.server.run(
                        read_stream,
                        write_stream,
                        self.server.create_initialization_options(),
                    )
                )

                # Background indexing only if explicitly enabled in config
                config = self.config.get("background_indexing", {})
                if config.get("index_on_startup", False):
                    self._start_background_indexing()

                # Wait for server to complete
                await server_task
        finally:
            # Clean up background task
            self._stop_background_indexing()


async def main():
    """Main entry point."""
    import sys

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    server = KnowledgeLibrarianServer(config_path)
    await server.run()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
