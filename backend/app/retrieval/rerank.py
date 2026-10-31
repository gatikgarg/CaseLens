from functools import lru_cache

from backend.app.core.config import get_settings


@lru_cache
def _ce():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(get_settings().rerank_model, max_length=512)


def rerank(query: str, hits: list, top_n: int) -> list:
    if not hits:
        return hits
    scores = _ce().predict([(query, h.text) for h in hits], batch_size=16)
    for h, s in zip(hits, scores):
        h.scores["rerank"] = float(s)
    out = sorted(hits, key=lambda h: h.scores["rerank"], reverse=True)[:top_n]
    for r, h in enumerate(out, 1):
        h.ranks["rerank"] = r
    return out

