# SupportLens — Build Instructions

**An Enterprise Customer Support Intelligence Platform (local, production-grade RAG + SQL analytics + dynamic charts)**

> Follow this document top to bottom. Every phase ends with a **Checkpoint** you must pass before moving on. All tools are free and open source. The only paid-per-use component is your own DeepSeek API key, which you already have.

---

## 0. How to use this document

- Phases are ordered so you have a **working, demoable app after every phase**. You start with the UI (as requested), backed by a mock, and replace mocks with real components one by one.
- Code blocks are the real implementation skeletons. Where a detail depends on the **actual column names of the Mendeley dataset**, this document does **not guess**. Phase 4 has you profile the data and fill a mapping file. This matters: inventing column names is exactly the kind of fabrication this project is designed to prevent.
- Rough effort for one person part-time: **5–7 weeks**. Do not skip Phase 11 (evaluation); it is what separates this project from a tutorial.
- Windows users: use **WSL2 (Ubuntu)** + Docker Desktop for the least friction. Native PowerShell works too; activation commands for both are shown where they differ.

### Milestone map

| Phase | You build | Demoable result |
|---|---|---|
| 0 | Repo, Docker infra, config | Postgres + Qdrant running |
| 1 | **Frontend UI (mock data)** | The clean chat UI with a fake chart, in your browser |
| 2 | FastAPI skeleton | UI talks to a real (still fake) backend |
| 3 | Data download + profiling | Profile report of the real dataset |
| 4 | Schema + ingestion | Clean data in PostgreSQL + quality report |
| 5 | Document processing | Searchable documents with parent–child links |
| 6 | Embeddings + Qdrant | Dense + BM25 index |
| 7 | LLM provider layer (DeepSeek) | Provider-independent LLM client |
| 8 | Hybrid retrieval | RRF + rewrite + rerank + context assembly |
| 9 | SQL analytics + Python charts | Verified numbers → Plotly figures |
| 10 | LangGraph agent | End-to-end grounded answers with citations |
| 11 | Wire UI, explorer, inspector, streaming | The complete product |
| 12 | Evaluation | Benchmark tables with real numbers |
| 13 | Hardening, packaging, portfolio | One-command local run, README, interview prep |

---

## 1. Architecture

### 1.1 Request flow

```
┌────────────────────────────── Browser (http://localhost:8000) ──────────────────────────────┐
│  React UI: chat • charts (Plotly.js renders Python-built figure JSON) • evidence • inspector │
└───────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                            │ POST /api/chat (JSON or SSE)
┌───────────────────────────────────────────▼──────────────────────────────────────────────────┐
│ FastAPI backend                                                                              │
│                                                                                              │
│  LangGraph agent                                                                             │
│  ┌──────┐   ┌───────┐   ┌────────────┐   ┌─────────┐   ┌────────┐                             │
│  │ plan │──▶│ agent │◀─▶│ exec_tools │   │ compose │──▶│ verify │──▶ response                 │
│  └──┬───┘   └───┬───┘   └─────┬──────┘   └─────────┘   └───┬────┘   (repair loop ×1)          │
│     │ out_of_scope            │ tools                      │                                 │
│     ▼                         ▼                            │                                 │
│  refuse        ┌──────────────┼───────────────┬────────────┘                                 │
│                ▼              ▼               ▼                                              │
│        analytics_query   search_tickets   render_chart / get_ticket / get_history            │
│        (semantic layer)  (hybrid RAG)     (Plotly built from stored DataFrames)              │
│                │              │                                                              │
└────────────────┼──────────────┼──────────────────────────────────────────────────────────────┘
                 ▼              ▼
          PostgreSQL        Qdrant (dense + BM25 sparse vectors, payload filters)
   (tickets, events, utterances,   ▲
    documents, ticket_facts view)  │ embeddings: BGE-M3 (local)  •  reranker: bge-reranker-v2-m3 (local)
```

### 1.2 Technology stack (all free / open source)

| Concern | Choice | Why |
|---|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2 | Typed contracts, async, auto OpenAPI docs |
| Structured store | PostgreSQL 16 (Docker) | Real relational modeling, window functions, materialized views |
| Migrations | Alembic + SQLAlchemy 2.0 | Versioned schema |
| Vector DB | Qdrant (Docker) | Named dense + sparse vectors, payload filters, server-side fusion |
| Dense embeddings | `BAAI/bge-m3` via sentence-transformers | Multilingual, strong, free (config-swappable to a smaller model) |
| Sparse / BM25 | `fastembed` `Qdrant/bm25` | True BM25 weights stored as Qdrant sparse vectors |
| Fusion | Reciprocal Rank Fusion (own implementation + Qdrant native for comparison) | You can explain it and benchmark both |
| Reranker | `BAAI/bge-reranker-v2-m3` (cross-encoder) | Free, local |
| Orchestration | LangGraph | Explicit state machine, multi-step tool loop |
| LLM | DeepSeek via OpenAI-compatible API (`openai` SDK) | Your existing key; provider abstraction behind an interface |
| Charts | **Plotly (Python)** builds figures server-side → JSON → Plotly.js renders | "Python-based graphs", interactive, data-validated |
| Frontend | React + Vite + TypeScript + Tailwind | Clean UI like your screenshot |
| SQL safety | Semantic layer (primary), `sqlglot` guard (fallback) | Prevents wrong/unsafe LLM SQL |
| Eval | Own metrics + DeepSeek judge (optional local judge via Ollama) | Transparent and reproducible |
| Tests | pytest, httpx | |

### 1.3 Key design decisions (memorize these for interviews)

1. **The LLM never writes numbers.** Numbers come from SQL results. The LLM picks *which* analysis to run (typed tool call), and a verifier checks that every number in the final answer exists in tool output.
2. **Semantic layer over free-form text-to-SQL.** The LLM calls `analytics_query(metric, dimension, filters, …)` with names from a whitelist defined in YAML. SQL is generated by deterministic code. Free-form SQL is an optional guarded fallback only.
3. **Charts are built from stored DataFrames, not LLM output.** The LLM sends a `ChartSpec` (type, x, y, title). Backend validates column names against the real result and builds the Plotly figure in Python.
4. **Hybrid retrieval, measured not assumed.** Dense, BM25, RRF-hybrid, +rerank, +rewrite are each an ablation in the evaluation.
5. **Parent–child documents.** Small child chunks (messages) are searched; the parent ticket facts come from Postgres at context-assembly time.
6. **Honest coverage.** Only a subset of tickets has conversations. Coverage statistics are computed from the DB and injected into prompts; the system must say "not available" rather than infer.
7. **Evidence has IDs.** Retrieval evidence is `E1…En`; analytics results are `D1…Dn`. Answers cite these; the UI links them to the source.
8. **Idempotent everything.** File-hash-gated ingestion, deterministic UUIDv5 point IDs, content-hash-gated re-indexing.

---

## 2. Prerequisites

- Python **3.11**, Node **20+**, Git, Docker Desktop (or Docker Engine + Compose v2)
- 16 GB RAM recommended (8 GB works with the small-model fallback in §8.1)
- ~10 GB free disk (models + Docker volumes)
- DeepSeek API key
- Check model names and prices on DeepSeek's official docs before you start; they change. They live in `.env`/config, never in code.

---

## 3. Repository structure

```
supportlens/
├── README.md
├── building_instructions.md
├── docker-compose.yml
├── .env.example                 # copy to .env (never commit)
├── .gitignore
├── requirements.txt
├── alembic.ini
├── configs/
│   ├── settings.yaml            # retrieval/agent defaults
│   ├── column_map.yaml          # YOU fill after profiling (Phase 3)
│   └── semantic_layer.yaml      # metrics, dimensions, filters (Phase 9)
├── data/                        # gitignored
│   ├── raw/mendeley_helpdesk_v3/
│   └── processed/               # profile + quality reports
├── backend/
│   └── app/
│       ├── main.py
│       ├── core/                # config.py, logging.py, timing.py
│       ├── api/                 # routes_chat.py, routes_tickets.py, routes_retrieval.py, routes_health.py
│       ├── schemas/             # chat.py, evidence.py, chart.py, filters.py
│       ├── db/                  # session.py, models.py, migrations/
│       ├── ingestion/
│       │   ├── adapters/        # base.py, mendeley.py, (zendesk.py stub)
│       │   ├── profile.py  validate.py  load.py  run.py
│       ├── documents/           # builder.py, chunker.py
│       ├── embeddings/          # encoder.py, sparse.py
│       ├── vectorstore/         # qdrant_store.py, indexer.py
│       ├── retrieval/           # filters.py, fusion.py, rewrite.py, rerank.py, assemble.py, pipeline.py
│       ├── analytics/           # semantic_layer.py, query_builder.py, sql_guard.py
│       ├── viz/                 # chart_builder.py
│       ├── llm/                 # base.py, deepseek.py, prompts.py
│       ├── agent/               # state.py, tools.py, nodes.py, graph.py, grounding.py
│       └── static/              # built frontend copied here (Phase 13)
├── frontend/
│   └── src/
│       ├── main.tsx  App.tsx  index.css  types.ts  api.ts  mock.ts
│       ├── components/          # Sidebar, Composer, Home, ChatThread, MessageView, ChartCard, EvidenceDrawer
│       └── pages/               # Explorer.tsx, Inspector.tsx
├── evaluation/
│   ├── datasets/                # retrieval_dev/test.jsonl, analytics.jsonl, e2e.jsonl
│   ├── metrics.py  generate_dataset.py  run_retrieval_eval.py  run_analytics_eval.py  run_e2e_eval.py
│   └── results/
├── scripts/                     # index_all.py, ask.py (CLI), export_results.py
├── tests/
└── docs/                        # DESIGN.md, EVALUATION.md, screenshots
```

---

## Phase 0 — Scaffold & infrastructure

### 0.1 Create the project

```bash
mkdir supportlens && cd supportlens
git init
python3.11 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
mkdir -p configs data/raw data/processed backend/app/{core,api,schemas,db,ingestion/adapters,documents,embeddings,vectorstore,retrieval,analytics,viz,llm,agent,static} evaluation/{datasets,results} scripts tests docs
touch backend/app/__init__.py   # add __init__.py to every package folder under backend/app
```

`.gitignore`:

```
.venv/
__pycache__/
.env
data/
node_modules/
frontend/dist/
backend/app/static/*
!backend/app/static/.gitkeep
evaluation/results/*.tmp
.cache/
```

### 0.2 Python dependencies

`requirements.txt` (pin exact versions with `pip freeze` once everything works):

```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
sqlalchemy>=2
alembic
psycopg[binary]>=3
pandas
numpy
pyyaml
plotly
kaleido
qdrant-client
fastembed
sentence-transformers
langgraph
openai
sqlglot
tenacity
httpx
pytest
pytest-asyncio
```

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU build; use the CUDA index if you have an NVIDIA GPU
pip install -r requirements.txt
```

### 0.3 Docker infrastructure

`docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: supportlens
      POSTGRES_PASSWORD: supportlens
      POSTGRES_DB: supportlens
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U supportlens"]
      interval: 5s
      retries: 10

  qdrant:
    image: qdrant/qdrant:v1.12.4      # pin; check for newer stable
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]

volumes:
  pgdata:
  qdrant_data:
```

```bash
docker compose up -d
```

### 0.4 Config

`.env.example`:

```
DATABASE_URL=postgresql+psycopg://supportlens:supportlens@localhost:5432/supportlens
READONLY_DATABASE_URL=postgresql+psycopg://sl_readonly:sl_readonly@localhost:5432/supportlens
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=support_docs

LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL_FAST=deepseek-chat
LLM_MODEL_THOROUGH=deepseek-chat        # set to a reasoning model if it supports tool calling (verify in docs)
LLM_PRICE_IN_PER_M=0.0                  # fill from DeepSeek pricing page (USD per 1M tokens)
LLM_PRICE_OUT_PER_M=0.0

EMBED_MODEL=BAAI/bge-m3
EMBED_DIM=1024
EMBED_QUERY_PREFIX=
RERANK_MODEL=BAAI/bge-reranker-v2-m3
USE_MOCK_LLM=false
```

`backend/app/core/config.py`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    readonly_database_url: str | None = None
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "support_docs"
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model_fast: str = "deepseek-chat"
    llm_model_thorough: str = "deepseek-chat"
    llm_price_in_per_m: float = 0.0
    llm_price_out_per_m: float = 0.0
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    embed_query_prefix: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Checkpoint 0
- `docker compose ps` shows both services healthy.
- `curl http://localhost:6333/collections` returns JSON.
- `python -c "from backend.app.core.config import get_settings as g; print(g().qdrant_url)"` prints the URL (run from repo root with `PYTHONPATH=.`).

---
## Phase 1 — Frontend UI first (mock data)

**Goal:** reproduce the look of your reference screenshot: left sidebar, big two-line greeting, rounded composer with a toolbar, dismissible info banner, template chips, and then a chat view that renders markdown, **Plotly charts**, citations and an evidence drawer. It runs entirely on mock data so you can finish the UX before any backend exists.

### 1.1 Mapping the screenshot to SupportLens

| Screenshot element | SupportLens equivalent |
|---|---|
| "New video" | **New chat** |
| Search / Projects / Brand Kits / Memory / Resources | **Search**, **Ticket Explorer**, **Retrieval Inspector**, **Evaluation**, **Data Sources** |
| Recents + "View all videos" | Recent chats + "View all chats" |
| "Hey Gatik, What are we building today?" | "Hey {name}," / "What do you want to investigate today?" (second line gray) |
| Composer: `+`, aspect ratio, duration, quality, credits | `+` (filters), **retrieval mode** (Hybrid/Dense/BM25), **effort** (Fast/Thorough), **evidence k**, send button |
| Banner "Create videos from Claude… Explore MCP" (dismissible) | "Every answer cites tickets and database results" + *How it works* |
| Template chips (Launch video, Changelog…) | Prompt chips (Monthly volume, Priority split, Resolution times, Similar tickets, Category trends, Investigate) |

### 1.2 Create the app

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss@3 postcss autoprefixer @types/react-plotly.js
npx tailwindcss init -p
npm install react-markdown remark-gfm lucide-react plotly.js-dist-min react-plotly.js @fontsource/inter
```

`tailwind.config.js`:

```js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] },
      colors: { sidebar: "#F7F7F8", line: "#E8E8EA", ink: "#111113", muted: "#6B6B73" },
      boxShadow: { composer: "0 2px 12px rgba(0,0,0,0.06)" },
    },
  },
  plugins: [],
};
```

`src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
html, body, #root { height: 100%; }
body { @apply bg-white text-ink font-sans antialiased; }
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-thumb { background: #d4d4d8; border-radius: 8px; }
```

`vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
```

`src/plotly.d.ts`:

```ts
declare module "plotly.js-dist-min";
```

`.env.development` (in `frontend/`): `VITE_USE_MOCK=true`

### 1.3 Types (this is the API contract; the backend mirrors it in Pydantic)

`src/types.ts`:

```ts
export type RetrievalMode = "hybrid" | "dense" | "bm25";
export type Effort = "fast" | "thorough";

export interface ChatOptions { mode: RetrievalMode; effort: Effort; top_k: number; filters?: Record<string, unknown>; }
export interface ChatRequest { conversation_id: string | null; message: string; options: ChatOptions; }

export interface EvidenceItem {
  ref_id: string;                 // "E1"
  ticket_id: string;
  doc_type: "ticket_summary" | "utterance" | "history_event";
  text: string;
  scores: Record<string, number>; // dense, bm25, rrf, rerank
  rank: number;
  has_conversation: boolean;
  cited: boolean;
  ticket_facts?: Record<string, unknown>;
}
export interface TablePayload { columns: string[]; rows: (string | number | null)[][]; }
export interface ChartPayload {
  chart_id: string;               // "D1"
  title: string;
  chart_type: string;
  figure: { data: any[]; layout: any };   // Plotly JSON built by Python
  table: TablePayload;
  provenance: { tool: string; params: Record<string, unknown>; sql: string; row_count: number; caveats: string[] };
}
export interface Finding { statement: string; status: "verified" | "hypothesis" | "unavailable"; citations: string[]; }
export interface TraceStep { name: string; ms: number; detail?: string; }
export interface ChatResponse {
  conversation_id: string; message_id: string;
  answer_markdown: string;
  findings: Finding[]; charts: ChartPayload[]; tables: ChartPayload[];
  evidence: EvidenceItem[]; follow_ups: string[];
  trace: { route: string; steps: TraceStep[]; tokens_in: number; tokens_out: number; cost_usd: number; total_ms: number; verification?: { ok: boolean; issues: string[] } };
}
export interface UiMessage { id: string; role: "user" | "assistant"; text: string; response?: ChatResponse; pending?: boolean; error?: string; }
export interface Conversation { id: string; title: string; messages: UiMessage[]; }
```

### 1.4 Mock + API layer

`src/mock.ts`:

```ts
import { ChatRequest, ChatResponse } from "./types";

export async function mockChat(req: ChatRequest): Promise<ChatResponse> {
  await new Promise((r) => setTimeout(r, 1200));
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const values = [120, 98, 143, 130, 160, 151];
  return {
    conversation_id: req.conversation_id ?? crypto.randomUUID(),
    message_id: crypto.randomUUID(),
    answer_markdown: `**Mock answer.** Volume rose from ${values[0]} to ${values[5]} tickets [D1]. A similar complaint appears in ticket 1001 [E1].`,
    findings: [{ statement: "Volume rose", status: "verified", citations: ["D1"] }],
    charts: [{
      chart_id: "D1", title: "Monthly ticket volume", chart_type: "bar",
      figure: { data: [{ type: "bar", x: months, y: values, marker: { color: "#3b82f6" } }], layout: { title: "Monthly ticket volume", margin: { t: 40, r: 10, b: 40, l: 40 } } },
      table: { columns: ["month", "ticket_count"], rows: months.map((m, i) => [m, values[i]]) },
      provenance: { tool: "analytics_query", params: { metric: "ticket_count", dimension: "created_month" }, sql: "SELECT …", row_count: 6, caveats: [] },
    }],
    tables: [],
    evidence: [{ ref_id: "E1", ticket_id: "1001", doc_type: "utterance", text: "Customer could not log in after update…", scores: { dense: 0.71, bm25: 12.4, rrf: 0.031, rerank: 0.88 }, rank: 1, has_conversation: true, cited: true }],
    follow_ups: ["Break this down by priority", "Which category grew the most?"],
    trace: { route: "analytics", steps: [{ name: "plan", ms: 410 }, { name: "analytics_query", ms: 35 }, { name: "compose", ms: 900 }], tokens_in: 1800, tokens_out: 260, cost_usd: 0, total_ms: 1350 },
  };
}
```

`src/api.ts`:

```ts
import { ChatRequest, ChatResponse } from "./types";
import { mockChat } from "./mock";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export async function sendChat(req: ChatRequest): Promise<ChatResponse> {
  if (USE_MOCK) return mockChat(req);
  const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}
```

### 1.5 Components

`src/main.tsx`:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "./index.css";
import App from "./App";
ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
```

`src/components/Sidebar.tsx`:

```tsx
import { Plus, Search, Ticket, ScanSearch, FlaskConical, Database, PanelLeft, ArrowUpRight } from "lucide-react";
import { Conversation } from "../types";

export type View = "chat" | "explorer" | "inspector";
interface Props { conversations: Conversation[]; activeId: string | null; view: View; onNew: () => void; onSelect: (id: string) => void; onView: (v: View) => void; }

const Item = ({ icon: Icon, label, active, onClick }: any) => (
  <button onClick={onClick} className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] ${active ? "bg-[#EDEDF0]" : "hover:bg-[#EFEFF2]"}`}>
    <Icon size={17} strokeWidth={1.8} /> {label}
  </button>
);

export default function Sidebar({ conversations, activeId, view, onNew, onSelect, onView }: Props) {
  return (
    <aside className="w-[260px] shrink-0 bg-sidebar border-r border-line flex flex-col px-2 py-3">
      <div className="flex items-center justify-between px-2 pb-4">
        <div className="w-7 h-7 rounded-lg bg-ink text-white grid place-items-center font-semibold text-sm">S</div>
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
```

`src/components/Composer.tsx`:

```tsx
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
```

`src/components/Home.tsx` (the empty-state screen from your screenshot):

```tsx
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
```

`src/components/ChartCard.tsx` (renders the figure **built by Python**):

```tsx
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
```

`src/components/MessageView.tsx`:

```tsx
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
      {r.trace.verification && !r.trace.verification.ok && <div className="text-[12px] text-amber-700 mt-2">⚠ Some claims could not be fully verified: {r.trace.verification.issues.join("; ")}</div>}
      <div className="mt-3 flex flex-wrap gap-2">{r.follow_ups.map((f) => <button key={f} onClick={() => onFollowUp(f)} className="px-3 py-1 rounded-full border border-line text-[13px] hover:bg-sidebar">{f}</button>)}</div>
      <div className="mt-2 text-[11px] text-muted">{r.trace.route} · {r.trace.total_ms} ms · {r.trace.tokens_in + r.trace.tokens_out} tokens</div>
    </div>
  );
}
```

`src/components/EvidenceDrawer.tsx`:

```tsx
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
```

`src/App.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import Sidebar, { View } from "./components/Sidebar";
import Home from "./components/Home";
import Composer from "./components/Composer";
import MessageView from "./components/MessageView";
import EvidenceDrawer from "./components/EvidenceDrawer";
import { sendChat } from "./api";
import { ChatOptions, ChatResponse, Conversation, UiMessage } from "./types";

const USER_NAME = "there";   // make configurable later

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
      patch(cid, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === pending.id ? { ...m, pending: false, text: res.answer_markdown, response: res } : m)) }));
    } catch (e: any) {
      patch(cid, (c) => ({ ...c, messages: c.messages.map((m) => (m.id === pending.id ? { ...m, pending: false, error: String(e.message ?? e) } : m)) }));
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
          {view !== "chat" && <div className="p-10 text-muted">This page is built in Phase 11.</div>}
        </div>
        {drawer && <EvidenceDrawer response={drawer.response} focus={drawer.focus} onClose={() => setDrawer(null)} />}
      </main>
    </div>
  );
}
```

```bash
npm run dev      # http://localhost:5173
```

### Checkpoint 1
- Home screen resembles the screenshot (sidebar, greeting, composer, banner, chips).
- Clicking a chip fills the composer; sending shows "Analyzing tickets…", then a markdown answer with a **bar chart**, working `chart / data / query` tabs, clickable `[D1]`/`[E1]` chips opening the evidence drawer.
- Resize the window; the chart reflows.
- If the Plotly import fails in Vite, add `optimizeDeps: { include: ["plotly.js-dist-min"] }` to `vite.config.ts`.

---

## Phase 2 — FastAPI skeleton (still returns mock answers)

### 2.1 Schemas (mirror `types.ts` exactly)

`backend/app/schemas/chat.py`:

```python
from typing import Any, Literal
from pydantic import BaseModel, Field

class ChatOptions(BaseModel):
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid"
    effort: Literal["fast", "thorough"] = "fast"
    top_k: int = Field(8, ge=1, le=30)
    filters: dict[str, Any] | None = None

class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    options: ChatOptions = ChatOptions()

class EvidenceItem(BaseModel):
    ref_id: str
    ticket_id: str
    doc_type: Literal["ticket_summary", "utterance", "history_event"]
    text: str
    scores: dict[str, float] = {}
    rank: int
    has_conversation: bool
    cited: bool = False
    ticket_facts: dict[str, Any] | None = None

class TablePayload(BaseModel):
    columns: list[str]
    rows: list[list[Any]]

class Provenance(BaseModel):
    tool: str
    params: dict[str, Any]
    sql: str
    row_count: int
    caveats: list[str] = []

class ChartPayload(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    figure: dict[str, Any]
    table: TablePayload
    provenance: Provenance

class Finding(BaseModel):
    statement: str
    status: Literal["verified", "hypothesis", "unavailable"]
    citations: list[str] = []

class TraceStep(BaseModel):
    name: str
    ms: int
    detail: str | None = None

class Trace(BaseModel):
    route: str = ""
    steps: list[TraceStep] = []
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    total_ms: int = 0
    verification: dict[str, Any] | None = None

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer_markdown: str
    findings: list[Finding] = []
    charts: list[ChartPayload] = []
    tables: list[ChartPayload] = []
    evidence: list[EvidenceItem] = []
    follow_ups: list[str] = []
    trace: Trace = Trace()
```

### 2.2 App

`backend/app/main.py`:

```python
import uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.schemas.chat import *

app = FastAPI(title="SupportLens")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:   # replaced by the real agent in Phase 10
    return ChatResponse(
        conversation_id=req.conversation_id or str(uuid.uuid4()), message_id=str(uuid.uuid4()),
        answer_markdown=f"Backend is alive. You asked: *{req.message}*",
        trace=Trace(route="stub"),
    )

static_dir = Path(__file__).parent / "static"
if (static_dir / "index.html").exists():                 # production: serve the built UI
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")
```

```bash
uvicorn backend.app.main:app --reload --port 8000     # run from repo root
```

Set `VITE_USE_MOCK=false` in `frontend/.env.development`, restart `npm run dev`.

### Checkpoint 2
- `http://localhost:8000/docs` shows the OpenAPI UI.
- The UI now displays "Backend is alive…" for any question (no chart yet, which is expected).

---
## Phase 3 — Get the data and profile it (do not skip)

### 3.1 Download

1. Search **"Mendeley Data Help Desk Tickets Version 3"** and open the dataset page. Read the **license** and the data description/README; note the citation (you will put it in your README).
2. Download and unzip into `data/raw/mendeley_helpdesk_v3/`. You should see `issues.csv`, `issues_change_history.csv`, `issues_snapshot.csv`, `sample_utterances.csv`, `holidays_by_country.csv` plus documentation files.

### 3.2 Profiling script

`backend/app/ingestion/profile.py`:

```python
"""Usage: python -m backend.app.ingestion.profile data/raw/mendeley_helpdesk_v3"""
import sys
from pathlib import Path
import pandas as pd

def profile_file(path: Path) -> str:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], low_memory=False, encoding_errors="replace")
    out = [f"## {path.name}", f"- rows: **{len(df):,}**, columns: **{df.shape[1]}**", "", "| column | non-null % | unique | sample values |", "|---|---|---|---|"]
    for c in df.columns:
        s = df[c]
        sample = ", ".join(map(lambda v: repr(v)[:40], s.dropna().unique()[:3]))
        out.append(f"| `{c}` | {100*s.notna().mean():.1f} | {s.nunique():,} | {sample} |")
    dup = df.duplicated().sum()
    out += ["", f"- exact duplicate rows: {dup:,}", ""]
    return "\n".join(out)

if __name__ == "__main__":
    root = Path(sys.argv[1]); rep = ["# Dataset profile\n"]
    for p in sorted(root.glob("*.csv")):
        rep.append(profile_file(p))
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("data/processed/profile_report.md").write_text("\n".join(rep), encoding="utf-8")
    print("wrote data/processed/profile_report.md")
```

```bash
python -m backend.app.ingestion.profile data/raw/mendeley_helpdesk_v3
```

### 3.3 Decide the mapping

Open `profile_report.md` and answer these questions **in writing** (put the answers in `docs/DESIGN.md`):

1. Which column is the ticket primary key in `issues.csv`? Is it unique? Is it the same key used in the history, snapshot and utterance files?
2. Which columns hold category, priority, project, status, created/resolved timestamps? Which timestamp formats and timezones?
3. How are history rows structured (one row per change? field name + old/new values?)
4. What does `sample_utterances.csv` contain: speaker role, text, ordering, timestamp? What fraction of tickets have utterances?
5. Is any customer/product/country information actually present? If not, the system must say so. Never infer it.
6. Is there a country field that joins to `holidays_by_country.csv`? (Determines whether business-hours resolution time is possible.)

Create `configs/column_map.yaml` from the real column names (keys on the left are fixed canonical names; values are the **actual** CSV headers). Anything you cannot map stays `null` and is simply absent from the canonical table (it is still preserved in the `raw` JSON column).

```yaml
source_name: mendeley_helpdesk_v3
files:
  tickets:    issues.csv
  events:     issues_change_history.csv
  snapshots:  issues_snapshot.csv
  utterances: sample_utterances.csv
  holidays:   holidays_by_country.csv
tickets:
  ticket_id:    <REAL_COLUMN>
  project_id:   <REAL_COLUMN or null>
  category:     <REAL_COLUMN or null>
  priority:     <REAL_COLUMN or null>
  status:       <REAL_COLUMN or null>
  created_at:   <REAL_COLUMN>
  resolved_at:  <REAL_COLUMN or null>
  title:        <REAL_COLUMN or null>
  description:  <REAL_COLUMN or null>
  country:      <REAL_COLUMN or null>
events:
  ticket_id: <REAL_COLUMN>
  changed_at: <REAL_COLUMN>
  field: <REAL_COLUMN or null>
  old_value: <REAL_COLUMN or null>
  new_value: <REAL_COLUMN or null>
utterances:
  utterance_id: <REAL_COLUMN or null>   # null → generated from row order
  ticket_id: <REAL_COLUMN>
  speaker_role: <REAL_COLUMN or null>
  text: <REAL_COLUMN>
  sent_at: <REAL_COLUMN or null>
  seq: <REAL_COLUMN or null>
timestamp_format: null                  # e.g. "%Y-%m-%d %H:%M:%S" or null to let pandas infer
```

### Checkpoint 3
- Profile report exists; `column_map.yaml` has no remaining `<REAL_COLUMN>` placeholders; design notes answer the six questions.

---

## Phase 4 — Relational model and ingestion

### 4.1 SQLAlchemy models

`backend/app/db/models.py`:

```python
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_file: Mapped[str] = mapped_column(String)
    file_sha256: Mapped[str] = mapped_column(String, index=True)
    target_table: Mapped[str] = mapped_column(String)
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="running")      # running|success|failed|skipped
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class IngestionReject(Base):
    __tablename__ = "ingestion_rejects"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"), index=True)
    reason: Mapped[str] = mapped_column(String)                          # missing_pk|bad_timestamp|orphan_fk|empty_text
    row_json: Mapped[dict] = mapped_column(JSONB)

class Ticket(Base):
    __tablename__ = "tickets"
    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_system: Mapped[str] = mapped_column(String, default="mendeley_helpdesk_v3")
    project_id: Mapped[str | None] = mapped_column(String, index=True)
    category: Mapped[str | None] = mapped_column(String, index=True)
    priority: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str | None] = mapped_column(String, index=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)                             # every original column, unmodified
    row_hash: Mapped[str] = mapped_column(String)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))

class TicketEvent(Base):
    __tablename__ = "ticket_events"
    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    field: Mapped[str | None] = mapped_column(String, index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB)
    row_hash: Mapped[str] = mapped_column(String, unique=True)           # dedupe key
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))

class Utterance(Base):
    __tablename__ = "utterances"
    utterance_id: Mapped[str] = mapped_column(String, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.ticket_id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    speaker_role: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.run_id"))

class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String, index=True)
    day: Mapped[datetime] = mapped_column(DateTime)
    name: Mapped[str | None] = mapped_column(String)
    raw: Mapped[dict] = mapped_column(JSONB)

class TicketSnapshot(Base):                  # structure depends on profiling; keep raw JSON + keys
    __tablename__ = "ticket_snapshots"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String, index=True)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB)

class Document(Base):                        # Phase 5: searchable documents + index state
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String, primary_key=True)        # uuid5
    parent_id: Mapped[str | None] = mapped_column(String, index=True)
    ticket_id: Mapped[str] = mapped_column(String, index=True)
    doc_type: Mapped[str] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String)
    indexed_hash: Mapped[str | None] = mapped_column(String)             # == content_hash once embedded

class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    response_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`backend/app/db/session.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.config import get_settings
engine = create_engine(get_settings().database_url, pool_size=10, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
```

Alembic:

```bash
alembic init backend/app/db/migrations
# in alembic.ini: leave sqlalchemy.url blank
# in migrations/env.py: set target_metadata = Base.metadata and url = get_settings().database_url
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### 4.2 Analytical view and read-only role (second migration, `op.execute`)

```sql
CREATE MATERIALIZED VIEW ticket_facts AS
SELECT
  t.ticket_id, t.project_id, t.category, t.priority, t.status, t.country,
  t.created_at, t.resolved_at,
  CASE WHEN t.resolved_at >= t.created_at
       THEN EXTRACT(EPOCH FROM (t.resolved_at - t.created_at))/3600.0 END AS resolution_hours,
  (t.resolved_at IS NOT NULL) AS is_resolved,
  COALESCE(e.n_events, 0)      AS n_events,
  COALESCE(e.n_reassign, 0)    AS n_reassignments,
  EXISTS (SELECT 1 FROM utterances u WHERE u.ticket_id = t.ticket_id) AS has_conversation
FROM tickets t
LEFT JOIN (
  SELECT ticket_id, COUNT(*) AS n_events,
         COUNT(*) FILTER (WHERE field ILIKE '%assign%') AS n_reassign   -- adjust to the real field names found in profiling
  FROM ticket_events GROUP BY ticket_id) e USING (ticket_id);

CREATE UNIQUE INDEX ON ticket_facts (ticket_id);
CREATE INDEX ON ticket_facts (created_at);
CREATE INDEX ON ticket_facts (category);
CREATE INDEX ON ticket_facts (priority);

CREATE VIEW dataset_coverage AS
SELECT COUNT(*) AS total_tickets,
       COUNT(*) FILTER (WHERE has_conversation) AS tickets_with_conversation,
       COUNT(*) FILTER (WHERE resolution_hours IS NOT NULL) AS tickets_with_resolution_time,
       MIN(created_at) AS first_ticket_at, MAX(created_at) AS last_ticket_at
FROM ticket_facts;

CREATE ROLE sl_readonly LOGIN PASSWORD 'sl_readonly';
GRANT CONNECT ON DATABASE supportlens TO sl_readonly;
GRANT USAGE ON SCHEMA public TO sl_readonly;
GRANT SELECT ON ticket_facts, dataset_coverage TO sl_readonly;   -- ONLY the analytical surfaces
```

Refresh after every ingestion: `REFRESH MATERIALIZED VIEW CONCURRENTLY ticket_facts;`

### 4.3 Adapter abstraction (this is what makes it extensible to Zendesk, Intercom, Salesforce)

`backend/app/ingestion/adapters/base.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

@dataclass
class Batch:
    table: str                 # "tickets" | "events" | "utterances" | "holidays" | "snapshots"
    source_file: str
    records: list[dict]        # canonical keys + "raw" dict with all original columns

class TicketSourceAdapter(Protocol):
    name: str
    def extract(self, root: Path) -> Iterator[Batch]: ...
```

To support Zendesk later, you write `zendesk.py` that implements `extract()` and emits the same canonical batches. Nothing downstream changes. Add a stub file with a docstring now; it signals the design.

### 4.4 Mendeley adapter

`backend/app/ingestion/adapters/mendeley.py`:

```python
import hashlib, json
from pathlib import Path
from typing import Iterator
import pandas as pd, yaml
from .base import Batch

def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding_errors="replace", low_memory=False)

def _canon(df: pd.DataFrame, mapping: dict, ts_fmt: str | None, ts_cols: list[str]) -> list[dict]:
    out = pd.DataFrame(index=df.index)
    for canon, real in mapping.items():
        out[canon] = df[real] if real and real in df.columns else None
    for c in ts_cols:
        if c in out: out[c] = pd.to_datetime(out[c], format=ts_fmt, errors="coerce", utc=True)
    out["raw"] = df.apply(lambda r: {k: (None if pd.isna(v) else v) for k, v in r.items()}, axis=1)
    out["row_hash"] = out["raw"].map(lambda d: hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest())
    return out.to_dict("records")

class MendeleyAdapter:
    name = "mendeley_helpdesk_v3"
    def __init__(self, column_map_path: str = "configs/column_map.yaml"):
        self.cfg = yaml.safe_load(open(column_map_path))

    def extract(self, root: Path) -> Iterator[Batch]:
        c, fmt = self.cfg, self.cfg.get("timestamp_format")
        spec = [("tickets", ["created_at", "resolved_at"]), ("events", ["changed_at"]), ("utterances", ["sent_at"])]
        for table, ts_cols in spec:
            fname = c["files"][table]; df = _read(root / fname)
            yield Batch(table, fname, _canon(df, c[table], fmt, ts_cols))
        # holidays + snapshots: keep as raw JSON rows with whatever keys exist (see profile report)
```

### 4.5 Validation, dedupe, loading, idempotency

`backend/app/ingestion/run.py` (core logic; keep each helper in its own file if you prefer):

```python
import hashlib, sys
from pathlib import Path
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from backend.app.db.models import *
from backend.app.db.session import SessionLocal
from backend.app.ingestion.adapters.mendeley import MendeleyAdapter

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

MODEL = {"tickets": Ticket, "events": TicketEvent, "utterances": Utterance}

def validate(table: str, rec: dict, known_tickets: set[str]) -> str | None:
    """return a reject reason or None"""
    if not rec.get("ticket_id") and table != "holidays": return "missing_pk"
    if table == "tickets" and pd.isna(rec.get("created_at")): return "bad_timestamp"
    if table in ("events", "utterances") and rec["ticket_id"] not in known_tickets: return "orphan_fk"
    if table == "utterances" and not (rec.get("text") or "").strip(): return "empty_text"
    return None

def run(root: str = "data/raw/mendeley_helpdesk_v3"):
    adapter, root = MendeleyAdapter(), Path(root)
    with SessionLocal() as s:
        known = set(s.scalars(select(Ticket.ticket_id)))
        for batch in adapter.extract(root):                     # tickets first (spec order) so FK checks work
            digest = sha256_file(root / batch.source_file)
            if s.scalar(select(IngestionRun).where(IngestionRun.file_sha256 == digest, IngestionRun.status == "success")):
                print(f"skip {batch.source_file} (already ingested)"); continue
            run_ = IngestionRun(source_file=batch.source_file, file_sha256=digest, target_table=batch.table); s.add(run_); s.flush()
            good, seen, dups = [], set(), 0
            for rec in batch.records:
                reason = validate(batch.table, rec, known)
                if reason:
                    s.add(IngestionReject(run_id=run_.run_id, reason=reason, row_json=rec["raw"])); run_.rows_rejected += 1; continue
                key = rec["ticket_id"] if batch.table == "tickets" else rec["row_hash"]
                if key in seen: dups += 1; continue            # keep first occurrence; policy documented in DESIGN.md
                seen.add(key); rec["run_id"] = run_.run_id; good.append(rec)
            # --- bulk upsert in chunks ---
            if batch.table in MODEL:
                M = MODEL[batch.table]; cols = {c.name for c in M.__table__.columns}
                for i in range(0, len(good), 5000):
                    rows = [{k: v for k, v in r.items() if k in cols} for r in good[i:i+5000]]
                    stmt = insert(M).values(rows)
                    pk = list(M.__table__.primary_key.columns.keys())[0]
                    if batch.table == "events":
                        stmt = stmt.on_conflict_do_nothing(index_elements=["row_hash"])
                    else:
                        stmt = stmt.on_conflict_do_update(index_elements=[pk], set_={c: stmt.excluded[c] for c in cols - {pk}})
                    s.execute(stmt)
            if batch.table == "tickets": known |= {r["ticket_id"] for r in good}
            run_.rows_read, run_.rows_loaded, run_.duplicates_removed, run_.status = len(batch.records), len(good), dups, "success"
            run_.finished_at = text("now()")
            s.commit(); print(batch.table, "loaded", len(good), "rejected", run_.rows_rejected)
        s.execute(text("REFRESH MATERIALIZED VIEW ticket_facts")); s.commit()

if __name__ == "__main__": run(*sys.argv[1:])
```

Notes:
- If utterances have no ID column, generate `utterance_id = f"{ticket_id}:{seq}"` in the adapter (`seq` = row order inside a ticket).
- Add loaders for `holidays` and `snapshots` following the same pattern (raw JSON preserved).
- **Never silently drop**: every discarded row lands in `ingestion_rejects` with a reason.

### 4.6 Quality report

`scripts/quality_report.py` queries and writes `data/processed/quality_report.md`:

- row counts per table, rejects grouped by reason
- % tickets with `resolved_at`, with `resolution_hours`, with ≥1 utterance (**coverage**)
- negative or absurd resolution durations (resolved before created)
- orphan counts, duplicate counts, date range

### Checkpoint 4
- `python -m backend.app.ingestion.run` loads data; **running it a second time loads nothing** (idempotency proof).
- `SELECT * FROM dataset_coverage;` returns sensible numbers. These numbers are quoted in your README and used in prompts.
- `ingestion_rejects` is explainable, not mysterious.

---

## Phase 5 — Document processing

**Goal:** turn rows into searchable, provenance-carrying documents.

### 5.1 Document types

| `doc_type` | Built from | Role |
|---|---|---|
| `ticket_summary` | tickets + event history | One per ticket. **Parent.** Structured facts rendered as text |
| `utterance` | utterances, grouped per ticket and chunked | **Children.** Carry parent_id |
| `history_event` (optional) | consecutive events summarized (assignment path) | Lets semantic search answer "tickets reassigned many times" |

### 5.2 Rules (these protect against hallucination)

- Text is rendered **only from fields that exist**. A missing field is omitted, never filled with "Unknown customer".
- Every child chunk is prefixed with a **contextual header** (`Ticket {id} | {category} | {priority} | project {project}`) so a chunk is self-describing for both BM25 and embeddings.
- Payload (filterable metadata): `ticket_id, parent_id, doc_type, project, category, priority, status, created_ts (int epoch), has_conversation, source_file, chunk_idx, n_chunks, speaker_roles`.
- IDs are deterministic: `uuid5(NAMESPACE, f"{ticket_id}|{doc_type}|{chunk_idx}")`. Re-running never duplicates.

### 5.3 Chunker

`backend/app/documents/chunker.py`:

```python
from dataclasses import dataclass
from transformers import AutoTokenizer
from backend.app.core.config import get_settings

_tok = None
def tok():
    global _tok
    if _tok is None: _tok = AutoTokenizer.from_pretrained(get_settings().embed_model)
    return _tok

def n_tokens(s: str) -> int: return len(tok().encode(s, add_special_tokens=False))

@dataclass
class Turn: seq: int; role: str | None; text: str

def chunk_turns(turns: list[Turn], header: str, max_tokens: int = 256, overlap_turns: int = 1) -> list[tuple[str, list[Turn]]]:
    """Greedy, turn-aligned chunks. Never splits a turn unless a single turn exceeds max_tokens."""
    chunks, cur, cur_tok = [], [], n_tokens(header)
    def flush():
        if cur: chunks.append((header + "\n" + "\n".join(f"{(t.role or 'speaker')}: {t.text}" for t in cur), list(cur)))
    for t in turns:
        tt = n_tokens(t.text)
        if cur and cur_tok + tt > max_tokens:
            flush(); cur = cur[-overlap_turns:] if overlap_turns else []
            cur_tok = n_tokens(header) + sum(n_tokens(x.text) for x in cur)
        cur.append(t); cur_tok += tt
    flush()
    return chunks
```

### 5.4 Builder

`backend/app/documents/builder.py` (outline; write the full SQL/ORM reads yourself):

```python
import hashlib, uuid
NS = uuid.UUID("5e1f0a52-7b7e-4b8c-9a55-0c0d6d5f2a11")
def doc_id(ticket_id, doc_type, idx=0): return str(uuid.uuid5(NS, f"{ticket_id}|{doc_type}|{idx}"))
def h(text): return hashlib.sha256(text.encode()).hexdigest()

def ticket_summary_text(t, events, has_conv) -> str:
    lines = [f"Ticket {t.ticket_id}"]
    for label, val in [("Project", t.project_id), ("Category", t.category), ("Priority", t.priority), ("Status", t.status), ("Title", t.title)]:
        if val: lines.append(f"{label}: {val}")
    if t.created_at: lines.append(f"Created: {t.created_at:%Y-%m-%d}")
    if t.resolved_at: lines.append(f"Resolved: {t.resolved_at:%Y-%m-%d}")
    if t.description: lines.append(f"Description: {t.description[:1500]}")
    # assignment / status path from events, only if events exist:
    # lines.append("Assignment path: A → B → C (2 reassignments)")
    lines.append("Conversation available: " + ("yes" if has_conv else "no"))
    return "\n".join(lines)
```

For each ticket: upsert one `ticket_summary` doc; for each ticket with utterances, order by `seq` (or `sent_at`), `chunk_turns(...)`, and upsert child docs with `parent_id = doc_id(ticket_id, "ticket_summary")`. Upsert into `documents` setting `content_hash`; if the hash changed, set `indexed_hash = NULL`.

CLI: `python -m backend.app.documents.builder`.

### Checkpoint 5
- `SELECT doc_type, COUNT(*) FROM documents GROUP BY 1;` makes sense versus ticket/utterance counts.
- Print 5 random docs of each type and read them. If a human cannot understand a chunk in isolation, fix the header/template.
- Chunk token histogram (you will cite this in DESIGN.md): median, p95.

---

## Phase 6 — Embeddings and Qdrant

### 6.1 Dense encoder

`backend/app/embeddings/encoder.py`:

```python
import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from backend.app.core.config import get_settings

@lru_cache
def model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embed_model)   # add device="cuda" if available

def embed_docs(texts: list[str], batch_size: int = 32) -> np.ndarray:
    return model().encode(texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)

def embed_query(q: str) -> np.ndarray:
    s = get_settings()
    return model().encode([s.embed_query_prefix + q], normalize_embeddings=True)[0]
```

**Low-resource fallback:** set `EMBED_MODEL=BAAI/bge-small-en-v1.5`, `EMBED_DIM=384`, `EMBED_QUERY_PREFIX="Represent this sentence for searching relevant passages: "`, then rebuild the collection. Making the model swappable lets you benchmark models in Phase 12.

### 6.2 Sparse (BM25) encoder

`backend/app/embeddings/sparse.py`:

```python
from functools import lru_cache
from fastembed import SparseTextEmbedding
from qdrant_client.models import SparseVector

@lru_cache
def _m() -> SparseTextEmbedding: return SparseTextEmbedding("Qdrant/bm25")

def sparse_docs(texts: list[str]) -> list[SparseVector]:
    return [SparseVector(indices=e.indices.tolist(), values=e.values.tolist()) for e in _m().embed(texts)]

def sparse_query(q: str) -> SparseVector:
    e = next(iter(_m().query_embed(q)))
    return SparseVector(indices=e.indices.tolist(), values=e.values.tolist())
```

IDF is applied by Qdrant at query time (`Modifier.IDF`), which is why this is real BM25 behavior rather than term-frequency only.

### 6.3 Qdrant store

`backend/app/vectorstore/qdrant_store.py`:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, VectorParams, SparseVectorParams, Modifier, PayloadSchemaType, PointStruct)
from backend.app.core.config import get_settings

def client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url, timeout=60)

def ensure_collection(recreate: bool = False):
    s, c = get_settings(), client()
    if recreate and c.collection_exists(s.qdrant_collection): c.delete_collection(s.qdrant_collection)
    if not c.collection_exists(s.qdrant_collection):
        c.create_collection(
            s.qdrant_collection,
            vectors_config={"dense": VectorParams(size=s.embed_dim, distance=Distance.COSINE)},
            sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
        )
        for f in ["project", "category", "priority", "status", "doc_type", "ticket_id"]:
            c.create_payload_index(s.qdrant_collection, f, PayloadSchemaType.KEYWORD)
        c.create_payload_index(s.qdrant_collection, "created_ts", PayloadSchemaType.INTEGER)
        c.create_payload_index(s.qdrant_collection, "has_conversation", PayloadSchemaType.BOOL)
```

### 6.4 Incremental indexer

`backend/app/vectorstore/indexer.py`:

```python
from sqlalchemy import select, update
from qdrant_client.models import PointStruct
from backend.app.db.models import Document
from backend.app.db.session import SessionLocal
from backend.app.embeddings.encoder import embed_docs
from backend.app.embeddings.sparse import sparse_docs
from backend.app.vectorstore.qdrant_store import client, ensure_collection
from backend.app.core.config import get_settings

def index_pending(batch: int = 64):
    ensure_collection(); c, coll = client(), get_settings().qdrant_collection
    with SessionLocal() as s:
        while True:
            docs = s.scalars(select(Document).where((Document.indexed_hash.is_(None)) | (Document.indexed_hash != Document.content_hash)).limit(batch)).all()
            if not docs: break
            texts = [d.text for d in docs]
            dense, sparse = embed_docs(texts), sparse_docs(texts)
            c.upsert(coll, [PointStruct(id=d.doc_id, vector={"dense": dense[i].tolist(), "bm25": sparse[i]}, payload={**d.payload, "doc_type": d.doc_type, "ticket_id": d.ticket_id, "parent_id": d.parent_id})
                            for i, d in enumerate(docs)])
            for d in docs: d.indexed_hash = d.content_hash
            s.commit(); print("indexed", len(docs))
```

`scripts/index_all.py` calls `index_pending()`. Time the full run and record docs/second (a performance number for your README).

### Checkpoint 6
- Qdrant dashboard at `http://localhost:6333/dashboard` shows the collection with point count == `documents` count.
- Re-running `index_all.py` indexes **zero** new docs.
- Sanity query in a notebook: embed "cannot log in", run dense search with `using="dense"` and sparse with `using="bm25"`; results should look plausible and different from each other.

---

## Phase 7 — LLM provider layer (DeepSeek behind an interface)

Built before advanced retrieval because query rewriting needs it.

`backend/app/llm/base.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class ToolCall: id: str; name: str; arguments: dict

@dataclass
class LLMResult:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    raw_message: dict[str, Any] | None = None     # assistant message to append back into the transcript

class LLMClient(Protocol):
    def chat(self, messages: list[dict], *, tools: list[dict] | None = None, json_mode: bool = False,
             temperature: float = 0.0, model: str | None = None, max_tokens: int = 2000) -> LLMResult: ...
```

`backend/app/llm/deepseek.py`:

```python
import json
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.app.core.config import get_settings
from .base import LLMResult, ToolCall

class DeepSeekClient:
    def __init__(self):
        s = get_settings()
        self.c = OpenAI(api_key=s.deepseek_api_key, base_url=s.deepseek_base_url, timeout=90)
        self.default_model = s.llm_model_fast

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def chat(self, messages, *, tools=None, json_mode=False, temperature=0.0, model=None, max_tokens=2000) -> LLMResult:
        kw = dict(model=model or self.default_model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        if tools: kw["tools"] = tools
        if json_mode: kw["response_format"] = {"type": "json_object"}   # prompt must contain the word "json"
        r = self.c.chat.completions.create(**kw)
        m = r.choices[0].message
        calls = [ToolCall(tc.id, tc.function.name, json.loads(tc.function.arguments or "{}")) for tc in (m.tool_calls or [])]
        return LLMResult(m.content, calls, r.usage.prompt_tokens, r.usage.completion_tokens, m.model_dump(exclude_none=True))

def get_llm():
    return DeepSeekClient()      # later: switch on settings.llm_provider (OpenAI-compatible, Ollama, etc.)
```

Also implement `FakeLLM` (returns canned JSON) used by tests so the pipeline is testable offline and without cost.

Cost tracking: `cost = tokens_in/1e6*price_in + tokens_out/1e6*price_out`, with prices from settings.

### Checkpoint 7
- A 10-line script gets a reply from DeepSeek, and a second script makes it emit a tool call for a dummy `get_time` function and parses it correctly.

---

## Phase 8 — Hybrid retrieval

### 8.1 Filters

`backend/app/schemas/filters.py`:

```python
from datetime import datetime
from pydantic import BaseModel
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range

class Filters(BaseModel):
    project: list[str] | None = None
    category: list[str] | None = None
    priority: list[str] | None = None
    status: list[str] | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    has_conversation: bool | None = None
    doc_types: list[str] | None = None

    def to_qdrant(self) -> Filter | None:
        must = []
        for f in ("project", "category", "priority", "status"):
            v = getattr(self, f)
            if v: must.append(FieldCondition(key=f, match=MatchAny(any=v)))
        if self.doc_types: must.append(FieldCondition(key="doc_type", match=MatchAny(any=self.doc_types)))
        if self.has_conversation is not None: must.append(FieldCondition(key="has_conversation", match=MatchValue(value=self.has_conversation)))
        if self.created_from or self.created_to:
            must.append(FieldCondition(key="created_ts", range=Range(gte=int(self.created_from.timestamp()) if self.created_from else None, lte=int(self.created_to.timestamp()) if self.created_to else None)))
        return Filter(must=must) if must else None
```

**Filter values must exist.** LLM-extracted filter values are validated against `SELECT DISTINCT category/priority/project` from Postgres (cached). Invalid values are dropped and logged, never sent as a filter that silently returns nothing.

### 8.2 Hit model and single-strategy retrievers

`backend/app/retrieval/pipeline.py` (types and retrievers):

```python
from dataclasses import dataclass, field
from backend.app.vectorstore.qdrant_store import client
from backend.app.embeddings.encoder import embed_query
from backend.app.embeddings.sparse import sparse_query
from backend.app.core.config import get_settings

@dataclass
class Hit:
    id: str; ticket_id: str; doc_type: str; text: str; payload: dict
    scores: dict[str, float] = field(default_factory=dict)   # dense, bm25, rrf, rerank
    ranks: dict[str, int] = field(default_factory=dict)

def _to_hits(points, name: str) -> list[Hit]:
    hits = []
    for r, p in enumerate(points, 1):
        pl = p.payload or {}
        hits.append(Hit(str(p.id), pl["ticket_id"], pl["doc_type"], pl.get("text", ""), pl, {name: p.score}, {name: r}))
    return hits

def dense_search(q: str, flt, limit: int) -> list[Hit]:
    r = client().query_points(get_settings().qdrant_collection, query=embed_query(q).tolist(), using="dense", query_filter=flt, limit=limit, with_payload=True)
    return _to_hits(r.points, "dense")

def sparse_search(q: str, flt, limit: int) -> list[Hit]:
    r = client().query_points(get_settings().qdrant_collection, query=sparse_query(q), using="bm25", query_filter=flt, limit=limit, with_payload=True)
    return _to_hits(r.points, "bm25")
```

Important: put the chunk text in the Qdrant payload (`payload["text"]`) when indexing, or fetch from Postgres by `doc_id`. Pick one and document the trade-off (payload = faster reads; Postgres = single source of truth). Recommended: store in payload, Postgres remains the source of truth for rebuilds. Update `indexer.py` payload accordingly.

### 8.3 Reciprocal Rank Fusion (own implementation)

`backend/app/retrieval/fusion.py`:

```python
from collections import defaultdict
from .pipeline import Hit

def rrf(rankings: list[list[Hit]], k: int = 60, weights: list[float] | None = None) -> list[Hit]:
    """score(d) = Σ_i w_i / (k + rank_i(d)).  Rank-based, so BM25 and cosine scales never need normalization."""
    weights = weights or [1.0] * len(rankings)
    score, best = defaultdict(float), {}
    for w, lst in zip(weights, rankings):
        for r, h in enumerate(lst, 1):
            score[h.id] += w / (k + r)
            if h.id not in best: best[h.id] = h
            else: best[h.id].scores.update(h.scores); best[h.id].ranks.update(h.ranks)
    fused = sorted(best.values(), key=lambda h: score[h.id], reverse=True)
    for r, h in enumerate(fused, 1): h.scores["rrf"], h.ranks["rrf"] = score[h.id], r
    return fused
```

Also implement `qdrant_native_hybrid()` using `prefetch=[Prefetch(query=dense, using="dense", limit=50), Prefetch(query=sparse, using="bm25", limit=50)]` and `query=FusionQuery(fusion=Fusion.RRF)`. You will compare both in Phase 12; being able to say "my client-side RRF matched the native one within X Recall@10 and gave me per-stage inspectability" is a strong interview answer.

### 8.4 Query rewriting, expansion, filter extraction

`backend/app/retrieval/rewrite.py`:

```python
import json
from backend.app.llm.deepseek import get_llm

SYS = """You prepare search queries for a customer-support ticket database.
Return JSON only: {"standalone": str, "variants": [str, str], "filters": {"category": [..], "priority": [..], "project": [..], "created_from": "YYYY-MM-DD"|null, "created_to": "YYYY-MM-DD"|null}}
- standalone: the question rewritten so it needs no chat history.
- variants: 2 alternative phrasings using different vocabulary (synonyms, symptoms vs causes). Do not add facts not implied by the question.
- filters: ONLY if the user explicitly constrained them. Allowed values: {allowed}. Otherwise empty."""

def rewrite(question: str, history: list[dict], allowed: dict) -> dict:
    msgs = [{"role": "system", "content": SYS.replace("{allowed}", json.dumps(allowed)[:3000])},
            {"role": "user", "content": json.dumps({"history": history[-6:], "question": question})}]
    out = get_llm().chat(msgs, json_mode=True)
    try: return json.loads(out.content)
    except Exception: return {"standalone": question, "variants": [], "filters": {}}   # fail open
```

### 8.5 Cross-encoder reranker

`backend/app/retrieval/rerank.py`:

```python
from functools import lru_cache
from sentence_transformers import CrossEncoder
from backend.app.core.config import get_settings

@lru_cache
def _ce(): return CrossEncoder(get_settings().rerank_model, max_length=512)

def rerank(query: str, hits, top_n: int):
    if not hits: return hits
    scores = _ce().predict([(query, h.text) for h in hits], batch_size=16)
    for h, s in zip(hits, scores): h.scores["rerank"] = float(s)
    out = sorted(hits, key=lambda h: h.scores["rerank"], reverse=True)[:top_n]
    for r, h in enumerate(out, 1): h.ranks["rerank"] = r
    return out
```

### 8.6 Pipeline with per-stage capture

Extend `pipeline.py`:

```python
import time
from .fusion import rrf
from .rewrite import rewrite
from .rerank import rerank

def search(question, options, history=None, filters=None, allowed=None, do_rewrite=True, do_rerank=True, n_candidates=50):
    t, stages = {}, {}
    def tick(name, t0): t[name] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    rw = rewrite(question, history or [], allowed or {}) if do_rewrite else {"standalone": question, "variants": [], "filters": {}}
    queries = [rw["standalone"], *rw.get("variants", [])[:2]]; tick("rewrite", t0)
    flt = (filters or Filters()).to_qdrant()

    t0 = time.perf_counter(); lists = []
    for q in queries:
        if options.mode in ("dense", "hybrid"): lists.append(dense_search(q, flt, n_candidates))
        if options.mode in ("bm25", "hybrid"):  lists.append(sparse_search(q, flt, n_candidates))
    tick("retrieve", t0); stages["retrieved"] = lists

    t0 = time.perf_counter(); fused = rrf(lists)[:n_candidates] if len(lists) > 1 else lists[0]; tick("fuse", t0); stages["fused"] = fused
    t0 = time.perf_counter(); final = rerank(rw["standalone"], fused, options.top_k * 2) if do_rerank else fused[: options.top_k * 2]; tick("rerank", t0); stages["reranked"] = final
    return {"rewrite": rw, "stages": stages, "hits": final, "timings_ms": t}
```

### 8.7 Context assembly

`backend/app/retrieval/assemble.py`:

1. **Collapse** near-duplicates (same `ticket_id` + overlapping chunk range); keep max 3 chunks per ticket so one noisy ticket cannot crowd out the rest.
2. **Parent expansion:** fetch ticket facts (`ticket_facts` row) for each distinct ticket from Postgres and attach as `ticket_facts`.
3. **Token budget:** accumulate evidence in rank order until ~6,000 tokens (configurable).
4. **Label** items `E1…En` in rank order. Each `EvidenceItem` includes `has_conversation` so the model and UI know when no conversation exists.
5. Return `list[EvidenceItem]` (schema in Phase 2).

### Checkpoint 8
- CLI `python scripts/ask.py --retrieve "user cannot log in after update" --mode hybrid` prints the four stages with scores and rank movement.
- Same query run with `dense`, `bm25`, `hybrid`: you can see cases where each wins (this becomes a table in `docs/EVALUATION.md`).
- Filter test: a query with `priority=<real value>` returns only that priority.

---
## Phase 9 — SQL analytics (semantic layer) and Python charts

### 9.1 Semantic layer

`configs/semantic_layer.yaml` (adjust to columns that really exist per profiling):

```yaml
source: ticket_facts
dimensions:
  category:       {expr: "category",   kind: categorical}
  priority:       {expr: "priority",   kind: categorical}
  project:        {expr: "project_id", kind: categorical}
  status:         {expr: "status",     kind: categorical}
  has_conversation: {expr: "has_conversation", kind: categorical}
  created_day:    {expr: "date_trunc('day', created_at)",     kind: time}
  created_week:   {expr: "date_trunc('week', created_at)",    kind: time}
  created_month:  {expr: "date_trunc('month', created_at)",   kind: time}
  created_quarter:{expr: "date_trunc('quarter', created_at)", kind: time}
  created_year:   {expr: "date_trunc('year', created_at)",    kind: time}
metrics:
  ticket_count:             {expr: "COUNT(*)", unit: tickets}
  resolved_count:           {expr: "COUNT(*) FILTER (WHERE is_resolved)", unit: tickets}
  avg_resolution_hours:     {expr: "AVG(resolution_hours)", unit: hours, needs_non_null: resolution_hours}
  median_resolution_hours:  {expr: "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY resolution_hours)", unit: hours, needs_non_null: resolution_hours}
  p90_resolution_hours:     {expr: "PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY resolution_hours)", unit: hours, needs_non_null: resolution_hours}
  avg_reassignments:        {expr: "AVG(n_reassignments)", unit: count}
max_rows: 500
```

### 9.2 Query builder

`backend/app/analytics/query_builder.py`:

```python
import uuid
from dataclasses import dataclass, field
from datetime import date
import pandas as pd, yaml
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from backend.app.core.config import get_settings

SL = yaml.safe_load(open("configs/semantic_layer.yaml"))
_engine = None
def ro_engine():
    global _engine
    if _engine is None:
        s = get_settings()
        _engine = create_engine(s.readonly_database_url or s.database_url, connect_args={"options": "-c statement_timeout=15000"})
    return _engine

class AnalyticsArgs(BaseModel):
    metric: str
    dimension: str | None = None
    second_dimension: str | None = None            # for grouped charts (e.g. month × priority)
    filters: dict[str, list[str]] = Field(default_factory=dict)   # {"priority": ["High"], "category": [...]}
    date_from: date | None = None
    date_to: date | None = None
    order_by: str | None = None                    # a metric or dimension name
    descending: bool = True
    limit: int = 50

@dataclass
class AnalyticsResult:
    result_id: str; df: pd.DataFrame; sql: str; params: dict; caveats: list[str] = field(default_factory=list)

class AnalyticsError(ValueError): pass

def run_analytics(a: AnalyticsArgs, ref_id: str) -> AnalyticsResult:
    m, D = SL["metrics"], SL["dimensions"]
    if a.metric not in m: raise AnalyticsError(f"unknown metric '{a.metric}'. valid: {sorted(m)}")
    dims = [d for d in (a.dimension, a.second_dimension) if d]
    for d in dims + list(a.filters):
        if d not in D: raise AnalyticsError(f"unknown dimension '{d}'. valid: {sorted(D)}")
    sel = [f"{D[d]['expr']} AS {d}" for d in dims] + [f"{m[a.metric]['expr']} AS {a.metric}"]
    where, params = [], {}
    for i, (d, vals) in enumerate(a.filters.items()):
        where.append(f"{D[d]['expr']} = ANY(:f{i})"); params[f"f{i}"] = vals
    if a.date_from: where.append("created_at >= :df"); params["df"] = a.date_from
    if a.date_to:   where.append("created_at <  :dt"); params["dt"] = a.date_to
    nn = m[a.metric].get("needs_non_null")
    if nn: where.append(f"{nn} IS NOT NULL")
    order = a.order_by or (dims[0] if dims and D[dims[0]]["kind"] == "time" else a.metric)
    if order not in m and order not in D: raise AnalyticsError(f"bad order_by '{order}'")
    direction = "ASC" if (order in D and D[order]["kind"] == "time") else ("DESC" if a.descending else "ASC")
    limit = min(a.limit, SL["max_rows"])
    sql = f"SELECT {', '.join(sel)} FROM {SL['source']}" + (f" WHERE {' AND '.join(where)}" if where else "") \
        + (f" GROUP BY {', '.join(str(i+1) for i in range(len(dims)))}" if dims else "") + f" ORDER BY {order} {direction} LIMIT {limit}"
    with ro_engine().connect() as c:
        df = pd.read_sql(text(sql), c, params=params)
        caveats = []
        if nn:
            tot, ok = c.execute(text(f"SELECT COUNT(*), COUNT({nn}) FROM {SL['source']}")).one()
            caveats.append(f"{m[a.metric]['unit']} computed only for {ok:,} of {tot:,} tickets that have a valid {nn}.")
        if len(df) == limit: caveats.append(f"Result truncated at {limit} rows.")
    return AnalyticsResult(ref_id, df, sql, {**a.model_dump(mode="json")}, caveats)
```

Safety properties to state in interviews: identifiers come only from YAML (never from LLM strings), values are bound parameters, a read-only role with `statement_timeout`, row cap, and **coverage caveats attached automatically** so the answer cannot overstate a partial metric.

### 9.3 Optional fallback: guarded text-to-SQL

Only if the semantic layer cannot express a question. `analytics/sql_guard.py` with `sqlglot`: parse → must be exactly one `SELECT` → every table ∈ {`ticket_facts`, `dataset_coverage`} → no `;` chains, no `pg_*`/`information_schema` → inject `LIMIT` → execute with the read-only role. Log every use; in evaluation report how often the fallback fires and its accuracy. Keep it **disabled by default**.

### 9.4 Chart builder (Python, Plotly)

`backend/app/viz/chart_builder.py`:

```python
import json
import pandas as pd
import plotly.express as px, plotly.graph_objects as go
from typing import Literal
from pydantic import BaseModel

class ChartSpec(BaseModel):
    result_id: str
    chart_type: Literal["bar", "hbar", "line", "area", "pie", "donut", "scatter", "grouped_bar", "stacked_bar", "table"]
    x: str | None = None
    y: str | None = None
    color: str | None = None
    title: str
    top_n: int | None = None            # keep top N categories; the rest are summarized as "Other" IF y is additive

PALETTE = ["#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]
ADDITIVE = {"ticket_count", "resolved_count"}

class ChartError(ValueError): pass

def build_figure(df: pd.DataFrame, s: ChartSpec) -> go.Figure:
    cols = set(df.columns)
    for name in (s.x, s.y, s.color):
        if name and name not in cols: raise ChartError(f"column '{name}' not in result. columns: {sorted(cols)}")
    if s.chart_type != "table" and (not s.x or not s.y): raise ChartError("x and y are required")
    if s.y and not pd.api.types.is_numeric_dtype(df[s.y]): raise ChartError(f"y column '{s.y}' is not numeric")
    d = df.copy()
    if s.top_n and s.x and len(d) > s.top_n:
        d = d.nlargest(s.top_n, s.y)
        if s.y in ADDITIVE:
            other = df.drop(d.index)[s.y].sum(); d = pd.concat([d, pd.DataFrame({s.x: ["Other"], s.y: [other]})])
    kw = dict(x=s.x, y=s.y, color=s.color, title=s.title, color_discrete_sequence=PALETTE)
    t = s.chart_type
    if   t == "bar":          fig = px.bar(d, **kw)
    elif t == "hbar":         fig = px.bar(d.sort_values(s.y), x=s.y, y=s.x, orientation="h", title=s.title, color_discrete_sequence=PALETTE)
    elif t == "grouped_bar":  fig = px.bar(d, barmode="group", **kw)
    elif t == "stacked_bar":  fig = px.bar(d, barmode="stack", **kw)
    elif t == "line":         fig = px.line(d.sort_values(s.x), markers=True, **kw)
    elif t == "area":         fig = px.area(d.sort_values(s.x), **kw)
    elif t == "scatter":      fig = px.scatter(d, **kw)
    elif t in ("pie", "donut"): fig = px.pie(d, names=s.x, values=s.y, hole=0.45 if t == "donut" else 0, title=s.title, color_discrete_sequence=PALETTE)
    else: fig = go.Figure(go.Table(header=dict(values=list(d.columns)), cells=dict(values=[d[c] for c in d.columns])))
    fig.update_layout(template="plotly_white", font=dict(family="Inter, system-ui, sans-serif", size=13), margin=dict(t=56, r=16, b=48, l=56), legend_title_text="")
    return fig

def figure_json(fig: go.Figure) -> dict:
    return json.loads(fig.to_json())          # converts numpy/pandas types safely

def to_table_payload(df: pd.DataFrame, max_rows: int = 200):
    d = df.head(max_rows).copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]): d[c] = d[c].dt.strftime("%Y-%m-%d")
    return {"columns": list(d.columns), "rows": d.where(d.notna(), None).values.tolist()}
```

Guarantee to test (**chart/data consistency**): for any chart, the y-values inside `figure.data` equal the values in `table.rows`. If someone edits the builder and breaks this, the test fails.

### Checkpoint 9
- A script runs `AnalyticsArgs(metric="ticket_count", dimension="created_month")`, builds a `line` chart, writes `fig.write_html("test.html")`; open it; numbers match a hand-written SQL query in `psql`.
- Invalid metric/dimension/column produce clear `AnalyticsError`/`ChartError` messages (the agent will use these to self-correct).
- Pytest: SQL injection attempt in a filter value (`"'; DROP TABLE tickets;--"`) returns an empty result, nothing breaks.

---

## Phase 10 — LangGraph agent

### 10.1 Tools (what DeepSeek can call)

`backend/app/agent/tools.py`:

```python
from pydantic import BaseModel, Field
from backend.app.analytics.query_builder import AnalyticsArgs
from backend.app.viz.chart_builder import ChartSpec

class SearchArgs(BaseModel):
    query: str = Field(description="What to look for, in natural language")
    priority: list[str] | None = None
    category: list[str] | None = None
    project: list[str] | None = None
    created_from: str | None = None
    created_to: str | None = None
    has_conversation: bool | None = None

class GetTicketArgs(BaseModel): ticket_id: str
class TicketHistoryArgs(BaseModel): ticket_id: str

def spec(name: str, desc: str, model) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": model.model_json_schema()}}

TOOLS = {
  "analytics_query": spec("analytics_query", "Run a structured aggregation over ticket data (counts, averages, trends). Use for ANY number, count, rate or distribution. Returns a table with result_id like D1.", AnalyticsArgs),
  "render_chart":    spec("render_chart", "Render a chart from a previous analytics result_id. Never invent data; only reference columns of that result.", ChartSpec),
  "search_tickets":  spec("search_tickets", "Semantic + keyword search over ticket summaries and available conversation messages. Use for similar issues, examples, root-cause themes.", SearchArgs),
  "get_ticket":      spec("get_ticket", "Fetch the structured facts and any available messages of one ticket.", GetTicketArgs),
  "get_ticket_history": spec("get_ticket_history", "Fetch the assignment/status change history of one ticket.", TicketHistoryArgs),
}
ROUTE_TOOLS = {
  "analytics":   ["analytics_query", "render_chart"],
  "semantic":    ["search_tickets", "get_ticket", "get_ticket_history"],
  "investigate": list(TOOLS),
}
```

Pydantic generates the JSON schema, so tool definitions and validation come from a single source of truth.

### 10.2 State

`backend/app/agent/state.py`:

```python
from typing import Any, TypedDict

class AgentState(TypedDict, total=False):
    question: str
    history: list[dict]
    options: dict
    route: str                         # analytics | semantic | investigate | out_of_scope
    standalone_question: str
    transcript: list[dict]             # tool-loop messages
    iterations: int
    results: dict[str, Any]            # "D1" -> AnalyticsResult
    charts: list[dict]
    evidence: list[dict]               # EvidenceItem dicts (E1..)
    answer: dict | None                # {"answer_markdown", "findings", "follow_ups"}
    verification: dict | None
    repair_attempts: int
    trace: list[dict]
    tokens_in: int
    tokens_out: int
```

### 10.3 Prompts (the guardrails live here)

`backend/app/llm/prompts.py`:

```python
PLAN_SYS = """You are the planner of a customer-support analytics assistant. Classify the user's latest question.
Return JSON only: {"route": "analytics"|"semantic"|"investigate"|"out_of_scope", "standalone_question": str, "reason": str}
- analytics: needs counts, averages, trends, distributions, comparisons, or any chart.
- semantic: asks for similar tickets, examples, common complaints, what customers said.
- investigate: needs both numbers and examples, or a 'why' question.
- out_of_scope: unrelated to the support ticket data (answer politely that you can only analyze the loaded ticket data).
standalone_question must be self-contained using the chat history."""

AGENT_SYS = """You are SupportLens, an analyst over a historical help-desk dataset. You can ONLY use the provided tools.
RULES
1. Never state a number, count, date or ticket id that did not come from a tool result. If you need a number, call analytics_query.
2. Tool calls are cheap: prefer 1-4 well-chosen calls. If a tool returns an error, read the message and correct your call.
3. To show a chart, first call analytics_query, then render_chart with the returned result_id and real column names.
4. DATA COVERAGE (verified from the database): {coverage}
   Conversations exist only for a subset of tickets. Never infer customer identity, product, or message content that is not in tool output.
5. Stop calling tools when you have enough evidence."""

COMPOSE_SYS = """Write the final answer for the user as JSON only (the word json is required):
{"answer_markdown": str, "findings": [{"statement": str, "status": "verified"|"hypothesis"|"unavailable", "citations": ["D1","E3"]}], "follow_ups": [str, str]}
RULES
- Cite with [D#] for analytics results and [E#] for ticket evidence, inline, immediately after the claim.
- status=verified ONLY if directly supported by a cited item. status=hypothesis for reasonable interpretation, and say so in plain words. status=unavailable for anything the data cannot answer (state what is missing).
- Every number in answer_markdown must appear in the provided results. Do not compute new numbers except trivial differences/percentages of cited values, and cite both sources.
- Mention caveats provided with results (e.g. metric computed on a subset).
- If charts were rendered, refer to them by id (e.g. 'see D1') and explain the pattern briefly. Do not describe values that are not in the table.
- Be concise: a short direct answer first, then supporting detail."""
```

### 10.4 Nodes

`backend/app/agent/nodes.py` — implement as follows (full code is straightforward; the contracts matter):

```python
def plan_node(state):          # LLM json_mode → route, standalone_question; appends trace step
def agent_node(state):         # LLM call with tools = ROUTE_TOOLS[route]; appends assistant message to transcript
def exec_tools_node(state):    # runs every tool_call; appends tool messages; updates results/charts/evidence
def compose_node(state):       # LLM json_mode with COMPOSE_SYS + digest of results/evidence → state["answer"]
def verify_node(state):        # programmatic checks (see 10.6) → state["verification"]
def refuse_node(state):        # fixed polite out-of-scope answer, no data claims
```

`exec_tools_node` dispatch details:

```python
def exec_one(call, state):
    try:
        if call.name == "analytics_query":
            ref = f"D{len(state['results'])+1}"
            res = run_analytics(AnalyticsArgs(**call.arguments), ref); state["results"][ref] = res
            return f"{ref}: {len(res.df)} rows. caveats={res.caveats}\n" + res.df.head(50).to_markdown(index=False)
        if call.name == "render_chart":
            s = ChartSpec(**call.arguments); res = state["results"][s.result_id]     # KeyError → handled below
            fig = build_figure(res.df, s)
            state["charts"].append({"chart_id": s.result_id, "title": s.title, "chart_type": s.chart_type,
                                    "figure": figure_json(fig), "table": to_table_payload(res.df),
                                    "provenance": {"tool": "analytics_query", "params": res.params, "sql": res.sql, "row_count": len(res.df), "caveats": res.caveats}})
            return f"chart for {s.result_id} rendered"
        if call.name == "search_tickets":
            out = retrieval.search(...); items = assemble(out["hits"], start=len(state["evidence"])+1)
            state["evidence"] += [i.model_dump() for i in items]
            return "\n\n".join(f"[{i.ref_id}] ticket {i.ticket_id} ({i.doc_type}; conversation={'yes' if i.has_conversation else 'no'})\n{i.text[:700]}" for i in items)
        # get_ticket / get_ticket_history: read from Postgres, return text, register as evidence items too
    except Exception as e:                       # never crash the loop; give the model a chance to repair
        return f"TOOL_ERROR: {type(e).__name__}: {e}"
```

Rules inside the loop:
- `MAX_ITERATIONS`: 4 for `fast`, 8 for `thorough`; after the cap, force the graph to `compose` with what it has.
- Tool outputs passed back to the LLM are **truncated** (50 rows / ~700 chars per evidence); the full data stays in `state` and goes to the UI.
- Always record per-node timing and token usage in `state["trace"]`.

### 10.5 Graph

`backend/app/agent/graph.py`:

```python
from langgraph.graph import StateGraph, END
from .state import AgentState
from . import nodes

MAX = {"fast": 4, "thorough": 8}

def after_plan(s): return "refuse" if s["route"] == "out_of_scope" else "agent"
def after_agent(s):
    wants_tools = bool(s["transcript"][-1].get("tool_calls"))
    return "exec_tools" if wants_tools and s["iterations"] < MAX[s["options"]["effort"]] else "compose"
def after_verify(s): return "compose" if (not s["verification"]["ok"] and s["repair_attempts"] < 1) else END

g = StateGraph(AgentState)
for name, fn in [("plan", nodes.plan_node), ("agent", nodes.agent_node), ("exec_tools", nodes.exec_tools_node),
                 ("compose", nodes.compose_node), ("verify", nodes.verify_node), ("refuse", nodes.refuse_node)]:
    g.add_node(name, fn)
g.set_entry_point("plan")
g.add_conditional_edges("plan", after_plan, {"agent": "agent", "refuse": "refuse"})
g.add_conditional_edges("agent", after_agent, {"exec_tools": "exec_tools", "compose": "compose"})
g.add_edge("exec_tools", "agent")
g.add_edge("compose", "verify")
g.add_conditional_edges("verify", after_verify, {"compose": "compose", END: END})
g.add_edge("refuse", END)
agent = g.compile()
```

### 10.6 Grounding verification (the anti-hallucination layer)

`backend/app/agent/grounding.py`:

```python
import re
NUM = re.compile(r"(?<![\w.#\[])\d[\d,]*\.?\d*%?")
CITE = re.compile(r"\[((?:E|D)\d+)\]")

def numbers_in(text: str) -> list[float]:
    t = CITE.sub("", text)
    out = []
    for m in NUM.findall(t):
        try: out.append(float(m.replace(",", "").rstrip("%")))
        except ValueError: pass
    return out

def allowed_numbers(results: dict, evidence: list[dict]) -> set[float]:
    ok = set()
    for res in results.values():
        df = res.df; ok.add(float(len(df)))
        for c in df.select_dtypes("number").columns:
            col = df[c].dropna()
            for v in col: ok |= {float(v), round(float(v), 0), round(float(v), 1), round(float(v), 2)}
            tot = col.sum()
            if tot: ok |= {round(float(v) / tot * 100, p) for v in col for p in (0, 1)}     # shares
            ok |= {float(tot), round(float(col.mean()), 1), round(float(col.max() - col.min()), 1)}
    for e in evidence:
        ok |= set(numbers_in(e["text"]))
    return ok

def verify(answer: dict, results: dict, evidence: list[dict], ticket_id_re: str) -> dict:
    issues, text = [], answer["answer_markdown"]
    valid_refs = set(results) | {e["ref_id"] for e in evidence}
    cited = set(CITE.findall(text)) | {c for f in answer["findings"] for c in f["citations"]}
    for c in cited - valid_refs: issues.append(f"citation {c} does not exist")
    for f in answer["findings"]:
        if f["status"] == "verified" and not f["citations"]: issues.append(f"verified finding without citation: {f['statement'][:60]}")
    allowed = allowed_numbers(results, evidence)
    for n in numbers_in(text):
        if n <= 10 or 1990 <= n <= 2100: continue                       # small ordinals / years: heuristic, documented
        if not any(abs(n - a) <= max(0.005 * abs(a), 0.051) for a in allowed): issues.append(f"number {n:g} not found in tool output")
    known_ids = {e["ticket_id"] for e in evidence}
    for tid in set(re.findall(ticket_id_re, text)):
        if tid not in known_ids: issues.append(f"ticket id {tid} not in retrieved evidence")
    return {"ok": not issues, "issues": issues}
```

On failure, `compose_node` is re-run **once** with the issue list appended ("Fix these problems; remove claims you cannot support"). If still failing, the response is returned **with the issues shown in the UI** (the amber warning in `MessageView`). That is honest behavior and a good interview talking point. Mark `cited=True` on evidence items referenced in the final answer.

Known limitation to document: the numeric check is heuristic (it catches invented numbers, not subtle misreadings). The LLM-judge faithfulness metric in Phase 12 measures the rest.

### 10.7 Entry point and persistence

`backend/app/api/routes_chat.py`:

```python
@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    cid = req.conversation_id or str(uuid4())
    history = load_history(cid)                              # last N messages from Postgres
    state = await agent.ainvoke({"question": req.message, "history": history, "options": req.options.model_dump(),
                                 "results": {}, "charts": [], "evidence": [], "transcript": [], "iterations": 0,
                                 "repair_attempts": 0, "trace": [], "tokens_in": 0, "tokens_out": 0})
    resp = build_response(cid, state)                        # maps state → ChatResponse, computes cost, total_ms
    save_turn(cid, req.message, resp)
    return resp
```

Also create `scripts/ask.py "question"` to run the agent from the terminal and print the JSON trace; most of your debugging happens there, not in the browser.

### Checkpoint 10 — run these 8 questions through `ask.py`
1. "How many tickets were created per month?" → analytics only; matches psql.
2. "Show a bar chart of tickets by priority." → chart built; numbers match.
3. "Compare average resolution time by category." → includes a **coverage caveat**.
4. "Find tickets similar to a user who cannot log in after an update." → evidence with `E#` citations.
5. "Which customer complained the most?" → answers **unavailable** (no customer identity in the data) instead of inventing.
6. "What is the weather in Paris?" → polite out-of-scope refusal.
7. "Why did volume spike in <a real month>?" → investigate: uses SQL + examples, labels hypotheses as hypotheses.
8. A follow-up ("break that down by priority") → uses chat history correctly.

---

## Phase 11 — Wire the complete UI

### 11.1 Switch off mock mode, verify end-to-end
`VITE_USE_MOCK=false`, backend running. Ask the Phase 10 questions in the browser. Charts must render in the same thread beneath the explanation.

### 11.2 Streaming progress (recommended)
Add `POST /api/chat/stream` using FastAPI `StreamingResponse` (SSE). Use `agent.astream(state, stream_mode="updates")` and emit `{"event":"step","name":"analytics_query","ms":35}` per node, then `{"event":"final","data":<ChatResponse>}`. In the UI show live status lines ("Planning → Querying database → Retrieving → Reranking → Writing"). Read with `fetch` + `ReadableStream` and parse `data:` lines.

### 11.3 Ticket Explorer page
Backend:
- `GET /api/tickets?q=&priority=&category=&project=&from=&to=&page=` → paginated list from `ticket_facts` (+ text search over title via `ILIKE`).
- `GET /api/tickets/{id}` → facts, `events` (ordered), `utterances` (ordered; empty array if none, plus `"conversation_available": false`).

Frontend `pages/Explorer.tsx`: filter bar + virtual table + right-side detail panel with timeline (status/assignment changes) and conversation (or the explicit text "No conversation exists for this ticket in the dataset").

### 11.4 Retrieval Inspector page
Backend: `POST /api/retrieval/debug` `{query, mode, top_k, do_rewrite, do_rerank}` → returns `rewrite`, every stage list with scores and ranks, timings.
Frontend `pages/Inspector.tsx`: four columns **Dense → BM25 → RRF fused → Reranked**; each row shows ticket id, snippet, score, and a **rank-movement badge** (e.g. "↑ 14 → 2 after rerank"). Toggles for rewrite/rerank. This page is your best demo asset: it visibly proves hybrid + rerank do something.

### 11.5 Finishing touches
- Persist conversations server-side (already in `conversations`/`messages`), load Recents from `GET /api/conversations`.
- Evidence drawer shows `cited` vs `not cited`, so users see what the model was given versus what it used.
- Error states: backend down, LLM timeout (show retry), empty result ("No tickets match these filters").
- Keyboard: Enter sends, Shift+Enter newline; Esc closes the drawer.

### Checkpoint 11
Screen-record a 2-minute demo: ask for a chart, ask a follow-up, open the evidence drawer, open the Inspector on the same query. This becomes your README GIF.

---

## Phase 12 — Evaluation (this is what makes the project credible)

Rule: **tune on dev, report on test.** Never report numbers on data you tuned against.

### 12.1 Datasets

| File | Contents | Size target |
|---|---|---|
| `retrieval_dev.jsonl` / `retrieval_test.jsonl` | `{qid, question, gold_ticket_ids, type}` | 150 dev / 150 test |
| `analytics.jsonl` | `{qid, question, expected_args, golden_sql, expected_result}` hand-written | 30–40 |
| `e2e.jsonl` | mixed questions incl. unanswerable/out-of-scope; `{qid, question, must_cite?, expect_status}` | 40–60 |

**Retrieval set generation** (`evaluation/generate_dataset.py`): sample tickets that have conversations, stratified by category/priority/project. For each, prompt DeepSeek with the ticket text and ask for 2 questions a support analyst might type (one symptom-style, one theme-style) **without copying distinctive phrases or ids**. Gold = the source ticket. Then:
1. **Manually review at least 30%** and fix/drop bad ones.
2. Add 30+ **hand-written** questions.
3. Be aware: other tickets can also be valid answers, so Recall/Precision are **lower bounds**. State this limitation in `EVALUATION.md`.
4. Synthetic questions that reuse the source wording inflate BM25; check lexical overlap and filter high-overlap questions.

### 12.2 Metrics (ticket level: collapse chunk hits to unique tickets in rank order)

`evaluation/metrics.py`:

```python
import math

def collapse(ranked_ticket_ids: list[str]) -> list[str]:
    seen, out = set(), []
    for t in ranked_ticket_ids:
        if t not in seen: seen.add(t); out.append(t)
    return out

def recall_at_k(ranked, gold: set, k): return len(set(ranked[:k]) & gold) / len(gold)
def precision_at_k(ranked, gold: set, k): return len(set(ranked[:k]) & gold) / k
def mrr(ranked, gold: set):
    for i, t in enumerate(ranked, 1):
        if t in gold: return 1.0 / i
    return 0.0
def ndcg_at_k(ranked, gold: set, k):
    dcg = sum(1 / math.log2(i + 1) for i, t in enumerate(ranked[:k], 1) if t in gold)
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / idcg if idcg else 0.0
```

Add a bootstrap confidence interval helper (resample queries 1,000×, report 95% CI). Differences smaller than the CI are **not** claims.

### 12.3 Retrieval ablation matrix (`run_retrieval_eval.py`, configs from YAML)

| ID | Dense | BM25 | Fusion | Rewrite | Expansion | Rerank | Notes |
|---|---|---|---|---|---|---|---|
| R1 | ✓ | | | | | | baseline |
| R2 | | ✓ | | | | | baseline |
| R3 | ✓ | ✓ | RRF | | | | |
| R4 | ✓ | ✓ | Qdrant-native RRF | | | | compare with R3 |
| R5 | ✓ | ✓ | RRF | | | ✓ | |
| R6 | ✓ | ✓ | RRF | ✓ | | ✓ | |
| R7 | ✓ | ✓ | RRF | ✓ | ✓ | ✓ | full pipeline |

Further sweeps: chunk size (128/256/512 tokens), overlap (0/1 turns), RRF `k` (20/60/100), candidate pool (20/50/100), embedding model (BGE-M3 vs a small model), reranker top-n. Record for each run: Recall@{1,5,10}, Precision@5, MRR, NDCG@10, **latency p50/p95**, and the number of LLM calls (cost). Write `results/retrieval_<timestamp>.json` and auto-generate a markdown table plus a Plotly bar chart for `docs/EVALUATION.md`.

### 12.4 Analytics evaluation (`run_analytics_eval.py`)
Run each question through the agent in `analytics` mode, capture the `AnalyticsArgs` and the resulting DataFrame. Score:
- **Tool accuracy:** metric + dimension match expected.
- **Numeric exactness:** result equals the golden SQL output.
- **Chart validity:** correct type family, columns exist, chart/data consistency.
- **Fallback rate** if text-to-SQL is enabled.

### 12.5 End-to-end generation evaluation (`run_e2e_eval.py`)

| Metric | How |
|---|---|
| **Faithfulness** | Judge LLM splits the answer into atomic claims; for each, checks support in the supplied evidence/results; score = supported / total |
| **Answer relevance** | Judge rubric 1–5 against the question (with a written rubric; report mean and distribution) |
| **Citation accuracy** | (a) *validity*: cited IDs exist (programmatic); (b) *precision*: cited item actually supports the sentence (judge); (c) *recall*: share of claims with ≥1 valid citation |
| **Abstention correctness** | On unanswerable questions (customer names, product, future dates), the answer must say unavailable; score pass/fail |
| **Numeric grounding** | share of answers where the Phase 10 verifier passes on the first attempt |
| **Latency** | p50/p95 total and per-node |
| **Cost** | tokens × configured price, per question |

Judge hygiene: DeepSeek judging DeepSeek is biased toward itself. Mitigations: (1) hand-label 30 answers and report judge–human agreement (Cohen's κ or % agreement), (2) optionally run a second, different judge locally with Ollama (free), (3) keep judge prompts in the repo and temperature 0.

### 12.6 Report
`docs/EVALUATION.md` contains: dataset construction, limitations, the ablation tables, the headline finding ("hybrid+rerank improved MRR from X to Y, +Z% latency"), at least one **negative result** (something that did *not* help; hiring managers trust this), and failure analysis of 10 bad cases with categories (vocabulary mismatch, missing filter, over-aggressive rewrite, etc.).

### Checkpoint 12
- A single command `python -m evaluation.run_retrieval_eval --config configs/eval_retrieval.yaml` reproduces the tables.
- You can say, with numbers, why your final default configuration is the default.

---

## Phase 13 — Hardening, packaging, portfolio

### 13.1 Tests (`pytest`)
- Unit: chunker boundaries, RRF correctness (hand-computed example), filter builder, query builder (injection, bad names), chart builder (**chart/data consistency**), grounding verifier (invented number is flagged, derived percentage is accepted), metric functions.
- Integration (Docker up): ingest a tiny fixture dataset (20 tickets) → index → search → ask with `FakeLLM`.
- Idempotency: ingest twice, index twice → counts unchanged.
- Golden agent tests with recorded LLM responses (VCR-style JSON fixtures) so CI needs no API key.
- GitHub Actions: lint (`ruff`), type-check (`mypy` on core packages), unit tests.

### 13.2 Performance checklist
- Batch embedding (32–64), sorted by length; record docs/sec.
- Warm models at app startup (`lifespan` handler) so the first query is not slow.
- LRU cache for query embeddings and rewrite results (key = normalized question + history hash).
- Reuse one Qdrant client and the SQLAlchemy pool; run blocking model inference in a thread (`run_in_executor`) so FastAPI stays responsive.
- `EXPLAIN ANALYZE` the semantic-layer queries; add indexes where scans show up; keep `ticket_facts` materialized.
- Report a **latency breakdown** (rewrite / retrieve / fuse / rerank / LLM / verify) in the README.
- Optional: ONNX/quantized reranker; benchmark quality-vs-latency trade-off.

### 13.3 One-command local run ("download and run")
1. `cd frontend && npm run build` then copy `dist/*` into `backend/app/static/` (FastAPI already serves it).
2. `backend/Dockerfile` (python:3.11-slim, installs requirements, copies code, mounts a `model_cache` volume so models download once).
3. Add to `docker-compose.yml` an `app` service behind a profile:

```yaml
  app:
    build: { context: ., dockerfile: backend/Dockerfile }
    profiles: ["app"]
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://supportlens:supportlens@postgres:5432/supportlens
      QDRANT_URL: http://qdrant:6333
    depends_on: { postgres: { condition: service_healthy }, qdrant: { condition: service_started } }
    ports: ["8000:8000"]
    volumes: ["./data:/app/data", "./configs:/app/configs", "model_cache:/root/.cache"]
```

4. The README quick start becomes:

```bash
git clone … && cd supportlens
cp .env.example .env            # add your DEEPSEEK_API_KEY
# download the Mendeley dataset into data/raw/mendeley_helpdesk_v3/
docker compose --profile app up -d
docker compose exec app python -m backend.app.ingestion.run
docker compose exec app python -m backend.app.documents.builder
docker compose exec app python scripts/index_all.py
# open http://localhost:8000
```

### 13.4 README structure (hiring managers skim; order matters)
1. One-paragraph pitch + **demo GIF** (chart + citations + inspector)
2. Architecture diagram
3. Key results table (Recall@10, MRR, NDCG, faithfulness, latency, cost/query)
4. Feature list mapped to the skills you want to show
5. Quick start
6. Design decisions & trade-offs (link `docs/DESIGN.md`)
7. Evaluation (link `docs/EVALUATION.md`), **including limitations**
8. Data statement: dataset citation + license, coverage numbers, "no fabricated conversations or identities"
9. Extending to Zendesk/Intercom/Salesforce (adapter interface)
10. Roadmap (auth, observability, multi-tenant) clearly marked as out of scope

### 13.5 Interview preparation: questions you must be able to answer
- Why RRF rather than weighted score fusion? (scale mismatch; robust; one parameter)
- Why a cross-encoder after retrieval, and what does it cost? (accuracy vs latency; candidate pool trade-off)
- Why a semantic layer instead of text-to-SQL? (correctness, safety, auditability; where it fails: novel questions)
- How do you prevent the model inventing numbers? (tool-only numbers + verifier + caveats; limits of the heuristic)
- What did your ablation show, and what did *not* help?
- How would the design change at 100× scale? (batch/async embedding, Qdrant sharding/quantization, read replicas, caching, queueing the LLM)
- How would you handle PII and multi-tenancy later? (named as deliberate non-goals now; where the hooks go: adapter layer redaction, per-tenant collections/payload filters)
- Where does the system still fail? (have 3 concrete examples from the failure analysis)

---

## Appendix A — Definition of done

- [ ] UI matches the reference layout; chat renders markdown, Plotly charts, data/query tabs, citations
- [ ] Ingestion is idempotent; rejects are recorded; coverage statistics exist
- [ ] Documents are deterministic, parent–child, with provenance payloads
- [ ] Dense + BM25 + RRF + rewrite + expansion + rerank + context assembly implemented and measurable
- [ ] Agent routes between analytics, semantic and investigate; out-of-scope is refused
- [ ] Every number in an answer is traceable to a `D#`; every example to an `E#`; unavailable data is declared unavailable
- [ ] Charts are built in Python from real query results; chart/data consistency tested
- [ ] Ticket Explorer and Retrieval Inspector pages work
- [ ] Evaluation reproduces from one command; dev/test split respected; limitations documented
- [ ] `docker compose --profile app up` yields a working app at `http://localhost:8000`
- [ ] README with GIF, results, design decisions, dataset citation

## Appendix B — Common failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| Qdrant search returns nothing | Filter value doesn't exist, or payload index missing | Validate filter values against Postgres; create payload indexes |
| Dense results look random | Wrong query prefix/model mismatch with indexed model | Rebuild the collection when the embedding model changes (dimension too) |
| BM25 returns junk | Text not in payload / language mismatch | Check `fastembed` language setting; verify tokenization on a sample |
| Agent loops on tool errors | Error text unhelpful | Return valid names in the error (already shown in `AnalyticsError`) and cap iterations |
| DeepSeek JSON parse failure | Missing the word "json" in prompt, or truncated output | Keep the word in prompts; raise `max_tokens`; wrap in fail-safe parse + one retry |
| Chart shows wrong values | LLM passed a wrong column | Builder rejects unknown columns; consistency test |
| Resolution times look absurd | Timezone/format parsing, resolved < created | Set `timestamp_format`; exclude negatives in `ticket_facts`; read the quality report |
| First query very slow | Models load lazily | Warm up in FastAPI lifespan |
| Plotly won't render in Vite | CJS import issue | `optimizeDeps.include: ["plotly.js-dist-min"]` |

## Appendix C — Recommended working order inside each week

1. **Week 1:** Phases 0–2 (UI done, infra up), Phase 3 profiling.
2. **Week 2:** Phase 4 ingestion + quality report; Phase 5 documents.
3. **Week 3:** Phases 6–8 (indexing, LLM layer, hybrid retrieval, inspector CLI).
4. **Week 4:** Phase 9 analytics + charts; Phase 10 agent.
5. **Week 5:** Phase 11 UI wiring/explorer/inspector; start eval dataset creation.
6. **Week 6:** Phase 12 evaluation + ablations; fix what the failure analysis reveals.
7. **Week 7:** Phase 13 packaging, README, demo GIF, interview rehearsal.

Commit at every checkpoint with a message that names the phase; a clean git history is part of the portfolio.
