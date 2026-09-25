from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import init_db
from app.api import auth, chat, history


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"🚀 {settings.APP_NAME} backend started")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="AetherArc — Aether's native provider-free intelligence backend.",
    version="0.8.0",
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
app.include_router(history.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.8.0", "brain": "aether-native"}


@app.get("/")
async def root():
    return {
        "message": "AetherArc Backend is running",
        "docs": "/docs",
        "health": "/health",
        "agents": ["aether"],
        "brain": "aether-native",
        "external_model_used": False,
        "notes": [
            "Aether's production chat path uses its native cognitive core.",
            "No ChatGPT, Qwen, Claude, Llama, Hugging Face, or other hosted model is called by the Aether front door.",
            "Specialist agents remain separate code and are not silently used as Aether's brain.",
            "Persistent conversation history is available to logged-in users.",
            "OAuth: client sends authorization code; backend verifies with Google/GitHub before issuing JWT.",
        ],
    }
