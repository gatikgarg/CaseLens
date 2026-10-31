from typing import Any, Literal

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    ref_id: str
    ticket_id: str
    doc_type: Literal["ticket_summary", "utterance", "history_event"]
    text: str
    scores: dict[str, float] = {}
    rank: int
    has_conversation: bool
    cited: bool = False
    ticket_facts: dict[str, Any] | None = None

