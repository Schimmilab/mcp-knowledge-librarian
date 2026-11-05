# New Features

## 1. 🔗 Deep-Links with Page Numbers

Search results now include `#page=N` fragments in file:// URLs:

```
file:///path/to/document.pdf#page=231
```

**Implementation:**
- Modified `indexer.py` line 268 to add page fragments
- Supported by most PDF viewers (Preview, Acrobat, etc.)

**Usage:**
```python
# Search returns URLs like:
# file:///Users/.../library/ML_Book.pdf#page=42
results = indexer.search(SearchQuery(query="neural networks"))
for result in results:
    print(f"{result.document_title} - {result.document_path}")
```

---

## 2. 🔍 OCR Integration

Re-index scanned PDFs with OCR support using the new `reindex_with_ocr.py` script.

**Prerequisites:**
```bash
# Install Tesseract OCR engine
brew install tesseract          # macOS
apt-get install tesseract-ocr   # Ubuntu/Debian
```

**Usage:**
```bash
# Re-index all documents marked as "ocr_required"
python scripts/reindex_with_ocr.py

# Specify custom index path
python scripts/reindex_with_ocr.py --index-path /path/to/.index

# Use different language (e.g., German)
python scripts/reindex_with_ocr.py --language deu
```

**Supported Languages:**
- `eng` - English (default)
- `deu` - German
- `fra` - French
- `spa` - Spanish
- Install more: `brew install tesseract-lang`

**Features:**
- Automatically detects scanned PDFs (< 50 chars/page)
- Extracts text from images using Tesseract
- Updates index with searchable text
- Shows progress and statistics

---

## 3. 🌐 HTTP Preview Server

Local web server for browsing and searching PDFs with clickable links.

**Usage:**
```bash
# Start the server
python scripts/pdf_preview_server.py

# Custom host/port
python scripts/pdf_preview_server.py --host 0.0.0.0 --port 9000

# Custom index path
python scripts/pdf_preview_server.py --index-path /path/to/.index
```

**Features:**
- 📚 **Library Browser** - View all indexed documents at `http://localhost:8765`
- 🔍 **Search Interface** - Search and get clickable results
- 📄 **PDF Viewer** - In-browser PDF viewing with page navigation
- 🔗 **Shareable URLs** - Copy links to specific pages: `http://localhost:8765/pdf/{doc_id}?page=42`

**Endpoints:**
- `GET /` - Library homepage
- `GET /search?q=query` - Search interface
- `GET /pdf/{document_id}?page=N` - View PDF at specific page

**Example Workflow:**
1. Start server: `python scripts/pdf_preview_server.py`
2. Open browser: `http://localhost:8765`
3. Search for "machine learning"
4. Click result → Opens PDF at exact page
5. Share URL with colleagues

**Integration with MCP Server:**

To make the MCP server return HTTP URLs instead of file:// URLs, update `config.yaml`:

```yaml
# config.yaml
http_preview:
  enabled: true
  base_url: "http://localhost:8765"
```

Then use `HTTPIndexManager` in server.py:

```python
from .http_indexer import HTTPIndexManager

# In __init__:
self.indexer = HTTPIndexManager(
    index_path=self.config["index_path"],
    enable_semantic=self.config["search"]["enable_semantic"],
    http_base_url=self.config.get("http_preview", {}).get("base_url"),
)
```

---

## 📊 Summary

| Feature | Status | File |
|---------|--------|------|
| Deep-Links (#page=N) | ✅ Implemented | `indexer.py:268` |
| OCR Re-indexing | ✅ Ready | `scripts/reindex_with_ocr.py` |
| HTTP Preview Server | ✅ Ready | `scripts/pdf_preview_server.py` |
| HTTP URL Integration | ✅ Optional | `http_indexer.py` |

---

## 🚀 Quick Start

```bash
# 1. Re-index scanned PDFs with OCR
python scripts/reindex_with_ocr.py

# 2. Start HTTP preview server
python scripts/pdf_preview_server.py

# 3. Open browser
open http://localhost:8765

# 4. Search and enjoy clickable links! 🎉
```

---

## 🛠️ Technical Details

### Deep-Links
- Uses standard PDF fragment identifier syntax
- Works with `file://` and `http://` protocols
- Supported by all major PDF viewers

### OCR Processing
- Uses Tesseract OCR engine
- Processes images embedded in PDFs
- Fallback: Returns empty string on OCR failure
- Configurable language support

### HTTP Server
- Built with `aiohttp` (async)
- Serves PDFs with correct MIME types
- Browser-native PDF rendering
- No client-side JavaScript required

### Performance
- **OCR:** ~2-5 seconds per page (depends on image size)
- **HTTP Server:** < 10ms response time (serving from local disk)
- **Indexing:** Same performance as before (Whoosh + optional embeddings)

---

## 📝 Notes

### Browser Compatibility
The HTTP server's PDF viewer works best in:
- ✅ Chrome/Edge (built-in PDF.js)
- ✅ Firefox (built-in PDF viewer)
- ✅ Safari (built-in PDF viewer)

### Security Considerations
- Server binds to `127.0.0.1` by default (local only)
- No authentication (suitable for local use only)
- For network access, consider adding basic auth

### Future Improvements
- [ ] Add authentication for HTTP server
- [ ] Implement PDF highlighting (search terms)
- [ ] Cache OCR results to avoid re-processing
- [ ] Support for more document formats (DOCX, EPUB)
- [ ] Real-time indexing with file system watchers
