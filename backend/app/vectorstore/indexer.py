from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.db.models import Document
from backend.app.db.session import SessionLocal
from backend.app.embeddings.encoder import embed_docs
from backend.app.embeddings.sparse import sparse_docs
from backend.app.vectorstore.qdrant_store import client, ensure_collection


def index_pending(batch: int = 64) -> int:
    from qdrant_client.models import PointStruct

    ensure_collection()
    c, coll = client(), get_settings().qdrant_collection
    total = 0
    with SessionLocal() as s:
        while True:
            docs = s.scalars(
                select(Document)
                .where(
                    (Document.indexed_hash.is_(None))
                    | (Document.indexed_hash != Document.content_hash)
                )
                .limit(batch)
            ).all()
            if not docs:
                break
            texts = [d.text for d in docs]
            dense = embed_docs(texts)
            sparse = sparse_docs(texts)
            c.upsert(
                coll,
                [
                    PointStruct(
                        id=d.doc_id,
                        vector={"dense": dense[i].tolist(), "bm25": sparse[i]},
                        payload={
                            **d.payload,
                            "doc_type": d.doc_type,
                            "ticket_id": d.ticket_id,
                            "parent_id": d.parent_id,
                            "text": d.text,
                        },
                    )
                    for i, d in enumerate(docs)
                ],
            )
            for d in docs:
                d.indexed_hash = d.content_hash
            s.commit()
            total += len(docs)
            print("indexed", len(docs), "docs (total", total, ")")
    return total


if __name__ == "__main__":
    index_pending()

