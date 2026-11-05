#!/usr/bin/env python3
"""Batch-embed all chunks that don't have an embedding yet.

Resumable: embeddings are committed per batch, so a stopped/killed run just
resumes with the remaining chunks. Safe to re-run after new documents are
indexed (e.g. after the OCR reindex) — only missing chunks are processed.

Usage:
  python3 scripts/embed_chunks.py --index PATH [--model NAME] [--batch 256]
"""
import argparse
import sys
import time

from mcp_knowledge_librarian.embeddings import EmbeddingModel
from mcp_knowledge_librarian.indexer import IndexManager


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="Index directory (contains librarian.db)")
    ap.add_argument("--model", default="intfloat/multilingual-e5-small")
    ap.add_argument("--batch", type=int, default=256, help="Chunks per DB fetch/commit")
    args = ap.parse_args()

    mgr = IndexManager(index_path=args.index)
    mgr._conn.execute("PRAGMA busy_timeout=60000")  # coexist with the running server
    emb = EmbeddingModel(args.model)

    total = mgr._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    start_embedded = mgr.count_embeddings()
    print(f"[start] {total} chunks, {start_embedded} already embedded, model={args.model}",
          flush=True)

    done = 0
    t0 = time.time()
    while True:
        batch = mgr.chunks_missing_embeddings(limit=args.batch)
        if not batch:
            break
        try:
            vecs = emb.encode_passages([t for _, t in batch], batch_size=64)
            mgr.store_embeddings([(cid, vecs[i]) for i, (cid, _) in enumerate(batch)])
        except Exception as e:
            print(f"[error] batch failed, aborting: {type(e).__name__}: {e}", flush=True)
            return 1
        done += len(batch)
        embedded = mgr.count_embeddings()
        rate = done / max(time.time() - t0, 1)
        remaining = max(total - embedded, 0)
        eta = remaining / rate / 60 if rate else 0
        print(f"[embed] +{done} this run  total={embedded}/{total}  "
              f"{rate:.0f}/s  eta~{eta:.0f}m", flush=True)

    dt = (time.time() - t0) / 60
    print(f"[done] {mgr.count_embeddings()}/{total} embedded (+{done} this run) in {dt:.1f} min",
          flush=True)
    mgr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
