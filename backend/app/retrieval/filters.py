from datetime import datetime

from pydantic import BaseModel


class Filters(BaseModel):
    project: list[str] | None = None
    category: list[str] | None = None
    priority: list[str] | None = None
    status: list[str] | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    has_conversation: bool | None = None
    doc_types: list[str] | None = None

    def to_qdrant(self):
        from qdrant_client.models import (
            FieldCondition,
            Filter,
            MatchAny,
            MatchValue,
            Range,
        )

        must = []
        for f in ("project", "category", "priority", "status"):
            v = getattr(self, f)
            if v:
                must.append(FieldCondition(key=f, match=MatchAny(any=v)))
        if self.doc_types:
            must.append(FieldCondition(key="doc_type", match=MatchAny(any=self.doc_types)))
        if self.has_conversation is not None:
            must.append(FieldCondition(key="has_conversation", match=MatchValue(value=self.has_conversation)))
        if self.created_from or self.created_to:
            must.append(
                FieldCondition(
                    key="created_ts",
                    range=Range(
                        gte=int(self.created_from.timestamp()) if self.created_from else None,
                        lte=int(self.created_to.timestamp()) if self.created_to else None,
                    ),
                )
            )
        return Filter(must=must) if must else None

