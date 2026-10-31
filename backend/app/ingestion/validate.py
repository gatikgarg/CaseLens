import pandas as pd


def validate(table: str, rec: dict, known_tickets: set[str]) -> str | None:
    """Return a reject reason or None."""
    if not rec.get("ticket_id") and table != "holidays" and table != "snapshots":
        return "missing_pk"
    if table == "tickets" and pd.isna(rec.get("created_at")):
        return "bad_timestamp"
    if table in ("events", "utterances") and rec["ticket_id"] not in known_tickets:
        return "orphan_fk"
    if table == "utterances" and not (rec.get("text") or "").strip():
        return "empty_text"
    return None

