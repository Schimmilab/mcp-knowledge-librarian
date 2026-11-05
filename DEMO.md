# Demo Guide

This guide walks through two demo scenarios as specified in the requirements.

## Setup

1. Install dependencies:
```bash
pip install -e .
pip install reportlab  # For creating demo PDFs
```

2. Create demo PDFs:
```bash
python scripts/create_demo_pdfs.py
```

This creates 5 sample PDFs in `demo_library/`:
- `machine_learning_guide.pdf` - ML concepts and neural networks
- `data_science_intro.pdf` - Data science workflow
- `python_beginners.pdf` - Python programming basics
- `neural_networks.pdf` - Deep dive into neural networks
- `statistics_fundamentals.pdf` - Statistics concepts

## Demo Scenario 1: Keyword Search with Page Citation

### Goal
Find information about "neural networks" and show exact page citations.

### Steps

1. **Index the documents:**
```bash
python scripts/demo.py index
```

Expected output:
```
==================================================================
  DEMO: Indexing PDF Library
==================================================================

----------------------------------------------------------------------
  Scanning demo_library/
----------------------------------------------------------------------

Found 5 PDF documents
  - machine_learning_guide.pdf (2 pages)
  - data_science_intro.pdf (1 pages)
  - python_beginners.pdf (1 pages)
  - neural_networks.pdf (1 pages)
  - statistics_fundamentals.pdf (1 pages)

✓ No duplicates found

----------------------------------------------------------------------
  Indexing Documents
----------------------------------------------------------------------

Processing machine_learning_guide.pdf... ✓ Indexed (2 chunks)
Processing data_science_intro.pdf... ✓ Indexed (1 chunks)
Processing python_beginners.pdf... ✓ Indexed (1 chunks)
Processing neural_networks.pdf... ✓ Indexed (1 chunks)
Processing statistics_fundamentals.pdf... ✓ Indexed (1 chunks)

----------------------------------------------------------------------
  Indexing Summary
----------------------------------------------------------------------

Indexed:      5
OCR required: 0
Errors:       0

Total documents in index: 5
Total text chunks:        6
```

2. **Search for "neural networks":**
```bash
python scripts/demo.py search
```

Expected output (excerpt):
```
==================================================================
  DEMO: Searching PDF Library
==================================================================

Index contains 5 documents with 6 chunks

----------------------------------------------------------------------
  Search: "neural networks"
----------------------------------------------------------------------

Found 3 results:

1. demo_library/neural_networks.pdf
   Page 1 | Score: 0.8532
   ...Deep neural networks have revolutionized artificial intelligence...

   Full context:
   Deep neural networks have revolutionized artificial intelligence,
   achieving breakthrough results in computer vision, natural language
   processing, and game playing...

2. demo_library/machine_learning_guide.pdf
   Page 2 | Score: 0.7241
   ...Neural networks are computational models inspired by biological
   neurons in the human brain...

3. demo_library/machine_learning_guide.pdf
   Page 1 | Score: 0.3156
   ...Applications of machine learning are widespread...
```

### ✅ Verification

Each result includes:
- ✅ **PDF path**: Exact file location
- ✅ **Page number**: Specific page (1-indexed)
- ✅ **Snippet**: Text excerpt with context
- ✅ **Score**: Relevance score
- ✅ **Full context**: Complete page text available via chunk_id

## Demo Scenario 2: Scan Detection (OCR Required)

### Goal
Demonstrate that scanned PDFs are correctly identified as requiring OCR.

### Steps

1. **Create a blank/scanned PDF:**

Create a test file `demo_library/scanned_document.pdf` with minimal or no text layer:

```python
from pypdf import PdfWriter

writer = PdfWriter()
writer.add_blank_page(width=612, height=792)  # Letter size, no text
with open("demo_library/scanned_document.pdf", "wb") as f:
    writer.write(f)
```

Or simply:
```bash
python -c "from pypdf import PdfWriter; w = PdfWriter(); w.add_blank_page(width=612, height=792); w.write('demo_library/scanned_document.pdf')"
```

2. **Index with OCR disabled:**

Ensure `config.yaml` has:
```yaml
extraction:
  detect_scans: true
  enable_ocr: false
```

3. **Run indexing:**
```bash
python scripts/demo.py index
```

Expected output:
```
Processing scanned_document.pdf... ⚠️  OCR required

----------------------------------------------------------------------
  Indexing Summary
----------------------------------------------------------------------

Indexed:      5
OCR required: 1
Errors:       0
```

4. **Check document status:**
```bash
python scripts/demo.py metadata
```

Expected output:
```
Filename: scanned_document.pdf
Path:     demo_library/scanned_document.pdf
Pages:    1
Status:   ocr_required
Scan:     True
```

### ✅ Verification

- ✅ **Scan detection**: Document correctly identified as scan
- ✅ **Status marking**: Status set to `ocr_required`
- ✅ **No crash**: System handles gracefully without OCR
- ✅ **Clear indication**: User informed that OCR is needed

### Optional: Enable OCR

To actually perform OCR (requires Tesseract):

1. Update `config.yaml`:
```yaml
extraction:
  enable_ocr: true
  ocr_language: "eng"
```

2. Re-index with force:
```python
# Via MCP tool
{
  "force_reindex": true
}
```

3. Scanned documents will now be processed with OCR (if text is detectable in images).

## Additional Demo: MCP Tool Usage

### Via MCP Client (e.g., Claude Desktop)

1. **Configure MCP:**

Add to Claude Desktop config:
```json
{
  "mcpServers": {
    "knowledge-librarian": {
      "command": "python",
      "args": [
        "-m",
        "mcp_knowledge_librarian.server",
        "/full/path/to/config.yaml"
      ],
      "cwd": "/full/path/to/mcp-knowledge-librarian"
    }
  }
}
```

2. **Use tools in conversation:**

```
User: "Index my PDF library"
Assistant: [Calls index_documents tool]

User: "Search for information about machine learning"
Assistant: [Calls search tool with query "machine learning"]
          [Shows results with citations: PDF path, page number, snippet]

User: "Get more context from the first result"
Assistant: [Calls get_snippet with chunk_id from result]
          [Shows full page text]
```

## Performance Metrics

Typical performance on the demo:

- **Indexing**: ~0.5 seconds for 5 documents
- **Search**: <50ms per query
- **Index size**: ~50KB for demo library

## Troubleshooting

### "Module not found" errors
```bash
pip install -e .
pip install reportlab
```

### "No documents in index"
```bash
python scripts/demo.py index
```

### OCR not working
1. Install Tesseract: `brew install tesseract` (macOS)
2. Enable in `config.yaml`: `enable_ocr: true`

## Cleanup

Remove all demo data:
```bash
make clean
```

Or manually:
```bash
rm -rf demo_library/ .index/
```
