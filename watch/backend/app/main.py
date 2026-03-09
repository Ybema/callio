from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.routers import auth, sources, billing, dashboard, scan, profile, prepare
from app.services.monitor import run_monitor
from app.database import engine, Base
from app.config import settings
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    auto_create = os.getenv("DB_AUTO_CREATE_TABLES", "").lower() in {"1", "true", "yes"}
    if auto_create:
        # Local bootstrap fallback; prefer Alembic migrations for schema changes.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        logger.info("Skipping create_all; expecting schema managed by Alembic migrations.")
    logger.info(
        "Matcher config: provider=%s openai_model=%s anthropic_model=%s anthropic_key=%s openai_key=%s",
        settings.matcher_llm_provider,
        settings.matcher_openai_model,
        settings.matcher_anthropic_model,
        "set" if settings.anthropic_api_key else "missing",
        "set" if settings.openai_api_key else "missing",
    )
    # Start monitoring scheduler — runs every 6 hours
    scheduler.add_job(run_monitor, "interval", hours=6, id="monitor")
    scheduler.start()
    logger.info("FundWatch started — monitor running every 6h")
    yield
    scheduler.shutdown()

app = FastAPI(title="FundWatch API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sources.router)
app.include_router(scan.router)
app.include_router(billing.router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(prepare.router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "fundwatch"}
