from backend.app.core.config import get_settings


def client():
    from qdrant_client import QdrantClient

    return QdrantClient(url=get_settings().qdrant_url, timeout=60)


def ensure_collection(recreate: bool = False) -> None:
    from qdrant_client.models import (
        Distance,
        Modifier,
        PayloadSchemaType,
        SparseVectorParams,
        VectorParams,
    )

    s = get_settings()
    c = client()
    if recreate and c.collection_exists(s.qdrant_collection):
        c.delete_collection(s.qdrant_collection)
    if not c.collection_exists(s.qdrant_collection):
        c.create_collection(
            s.qdrant_collection,
            vectors_config={"dense": VectorParams(size=s.embed_dim, distance=Distance.COSINE)},
            sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
        )
        for f in ["project", "category", "priority", "status", "doc_type", "ticket_id"]:
            c.create_payload_index(s.qdrant_collection, f, PayloadSchemaType.KEYWORD)
        c.create_payload_index(s.qdrant_collection, "created_ts", PayloadSchemaType.INTEGER)
        c.create_payload_index(s.qdrant_collection, "has_conversation", PayloadSchemaType.BOOL)

