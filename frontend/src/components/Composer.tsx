import { useRef, useState } from "react";
import { Plus, ArrowUp, ChevronDown, Layers, Gauge, Hash } from "lucide-react";
import { ChatOptions, Effort, RetrievalMode } from "../types";

interface Props { onSend: (text: string, opts: ChatOptions) => void; disabled?: boolean; initialText?: string; }

const Sel = ({ icon: Icon, value, onChange, options }: any) => (
  <label className="flex items-center gap-1.5 text-[13px] text-ink cursor-pointer">
    <Icon size={15} className="text-muted" />
    <select value={value} onChange={(e) => onChange(e.target.value)} className="bg-transparent outline-none appearance-none cursor-pointer pr-1">
      {options.map((o: any) => <option key={o.v} value={o.v}>{o.l}</option>)}
    </select>
    <ChevronDown size={13} className="text-muted -ml-1" />
  </label>
);

export default function Composer({ onSend, disabled, initialText = "" }: Props) {
  const [text, setText] = useState(initialText);
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [effort, setEffort] = useState<Effort>("fast");
  const [topK, setTopK] = useState(8);
  const ref = useRef<HTMLTextAreaElement>(null);
  const submit = () => { if (!text.trim() || disabled) return; onSend(text.trim(), { mode, effort, top_k: topK }); setText(""); };

  return (
    <div className="rounded-3xl border border-line bg-white shadow-composer">
      <textarea ref={ref} value={text} rows={2} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        placeholder="Ask about tickets, trends, or similar issues…"
        className="w-full resize-none px-5 pt-4 pb-1 bg-transparent outline-none text-[15px] placeholder:text-[#9A9AA3]" />
      <div className="flex items-center gap-4 px-4 pb-3">
        <button title="Filters" className="p-1 rounded-full hover:bg-sidebar"><Plus size={18} /></button>
        <Sel icon={Layers} value={mode} onChange={setMode} options={[{ v: "hybrid", l: "Hybrid" }, { v: "dense", l: "Dense" }, { v: "bm25", l: "BM25" }]} />
        <Sel icon={Hash} value={String(topK)} onChange={(v: string) => setTopK(Number(v))} options={[5, 8, 12, 20].map((n) => ({ v: String(n), l: `k = ${n}` }))} />
        <div className="flex-1" />
        <Sel icon={Gauge} value={effort} onChange={setEffort} options={[{ v: "fast", l: "Fast" }, { v: "thorough", l: "Thorough" }]} />
        <button onClick={submit} disabled={!text.trim() || disabled}
          className={`w-8 h-8 rounded-full grid place-items-center ${text.trim() && !disabled ? "bg-ink text-white" : "bg-[#E8E8EA] text-[#8a8a92]"}`}><ArrowUp size={17} /></button>
      </div>
    </div>
  );
}

