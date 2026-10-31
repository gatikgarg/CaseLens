from pathlib import Path

from sqlalchemy import text

from backend.app.db.session import SessionLocal


def run() -> str:
    with SessionLocal() as s:
        counts = {
            t: s.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()
            for t in ("tickets", "ticket_events", "utterances", "documents")
        }
        rejects = s.execute(
            text("SELECT reason, COUNT(*) FROM ingestion_rejects GROUP BY reason ORDER BY 2 DESC")
        ).all()
        coverage = s.execute(text("SELECT * FROM dataset_coverage")).mappings().one()
        bad_res = s.execute(
            text("SELECT COUNT(*) FROM ticket_facts WHERE resolution_hours < 0 OR resolution_hours > 24*365*10")
        ).scalar_one()
    lines = [
        "# Quality report",
        "",
        "| table | rows |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v:,} |" for k, v in counts.items()]
    lines += ["", "## Rejects by reason", ""]
    lines += ["| reason | count |", "|---|---|"]
    lines += [f"| {r} | {n:,} |" for r, n in rejects]
    total = coverage["total_tickets"]
    lines += [
        "",
        "## Coverage",
        "",
        f"- total tickets: {total:,}",
        f"- tickets with conversations: {coverage['tickets_with_conversation']:,}",
        f"- tickets with resolution time: {coverage['tickets_with_resolution_time']:,}",
        f"- date range: {coverage['first_ticket_at']} .. {coverage['last_ticket_at']}",
        f"- absurd resolution durations: {bad_res:,}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    out = Path("data/processed/quality_report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(run(), encoding="utf-8")
    print(f"wrote {out}")

