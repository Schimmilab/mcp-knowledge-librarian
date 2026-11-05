"""Optional cross-encoder reranking.

Hybrid retrieval returns a broad candidate pool; a cross-encoder reads each
(query, chunk) pair jointly and scores true relevance far more precisely than
the first-stage retrievers. This is the last quality stage of the pipeline and
is opt-in (search.enable_rerank), since it loads a second model and adds
per-query latency.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Strong multilingual cross-encoder (German + English), ~2.3 GB. The smaller
# mmarco-MiniLM was tested first but ranked German queries incorrectly (it
# scored an off-topic passage above the on-topic one).
DEFAULT_RERANKER = "BAAI/bge-reranker-v2-m3"


class Reranker:
    def __init__(self, model_name: str = DEFAULT_RERANKER, device: Optional[str] = None):
        self.model_name = model_name
        self._device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            import torch

            device = self._device or (
                "mps" if torch.backends.mps.is_available() else "cpu"
            )
            logger.info(f"Loading reranker {self.model_name} on {device}")
            self._model = CrossEncoder(self.model_name, device=device, max_length=512)
        return self._model

    def rerank(self, query: str, results: list, top_k: Optional[int] = None) -> list:
        """Reorder search results by cross-encoder relevance.

        Scores are squashed to 0..1 with a sigmoid for a stable display value;
        ordering uses the raw logits.
        """
        if not results:
            return results
        pairs = [(query, r.snippet) for r in results]
        scores = self.model.predict(pairs)
        order = sorted(range(len(results)), key=lambda i: scores[i], reverse=True)
        ranked = [
            results[i].model_copy(
                update={"score": round(1.0 / (1.0 + math.exp(-float(scores[i]))), 4)}
            )
            for i in order
        ]
        return ranked[:top_k] if top_k else ranked
