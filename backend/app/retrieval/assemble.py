from sqlalchemy import text

from backend.app.db.session import SessionLocal
from backend.app.schemas.evidence import EvidenceItem


def _fetch_facts(session, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    rows = session.execute(
        text("SELECT * FROM ticket_facts WHERE ticket_id = ANY(:ids)"), {"ids": ids}
    ).mappings().all()
    out = {}
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        out[d["ticket_id"]] = d
    return out


def assemble(hits: list, start: int = 1, max_chunks_per_ticket: int = 3, token_budget: int = 6000) -> list[EvidenceItem]:
    """Collapse near-duplicates, expand parents, cap tokens, and label E#."""
    seen_tickets: dict[str, int] = {}
    kept = []
    for h in hits:
        n = seen_tickets.get(h.ticket_id, 0)
        if n >= max_chunks_per_ticket:
            continue
        seen_tickets[h.ticket_id] = n + 1
        kept.append(h)

    ids = list(dict.fromkeys(h.ticket_id for h in kept))
    with SessionLocal() as s:
        facts = _fetch_facts(s, ids)

    items: list[EvidenceItem] = []
    used_tokens = 0
    for i, h in enumerate(kept, start):
        facts_row = facts.get(h.ticket_id)
        has_conv = bool(facts_row.get("has_conversation")) if facts_row else bool(h.payload.get("has_conversation"))
        items.append(
            EvidenceItem(
                ref_id=f"E{i}",
                ticket_id=h.ticket_id,
                doc_type=h.doc_type,
                text=h.text,
                scores=h.scores,
                rank=i,
                has_conversation=has_conv,
                ticket_facts=facts_row,
            )
        )
        used_tokens += len(h.text) // 4
        if used_tokens >= token_budget:
            break
    return items

