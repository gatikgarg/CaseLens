import uuid
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from backend.app.analytics.semantic_layer import load_semantic_layer
from backend.app.core.config import get_settings

SL = load_semantic_layer()

_engine = None


def ro_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        url = s.readonly_database_url or s.database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not set")
        _engine = create_engine(
            url,
            connect_args={"options": "-c statement_timeout=15000"},
        )
    return _engine


class AnalyticsArgs(BaseModel):
    metric: str
    dimension: str | None = None
    second_dimension: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_from: date | None = None
    date_to: date | None = None
    order_by: str | None = None
    descending: bool = True
    limit: int = 50


@dataclass
class AnalyticsResult:
    result_id: str
    df: pd.DataFrame
    sql: str
    params: dict
    caveats: list[str] = field(default_factory=list)


class AnalyticsError(ValueError):
    pass


def run_analytics(a: AnalyticsArgs, ref_id: str) -> AnalyticsResult:
    m, D = SL["metrics"], SL["dimensions"]
    if a.metric not in m:
        raise AnalyticsError(f"unknown metric '{a.metric}'. valid: {sorted(m)}")
    dims = [d for d in (a.dimension, a.second_dimension) if d]
    for d in dims + list(a.filters):
        if d not in D:
            raise AnalyticsError(f"unknown dimension '{d}'. valid: {sorted(D)}")

    sel = [f"{D[d]['expr']} AS {d}" for d in dims] + [f"{m[a.metric]['expr']} AS {a.metric}"]
    where: list[str] = []
    params: dict = {}
    for i, (d, vals) in enumerate(a.filters.items()):
        vals = vals if isinstance(vals, list) else [vals]
        where.append(f"{D[d]['expr']} = ANY(:f{i})")
        params[f"f{i}"] = vals
    if a.date_from:
        where.append("created_at >= :df")
        params["df"] = a.date_from
    if a.date_to:
        where.append("created_at <  :dt")
        params["dt"] = a.date_to

    nn = m[a.metric].get("needs_non_null")
    if nn:
        where.append(f"{nn} IS NOT NULL")

    order = a.order_by or (dims[0] if dims and D[dims[0]]["kind"] == "time" else a.metric)
    if order not in m and order not in D:
        raise AnalyticsError(f"bad order_by '{order}'")
    direction = (
        "ASC"
        if (order in D and D[order]["kind"] == "time")
        else ("DESC" if a.descending else "ASC")
    )
    limit = min(a.limit, SL["max_rows"])
    sql = (
        f"SELECT {', '.join(sel)} FROM {SL['source']}"
        + (f" WHERE {' AND '.join(where)}" if where else "")
        + (f" GROUP BY {', '.join(str(i + 1) for i in range(len(dims)))}" if dims else "")
        + f" ORDER BY {order} {direction} LIMIT {limit}"
    )

    with ro_engine().connect() as c:
        df = pd.read_sql(text(sql), c, params=params)
        caveats: list[str] = []
        if nn:
            tot, ok = c.execute(
                text(f"SELECT COUNT(*), COUNT({nn}) FROM {SL['source']}")
            ).one()
            caveats.append(
                f"{m[a.metric]['unit']} computed only for {ok:,} of {tot:,} tickets that have a valid {nn}."
            )
        if len(df) == limit:
            caveats.append(f"Result truncated at {limit} rows.")
    return AnalyticsResult(ref_id, df, sql, {**a.model_dump(mode="json")}, caveats)

