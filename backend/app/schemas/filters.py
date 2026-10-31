from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TicketFilters(BaseModel):
    q: str | None = None
    priority: str | None = None
    category: str | None = None
    project: str | None = None
    status: str | None = None
    from_: str | None = Field(None, alias="from")
    to: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=1, le=200)

    model_config = {"populate_by_name": True}


class RetrievalDebugRequest(BaseModel):
    query: str
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    top_k: int = Field(8, ge=1, le=30)
    do_rewrite: bool = True
    do_rerank: bool = True


class StageHit(BaseModel):
    rank: int
    doc_id: str
    ticket_id: str
    doc_type: str
    snippet: str
    score: float
    scores: dict[str, float] = {}


class RetrievalDebugResponse(BaseModel):
    query: str
    rewrite: dict[str, Any]
    stages: dict[str, list[StageHit]]
    timings_ms: dict[str, int]

