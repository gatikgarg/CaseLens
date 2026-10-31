from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict]
    options: dict
    route: str
    standalone_question: str
    transcript: list[dict]
    iterations: int
    results: dict[str, Any]
    charts: list[dict]
    evidence: list[dict]
    answer: dict | None
    verification: dict | None
    repair_attempts: int
    trace: list[dict]
    tokens_in: int
    tokens_out: int

