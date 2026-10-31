from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import routes_chat, routes_health, routes_retrieval, routes_tickets
from backend.app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    yield


app = FastAPI(title="CaseLens", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_chat.router)
app.include_router(routes_tickets.router)
app.include_router(routes_retrieval.router)

static_dir = Path(__file__).parent / "static"
if (static_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")

