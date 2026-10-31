from collections import defaultdict


def rrf(rankings: list, k: int = 60, weights: list[float] | None = None) -> list:
    """score(d) = sum_i w_i / (k + rank_i(d)). Rank-based; no scale normalization needed."""
    weights = weights or [1.0] * len(rankings)
    score: dict = defaultdict(float)
    best: dict = {}
    for w, lst in zip(weights, rankings):
        for r, h in enumerate(lst, 1):
            score[h.id] += w / (k + r)
            if h.id not in best:
                best[h.id] = h
            else:
                best[h.id].scores.update(h.scores)
                best[h.id].ranks.update(h.ranks)
    fused = sorted(best.values(), key=lambda h: score[h.id], reverse=True)
    for r, h in enumerate(fused, 1):
        h.scores["rrf"] = score[h.id]
        h.ranks["rrf"] = r
    return fused


def qdrant_native_hybrid(dense_query, sparse_query, flt, limit: int) -> list:
    """Server-side RRF fusion via Qdrant prefetch + FusionQuery."""
    from qdrant_client.models import Fusion, FusionQuery, Prefetch

    from backend.app.core.config import get_settings
    from backend.app.vectorstore.qdrant_store import client

    r = client().query_points(
        get_settings().qdrant_collection,
        prefetch=[
            Prefetch(query=dense_query, using="dense", limit=limit * 2),
            Prefetch(query=sparse_query, using="bm25", limit=limit * 2),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    return r.points

