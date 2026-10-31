from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatOptions(BaseModel):
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    effort: Literal["fast", "thorough"] = "fast"
    top_k: int = Field(8, ge=1, le=30)
    filters: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    options: ChatOptions = ChatOptions()


class Finding(BaseModel):
    statement: str
    status: Literal["verified", "hypothesis", "unavailable"]
    citations: list[str] = []


class TraceStep(BaseModel):
    name: str
    ms: int
    detail: str | None = None


class Trace(BaseModel):
    route: str = ""
    steps: list[TraceStep] = []
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    total_ms: int = 0
    verification: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer_markdown: str
    findings: list[Finding] = []
    charts: list["ChartPayload"] = []
    tables: list["ChartPayload"] = []
    evidence: list["EvidenceItem"] = []
    follow_ups: list[str] = []
    trace: Trace = Trace()


class MessageOut(BaseModel):
    id: str
    role: str
    text: str
    created_at: str | None = None
    response: ChatResponse | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str | None = None
    messages: list[MessageOut] = []


from backend.app.schemas.chart import ChartPayload  # noqa: E402
from backend.app.schemas.evidence import EvidenceItem  # noqa: E402

