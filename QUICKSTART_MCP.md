# Quick Start: Using New MCP Tools

## 🚀 Getting Started

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -e .

# Install Tesseract for OCR (optional)
brew install tesseract  # macOS
```

### 2. Start the MCP Server

```bash
# Using your MCP client (e.g., Claude Desktop)
# Server should be configured in your MCP settings
```

---

## 📋 Common Workflows

### Workflow 1: Search with HTTP Preview

```python
# 1. Start HTTP server
start_http_server()
# → Returns: {"status": "started", "url": "http://127.0.0.1:8765"}

# 2. Search for something
search(query="neural networks", max_results=10)
# → Returns results with clickable URLs

# 3. Open browser
# Visit: http://127.0.0.1:8765

# 4. Click search results → PDF opens at exact page! 🎉
```

### Workflow 2: OCR Processing

```python
# 1. Check which documents need OCR
get_statistics()
# → Shows: "ocr_required": 17

# 2. Process all scanned PDFs with OCR
reindex_with_ocr(ocr_language="eng")
# → Processes all 17 documents

# 3. Verify completion
get_statistics()
# → Shows: "ocr_required": 0
```

### Workflow 3: Full Setup

```python
# 1. Index all documents
index_documents(force_reindex=False)

# 2. Process scans with OCR
reindex_with_ocr(ocr_language="eng")

# 3. Start HTTP server
start_http_server(host="127.0.0.1", port=8765)

# 4. Get statistics
get_statistics()

# 5. Search
search(query="machine learning")

# 6. Open http://127.0.0.1:8765 in browser
```

---

## 🧪 Testing the New Features

### Test Deep-Links

```python
# Search for something
result = search(query="attention mechanism", max_results=5)

# Check the document_path in results:
# file:///path/to/doc.pdf#page=231
#                          ^^^^^^^^^^^ This is the deep-link!

# On macOS: Click the link → Preview opens at page 231
```

### Test HTTP Server

```python
# Start server
start_http_server(port=8765)

# Open in browser:
# http://localhost:8765              → Library homepage
# http://localhost:8765/search?q=ml  → Search interface
# http://localhost:8765/pdf/{id}?page=42 → Direct PDF access

# Stop server when done
stop_http_server()
```

### Test OCR

```python
# Check before
stats_before = get_statistics()
print(f"OCR required: {stats_before['status_counts']['ocr_required']}")

# Run OCR
result = reindex_with_ocr(ocr_language="eng")
print(f"Success: {result['success']}, Errors: {result['errors']}")

# Check after
stats_after = get_statistics()
print(f"OCR required: {stats_after['status_counts']['ocr_required']}")
```

---

## 🔧 Advanced Usage

### Multi-Language OCR

```python
# German documents
reindex_with_ocr(ocr_language="deu")

# French documents
reindex_with_ocr(ocr_language="fra")

# Spanish documents
reindex_with_ocr(ocr_language="spa")
```

### Custom HTTP Server Port

```python
# Use different port (e.g., for multiple instances)
start_http_server(host="127.0.0.1", port=9000)

# Access at: http://127.0.0.1:9000
```

### Network Access

```python
# ⚠️  WARNING: No authentication! Use only on trusted networks
start_http_server(host="0.0.0.0", port=8765)

# Now accessible from other devices:
# http://your-machine-ip:8765
```

---

## 📊 Monitoring

### Check Server Status

```python
stats = get_statistics()

print(f"Documents: {stats['total_documents']}")
print(f"Chunks: {stats['total_chunks']}")
print(f"HTTP Server: {stats['http_server']['running']}")
if stats['http_server']['running']:
    print(f"URL: {stats['http_server']['url']}")
```

### Document Status Breakdown

```python
stats = get_statistics()
status_counts = stats['status_counts']

print(f"Indexed: {status_counts.get('indexed', 0)}")
print(f"OCR Required: {status_counts.get('ocr_required', 0)}")
print(f"Errors: {status_counts.get('error', 0)}")
```

---

## 🐛 Troubleshooting

### OCR Fails

```bash
# Check if Tesseract is installed
tesseract --version

# Install if missing:
brew install tesseract  # macOS
apt-get install tesseract-ocr  # Ubuntu

# Install additional languages:
brew install tesseract-lang  # All languages
```

### HTTP Server Won't Start

```python
# Check if port is already in use
import socket
sock = socket.socket()
try:
    sock.bind(('127.0.0.1', 8765))
    print("Port 8765 is available")
except OSError:
    print("Port 8765 is in use! Try different port:")
    start_http_server(port=8766)
```

### Deep-Links Don't Work

- **macOS Preview:** ✅ Supports `#page=N`
- **Adobe Acrobat:** ✅ Supports `#page=N`
- **Chrome:** Use HTTP server instead (file:// restrictions)
- **Firefox:** Use HTTP server instead (file:// restrictions)

**Solution:** Use HTTP server for universal browser support!

```python
start_http_server()
# Now all links work in all browsers! 🎉
```

---

## 💡 Tips & Tricks

### 1. Persistent HTTP Server

The HTTP server runs in the background while the MCP server is active.
You don't need to restart it every time!

```python
# Start once
start_http_server()

# Use it all day!
search(query="anything")  # Results include HTTP URLs

# Stop when done
stop_http_server()
```

### 2. Batch OCR Processing

OCR processes documents sequentially. For large libraries:

```python
# Check how many need OCR
stats = get_statistics()
ocr_count = stats['status_counts'].get('ocr_required', 0)

print(f"Will process {ocr_count} documents")
print(f"Estimated time: {ocr_count * 3} seconds")  # ~3s per page average

# Start processing
reindex_with_ocr()
```

### 3. Search Result Verification

```python
# Get detailed context
results = search(query="transformer architecture", max_results=5)

for result in results['results']:
    # Get full chunk text
    chunk = get_snippet(chunk_id=result['chunk_id'])
    print(f"\nDocument: {result['document_title']}")
    print(f"Page: {result['page_number']}")
    print(f"Score: {result['score']}")
    print(f"Full text: {chunk['text'][:200]}...")
```

---

## 🎯 Next Steps

1. **Try the HTTP server:** Most user-friendly way to browse your library
2. **Run OCR on scans:** Make all documents searchable
3. **Share HTTP URLs:** Send colleagues direct links to specific pages
4. **Explore the API:** Check `MCP_TOOLS.md` for all available tools

Happy searching! 🔍📚
