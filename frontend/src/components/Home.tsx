import { useState } from "react";
import { X, Info } from "lucide-react";
import Composer from "./Composer";
import { ChatOptions } from "../types";

const CHIPS = [
  ["Monthly volume", "Show me the monthly ticket volume as a line chart."],
  ["Priority split", "Generate a bar chart of ticket distribution by priority."],
  ["Resolution times", "Compare average resolution times across issue categories."],
  ["Similar tickets", "Find historical tickets similar to: user cannot log in after an update."],
  ["Category trends", "Show the trend of the most frequently reported categories over time."],
  ["Investigate", "Why did ticket volume spike recently? Investigate with data and examples."],
];

export default function Home({ name, onSend }: { name: string; onSend: (t: string, o: ChatOptions) => void }) {
  const [banner, setBanner] = useState(true);
  const [seed, setSeed] = useState("");
  return (
    <div className="h-full flex flex-col items-center justify-center px-6">
      <div className="w-full max-w-[680px]">
        <h1 className="text-[26px] leading-9 font-medium text-center">Hey {name},</h1>
        <p className="text-[26px] leading-9 font-medium text-center text-muted mb-8">What do you want to investigate today?</p>
        <Composer key={seed} onSend={onSend} initialText={seed} />
        {banner && (
          <div className="mt-2 flex items-center gap-3 rounded-2xl bg-sidebar px-4 py-2.5 text-[13px] text-muted">
            <Info size={15} /><span className="flex-1">Every answer cites ticket evidence or database results.</span>
            <button className="px-3 py-1 rounded-lg border border-line bg-white text-ink">How it works</button>
            <button onClick={() => setBanner(false)}><X size={15} /></button>
          </div>
        )}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {CHIPS.map(([label, prompt]) => (
            <button key={label} onClick={() => setSeed(prompt)} className="px-4 py-1.5 rounded-full border border-line text-[13px] hover:bg-sidebar">{label}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

