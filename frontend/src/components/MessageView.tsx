import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { UiMessage } from "../types";
import ChartCard from "./ChartCard";

interface Props { msg: UiMessage; onCite: (ref: string, msg: UiMessage) => void; onFollowUp: (t: string) => void; }
const withCiteLinks = (s: string) => s.replace(/\[((?:E|D)\d+)\]/g, "[$1](#cite-$1)");

export default function MessageView({ msg, onCite, onFollowUp }: Props) {
  if (msg.role === "user")
    return <div className="flex justify-end"><div className="max-w-[80%] rounded-3xl bg-sidebar px-5 py-3 text-[15px]">{msg.text}</div></div>;
  if (msg.pending) return <div className="text-muted text-[14px] animate-pulse">Analyzing tickets…</div>;
  if (msg.error) return <div className="text-red-600 text-[14px]">Something went wrong: {msg.error}</div>;
  const r = msg.response!;
  return (
    <div className="text-[15px] leading-7">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        a: ({ href, children }) => href?.startsWith("#cite-")
          ? <button onClick={() => onCite(href.slice(6), msg)} className="mx-0.5 px-1.5 rounded-md bg-blue-50 text-blue-700 text-[12px] align-baseline hover:bg-blue-100">{children}</button>
          : <a href={href} target="_blank" className="text-blue-600 underline">{children}</a>,
      }}>{withCiteLinks(r.answer_markdown)}</ReactMarkdown>
      {r.charts.map((c) => <ChartCard key={c.chart_id} chart={c} />)}
      {r.tables.map((c) => <ChartCard key={c.chart_id} chart={c} />)}
      {r.trace.verification && !r.trace.verification.ok && <div className="text-[12px] text-amber-700 mt-2">⚠ Some claims could not be fully verified: {r.trace.verification.issues.join("; ")}</div>}
      <div className="mt-3 flex flex-wrap gap-2">{r.follow_ups.map((f) => <button key={f} onClick={() => onFollowUp(f)} className="px-3 py-1 rounded-full border border-line text-[13px] hover:bg-sidebar">{f}</button>)}</div>
      <div className="mt-2 text-[11px] text-muted">{r.trace.route} · {r.trace.total_ms} ms · {r.trace.tokens_in + r.trace.tokens_out} tokens</div>
    </div>
  );
}

