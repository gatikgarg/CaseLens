import { useEffect, useState } from "react";
import { fetchTicket, fetchTickets } from "../api";
import { TicketDetail, TicketRow } from "../types";

const fmt = (v: unknown) => (v == null ? "—" : String(v));

export default function Explorer() {
  const [q, setQ] = useState("");
  const [priority, setPriority] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [rows, setRows] = useState<TicketRow[]>([]);
  const [total, setTotal] = useState(0);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (priority) p.set("priority", priority);
    if (category) p.set("category", category);
    if (status) p.set("status", status);
    p.set("page", String(page));
    fetchTickets(p).then((r) => { setRows(r.items); setTotal(r.total); setError(""); }).catch((e) => setError(String(e.message ?? e)));
  }, [q, priority, category, status, page]);

  const open = (id: string) => fetchTicket(id).then(setDetail).catch((e) => setError(String(e.message ?? e)));

  return (
    <div className="flex h-full min-w-0">
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex flex-wrap gap-2 p-4 border-b border-line">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title…" className="px-3 py-1.5 rounded-lg border border-line text-[13px] w-56" />
          <input value={priority} onChange={(e) => setPriority(e.target.value)} placeholder="Priority" className="px-3 py-1.5 rounded-lg border border-line text-[13px] w-32" />
          <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category" className="px-3 py-1.5 rounded-lg border border-line text-[13px] w-32" />
          <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="Status" className="px-3 py-1.5 rounded-lg border border-line text-[13px] w-32" />
          <span className="text-[12px] text-muted self-center">{total} tickets</span>
        </div>
        {error && <div className="px-4 py-2 text-red-600 text-[13px]">{error}</div>}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-white"><tr>
              {["ticket_id", "title", "priority", "category", "status", "created_at", "resolution_hours"].map((c) => <th key={c} className="text-left px-3 py-2 border-b border-line">{c}</th>)}
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.ticket_id} onClick={() => open(r.ticket_id)} className="cursor-pointer hover:bg-sidebar">
                  <td className="px-3 py-2 border-b border-line/60">{r.ticket_id}</td>
                  <td className="px-3 py-2 border-b border-line/60 max-w-[360px] truncate">{fmt(r.title)}</td>
                  <td className="px-3 py-2 border-b border-line/60">{fmt(r.priority)}</td>
                  <td className="px-3 py-2 border-b border-line/60">{fmt(r.category)}</td>
                  <td className="px-3 py-2 border-b border-line/60">{fmt(r.status)}</td>
                  <td className="px-3 py-2 border-b border-line/60">{fmt(r.created_at)}</td>
                  <td className="px-3 py-2 border-b border-line/60">{r.resolution_hours != null ? Number(r.resolution_hours).toFixed(1) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="p-3 flex gap-3 items-center">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} className="px-3 py-1 rounded-lg border border-line text-[13px]">Prev</button>
          <span className="text-[13px] text-muted">Page {page}</span>
          <button onClick={() => setPage((p) => p + 1)} className="px-3 py-1 rounded-lg border border-line text-[13px]">Next</button>
        </div>
      </div>
      {detail && (
        <aside className="w-[420px] shrink-0 border-l border-line overflow-y-auto p-4 text-[13px]">
          <div className="flex justify-between items-center"><b>Ticket {String(detail.ticket.ticket_id)}</b><button onClick={() => setDetail(null)}>✕</button></div>
          <div className="mt-2 space-y-1">
            {Object.entries(detail.ticket).map(([k, v]) => <div key={k}><span className="text-muted">{k}:</span> {fmt(v)}</div>)}
          </div>
          <div className="mt-4 font-medium">Timeline</div>
          <div className="space-y-2 mt-2">
            {detail.events.length === 0 && <div className="text-muted">No history events.</div>}
            {detail.events.map((e, i) => <div key={i} className="rounded-lg border border-line p-2"><span className="text-muted">{fmt(e.field)}:</span> {fmt(e.old_value)} → {fmt(e.new_value)}</div>)}
          </div>
          <div className="mt-4 font-medium">Conversation</div>
          {!detail.conversation_available && <div className="mt-2 text-amber-700">No conversation exists for this ticket in the dataset.</div>}
          <div className="space-y-2 mt-2">
            {detail.utterances.map((u, i) => <div key={i} className="rounded-lg border border-line p-2"><span className="text-muted">{fmt(u.speaker_role)}:</span> {fmt(u.text)}</div>)}
          </div>
        </aside>
      )}
    </div>
  );
}

