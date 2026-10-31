from typing import Any

from pydantic import BaseModel


class TablePayload(BaseModel):
    columns: list[str]
    rows: list[list[Any]]


class Provenance(BaseModel):
    tool: str
    params: dict[str, Any]
    sql: str
    row_count: int
    caveats: list[str] = []


class ChartPayload(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    figure: dict[str, Any]
    table: TablePayload
    provenance: Provenance

