# MCP Knowledge Librarian

A Model Context Protocol (MCP) server for indexing and searching PDF libraries with citation support. Built for privacy-first, local-only operation with robust text extraction, duplicate detection, and hallucination-resistant search results.

## Features

### Core Capabilities
- **📚 PDF Cataloging**: Recursive scanning of directories with metadata extraction
- **🔍 Duplicate Detection**: Hash-based duplicate identification
- **📝 Text Extraction**: Support for both text-based and scanned PDFs
- **🤖 OCR Support**: Optional OCR for scanned documents (requires Tesseract)
- **💾 Persistent Index**: Single SQLite database with fast retrieval
- **🔎 Full-Text Search**: SQLite FTS5 with BM25 ranking (stdlib, no heavy dependencies)
- **⚡ Incremental Indexing**: Stat-only directory scans — file contents are only read for new or changed PDFs (cloud-mount friendly)
- **📖 Citation Support**: Every result includes PDF path, page number, and text snippet
- **🛡️ Hallucination Prevention**: Answers derived only from actual document content

### MCP Tools

The server provides the following MCP tools:

1. **`list_documents`** - List indexed documents (paginated)
2. **`index_documents`** - Incrementally scan library paths and index new/changed PDFs
3. **`search`** - Full-text search with BM25 ranking
4. **`get_snippet`** - Get full text snippet by chunk ID
5. **`get_document_metadata`** - Get detailed metadata for a document
6. **`get_statistics`** - Get index statistics and health information

## Installation

### Prerequisites

- Python 3.10 or higher
- (Optional) Tesseract OCR for scanned PDF support

```bash
# On macOS
brew install tesseract

# On Ubuntu/Debian
sudo apt-get install tesseract-ocr

# On Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd mcp-knowledge-librarian
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .

# With OCR support (pytesseract + pillow)
pip install -e ".[ocr]"

# For development
pip install -e ".[dev]"
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit it to customize settings (`config.yaml` is git-ignored, so your local paths stay private):

```yaml
# Directories to scan for PDFs
library_paths:
  - "./sample_library"
  - "/path/to/your/pdfs"

# Index storage location — keep OUTSIDE cloud-synced folders
index_path: "~/.cache/knowledge-librarian/index"

# Text extraction settings
extraction:
  detect_scans: true
  enable_ocr: false  # Set to true if you have Tesseract installed
  ocr_language: "eng"

# Search settings
search:
  max_results: 20
  min_score: 0.1
```

## Usage

### Running the MCP Server

```bash
python -m mcp_knowledge_librarian.server config.yaml
```

For use with Claude Desktop or other MCP clients, add to your MCP configuration:

```json
{
  "mcpServers": {
    "knowledge-librarian": {
      "command": "python",
      "args": ["-m", "mcp_knowledge_librarian.server", "/path/to/config.yaml"],
      "cwd": "/path/to/mcp-knowledge-librarian"
    }
  }
}
```

### Indexing Documents

Use the `index_documents` tool to scan and index your PDF library:

```json
{
  "force_reindex": false
}
```

**Example Output:**
```json
{
  "indexed": 42,
  "skipped": 3,
  "errors": 0,
  "ocr_required": 2,
  "details": [
    {
      "filename": "machine_learning.pdf",
      "status": "indexed",
      "chunks": 15,
      "is_scan": false
    },
    {
      "filename": "scanned_doc.pdf",
      "status": "ocr_required",
      "chunks": 0,
      "is_scan": true
    }
  ]
}
```

### Searching

Use the `search` tool to find documents:

```json
{
  "query": "neural networks deep learning",
  "max_results": 10,
  "min_score": 0.1
}
```

**Example Output:**
```json
{
  "query": "neural networks deep learning",
  "total_results": 5,
  "results": [
    {
      "document_id": "a1b2c3d4...",
      "document_path": "/library/ml_guide.pdf",
      "document_title": "Machine Learning Guide",
      "page_number": 42,
      "snippet": "...neural networks are computational models inspired by biological neurons. Deep learning extends this...",
      "score": 0.8532,
      "chunk_id": "a1b2c3d4:page:42"
    }
  ]
}
```

### Getting Full Snippet

Use the `get_snippet` tool with a chunk ID from search results:

```json
{
  "chunk_id": "a1b2c3d4:page:42"
}
```

**Example Output:**
```json
{
  "chunk_id": "a1b2c3d4:page:42",
  "document_id": "a1b2c3d4...",
  "document_path": "/library/ml_guide.pdf",
  "document_title": "Machine Learning Guide",
  "page_number": 42,
  "text": "Full page text content here...",
  "char_offset": 0,
  "char_length": 2547
}
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp_knowledge_librarian --cov-report=html

# Run specific test file
pytest tests/test_integration.py
```

## Architecture

### Components

1. **Catalog** (`catalog.py`): PDF discovery, metadata extraction, duplicate detection
2. **Extractor** (`extractor.py`): Text extraction with OCR support and scan detection
3. **Indexer** (`indexer.py`): SQLite/FTS5-based indexing with BM25 ranking
4. **Server** (`server.py`): MCP server implementation with tool handlers

### Data Flow

```
PDF Files → Catalog → Extract Text → Index → Search → Results with Citations
                ↓                        ↓
           Metadata                 Persistence
```

### Storage

- **Everything**: `<index_path>/librarian.db` — a single SQLite database
  (documents, chunks, FTS5 full-text index). No pickles, no in-memory caches.

Legacy pickle/Whoosh indexes can be migrated without re-reading any PDFs:

```bash
python scripts/migrate_to_sqlite.py <old_index_dir> <new_index_dir>
```

## Development

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type check (if using mypy)
mypy src/
```

### Adding Tests

Follow the existing test structure:
- `test_catalog.py` - Cataloging and metadata tests
- `test_extractor.py` - Text extraction tests
- `test_integration.py` - End-to-end workflow tests

## Limitations and Known Issues

1. **OCR Performance**: OCR can be slow for large scanned documents
2. **Image PDFs**: Complex image-based PDFs may have limited OCR accuracy
3. **Cloud mounts**: The first indexing of files on OneDrive/Google Drive
   downloads them once; afterwards only stat() calls are needed

## Privacy and Security

✅ **Privacy-first design:**
- All processing happens locally
- No data sent to external services
- No telemetry or tracking

⚠️ **Security notes:**
- Index files are stored unencrypted
- Use appropriate file system permissions
- Be cautious when indexing sensitive documents

## Performance Metrics

Typical performance on modern hardware:

- **Indexing**: ~5-10 PDFs/second (text-based)
- **OCR**: ~1-2 pages/second
- **Search**: <100ms for typical queries
- **Index size**: ~1-2% of original PDF size

## Troubleshooting

### "OCR required" status but OCR disabled
Enable OCR in `config.yaml`:
```yaml
extraction:
  enable_ocr: true
```

### "Module not found" errors
Ensure all dependencies are installed:
```bash
pip install -e .
```

### Slow indexing
- Disable OCR for text-based PDFs
- Keep the index on local disk, never in a cloud-synced folder

### Search returns no results
- Check index statistics: `get_statistics` tool
- Verify documents are indexed: `list_documents` tool
- Lower `min_score` threshold in search query

## Contributing

Contributions welcome! Please ensure:
1. Tests pass: `pytest`
2. Code is formatted: `black src/ tests/`
3. No linting errors: `ruff check src/ tests/`

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

Built with:
- [MCP SDK](https://github.com/anthropics/mcp) - Model Context Protocol
- [PyPDF](https://pypdf.readthedocs.io/) - PDF processing
- [SQLite FTS5](https://www.sqlite.org/fts5.html) - Full-text search (stdlib)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) - OCR engine (optional)
