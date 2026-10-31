from pydantic import BaseModel, Field

from backend.app.analytics.query_builder import AnalyticsArgs
from backend.app.viz.chart_builder import ChartSpec


class SearchArgs(BaseModel):
    query: str = Field(description="What to look for, in natural language")
    priority: list[str] | None = None
    category: list[str] | None = None
    project: list[str] | None = None
    created_from: str | None = None
    created_to: str | None = None
    has_conversation: bool | None = None


class GetTicketArgs(BaseModel):
    ticket_id: str


class TicketHistoryArgs(BaseModel):
    ticket_id: str


def spec(name: str, desc: str, model) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": model.model_json_schema(),
        },
    }


TOOLS = {
    "analytics_query": spec(
        "analytics_query",
        "Run a structured aggregation over ticket data (counts, averages, trends). Use for ANY number, count, rate or distribution. Returns a table with result_id like D1.",
        AnalyticsArgs,
    ),
    "render_chart": spec(
        "render_chart",
        "Render a chart from a previous analytics result_id. Never invent data; only reference columns of that result.",
        ChartSpec,
    ),
    "search_tickets": spec(
        "search_tickets",
        "Semantic + keyword search over ticket summaries and available conversation messages. Use for similar issues, examples, root-cause themes.",
        SearchArgs,
    ),
    "get_ticket": spec("get_ticket", "Fetch the structured facts and any available messages of one ticket.", GetTicketArgs),
    "get_ticket_history": spec("get_ticket_history", "Fetch the assignment/status change history of one ticket.", TicketHistoryArgs),
}

ROUTE_TOOLS = {
    "analytics": ["analytics_query", "render_chart"],
    "semantic": ["search_tickets", "get_ticket", "get_ticket_history"],
    "investigate": list(TOOLS),
}

