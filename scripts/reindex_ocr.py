#!/usr/bin/env python3
"""Batch OCR-reindex of all documents stuck in status 'ocr_required'.

Runs the same extract → index path as the reindex_with_ocr MCP tool, but:
- decoupled (long batch, hours) instead of one blocking tool call
- smallest documents first, so short docs finish fast and the big books trail
- resumable: each document is committed as it finishes, so a stopped/killed run
  just picks up the remaining ocr_required docs next time
- progress to stdout (line-buffered) so it can be tailed live

Usage:
  python3 scripts/reindex_ocr.py --index PATH --lang deu+eng [--max-pages N]
"""
import argparse
import sys
import time

from mcp_knowledge_librarian.extractor import TextExtractor
from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import DocumentStatus


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="Index directory (contains librarian.db)")
    ap.add_argument("--lang", default="deu+eng", help="Tesseract language(s)")
    ap.add_argument("--max-pages", type=int, default=0,
                    help="Skip docs with more pages than this (0 = no limit)")
    args = ap.parse_args()

    mgr = IndexManager(index_path=args.index)
    # Play nice with the running MCP server sharing this DB (WAL, read-only).
    mgr._conn.execute("PRAGMA busy_timeout=60000")
    extractor = TextExtractor(enable_ocr=True, ocr_language=args.lang)

    docs = mgr.documents_with_status(DocumentStatus.OCR_REQUIRED)
    docs.sort(key=lambda d: d.page_count)  # small -> large
    if args.max_pages:
        docs = [d for d in docs if d.page_count <= args.max_pages]

    total = len(docs)
    total_pages = sum(d.page_count for d in docs)
    done_pages = 0
    ok = warn = err = 0
    t_start = time.time()
    print(f"[start] {total} docs / {total_pages} pages, lang={args.lang}", flush=True)

    for i, doc in enumerate(docs, 1):
        t0 = time.time()
        try:
            chunks, is_scan = extractor.extract_text_from_document(doc)
            mgr.index_document(doc, chunks, is_scan)
            if doc.status == DocumentStatus.INDEXED:
                ok += 1
                tag = f"OK  {len(chunks):4d} chunks"
            else:
                warn += 1
                tag = f"WARN {doc.status.value} (no text)"
        except Exception as e:  # keep going; a bad PDF must not kill the batch
            err += 1
            tag = f"ERR {type(e).__name__}: {str(e)[:80]}"

        done_pages += doc.page_count
        pct = 100 * done_pages / total_pages if total_pages else 100
        rate = done_pages / max(time.time() - t_start, 1)
        eta_min = (total_pages - done_pages) / rate / 60 if rate else 0
        print(f"[{i}/{total}] {pct:5.1f}% eta~{eta_min:4.0f}m  "
              f"{doc.page_count:4d}p {time.time()-t0:5.1f}s  {tag}  {doc.filename[:60]}",
              flush=True)

    dt = (time.time() - t_start) / 60
    print(f"[done] ok={ok} warn={warn} err={err} in {dt:.1f} min", flush=True)
    mgr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
