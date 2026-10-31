import { useState } from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import { ChartPayload } from "../types";

const Plot = createPlotlyComponent(Plotly);

export default function ChartCard({ chart }: { chart: ChartPayload }) {
  const [tab, setTab] = useState<"chart" | "data" | "query">("chart");
  return (
    <div className="my-3 rounded-2xl border border-line overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-line bg-sidebar text-[13px]">
        <span className="font-medium">{chart.chart_id} · {chart.title}</span>
        <div className="flex gap-1">{(["chart", "data", "query"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-2.5 py-1 rounded-lg ${tab === t ? "bg-white border border-line" : "text-muted"}`}>{t}</button>))}</div>
      </div>
      <div className="p-3">
        {tab === "chart" && <Plot data={chart.figure.data} layout={{ ...chart.figure.layout, autosize: true }} config={{ displaylogo: false, responsive: true }} useResizeHandler style={{ width: "100%", height: 380 }} />}
        {tab === "data" && (
          <div className="overflow-x-auto max-h-80"><table className="text-[13px] w-full">
            <thead><tr>{chart.table.columns.map((c) => <th key={c} className="text-left px-2 py-1 border-b border-line">{c}</th>)}</tr></thead>
            <tbody>{chart.table.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className="px-2 py-1 border-b border-line/60">{String(v)}</td>)}</tr>)}</tbody>
          </table></div>)}
        {tab === "query" && (
          <div className="text-[12px] space-y-2">
            <div><b>Tool:</b> {chart.provenance.tool} · <b>Rows:</b> {chart.provenance.row_count}</div>
            <pre className="bg-sidebar rounded-xl p-3 overflow-x-auto">{JSON.stringify(chart.provenance.params, null, 2)}</pre>
            <pre className="bg-sidebar rounded-xl p-3 overflow-x-auto whitespace-pre-wrap">{chart.provenance.sql}</pre>
            {chart.provenance.caveats.map((c, i) => <div key={i} className="text-amber-700">⚠ {c}</div>)}
          </div>)}
      </div>
    </div>
  );
}

