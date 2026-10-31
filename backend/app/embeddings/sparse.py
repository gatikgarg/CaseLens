from functools import lru_cache


@lru_cache
def _m():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding("Qdrant/bm25")


def sparse_docs(texts: list[str]) -> list:
    from qdrant_client.models import SparseVector

    return [
        SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
        for e in _m().embed(texts)
    ]


def sparse_query(q: str):
    from qdrant_client.models import SparseVector

    e = next(iter(_m().query_embed(q)))
    return SparseVector(indices=e.indices.tolist(), values=e.values.tolist())

