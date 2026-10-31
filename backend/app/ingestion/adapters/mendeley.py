import hashlib
import json
from pathlib import Path
from typing import Iterator

import pandas as pd
import yaml

from backend.app.ingestion.adapters.base import Batch


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_values=[""],
        low_memory=False,
        encoding_errors="replace",
    )


def _row_hash(raw: dict) -> str:
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _canon(
    df: pd.DataFrame,
    mapping: dict,
    ts_fmt: str | None,
    ts_cols: list[str],
) -> list[dict]:
    out = pd.DataFrame(index=df.index)
    for canon, real in mapping.items():
        out[canon] = df[real] if real and real in df.columns else None
    for c in ts_cols:
        if c in out.columns:
            out[c] = pd.to_datetime(out[c], format=ts_fmt, errors="coerce", utc=True)
    out["raw"] = df.apply(
        lambda r: {k: (None if pd.isna(v) else v) for k, v in r.items()}, axis=1
    )
    out["row_hash"] = out["raw"].map(_row_hash)
    return out.to_dict("records")


class MendeleyAdapter:
    name = "mendeley_helpdesk_v3"

    def __init__(self, column_map_path: str = "configs/column_map.yaml"):
        with open(column_map_path, encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)

    def extract(self, root: Path) -> Iterator[Batch]:
        c, fmt = self.cfg, self.cfg.get("timestamp_format")

        # Tickets must be yielded first so downstream FK checks see them.
        df = _read(root / c["files"]["tickets"])
        tickets = _canon(df, c["tickets"], fmt, ["created_at", "resolved_at"])
        yield Batch("tickets", c["files"]["tickets"], tickets)

        events = _canon(
            _read(root / c["files"]["events"]),
            c["events"],
            fmt,
            ["changed_at"],
        )
        yield Batch("events", c["files"]["events"], events)

        udf = _read(root / c["files"]["utterances"])
        utterances = _canon(udf, c["utterances"], fmt, ["sent_at"])
        for rec in utterances:
            tid = rec.get("ticket_id") or ""
            seq = rec.get("seq")
            if seq is None or pd.isna(seq):
                seq = int(rec.get("row_hash", "0")[:8], 16)  # stable placeholder; real seq from order below
            rec["seq"] = seq
        # Enumerate turns per ticket when the source provides no ordering column.
        if not (c["utterances"].get("seq") and c["utterances"]["seq"] in udf.columns):
            from collections import defaultdict

            counts: dict[str, int] = defaultdict(int)
            for rec in sorted(utterances, key=lambda r: (r.get("ticket_id") or "", r.get("sent_at") or pd.NaT)):
                counts[rec.get("ticket_id") or ""] += 1
                rec["seq"] = counts[rec.get("ticket_id") or ""]
        for rec in utterances:
            tid = rec.get("ticket_id") or ""
            rec["utterance_id"] = rec.get("utterance_id") or f"{tid}:{rec['seq']}"
        yield Batch("utterances", c["files"]["utterances"], utterances)

        # Holidays: only loadable once the country/day/name mapping is filled.
        holiday_map = c.get("holidays", {})
        if holiday_map.get("country") and holiday_map.get("day"):
            hdf = _read(root / c["files"]["holidays"])
            holidays = _canon(hdf, holiday_map, fmt, ["day"])
            yield Batch("holidays", c["files"]["holidays"], holidays)

        sdf = _read(root / c["files"]["snapshots"])
        snap_records = []
        for _, row in sdf.iterrows():
            raw = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            rec = {"raw": raw, "row_hash": _row_hash(raw)}
            for canon in ("ticket_id", "snapshot_at"):
                real = c.get("snapshots", {}).get(canon)
                rec[canon] = raw.get(real) if real and real in raw else None
            if rec.get("snapshot_at"):
                rec["snapshot_at"] = pd.to_datetime(rec["snapshot_at"], format=fmt, errors="coerce", utc=True)
            snap_records.append(rec)
        yield Batch("snapshots", c["files"]["snapshots"], snap_records)

