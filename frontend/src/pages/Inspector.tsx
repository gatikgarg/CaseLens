import { useState } from "react";
import { debugRetrieval } from "../api";
import { RetrievalDebugResponse } from "../types";

const COLS: [string, string][] = [["dense", "Dense"], ["bm25", "BM25"], ["fused", "RRF fused"], ["reranked", "Reranked"]];

export default function Inspector() {
  const [query, setQuery] = useState("user cannot log in after an update");
  const [mode, setMode] = useState("hybrid");
  const [topK, setTopK] = useState(8);
  const [doRewrite, setDoRewrite] = useState(true);
  const [doRerank, setDoRerank] = useState(true);
  const [result, setResult] = useState<RetrievalDebugResponse | null>(null);
  const [error, setError] = useState("");

  const run = () => debugRetrieval({ query, mode, top_k: topK, do_rewrite: doRewrite, do_rerank: doRerank })
    .then((r) => { setResult(r); setError(""); }).catch((e) => setError(String(e.message ?? e)));

  return (
    <div className="h-full flex flex-col p-4 gap-3">
      <div className="flex flex-wrap gap-2 items-center">
        <input value={query} onChange={(e) => setQuery(e.target.value)} className="flex-1 min-w-[280px] px-3 py-2 rounded-xl border border-line text-[14px]" />
        <select value={mode} onChange={(e) => setMode(e.target.value)} className="px-2 py-2 rounded-xl border border-line text-[13px]">
          {["hybrid", "dense", "bm25"].map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={topK} onChange={(e) => setTopK(Number(e.target.value))} className="px-2 py-2 rounded-xl border border-line text-[13px]">
          {[5, 8, 12, 20].map((n) => <option key={n} value={n}>k={n}</option>)}
        </select>
        <label className="text-[13px] flex items-center gap-1"><input type="checkbox" checked={doRewrite} onChange={(e) => setDoRewrite(e.target.checked)} /> rewrite</label>
        <label className="text-[13px] flex items-center gap-1"><input type="checkbox" checked={doRerank} onChange={(e) => setDoRerank(e.target.checked)} /> rerank</label>
        <button onClick={run} className="px-4 py-2 rounded-xl bg-ink text-white text-[13px]">Run</button>
      </div>
      {error && <div className="text-red-600 text-[13px]">{error}</div>}
      {result && (
        <div className="flex-1 overflow-auto">
          <div className="text-[12px] text-muted mb-2">rewrite: {JSON.stringify(result.rewrite)} · timings {JSON.stringify(result.timings_ms)}</div>
          <div className="grid grid-cols-4 gap-3">
            {COLS.map(([key, label]) => (
              <div key={key}>
                <div className="font-medium text-[13px] mb-2">{label}</div>
                <div className="space-y-2">
                  {(result.stages[key] || []).map((h) => {
                    const rrk = result.stages.reranked?.find((x) => x.doc_id === h.doc_id)?.rank;
                    const badge = key !== "reranked" && rrk != null && rrk !== h.rank
                      ? `${rrk < h.rank ? "↑" : "↓"} ${h.rank} → ${rrk} after rerank` : null;
                    return (
                      <div key={h.doc_id} className="rounded-xl border border-line p-2 text-[12px]">
                        <div className="flex justify-between"><b>ticket {h.ticket_id}</b><span className="text-muted">{h.score.toFixed(3)}</span></div>
                        <div className="text-muted">{h.doc_type} · rank {h.rank}</div>
                        {badge && <div className="text-blue-600">{badge}</div>}
                        <p className="mt-1 line-clamp-3">{h.snippet}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

