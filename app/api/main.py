"""FastAPI app. Serves news/markets/weather JSON + runs the scheduler in-process."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import selectors
from app.config import settings
from app.db.init import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("newsagg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    log.info("newsagg started on %s:%s", settings.host, settings.port)
    try:
        yield
    finally:
        stop_scheduler()
        log.info("newsagg stopped")


app = FastAPI(title="News Aggregator", version="0.1.0", lifespan=lifespan)

# CORS: frontend will live elsewhere (local dev or later separate subdomain).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/snapshot")
def snapshot():
    return selectors.snapshot()


@app.get("/api/news/major")
def news_major(limit: int = Query(8, ge=1, le=20)):
    return {"items": selectors.get_major_news(limit=limit)}


@app.get("/api/news/minor")
def news_minor(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    region: str | None = Query(None, pattern="^(gulf|iran_war|oil_markets|markets_macro|global)$"),
):
    return {"items": selectors.get_minor_news(limit=limit, offset=offset, region=region)}


@app.get("/api/markets")
def markets():
    return selectors.get_markets()


@app.get("/api/weather")
def weather():
    return {"cities": selectors.get_weather()}


# Mount the local frontend prototypes at the root so one uvicorn serves both.
# Registered AFTER API routes so /api/* still wins.
_frontend = Path(__file__).resolve().parents[2] / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
