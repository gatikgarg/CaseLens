import { Plus, Search, Ticket, ScanSearch, FlaskConical, Database, PanelLeft, ArrowUpRight } from "lucide-react";
import { Conversation } from "../types";

export type View = "chat" | "explorer" | "inspector";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  view: View;
  onNew: () => void;
  onSelect: (id: string) => void;
  onView: (v: View) => void;
}

const Item = ({ icon: Icon, label, active, onClick }: any) => (
  <button onClick={onClick} className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] ${active ? "bg-[#EDEDF0]" : "hover:bg-[#EFEFF2]"}`}>
    <Icon size={17} strokeWidth={1.8} /> {label}
  </button>
);

export default function Sidebar({ conversations, activeId, view, onNew, onSelect, onView }: Props) {
  return (
    <aside className="w-[260px] shrink-0 bg-sidebar border-r border-line flex flex-col px-2 py-3">
      <div className="flex items-center justify-between px-2 pb-4">
        <div className="w-7 h-7 rounded-lg bg-ink text-white grid place-items-center font-semibold text-sm">C</div>
        <PanelLeft size={18} className="text-muted" />
      </div>
      <Item icon={Plus} label="New chat" active={view === "chat" && !activeId} onClick={onNew} />
      <Item icon={Search} label="Search" onClick={() => {}} />
      <Item icon={Ticket} label="Ticket Explorer" active={view === "explorer"} onClick={() => onView("explorer")} />
      <Item icon={ScanSearch} label="Retrieval Inspector" active={view === "inspector"} onClick={() => onView("inspector")} />
      <Item icon={FlaskConical} label="Evaluation" onClick={() => {}} />
      <Item icon={Database} label="Data Sources" onClick={() => {}} />
      <div className="mt-6 px-3 pb-2 text-xs text-muted">Recents</div>
      <div className="flex-1 overflow-y-auto">
        {conversations.slice(0, 8).map((c) => (
          <button key={c.id} onClick={() => onSelect(c.id)}
            className={`w-full text-left px-3 py-2 rounded-xl text-[14px] truncate ${c.id === activeId ? "bg-[#EDEDF0]" : "hover:bg-[#EFEFF2]"}`}>{c.title}</button>
        ))}
        <button className="flex items-center gap-2 px-3 py-2 text-[13px] text-muted"><ArrowUpRight size={14} /> View all chats</button>
      </div>
    </aside>
  );
}

