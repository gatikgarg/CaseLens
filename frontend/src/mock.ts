import { ChatRequest, ChatResponse } from "./types";

export async function mockChat(req: ChatRequest): Promise<ChatResponse> {
  await new Promise((r) => setTimeout(r, 1200));
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const values = [120, 98, 143, 130, 160, 151];
  return {
    conversation_id: req.conversation_id ?? crypto.randomUUID(),
    message_id: crypto.randomUUID(),
    answer_markdown: `**Mock answer.** Volume rose from ${values[0]} to ${values[5]} tickets [D1]. A similar complaint appears in ticket T-1001 [E1].`,
    findings: [{ statement: "Volume rose", status: "verified", citations: ["D1"] }],
    charts: [{
      chart_id: "D1", title: "Monthly ticket volume", chart_type: "bar",
      figure: { data: [{ type: "bar", x: months, y: values, marker: { color: "#3b82f6" } }], layout: { title: "Monthly ticket volume", margin: { t: 40, r: 10, b: 40, l: 40 } } },
      table: { columns: ["month", "ticket_count"], rows: months.map((m, i) => [m, values[i]]) },
      provenance: { tool: "analytics_query", params: { metric: "ticket_count", dimension: "created_month" }, sql: "SELECT date_trunc('month', created_at) ...", row_count: 6, caveats: [] },
    }],
    tables: [],
    evidence: [{ ref_id: "E1", ticket_id: "T-1001", doc_type: "utterance", text: "Customer could not log in after update; login form shows a blank screen.", scores: { dense: 0.71, bm25: 12.4, rrf: 0.031, rerank: 0.88 }, rank: 1, has_conversation: true, cited: true }],
    follow_ups: ["Break this down by priority", "Which category grew the most?"],
    trace: { route: "analytics", steps: [{ name: "plan", ms: 410 }, { name: "analytics_query", ms: 35 }, { name: "compose", ms: 900 }], tokens_in: 1800, tokens_out: 260, cost_usd: 0, total_ms: 1350 },
  };
}

