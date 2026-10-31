import { useEffect, useMemo, useState } from "react";
import Sidebar, { View } from "./components/Sidebar";
import Home from "./components/Home";
import Composer from "./components/Composer";
import MessageView from "./components/MessageView";
import EvidenceDrawer from "./components/EvidenceDrawer";
import Explorer from "./pages/Explorer";
import Inspector from "./pages/Inspector";
import { sendChat } from "./api";
import { ChatOptions, ChatResponse, Conversation, UiMessage } from "./types";

const USER_NAME = "there";

export default function App() {
  const [convs, setConvs] = useState<Conversation[]>(() => JSON.parse(localStorage.getItem("sl_convs") ?? "[]"));
  const [activeId, setActiveId] = useState<string | null>(null);
  const [view, setView] = useState<View>("chat");
  const [busy, setBusy] = useState(false);
  const [drawer, setDrawer] = useState<{ response: ChatResponse; focus: string } | null>(null);

  useEffect(() => localStorage.setItem("sl_convs", JSON.stringify(convs.slice(0, 50))), [convs]);
  const active = useMemo(() => convs.find((c) => c.id === activeId) ?? null, [convs, activeId]);

  const patch = (cid: string, fn: (c: Conversation) => Conversation) => setConvs((p) => p.map((c) => (c.id === cid ? fn(c) : c)));

  async function send(text: string, options: ChatOptions) {
    let cid = activeId;
    const userMsg: UiMessage = { id: crypto.randomUUID(), role: "user", text };
    const pending: UiMessage = { id: crypto.randomUUID(), role: "assistant", text: "", pending: true };
    if (!cid) {
      cid = crypto.randomUUID();
      setConvs((p) => [{ id: cid!, title: text.slice(0, 40), messages: [userMsg, pending] }, ...p]);
      setActiveId(cid);
    } else patch(cid, (c) => ({ ...c, messages: [...c.messages, userMsg, pending] }));
    setBusy(true); setView("chat");
    try {
      const res = await sendChat({ conversation_id: cid, message: text, options });
      patch(cid!, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === pending.id ? { ...m, pending: false, text: res.answer_markdown, response: res } : m)) }));
    } catch (e: any) {
      patch(cid!, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === pending.id ? { ...m, pending: false, error: String(e.message ?? e) } : m)) }));
    } finally { setBusy(false); }
  }

  return (
    <div className="h-full flex">
      <Sidebar conversations={convs} activeId={activeId} view={view}
        onNew={() => { setActiveId(null); setView("chat"); setDrawer(null); }}
        onSelect={(id) => { setActiveId(id); setView("chat"); }} onView={setView} />
      <main className="flex-1 min-w-0 flex">
        <div className="flex-1 min-w-0 flex flex-col">
          {view === "chat" && !active && <Home name={USER_NAME} onSend={send} />}
          {view === "chat" && active && (
            <>
              <div className="flex-1 overflow-y-auto"><div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
                {active.messages.map((m) => (
                  <MessageView key={m.id} msg={m} onFollowUp={(t) => send(t, { mode: "hybrid", effort: "fast", top_k: 8 })}
                    onCite={(ref, msg) => msg.response && setDrawer({ response: msg.response, focus: ref })} />))}
              </div></div>
              <div className="max-w-3xl w-full mx-auto px-6 pb-5"><Composer onSend={send} disabled={busy} /></div>
            </>
          )}
          {view === "explorer" && <Explorer />}
          {view === "inspector" && <Inspector />}
        </div>
        {drawer && <EvidenceDrawer response={drawer.response} focus={drawer.focus} onClose={() => setDrawer(null)} />}
      </main>
    </div>
  );
}

