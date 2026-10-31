import { ChatRequest, ChatResponse, RetrievalDebugResponse, TicketDetail, TicketRow } from "./types";
import { mockChat } from "./mock";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  if (USE_MOCK) return mockChat(req);
  return post<ChatResponse>("/api/chat", req);
}

export async function fetchTickets(params: URLSearchParams): Promise<{ items: TicketRow[]; total: number; page: number; page_size: number }> {
  if (USE_MOCK) return { items: [], total: 0, page: 1, page_size: 25 };
  const res = await fetch(`/api/tickets?${params.toString()}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export async function fetchTicket(id: string): Promise<TicketDetail> {
  const res = await fetch(`/api/tickets/${id}`);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export async function debugRetrieval(body: { query: string; mode: string; top_k: number; do_rewrite: boolean; do_rerank: boolean }): Promise<RetrievalDebugResponse> {
  return post<RetrievalDebugResponse>("/api/retrieval/debug", body);
}

