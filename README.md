# CaseLens

An enterprise customer-support intelligence platform: a local, production-grade
RAG + SQL analytics + dynamic charting system over help-desk ticket data. It
answers questions with grounded, cited answers, builds charts in Python from
verified database results, and exposes a Retrieval Inspector that makes hybrid
search + reranking visible.

The complete, phase-by-phase build instructions are in
[CaseLens.md](./CaseLens.md); design decisions are in
[docs/DESIGN.md](./docs/DESIGN.md) and evaluation methodology in
[docs/EVALUATION.md](./docs/EVALUATION.md).

## Architecture

React UI → FastAPI → LangGraph agent → tools → PostgreSQL (structured facts +
`ticket_facts` materialized view) and Qdrant (dense BGE-M3 + BM25 sparse
vectors). The LLM (DeepSeek, OpenAI-compatible) only selects typed tool calls;
numbers come from SQL, charts from stored DataFrames, and a verifier checks
that every number and citation in the final answer exists in tool output.

## Quick start

Prerequisites: Docker Desktop (or Docker Engine + Compose v2), Python 3.11,
Node 20+.

```bash
cp .env.example .env            # add your DEEPSEEK_API_KEY
# download the Mendeley Help Desk Tickets v3 dataset into data/raw/mendeley_helpdesk_v3/
docker compose up -d postgres qdrant
alembic upgrade head
python -m backend.app.ingestion.profile data/raw/mendeley_helpdesk_v3
# fill configs/column_map.yaml from data/processed/profile_report.md
python -m backend.app.ingestion.run
python -m backend.app.documents.builder
python scripts/index_all.py
```

Then run the UI against the real backend:

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173 (VITE_USE_MOCK=true)
uvicorn backend.app.main:app --reload --port 8000
```

Or run everything as one containerized app (after building the frontend):

```bash
cd frontend && npm install && npm run build
cp -r frontend/dist/* backend/app/static/
docker compose --profile app up -d
docker compose exec app python -m backend.app.ingestion.run
docker compose exec app python -m backend.app.documents.builder
docker compose exec app python scripts/index_all.py
# open http://localhost:8000
```

## Frontend-only demo (mock data)

```bash
cd frontend && npm install && npm run dev
```

This runs the full chat UX (markdown, Plotly chart, citations, evidence drawer,
Ticket Explorer and Retrieval Inspector shells) on mock data with no backend.

## Tests

```bash
pytest tests -q
```

Unit tests cover chunker boundaries, RRF correctness, filter building, query
builder guards, chart/data consistency, grounding verification, and eval
metrics. Integration and golden agent tests are wired for CI in Phase 13.

## What needs your input

- A DeepSeek API key in `.env` (the app also runs with `USE_MOCK_LLM=true`).
- The Mendeley Help Desk Tickets v3 CSV files in `data/raw/mendeley_helpdesk_v3/`.
- The real column names filled into `configs/column_map.yaml` after profiling
  (the build intentionally does not guess them).
- Evaluation datasets and the final result tables in `docs/EVALUATION.md`.

