from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import init_db
from app.api import auth, chat, permissions


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"🚀 {settings.APP_NAME} backend started")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AetherArc — Aether Brain + Manager + ResearchAI + CoderAI + ImageAI multi-agent backend "
        "with a central permission gateway."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

_origins = list(settings.CORS_ORIGINS)
if settings.DEBUG:
    _origins = _origins + ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(permissions.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.3.0"}


@app.get("/")
async def root():
    return {
        "message": "AetherArc Backend is running",
        "docs": "/docs",
        "health": "/health",
        "agents": ["aether", "manager", "research", "coder", "image"],
        "notes": [
            "Aether is the central brain; model providers are replaceable.",
            "External actions pass through the permission gateway before registered tools execute.",
            "Permissions support allow, ask, and deny per capability.",
            "ImageAI produces prompts/concepts only — it does not generate real images yet.",
            "OAuth: client sends authorization code; backend verifies with Google/GitHub before issuing JWT.",
        ],
    }
