# MCP Tools Reference

## Available Tools

The MCP Knowledge Librarian server now provides these tools:

### 📚 Core Tools

#### `list_documents`
List all indexed documents with metadata.

**Parameters:** None

**Returns:**
```json
{
  "total_documents": 181,
  "documents": [
    {
      "id": "abc123...",
      "filename": "ML_Book.pdf",
      "path": "/path/to/ML_Book.pdf",
      "title": "Machine Learning",
      "author": "John Doe",
      "page_count": 500,
      "status": "indexed",
      "is_scan": false,
      "indexed_at": "2025-01-17T10:30:00"
    }
  ]
}
```

---

#### `search`
Full-text search across all documents (SQLite FTS5, BM25 ranking).

**Parameters:**
- `query` (string, required): Search query text
- `max_results` (integer, optional): Maximum results (default: 20)
- `min_score` (number, optional): Minimum relevance score 0.0-1.0 (default: 0.1)
- `document_id` (string, optional): Limit search to specific document

**Returns:**
```json
{
  "query": "neural networks",
  "total_results": 5,
  "results": [
    {
      "document_id": "abc123...",
      "document_path": "file:///path/to/ML_Book.pdf#page=42",
      "document_title": "Machine Learning",
      "page_number": 42,
      "snippet": "...neural networks are composed of...",
      "score": 0.8523,
      "chunk_id": "abc123:page:42"
    }
  ]
}
```

**Note:** `document_path` includes `#page=N` fragment for direct page navigation!

---

#### `get_snippet`
Get full text snippet from a specific chunk.

**Parameters:**
- `chunk_id` (string, required): Chunk ID from search results

**Returns:**
```json
{
  "chunk_id": "abc123:page:42",
  "document_id": "abc123...",
  "document_path": "file:///path/to/ML_Book.pdf#page=42",
  "document_title": "Machine Learning",
  "page_number": 42,
  "text": "Full text of the chunk...",
  "char_offset": 0,
  "char_length": 1234
}
```

---

#### `get_document_metadata`
Get detailed metadata for a specific document.

**Parameters:**
- `document_id` (string, required): Document ID

**Returns:**
```json
{
  "id": "abc123...",
  "filename": "ML_Book.pdf",
  "path": "/path/to/ML_Book.pdf",
  "size_bytes": 12345678,
  "page_count": 500,
  "title": "Machine Learning",
  "author": "John Doe",
  "creation_date": "2020-01-01T00:00:00",
  "modification_date": "2024-12-01T10:30:00",
  "status": "indexed",
  "is_scan": false,
  "indexed_at": "2025-01-17T10:30:00",
  "error_message": null
}
```

---

#### `get_statistics`
Get index statistics and health information.

**Parameters:** None

**Returns:**
```json
{
  "total_documents": 181,
  "total_chunks": 15234,
  "status_counts": {
    "indexed": 164,
    "ocr_required": 17,
    "error": 0
  },
  "index_path": "/path/to/.index",
  "http_server": {
    "running": true,
    "url": "http://127.0.0.1:8765"
  }
}
```

---

### 🔄 Indexing Tools

#### `index_documents`
Scan library paths and index all PDF documents.

**Parameters:**
- `force_reindex` (boolean, optional): Force reindexing of already indexed documents (default: false)

**Returns:**
```json
{
  "indexed": 150,
  "skipped": 30,
  "errors": 1,
  "ocr_required": 17,
  "details": [
    {
      "filename": "document.pdf",
      "status": "indexed",
      "chunks": 234,
      "is_scan": false
    }
  ]
}
```

---

#### `reindex_with_ocr` ✨ NEW
Re-index documents that require OCR (scanned PDFs).

**Parameters:**
- `ocr_language` (string, optional): OCR language code (default: "eng")
  - `eng` - English
  - `deu` - German
  - `fra` - French
  - `spa` - Spanish

**Prerequisites:**
```bash
brew install tesseract          # macOS
apt-get install tesseract-ocr   # Ubuntu/Debian
```

**Returns:**
```json
{
  "total": 17,
  "success": 15,
  "errors": 2,
  "details": [
    {
      "filename": "scanned_doc.pdf",
      "status": "success",
      "chunks": 45
    },
    {
      "filename": "bad_scan.pdf",
      "status": "error",
      "error": "OCR failed: image quality too low"
    }
  ]
}
```

**Example Usage:**
```python
# Via MCP
result = await client.call_tool("reindex_with_ocr", {
    "ocr_language": "eng"
})
```

---

### 🌐 HTTP Server Tools ✨ NEW

#### `start_http_server`
Start HTTP preview server for browsing PDFs in the browser.

**Parameters:**
- `host` (string, optional): Host to bind to (default: "127.0.0.1")
- `port` (integer, optional): Port to listen on (default: 8765)

**Returns:**
```json
{
  "status": "started",
  "url": "http://127.0.0.1:8765",
  "message": "HTTP preview server is running. Open http://127.0.0.1:8765 in your browser."
}
```

**Features:**
- 📚 Browse all documents at `http://localhost:8765`
- 🔍 Search interface at `http://localhost:8765/search?q=query`
- 📄 View PDFs at `http://localhost:8765/pdf/{doc_id}?page=N`
- 🔗 Shareable URLs with page navigation

**Example Usage:**
```python
# Start server
result = await client.call_tool("start_http_server", {
    "host": "127.0.0.1",
    "port": 8765
})

# Now open http://127.0.0.1:8765 in your browser
```

---

#### `stop_http_server`
Stop the HTTP preview server.

**Parameters:** None

**Returns:**
```json
{
  "status": "stopped",
  "message": "HTTP server stopped successfully"
}
```

---

## Usage Examples

### 🔍 Search Workflow with HTTP Server

```python
# 1. Start HTTP server
await client.call_tool("start_http_server", {"port": 8765})

# 2. Search for documents
results = await client.call_tool("search", {
    "query": "machine learning",
    "max_results": 10
})

# 3. Results now include HTTP URLs:
# {
#   "document_path": "http://127.0.0.1:8765/pdf/abc123?page=42",
#   ...
# }

# 4. Open URL in browser → PDF opens at exact page!
```

### 📄 OCR Workflow

```python
# 1. Check statistics
stats = await client.call_tool("get_statistics", {})
# Shows: "ocr_required": 17

# 2. Run OCR on all scanned PDFs
result = await client.call_tool("reindex_with_ocr", {
    "ocr_language": "eng"
})

# 3. Check statistics again
stats = await client.call_tool("get_statistics", {})
# Shows: "ocr_required": 0, "indexed": 181
```

### 🔗 Deep-Link Usage

All search results now include page fragments:

```python
# Search returns:
{
  "document_path": "file:///path/to/doc.pdf#page=42"
}

# Or with HTTP server:
{
  "document_path": "http://localhost:8765/pdf/abc123?page=42"
}

# Both open the PDF at page 42! ✨
```

---

## Status Codes

Documents can have these statuses:

- `pending` - Not yet indexed
- `indexed` - Successfully indexed and searchable
- `ocr_required` - Scanned PDF, needs OCR processing
- `error` - Indexing failed (check `error_message`)

---

## Configuration

### Enable HTTP URLs by Default

Update `config.yaml`:

```yaml
http_preview:
  enabled: true
  host: "127.0.0.1"
  port: 8765
  auto_start: true  # Start on server launch
```

### Enable OCR by Default

Update `config.yaml`:

```yaml
extraction:
  enable_ocr: true
  ocr_language: "eng"
```

---

## Performance Notes

- **OCR Processing:** ~2-5 seconds per page
- **HTTP Server:** < 10ms response time
- **Search:** < 100ms for most queries
- **Indexing:** ~0.5-1 second per document (without OCR)

---

## Browser Compatibility

HTTP server works best in:
- ✅ Chrome/Edge (built-in PDF.js)
- ✅ Firefox (built-in PDF viewer)
- ✅ Safari (built-in PDF viewer)

---

## Security Notes

- HTTP server binds to `127.0.0.1` by default (local only)
- No authentication (suitable for local use)
- For network access, consider adding basic auth or firewall rules
