import hashlib
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text

from backend.app.db.models import (
    Holiday,
    IngestionReject,
    IngestionRun,
    Ticket,
    TicketEvent,
    TicketSnapshot,
    Utterance,
)
from backend.app.db.session import SessionLocal
from backend.app.ingestion.adapters.mendeley import MendeleyAdapter
from backend.app.ingestion.load import bulk_upsert, mark_finished
from backend.app.ingestion.validate import validate


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


MODEL = {
    "tickets": Ticket,
    "events": TicketEvent,
    "utterances": Utterance,
    "holidays": Holiday,
    "snapshots": TicketSnapshot,
}


def run(root: str = "data/raw/mendeley_helpdesk_v3") -> None:
    adapter = MendeleyAdapter()
    root = Path(root)
    with SessionLocal() as s:
        known = set(s.scalars(select(Ticket.ticket_id)))
        for batch in adapter.extract(root):
            digest = sha256_file(root / batch.source_file)
            already = s.scalar(
                select(IngestionRun).where(
                    IngestionRun.file_sha256 == digest,
                    IngestionRun.status == "success",
                )
            )
            if already:
                print(f"skip {batch.source_file} (already ingested)")
                continue

            run_ = IngestionRun(
                source_file=batch.source_file,
                file_sha256=digest,
                target_table=batch.table,
            )
            s.add(run_)
            s.flush()

            good: list[dict] = []
            seen: set[str] = set()
            dups = 0
            for rec in batch.records:
                reason = validate(batch.table, rec, known)
                if reason:
                    s.add(IngestionReject(run_id=run_.run_id, reason=reason, row_json=rec["raw"]))
                    run_.rows_rejected += 1
                    continue
                key = rec["ticket_id"] if batch.table == "tickets" else rec["row_hash"]
                if key in seen:
                    dups += 1
                    continue
                seen.add(key)
                rec["run_id"] = run_.run_id
                good.append(rec)

            loaded = bulk_upsert(s, MODEL[batch.table], good)
            if batch.table == "tickets":
                known |= {r["ticket_id"] for r in good}

            run_.rows_read = len(batch.records)
            run_.rows_loaded = loaded
            run_.duplicates_removed = dups
            run_.status = "success"
            mark_finished(s, run_)
            s.commit()
            print(
                f"{batch.table}: loaded {loaded}, rejected {run_.rows_rejected}, "
                f"duplicates {dups} (rows read {len(batch.records)})"
            )

        s.execute(text("REFRESH MATERIALIZED VIEW ticket_facts"))
        s.commit()
        print("refreshed ticket_facts")


if __name__ == "__main__":
    run(*sys.argv[1:])

