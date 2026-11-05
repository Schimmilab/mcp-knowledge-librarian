"""Tests for embedding storage, semantic search, and hybrid RRF fusion.

Uses synthetic unit vectors instead of the real model, so these are fast and
deterministic and don't need network access.
"""

import numpy as np
import pytest

from mcp_knowledge_librarian.indexer import IndexManager
from mcp_knowledge_librarian.models import (
    DocumentMetadata,
    SearchQuery,
    TextChunk,
)


@pytest.fixture
def manager(tmp_path):
    return IndexManager(index_path=str(tmp_path / "index"))


def _doc(doc_id, text):
    md = DocumentMetadata(
        id=doc_id, filename=f"{doc_id}.pdf", path=f"/lib/{doc_id}.pdf",
        size_bytes=1, page_count=1,
    )
    ch = TextChunk(
        chunk_id=f"{doc_id}:1", document_id=doc_id, page_number=1,
        text=text, char_offset=0, char_length=len(text),
    )
    return md, ch


def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_rrf_fuses_rankings():
    scores = IndexManager._rrf([["a", "b", "c"], ["b", "a", "d"]])
    assert set(scores) == {"a", "b", "c", "d"}
    assert scores["a"] > scores["c"]  # a ranks high in both lists
    assert scores["b"] > scores["d"]


def test_store_count_and_missing(manager):
    md, ch = _doc("d1", "hello world")
    manager.index_document(md, [ch], is_scan=False)
    assert manager.count_embeddings() == 0
    assert manager.chunks_missing_embeddings() == [("d1:1", "hello world")]

    manager.store_embeddings([("d1:1", _unit([1, 0, 0]))])
    assert manager.count_embeddings() == 1
    assert manager.chunks_missing_embeddings() == []


def test_embedding_roundtrip_is_float16_close(manager):
    md, ch = _doc("d1", "hello")
    manager.index_document(md, [ch], is_scan=False)
    vec = _unit([0.3, 0.5, 0.81])
    manager.store_embeddings([("d1:1", vec)])
    ids, mat = manager._embedding_matrix()
    assert ids == ["d1:1"]
    np.testing.assert_allclose(mat[0], vec, atol=1e-2)  # fp16 tolerance


def test_semantic_search_ranks_by_cosine(manager):
    for did, vec, text in [
        ("d1", [1, 0, 0], "apple"),
        ("d2", [0, 1, 0], "banana"),
        ("d3", [0.9, 0.1, 0], "apricot"),
    ]:
        md, ch = _doc(did, text)
        manager.index_document(md, [ch], is_scan=False)
        manager.store_embeddings([(f"{did}:1", _unit(vec))])

    res = manager.semantic_search(_unit([1, 0, 0]), max_results=3)
    ids = [r.chunk_id for r in res]
    assert ids[0] == "d1:1"          # exact direction
    assert ids[1] == "d3:1"          # near before orthogonal
    assert res[0].score >= res[1].score >= res[2].score


def test_semantic_search_empty_without_embeddings(manager):
    md, ch = _doc("d1", "hello")
    manager.index_document(md, [ch], is_scan=False)
    assert manager.semantic_search(_unit([1, 0, 0])) == []


def test_semantic_search_document_filter(manager):
    for did, vec in [("d1", [1, 0, 0]), ("d2", [1, 0, 0])]:
        md, ch = _doc(did, "same direction")
        manager.index_document(md, [ch], is_scan=False)
        manager.store_embeddings([(f"{did}:1", _unit(vec))])
    res = manager.semantic_search(_unit([1, 0, 0]), max_results=5, document_id="d2")
    assert [r.chunk_id for r in res] == ["d2:1"]


def test_embedding_matrix_reloads_on_count_change(manager):
    md, ch = _doc("d1", "a")
    manager.index_document(md, [ch], is_scan=False)
    manager.store_embeddings([("d1:1", _unit([1, 0, 0]))])
    ids, _ = manager._embedding_matrix()  # primes cache at count=1
    assert ids == ["d1:1"]

    # Simulate another process inserting an embedding directly (no cache reset).
    md2, ch2 = _doc("d2", "b")
    manager.index_document(md2, [ch2], is_scan=False)
    v = np.asarray(_unit([0, 1, 0]), dtype=np.float16)
    with manager._conn:
        manager._conn.execute(
            "INSERT INTO chunk_embeddings (chunk_id, dim, vec) VALUES (?,?,?)",
            ("d2:1", 3, v.tobytes()),
        )
    ids2, _ = manager._embedding_matrix()  # count changed -> reload
    assert set(ids2) == {"d1:1", "d2:1"}


def test_hybrid_includes_both_retrievers(manager):
    # d1 matches the keyword lexically; d2 only matches the query vector.
    for did, vec, text in [
        ("d1", [0, 1, 0], "kombucha scoby culture"),
        ("d2", [1, 0, 0], "unrelated lexical content"),
    ]:
        md, ch = _doc(did, text)
        manager.index_document(md, [ch], is_scan=False)
        manager.store_embeddings([(f"{did}:1", _unit(vec))])

    sq = SearchQuery(query="kombucha", max_results=5, min_score=0.0)
    res = manager.hybrid_search(sq, _unit([1, 0, 0]))  # vector points at d2
    ids = {r.chunk_id for r in res}
    assert "d1:1" in ids  # contributed by BM25
    assert "d2:1" in ids  # contributed by semantic search
