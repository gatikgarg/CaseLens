from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert


def bulk_upsert(session, model, records: list[dict]) -> int:
    if not records:
        return 0
    cols = {c.name for c in model.__table__.columns}
    loaded = 0
    for i in range(0, len(records), 5000):
        rows = [{k: v for k, v in r.items() if k in cols} for r in records[i : i + 5000]]
        if not rows:
            continue
        stmt = insert(model).values(rows)
        pk = list(model.__table__.primary_key.columns.keys())[0]
        if model.__tablename__ == "ticket_events":
            stmt = stmt.on_conflict_do_nothing(index_elements=["row_hash"])
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=[pk],
                set_={c: stmt.excluded[c] for c in cols - {pk}},
            )
        session.execute(stmt)
        loaded += len(rows)
    return loaded


def mark_finished(session, run) -> None:
    run.finished_at = text("now()")

