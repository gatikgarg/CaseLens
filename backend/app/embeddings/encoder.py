from functools import lru_cache

import numpy as np

from backend.app.core.config import get_settings


@lru_cache
def model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embed_model)


def embed_docs(texts: list[str], batch_size: int = 32) -> np.ndarray:
    return model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def embed_query(q: str) -> np.ndarray:
    s = get_settings()
    return model().encode([s.embed_query_prefix + q], normalize_embeddings=True)[0]

