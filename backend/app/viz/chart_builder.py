import json
from typing import Literal

import pandas as pd
from pydantic import BaseModel


class ChartSpec(BaseModel):
    result_id: str
    chart_type: Literal["bar", "hbar", "line", "area", "pie", "donut", "scatter", "grouped_bar", "stacked_bar", "table"]
    x: str | None = None
    y: str | None = None
    color: str | None = None
    title: str
    top_n: int | None = None


PALETTE = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]
ADDITIVE = {"ticket_count", "resolved_count"}


class ChartError(ValueError):
    pass


def build_figure(df: pd.DataFrame, s: ChartSpec):
    import plotly.express as px
    import plotly.graph_objects as go

    cols = set(df.columns)
    for name in (s.x, s.y, s.color):
        if name and name not in cols:
            raise ChartError(f"column '{name}' not in result. columns: {sorted(cols)}")
    if s.chart_type != "table" and (not s.x or not s.y):
        raise ChartError("x and y are required")
    if s.y and not pd.api.types.is_numeric_dtype(df[s.y]):
        raise ChartError(f"y column '{s.y}' is not numeric")

    d = df.copy()
    if s.top_n and s.x and len(d) > s.top_n:
        d = d.nlargest(s.top_n, s.y)
        if s.y in ADDITIVE:
            other = df.drop(d.index)[s.y].sum()
            d = pd.concat([d, pd.DataFrame({s.x: ["Other"], s.y: [other]})])

    kw = dict(x=s.x, y=s.y, color=s.color, title=s.title, color_discrete_sequence=PALETTE)
    t = s.chart_type
    if t == "bar":
        fig = px.bar(d, **kw)
    elif t == "hbar":
        fig = px.bar(d.sort_values(s.y), x=s.y, y=s.x, orientation="h", title=s.title, color_discrete_sequence=PALETTE)
    elif t == "grouped_bar":
        fig = px.bar(d, barmode="group", **kw)
    elif t == "stacked_bar":
        fig = px.bar(d, barmode="stack", **kw)
    elif t == "line":
        fig = px.line(d.sort_values(s.x), markers=True, **kw)
    elif t == "area":
        fig = px.area(d.sort_values(s.x), **kw)
    elif t == "scatter":
        fig = px.scatter(d, **kw)
    elif t in ("pie", "donut"):
        fig = px.pie(
            d,
            names=s.x,
            values=s.y,
            hole=0.45 if t == "donut" else 0,
            title=s.title,
            color_discrete_sequence=PALETTE,
        )
    else:
        fig = go.Figure(
            go.Table(
                header=dict(values=list(d.columns)),
                cells=dict(values=[d[c] for c in d.columns]),
            )
        )
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, system-ui, sans-serif", size=13),
        margin=dict(t=56, r=16, b=48, l=56),
        legend_title_text="",
    )
    return fig


def figure_json(fig) -> dict:
    return json.loads(fig.to_json())


def to_table_payload(df: pd.DataFrame, max_rows: int = 200) -> dict:
    d = df.head(max_rows).copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d")
    return {"columns": list(d.columns), "rows": d.where(d.notna(), None).values.tolist()}

