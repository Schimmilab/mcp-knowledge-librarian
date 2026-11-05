# Changelog

## [0.3.0] - 2026-07-04

### ⚡ Performance & Resource Optimization

Kompletter Umbau der Index- und Speicher-Architektur. Zuvor war jede MCP-Instanz
mehrere hundert MB schwer und reindizierte beim Start; bei mehreren parallelen
Sessions führte das zu massiver CPU- und Cloud-Sync-Last.

#### 🗄️ SQLite FTS5 statt Whoosh + Pickle
- Whoosh-Index und ~318 MB Pickle-Cache ersetzt durch einen SQLite-FTS5-Store
- Kein vollständiges Laden von Metadaten/Chunks in den RAM mehr
- Migrationsskript `scripts/migrate_to_sqlite.py`; ungültige UTF-8-Surrogate werden sanitized

#### 🔍 Inkrementeller Scan
- stat-only Discovery — unveränderte Dateien werden nicht mehr gehasht oder geparst
- Nur neue/geänderte Dateien (mtime) werden verarbeitet; kein Cloud-Download für unveränderten Bestand
- Datei-mtime in den Metadaten getrackt

#### 🪶 Schlankere Abhängigkeiten
- `whoosh` und `sentence-transformers`/`torch` entfernt (semantic search war nur ein Platzhalter)
- OCR-Abhängigkeiten optional gemacht
- Kompaktere Tool-Outputs, paginiertes `list_documents`

#### ⚙️ Config
- Background-Indexing standardmäßig aus — verhindert N-fache Indizierung durch parallele MCP-Instanzen
- Index-Pfad außerhalb der Cloud-Mounts (lokal), `~`-Expansion
- Zusätzlicher Google-Drive-Library-Pfad

### 🐛 Fixes
- IndirectObject-Referenzen beim Lesen von PDF-Title/Author-Metadaten korrekt auflösen

### 🧹 Cleanup
- Verwaistes `reindex.py` entfernt (ersetzt durch `scripts/index_library.py`)

---

## [0.2.0] - 2025-01-17

### ✨ New Features

#### 🔗 Deep-Links with Page Numbers
- Search results now include `#page=N` fragments in URLs
- Format: `file:///path/to/doc.pdf#page=42`
- Works with Preview, Acrobat, and all major PDF viewers
- **File:** `src/mcp_knowledge_librarian/indexer.py:268`

#### 🔍 OCR Integration via MCP
- New MCP tool: `reindex_with_ocr`
- Re-index scanned PDFs with Tesseract OCR
- Multi-language support (eng, deu, fra, spa, etc.)
- Automatic detection of documents needing OCR
- **File:** `src/mcp_knowledge_librarian/server.py:453-522`

#### 🌐 HTTP Preview Server via MCP
- New MCP tools: `start_http_server`, `stop_http_server`
- Browse PDF library in your browser
- Search interface with clickable results
- Direct PDF viewing with page navigation
- Shareable URLs: `http://localhost:8765/pdf/{id}?page=42`
- **File:** `src/mcp_knowledge_librarian/http_server.py`

### 🔧 Improvements

- Added `http_server` status to `get_statistics` tool
- Enhanced search results with HTTP URLs when server is running
- Better error handling for OCR failures
- Improved logging for server operations

### 📦 Dependencies

- Added `aiohttp>=3.9.0` for HTTP server
- Added `pyyaml>=6.0.0` for config (was implicit)

### 📚 Documentation

- New: `MCP_TOOLS.md` - Complete MCP tools reference
- New: `QUICKSTART_MCP.md` - Quick start guide for MCP tools
- New: `FEATURES.md` - Detailed feature documentation
- New: `CHANGELOG.md` - This file

### 🛠️ Scripts

- `scripts/reindex_with_ocr.py` - Standalone OCR re-indexing
- `scripts/pdf_preview_server.py` - Standalone HTTP server
- `scripts/monitor_indexing.py` - Existing monitoring script

---

## [0.1.0] - 2025-01-16

### Initial Release

#### Core Features
- PDF document indexing with Whoosh
- Full-text search with keyword matching
- Document metadata extraction
- Chunk-based text storage
- Duplicate detection
- Background indexing
- MCP server implementation

#### MCP Tools
- `list_documents` - List all indexed documents
- `index_documents` - Index PDF documents
- `search` - Search documents
- `get_snippet` - Get text snippets
- `get_document_metadata` - Get document details
- `get_statistics` - Get index statistics

---

## Upgrade Guide

### From 0.1.0 to 0.2.0

1. **Install new dependencies:**
   ```bash
   pip install -e .
   ```

2. **Optional: Install Tesseract for OCR:**
   ```bash
   brew install tesseract  # macOS
   apt-get install tesseract-ocr  # Ubuntu
   ```

3. **New MCP tools available:**
   - `reindex_with_ocr` - Process scanned PDFs
   - `start_http_server` - Start web interface
   - `stop_http_server` - Stop web interface

4. **Search results now include page fragments:**
   ```python
   # Old: file:///path/to/doc.pdf
   # New: file:///path/to/doc.pdf#page=42
   ```

5. **HTTP server provides clickable links:**
   ```python
   start_http_server()
   # Open http://localhost:8765 in browser
   ```

### Breaking Changes

None! All existing functionality remains unchanged.

---

## Future Roadmap

### Planned Features
- [ ] PDF highlighting for search terms
- [ ] Real-time indexing with file system watchers
- [ ] Authentication for HTTP server
- [ ] Support for DOCX, EPUB formats
- [ ] Enhanced semantic search with embeddings
- [ ] Batch OCR processing with progress tracking
- [ ] API rate limiting and caching
- [ ] Multi-user support with separate indexes

### Under Consideration
- [ ] Browser extension for quick lookups
- [ ] Mobile app for document access
- [ ] Cloud storage integration (Dropbox, Drive)
- [ ] Citation export (BibTeX, EndNote)
- [ ] Document annotations and highlights
- [ ] Collaborative features (shared collections)

---

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

---

## License

MIT — see LICENSE.

---

## Acknowledgments

- Whoosh for full-text search
- PyPDF for PDF extraction
- Tesseract for OCR
- aiohttp for HTTP server
- MCP SDK for protocol implementation
