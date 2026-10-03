"""Точка входа FastAPI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router
from src.config import get_settings
from src.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте создаём таблицы (для MVP без Alembic)."""
    await init_db()
    yield


app = FastAPI(
    title="FileConv API",
    version="0.3.0",
    description="Сервис конвертации файлов. Трек B «Продукт».",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.api_prefix)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Health-check для Docker/K8s."""
    return {"status": "ok", "service": settings.app_name, "version": "0.3.0"}