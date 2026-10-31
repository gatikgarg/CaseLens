import time
from dataclasses import dataclass, field

from backend.app.core.config import get_settings
from backend.app.embeddings.encoder import embed_query
from backend.app.embeddings.sparse import sparse_query
from backend.app.retrieval.filters import Filters
from backend.app.retrieval.fusion import rrf
from backend.app.retrieval.rerank import rerank
from backend.app.retrieval.rewrite import rewrite
from backend.app.vectorstore.qdrant_store import client


@dataclass
class Hit:
    id: str
    ticket_id: str
    doc_type: str
    text: str
    payload: dict
    scores: dict[str, float] = field(default_factory=dict)
    ranks: dict[str, int] = field(default_factory=dict)


def _to_hits(points, name: str) -> list[Hit]:
    hits = []
    for r, p in enumerate(points, 1):
        pl = p.payload or {}
        hits.append(
            Hit(
                str(p.id),
                pl["ticket_id"],
                pl["doc_type"],
                pl.get("text", ""),
                pl,
                {name: p.score},
                {name: r},
            )
        )
    return hits


def dense_search(q: str, flt, limit: int) -> list[Hit]:
    r = client().query_points(
        get_settings().qdrant_collection,
        query=embed_query(q).tolist(),
        using="dense",
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    return _to_hits(r.points, "dense")


def sparse_search(q: str, flt, limit: int) -> list[Hit]:
    r = client().query_points(
        get_settings().qdrant_collection,
        query=sparse_query(q),
        using="bm25",
        query_filter=flt,
        limit=limit,
        with_payload=True,
    )
    return _to_hits(r.points, "bm25")


def search(
    question,
    options,
    history=None,
    filters=None,
    allowed=None,
    do_rewrite=True,
    do_rerank=True,
    n_candidates=50,
) -> dict:
    t: dict[str, int] = {}
    stages: dict[str, list[Hit]] = {}

    def tick(name, t0):
        t[name] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    rw = (
        rewrite(question, history or [], allowed or {})
        if do_rewrite
        else {"standalone": question, "variants": [], "filters": {}}
    )
    queries = [rw["standalone"], *rw.get("variants", [])[:2]]
    tick("rewrite", t0)
    flt = (filters or Filters()).to_qdrant()

    t0 = time.perf_counter()
    lists: list[list[Hit]] = []
    for q in queries:
        if options.mode in ("dense", "hybrid"):
            lists.append(dense_search(q, flt, n_candidates))
        if options.mode in ("bm25", "hybrid"):
            lists.append(sparse_search(q, flt, n_candidates))
    tick("retrieve", t0)
    stages["retrieved"] = [h for lst in lists for h in lst]

    t0 = time.perf_counter()
    fused = rrf(lists)[:n_candidates] if len(lists) > 1 else (lists[0] if lists else [])
    tick("fuse", t0)
    stages["fused"] = fused

    t0 = time.perf_counter()
    final = rerank(rw["standalone"], fused, options.top_k * 2) if do_rerank else fused[: options.top_k * 2]
    tick("rerank", t0)
    stages["reranked"] = final

    return {"rewrite": rw, "stages": stages, "hits": final, "timings_ms": t}


def inspect(query: str, mode: str, top_k: int, do_rewrite: bool, do_rerank: bool, n_candidates: int = 50) -> dict:
    t: dict[str, int] = {}

    def tick(name, t0):
        t[name] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    rw = rewrite(query, [], {}) if do_rewrite else {"standalone": query, "variants": [], "filters": {}}
    queries = [rw["standalone"], *rw.get("variants", [])[:2]]
    tick("rewrite", t0)

    dense: list[Hit] = []
    bm25: list[Hit] = []
    t0 = time.perf_counter()
    for q in queries:
        if mode in ("dense", "hybrid"):
            dense += dense_search(q, None, n_candidates)
        if mode in ("bm25", "hybrid"):
            bm25 += sparse_search(q, None, n_candidates)
    tick("retrieve", t0)

    lists = [dense, bm25] if mode == "hybrid" else ([dense] if mode == "dense" else [bm25])
    t0 = time.perf_counter()
    fused = rrf(lists)[:n_candidates] if len(lists) > 1 else (lists[0] if lists else [])
    tick("fuse", t0)

    t0 = time.perf_counter()
    final = rerank(rw["standalone"], fused, top_k * 2) if do_rerank else fused[: top_k * 2]
    tick("rerank", t0)

    return {"rewrite": rw, "stages": {"dense": dense, "bm25": bm25, "fused": fused, "reranked": final}, "timings_ms": t}

