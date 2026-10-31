import { X } from "lucide-react";
import { ChatResponse } from "../types";

export default function EvidenceDrawer({ response, focus, onClose }: { response: ChatResponse | null; focus: string | null; onClose: () => void }) {
  if (!response) return null;
  return (
    <aside className="w-[380px] shrink-0 border-l border-line bg-white overflow-y-auto">
      <div className="flex items-center justify-between px-4 py-3 border-b border-line"><b className="text-[14px]">Evidence supplied to the model</b><button onClick={onClose}><X size={16} /></button></div>
      <div className="p-3 space-y-3">
        {response.evidence.map((e) => (
          <div key={e.ref_id} className={`rounded-xl border p-3 text-[13px] ${focus === e.ref_id ? "border-blue-400 bg-blue-50/40" : "border-line"}`}>
            <div className="flex justify-between"><b>{e.ref_id} · ticket {e.ticket_id}</b><span className="text-muted">{e.cited ? "cited" : "not cited"}</span></div>
            <div className="text-muted text-[11px] mb-1">{e.doc_type} · rank {e.rank} · {Object.entries(e.scores).map(([k, v]) => `${k} ${v.toFixed(3)}`).join(" · ")}</div>
            <p className="whitespace-pre-wrap">{e.text}</p>
            {!e.has_conversation && <div className="mt-1 text-[11px] text-amber-700">No conversation exists for this ticket in the dataset.</div>}
          </div>))}
      </div>
    </aside>
  );
}

