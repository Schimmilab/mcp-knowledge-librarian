"""Local sentence-embedding model for semantic search.

Uses a multilingual E5 model (German + English content) via
sentence-transformers, accelerated on Apple MPS when available. Runs fully
offline once the model is cached — no data leaves the machine, which is the
whole point of a local knowledge base.

E5 models expect asymmetric prefixes: stored chunks are encoded as
"passage: ...", live queries as "query: ...".
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "intfloat/multilingual-e5-small"  # 384 dims, multilingual


class EmbeddingModel:
    """Lazy wrapper around a sentence-transformers model.

    The model (and its ~120 MB weights) is only loaded on first use, so
    importing this module — or running a BM25-only search — stays cheap.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, device: Optional[str] = None):
        self.model_name = model_name
        self._device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch

            device = self._device or (
                "mps" if torch.backends.mps.is_available() else "cpu"
            )
            logger.info(f"Loading embedding model {self.model_name} on {device}")
            self._model = SentenceTransformer(self.model_name, device=device)
        return self._model

    @property
    def dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def encode_passages(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Encode stored chunks. Returns an (N, dim) float32 array (L2-normalized)."""
        vecs = self.model.encode(
            [f"passage: {t}" for t in texts],
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        """Encode a search query. Returns a (dim,) float32 array (L2-normalized)."""
        vec = self.model.encode(
            f"query: {text}",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.astype(np.float32)
