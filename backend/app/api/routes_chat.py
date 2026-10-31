import json
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from backend.app.agent.graph import agent
from backend.app.db.models import ConversationRow, MessageRow
from backend.app.db.session import SessionLocal
from backend.app.llm.deepseek import cost_usd
from backend.app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    Finding,
    MessageOut,
    Trace,
    TraceStep,
)
from backend.app.schemas.chart import ChartPayload, Provenance, TablePayload
from backend.app.schemas.evidence import EvidenceItem

router = APIRouter()


def _initial_state(req: ChatRequest) -> dict:
    return {
        "question": req.message,
        "history": load_history(req.conversation_id or ""),
        "options": req.options.model_dump(),
        "route": "",
        "standalone_question": req.message,
        "transcript": [],
        "iterations": 0,
        "results": {},
        "charts": [],
        "evidence": [],
        "answer": None,
        "verification": None,
        "repair_attempts": 0,
        "trace": [],
        "tokens_in": 0,
        "tokens_out": 0,
    }


def load_history(cid: str) -> list[dict]:
    if not cid:
        return []
    try:
        with SessionLocal() as s:
            rows = s.scalars(
                select(MessageRow)
                .where(MessageRow.conversation_id == cid)
                .order_by(MessageRow.created_at)
                .limit(20)
            ).all()
        return [{"role": r.role, "text": r.text} for r in rows]
    except Exception:
        return []


def build_response(cid: str, state: dict) -> ChatResponse:
    answer = state.get("answer") or {"answer_markdown": "", "findings": [], "follow_ups": []}
    steps = [TraceStep(name=s["name"], ms=s["ms"], detail=s.get("detail")) for s in state.get("trace", [])]
    total_ms = sum(s.ms for s in steps)
    tokens_in = state.get("tokens_in", 0)
    tokens_out = state.get("tokens_out", 0)

    charts: list[ChartPayload] = []
    tables: list[ChartPayload] = []
    for c in state.get("charts", []):
        payload = ChartPayload(
            chart_id=c["chart_id"],
            title=c["title"],
            chart_type=c["chart_type"],
            figure=c["figure"],
            table=TablePayload(**c["table"]),
            provenance=Provenance(**c["provenance"]),
        )
        (tables if c["chart_type"] == "table" else charts).append(payload)

    return ChatResponse(
        conversation_id=cid,
        message_id=str(uuid4()),
        answer_markdown=answer.get("answer_markdown", ""),
        findings=[Finding(**f) for f in answer.get("findings", [])],
        charts=charts,
        tables=tables,
        evidence=[EvidenceItem(**e) for e in state.get("evidence", [])],
        follow_ups=answer.get("follow_ups", []),
        trace=Trace(
            route=state.get("route", ""),
            steps=steps,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd(tokens_in, tokens_out),
            total_ms=total_ms,
            verification=state.get("verification"),
        ),
    )


def save_turn(cid: str, user_text: str, resp: ChatResponse) -> None:
    try:
        with SessionLocal() as s:
            if not s.get(ConversationRow, cid):
                s.add(ConversationRow(id=cid, title=user_text[:40] or "New chat"))
            s.add(MessageRow(id=str(uuid4()), conversation_id=cid, role="user", text=user_text))
            s.add(
                MessageRow(
                    id=resp.message_id,
                    conversation_id=cid,
                    role="assistant",
                    text=resp.answer_markdown,
                    response_json=resp.model_dump(mode="json"),
                )
            )
            s.commit()
    except Exception:
        pass


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    cid = req.conversation_id or str(uuid4())
    state = await agent.ainvoke(_initial_state(req))
    resp = build_response(cid, state)
    save_turn(cid, req.message, resp)
    return resp


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    cid = req.conversation_id or str(uuid4())

    async def gen():
        final: dict = {}
        async for chunk in agent.astream(_initial_state(req), stream_mode="values"):
            final = chunk
            trace = chunk.get("trace", [])
            if trace:
                s = trace[-1]
                yield f"data: {json.dumps({'event': 'step', 'name': s['name'], 'ms': s['ms']})}\n\n"
        resp = build_response(cid, final or _initial_state(req))
        save_turn(cid, req.message, resp)
        yield f"data: {json.dumps({'event': 'final', 'data': resp.model_dump(mode='json')})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/conversations", response_model=list[ConversationOut])
def conversations() -> list[ConversationOut]:
    try:
        with SessionLocal() as s:
            convs = s.scalars(select(ConversationRow).order_by(ConversationRow.created_at.desc()).limit(50)).all()
            out = []
            for c in convs:
                msgs = s.scalars(
                    select(MessageRow).where(MessageRow.conversation_id == c.id).order_by(MessageRow.created_at)
                ).all()
                out.append(
                    ConversationOut(
                        id=c.id,
                        title=c.title,
                        created_at=c.created_at.isoformat() if c.created_at else None,
                        messages=[_message_out(m) for m in msgs],
                    )
                )
        return out
    except Exception:
        return []


def _message_out(m: MessageRow) -> MessageOut:
    resp = None
    if m.response_json:
        resp = ChatResponse(**m.response_json)
    return MessageOut(
        id=m.id,
        role=m.role,
        text=m.text,
        created_at=m.created_at.isoformat() if m.created_at else None,
        response=resp,
    )


@router.get("/api/conversations/{cid}", response_model=ConversationOut)
def conversation(cid: str) -> ConversationOut:
    with SessionLocal() as s:
        c = s.get(ConversationRow, cid)
        if not c:
            return ConversationOut(id=cid, title="")
        msgs = s.scalars(select(MessageRow).where(MessageRow.conversation_id == cid).order_by(MessageRow.created_at)).all()
        return ConversationOut(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat() if c.created_at else None,
            messages=[_message_out(m) for m in msgs],
        )

