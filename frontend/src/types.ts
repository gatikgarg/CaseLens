export type RetrievalMode = "hybrid" | "dense" | "bm25";
export type Effort = "fast" | "thorough";

export interface ChatOptions { mode: RetrievalMode; effort: Effort; top_k: number; filters?: Record<string, unknown>; }
export interface ChatRequest { conversation_id: string | null; message: string; options: ChatOptions; }

export interface EvidenceItem {
  ref_id: string;
  ticket_id: string;
  doc_type: "ticket_summary" | "utterance" | "history_event";
  text: string;
  scores: Record<string, number>;
  rank: number;
  has_conversation: boolean;
  cited: boolean;
  ticket_facts?: Record<string, unknown>;
}

export interface TablePayload { columns: string[]; rows: (string | number | null)[][]; }
export interface ChartPayload {
  chart_id: string;
  title: string;
  chart_type: string;
  figure: { data: any[]; layout: any };
  table: TablePayload;
  provenance: { tool: string; params: Record<string, unknown>; sql: string; row_count: number; caveats: string[] };
}

export interface Finding { statement: string; status: "verified" | "hypothesis" | "unavailable"; citations: string[]; }
export interface TraceStep { name: string; ms: number; detail?: string; }
export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer_markdown: string;
  findings: Finding[];
  charts: ChartPayload[];
  tables: ChartPayload[];
  evidence: EvidenceItem[];
  follow_ups: string[];
  trace: { route: string; steps: TraceStep[]; tokens_in: number; tokens_out: number; cost_usd: number; total_ms: number; verification?: { ok: boolean; issues: string[] } };
}

export interface UiMessage { id: string; role: "user" | "assistant"; text: string; response?: ChatResponse; pending?: boolean; error?: string; }
export interface Conversation { id: string; title: string; messages: UiMessage[]; }

export interface TicketRow {
  ticket_id: string; title?: string; category?: string | null; priority?: string | null;
  project_id?: string | null; status?: string | null; created_at?: string | null;
  resolution_hours?: number | null; has_conversation?: boolean; n_events?: number;
  [k: string]: unknown;
}

export interface TicketDetail {
  ticket: Record<string, unknown>;
  events: Record<string, unknown>[];
  utterances: Record<string, unknown>[];
  conversation_available: boolean;
}

export interface StageHit {
  rank: number; doc_id: string; ticket_id: string; doc_type: string;
  snippet: string; score: number; scores: Record<string, number>;
}

export interface RetrievalDebugResponse {
  query: string;
  rewrite: Record<string, unknown>;
  stages: Record<string, StageHit[]>;
  timings_ms: Record<string, number>;
}

