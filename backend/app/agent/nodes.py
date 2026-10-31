import json
import time

from sqlalchemy import text

from backend.app.agent.grounding import CITE, verify
from backend.app.agent.tools import ROUTE_TOOLS
from backend.app.analytics.query_builder import AnalyticsArgs, run_analytics
from backend.app.db.session import SessionLocal
from backend.app.llm.deepseek import get_llm
from backend.app.llm.prompts import AGENT_SYS, COMPOSE_SYS, PLAN_SYS
from backend.app.retrieval import assemble as assemble_evidence
from backend.app.retrieval import pipeline as retrieval
from backend.app.schemas.evidence import EvidenceItem
from backend.app.viz.chart_builder import ChartSpec, build_figure, figure_json, to_table_payload

TICKET_ID_RE = r"\b[A-Za-z]{1,8}-\d{1,12}\b"


def _coverage_text() -> str:
    try:
        with SessionLocal() as s:
            row = s.execute(text("SELECT * FROM dataset_coverage")).mappings().one()
        total = row["total_tickets"]
        with_conv = row["tickets_with_conversation"]
        with_res = row["tickets_with_resolution_time"]
        pct = round(with_conv / total * 100, 1) if total else 0.0
        return (
            f"{total:,} tickets; {with_conv:,} ({pct}%) have conversations; "
            f"{with_res:,} have resolution times."
        )
    except Exception:
        return "coverage statistics unavailable (database not reachable)"


def _now() -> int:
    return int(time.perf_counter() * 1000)


def plan_node(state: dict) -> dict:
    t0 = _now()
    msgs = [
        {"role": "system", "content": PLAN_SYS},
        {
            "role": "user",
            "content": json.dumps(
                {"history": state.get("history", [])[-6:], "question": state["question"]}
            ),
        },
    ]
    out = get_llm().chat(msgs, json_mode=True, max_tokens=300)
    try:
        plan = json.loads(out.content or "{}")
    except Exception:
        plan = {}
    state["route"] = plan.get("route", "investigate")
    state["standalone_question"] = plan.get("standalone_question") or state["question"]
    state["tokens_in"] += out.tokens_in
    state["tokens_out"] += out.tokens_out
    state["trace"].append({"name": "plan", "ms": _now() - t0, "detail": state["route"]})
    state["transcript"] = [
        {"role": "system", "content": AGENT_SYS.format(coverage=_coverage_text())},
        {"role": "user", "content": state["standalone_question"]},
    ]
    return {"route": state["route"], "standalone_question": state["standalone_question"], "transcript": state["transcript"], "trace": state["trace"], "tokens_in": state["tokens_in"], "tokens_out": state["tokens_out"]}


def agent_node(state: dict) -> dict:
    t0 = _now()
    tools = ROUTE_TOOLS.get(state["route"], list(ROUTE_TOOLS["investigate"]))
    model = get_llm()
    out = model.chat(state["transcript"], tools=tools, temperature=0.0)
    msg = {"role": "assistant", "content": out.content}
    if out.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for tc in out.tool_calls
        ]
    state["transcript"].append(msg)
    state["iterations"] = state.get("iterations", 0) + 1
    state["tokens_in"] += out.tokens_in
    state["tokens_out"] += out.tokens_out
    state["trace"].append(
        {"name": "agent", "ms": _now() - t0, "detail": ",".join(tc.name for tc in out.tool_calls)}
    )
    return {"transcript": state["transcript"], "iterations": state["iterations"], "trace": state["trace"], "tokens_in": state["tokens_in"], "tokens_out": state["tokens_out"]}


def _register_evidence(state: dict, ticket_id: str, doc_type: str, text: str, has_conversation: bool, facts: dict | None = None) -> str:
    ref = f"E{len(state['evidence']) + 1}"
    state["evidence"].append(
        EvidenceItem(
            ref_id=ref,
            ticket_id=ticket_id,
            doc_type=doc_type,
            text=text,
            scores={},
            rank=len(state["evidence"]) + 1,
            has_conversation=has_conversation,
            ticket_facts=facts,
        ).model_dump()
    )
    return ref


def _exec_one(call: dict, state: dict) -> str:
    name = call["function"]["name"]
    try:
        arguments = json.loads(call["function"].get("arguments") or "{}")
    except Exception:
        arguments = {}

    try:
        if name == "analytics_query":
            ref = f"D{len(state['results']) + 1}"
            res = run_analytics(AnalyticsArgs(**arguments), ref)
            state["results"][ref] = res
            return f"{ref}: {len(res.df)} rows. caveats={res.caveats}\n" + res.df.head(50).to_markdown(index=False)

        if name == "render_chart":
            s = ChartSpec(**arguments)
            res = state["results"][s.result_id]
            fig = build_figure(res.df, s)
            state["charts"].append(
                {
                    "chart_id": s.result_id,
                    "title": s.title,
                    "chart_type": s.chart_type,
                    "figure": figure_json(fig),
                    "table": to_table_payload(res.df),
                    "provenance": {
                        "tool": "analytics_query",
                        "params": res.params,
                        "sql": res.sql,
                        "row_count": len(res.df),
                        "caveats": res.caveats,
                    },
                }
            )
            return f"chart for {s.result_id} rendered"

        if name == "search_tickets":
            from backend.app.retrieval.filters import Filters

            filters = Filters(
                priority=arguments.get("priority"),
                category=arguments.get("category"),
                project=arguments.get("project"),
                created_from=None,
                created_to=None,
                has_conversation=arguments.get("has_conversation"),
            )
            out = retrieval.search(
                arguments.get("query") or state["standalone_question"],
                _Opts(state["options"]),
                filters=filters,
                do_rewrite=False,
                do_rerank=True,
            )
            items = assemble_evidence(out["hits"], start=len(state["evidence"]) + 1)
            state["evidence"] += [i.model_dump() for i in items]
            return "\n\n".join(
                f"[{i.ref_id}] ticket {i.ticket_id} ({i.doc_type}; conversation={'yes' if i.has_conversation else 'no'})\n{i.text[:700]}"
                for i in items
            )

        if name in ("get_ticket", "get_ticket_history"):
            tid = arguments.get("ticket_id")
            with SessionLocal() as s:
                if name == "get_ticket":
                    facts = s.execute(text("SELECT * FROM ticket_facts WHERE ticket_id = :id"), {"id": tid}).mappings().first()
                    utts = s.execute(text("SELECT * FROM utterances WHERE ticket_id = :id ORDER BY seq"), {"id": tid}).mappings().all()
                    lines = [f"Ticket {tid} facts: {json.dumps({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in (facts or {}).items()}, default=str)}"]
                    if utts:
                        lines += [f"{u['speaker_role'] or 'speaker'}: {u['text']}" for u in utts]
                    else:
                        lines.append("No conversation exists for this ticket in the dataset.")
                    ref = _register_evidence(state, tid, "ticket_summary", "\n".join(lines), bool(utts), facts and dict(facts) or None)
                    return f"[{ref}]\n" + "\n".join(lines)[:2000]
                else:
                    evts = s.execute(text("SELECT * FROM ticket_events WHERE ticket_id = :id ORDER BY changed_at"), {"id": tid}).mappings().all()
                    lines = [f"{e['changed_at']} {e['field']}: {e['old_value']} -> {e['new_value']}" for e in evts]
                    body = "\n".join(lines) or "No history events for this ticket."
                    ref = _register_evidence(state, tid, "history_event", body, False)
                    return f"[{ref}]\n" + body[:2000]
    except Exception as e:
        return f"TOOL_ERROR: {type(e).__name__}: {e}"
    return f"TOOL_ERROR: unknown tool {name}"


class _Opts:
    def __init__(self, options: dict):
        self.mode = options.get("mode", "hybrid")
        self.top_k = options.get("top_k", 8)
        self.effort = options.get("effort", "fast")


def exec_tools_node(state: dict) -> dict:
    t0 = _now()
    assistant = state["transcript"][-1]
    for call in assistant.get("tool_calls", []):
        result = _exec_one(call, state)
        state["transcript"].append(
            {"role": "tool", "tool_call_id": call["id"], "content": result}
        )
        state["trace"].append({"name": call["function"]["name"], "ms": _now() - t0})
    return {"transcript": state["transcript"], "results": state["results"], "charts": state["charts"], "evidence": state["evidence"], "trace": state["trace"]}


def _digest(state: dict) -> str:
    parts = []
    if state["results"]:
        parts.append("ANALYTICS RESULTS:")
        for ref, res in state["results"].items():
            parts.append(f"{ref} sql={res.sql} caveats={res.caveats}\n{res.df.head(50).to_markdown(index=False)}")
    if state["evidence"]:
        parts.append("EVIDENCE:")
        for e in state["evidence"]:
            parts.append(f"[{e['ref_id']}] ticket {e['ticket_id']} ({e['doc_type']}): {e['text'][:700]}")
    return "\n\n".join(parts) or "(no tool results)"


def compose_node(state: dict) -> dict:
    t0 = _now()
    prompt = (
        f"User question: {state['question']}\n\n"
        f"Tool results:\n{_digest(state)}\n\n"
        "Write the JSON answer now."
    )
    if state.get("verification") and not state["verification"].get("ok"):
        prompt += "\n\nPrevious verification FAILED with issues: " + json.dumps(state["verification"].get("issues", []))
        prompt += "\nFix these problems; remove claims you cannot support."
        state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    out = get_llm().chat(
        [{"role": "system", "content": COMPOSE_SYS}, {"role": "user", "content": prompt}],
        json_mode=True,
        max_tokens=1500,
    )
    state["tokens_in"] += out.tokens_in
    state["tokens_out"] += out.tokens_out
    try:
        answer = json.loads(out.content or "{}")
    except Exception:
        answer = {"answer_markdown": out.content or "No answer produced.", "findings": [], "follow_ups": []}
    answer.setdefault("answer_markdown", "No answer produced.")
    answer.setdefault("findings", [])
    answer.setdefault("follow_ups", [])
    state["answer"] = answer
    state["trace"].append({"name": "compose", "ms": _now() - t0})
    return {"answer": state["answer"], "repair_attempts": state.get("repair_attempts", 0), "trace": state["trace"], "tokens_in": state["tokens_in"], "tokens_out": state["tokens_out"]}


def verify_node(state: dict) -> dict:
    t0 = _now()
    state["verification"] = verify(
        state["answer"],
        state["results"],
        state["evidence"],
        TICKET_ID_RE,
    )
    cited = set(CITE.findall(state["answer"].get("answer_markdown", ""))) | {
        c for f in state["answer"].get("findings", []) for c in f.get("citations", [])
    }
    for e in state["evidence"]:
        e["cited"] = e["ref_id"] in cited
    state["trace"].append({"name": "verify", "ms": _now() - t0})
    return {"verification": state["verification"], "evidence": state["evidence"], "trace": state["trace"]}


def refuse_node(state: dict) -> dict:
    state["answer"] = {
        "answer_markdown": "I can only analyze the loaded help-desk ticket data (counts, trends, comparisons, similar tickets, and ticket history). I'm not able to answer questions outside that scope.",
        "findings": [{"statement": "Out of scope", "status": "unavailable", "citations": []}],
        "follow_ups": ["Show me the monthly ticket volume", "Find similar tickets about login problems"],
    }
    return {"answer": state["answer"]}

