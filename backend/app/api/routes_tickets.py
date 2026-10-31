from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.schemas.filters import TicketFilters

router = APIRouter()


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


@router.get("/api/tickets")
def tickets(f: TicketFilters = Depends()):
    where, params = [], {}
    if f.q:
        where.append("t.title ILIKE :q")
        params["q"] = f"%{f.q}%"
    for col, val in (("f.priority", f.priority), ("f.category", f.category), ("f.project_id", f.project), ("f.status", f.status)):
        if val:
            where.append(f"{col} = :{col.split('.')[1]}")
            params[col.split(".")[1]] = val
    if f.from_:
        where.append("f.created_at >= :from_")
        params["from_"] = f.from_
    if f.to:
        where.append("f.created_at <= :to")
        params["to"] = f.to
    sql = (
        "SELECT f.*, t.title, t.description FROM ticket_facts f JOIN tickets t USING (ticket_id)"
        + (f" WHERE {' AND '.join(where)}" if where else "")
        + " ORDER BY f.created_at DESC LIMIT :limit OFFSET :offset"
    )
    params["limit"] = f.page_size
    params["offset"] = (f.page - 1) * f.page_size
    with SessionLocal() as s:
        rows = s.execute(text(sql), params).mappings().all()
        count = s.execute(text("SELECT COUNT(*) FROM ticket_facts")).scalar_one()
    return {"items": [{k: _iso(v) for k, v in r.items()} for r in rows], "total": count, "page": f.page, "page_size": f.page_size}


@router.get("/api/tickets/{ticket_id}")
def ticket_detail(ticket_id: str):
    with SessionLocal() as s:
        facts = s.execute(text("SELECT * FROM ticket_facts WHERE ticket_id = :id"), {"id": ticket_id}).mappings().first()
        if not facts:
            raise HTTPException(404, "ticket not found")
        events = s.execute(
            text("SELECT * FROM ticket_events WHERE ticket_id = :id ORDER BY changed_at, event_id"),
            {"id": ticket_id},
        ).mappings().all()
        utterances = s.execute(
            text("SELECT * FROM utterances WHERE ticket_id = :id ORDER BY seq"),
            {"id": ticket_id},
        ).mappings().all()
    return {
        "ticket": {k: _iso(v) for k, v in facts.items()},
        "events": [{k: _iso(v) for k, v in e.items()} for e in events],
        "utterances": [{k: _iso(v) for k, v in u.items()} for u in utterances],
        "conversation_available": bool(utterances),
    }

