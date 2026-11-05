"""Tests for cross-encoder reranking logic (model mocked)."""

from mcp_knowledge_librarian.models import SearchResult
from mcp_knowledge_librarian.reranker import Reranker


def _result(cid, snippet):
    return SearchResult(
        document_id=cid, document_path="file://x", page_number=1,
        snippet=snippet, score=0.5, chunk_id=cid,
    )


class _FakeModel:
    """Scores a (query, passage) pair by passage length — deterministic."""

    def predict(self, pairs):
        return [float(len(p[1])) for p in pairs]


def test_rerank_orders_by_score_and_trims():
    rr = Reranker()
    rr._model = _FakeModel()  # bypass the real 2.3 GB model

    results = [
        _result("c1", "short"),
        _result("c2", "a considerably longer snippet than the others here"),
        _result("c3", "medium length snippet"),
    ]
    out = rr.rerank("query", results, top_k=2)

    assert [r.chunk_id for r in out] == ["c2", "c3"]  # longest passages win
    assert out[0].score >= out[1].score               # sigmoid preserves order
    assert all(0.0 <= r.score <= 1.0 for r in out)     # scores normalized


def test_rerank_empty_is_noop():
    rr = Reranker()
    rr._model = _FakeModel()
    assert rr.rerank("query", []) == []
