import hashlib
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from backend.app.db.models import Document, Ticket, TicketEvent, Utterance
from backend.app.db.session import SessionLocal
from backend.app.documents.chunker import Turn, chunk_turns

NS = uuid.UUID("5e1f0a52-7b7e-4b8c-9a55-0c0d6d5f2a11")


def doc_id(ticket_id: str, doc_type: str, idx: int = 0) -> str:
    return str(uuid.uuid5(NS, f"{ticket_id}|{doc_type}|{idx}"))


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ticket_summary_text(t, events, has_conv: bool) -> str:
    lines = [f"Ticket {t.ticket_id}"]
    for label, val in [
        ("Project", t.project_id),
        ("Category", t.category),
        ("Priority", t.priority),
        ("Status", t.status),
        ("Title", t.title),
    ]:
        if val:
            lines.append(f"{label}: {val}")
    if t.created_at:
        lines.append(f"Created: {t.created_at:%Y-%m-%d}")
    if t.resolved_at:
        lines.append(f"Resolved: {t.resolved_at:%Y-%m-%d}")
    if t.description:
        lines.append(f"Description: {t.description[:1500]}")
    if events:
        assign = [e for e in events if e.field and "assign" in e.field.lower()]
        if assign:
            path = " -> ".join(str(e.new_value) for e in assign[-8:])
            lines.append(f"Assignment path: {path} ({len(assign)} reassignments)")
    lines.append("Conversation available: " + ("yes" if has_conv else "no"))
    return "\n".join(lines)


def _payload(t, doc_type: str, parent_id: str | None, has_conv: bool, **extra) -> dict:
    return {
        "ticket_id": t.ticket_id,
        "parent_id": parent_id,
        "doc_type": doc_type,
        "project": t.project_id,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "created_ts": int(t.created_at.timestamp()) if t.created_at else None,
        "has_conversation": has_conv,
        "source_file": "mendeley_helpdesk_v3",
        **extra,
    }


def _upsert(session, d: Document) -> None:
    cols = [c.name for c in Document.__table__.columns]
    row = {k: getattr(d, k) for k in cols}
    stmt = insert(Document).values([row])
    stmt = stmt.on_conflict_do_update(
        index_elements=["doc_id"],
        set_={"text": stmt.excluded.text, "payload": stmt.excluded.payload, "content_hash": stmt.excluded.content_hash},
    )
    session.execute(stmt)


def build() -> None:
    with SessionLocal() as s:
        tickets = s.scalars(select(Ticket)).all()
        events_by_ticket: dict[str, list[TicketEvent]] = defaultdict(list)
        for e in s.scalars(select(TicketEvent).order_by(TicketEvent.changed_at, TicketEvent.event_id)):
            events_by_ticket[e.ticket_id].append(e)
        utterances_by_ticket: dict[str, list[Utterance]] = defaultdict(list)
        for u in s.scalars(select(Utterance).order_by(Utterance.seq)):
            utterances_by_ticket[u.ticket_id].append(u)

        for t in tickets:
            events = events_by_ticket.get(t.ticket_id, [])
            utts = utterances_by_ticket.get(t.ticket_id, [])
            has_conv = bool(utts)

            summary_text = ticket_summary_text(t, events, has_conv)
            summary_doc_id = doc_id(t.ticket_id, "ticket_summary")
            _upsert(
                s,
                Document(
                    doc_id=summary_doc_id,
                    parent_id=None,
                    ticket_id=t.ticket_id,
                    doc_type="ticket_summary",
                    text=summary_text,
                    payload=_payload(t, "ticket_summary", None, has_conv, chunk_idx=0, n_chunks=1),
                    content_hash=h(summary_text),
                    indexed_hash=None,
                ),
            )

            if utts:
                header = (
                    f"Ticket {t.ticket_id} | {t.category or 'no category'} | "
                    f"{t.priority or 'no priority'} | project {t.project_id or 'unknown'}"
                )
                turns = [Turn(seq=u.seq or i, role=u.speaker_role, text=u.text or "") for i, u in enumerate(utts)]
                chunks = chunk_turns(turns, header)
                for idx, (text, _chunk_turns) in enumerate(chunks):
                    _upsert(
                        s,
                        Document(
                            doc_id=doc_id(t.ticket_id, "utterance", idx),
                            parent_id=summary_doc_id,
                            ticket_id=t.ticket_id,
                            doc_type="utterance",
                            text=text,
                            payload=_payload(
                                t,
                                "utterance",
                                summary_doc_id,
                                has_conv,
                                chunk_idx=idx,
                                n_chunks=len(chunks),
                                speaker_roles=sorted({x.role for x in _chunk_turns if x.role}),
                            ),
                            content_hash=h(text),
                            indexed_hash=None,
                        ),
                    )

            if events:
                history_lines = [f"Ticket {t.ticket_id} change history"]
                for e in events[:50]:
                    if e.field:
                        history_lines.append(
                            f"{e.changed_at:%Y-%m-%d} {e.field}: {e.old_value or ''} -> {e.new_value or ''}"
                        )
                history_text = "\n".join(history_lines)
                _upsert(
                    s,
                    Document(
                        doc_id=doc_id(t.ticket_id, "history_event"),
                        parent_id=summary_doc_id,
                        ticket_id=t.ticket_id,
                        doc_type="history_event",
                        text=history_text,
                        payload=_payload(t, "history_event", summary_doc_id, has_conv, chunk_idx=0, n_chunks=1),
                        content_hash=h(history_text),
                        indexed_hash=None,
                    ),
                )

        s.commit()
        counts = {
            doc_type: n
            for doc_type, n in s.execute(
                select(Document.doc_type, func.count()).group_by(Document.doc_type)
            )
        }
        print("documents by type:", counts)


if __name__ == "__main__":
    build()

