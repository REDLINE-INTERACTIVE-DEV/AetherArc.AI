from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import init_db
from app.api import auth, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"🚀 {settings.APP_NAME} backend started")
    yield
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AetherArc — Manager + ResearchAI + CoderAI + ImageAI multi-agent cloud backend. "
        "Users never paste HF tokens. ImageAI currently produces prompts/concepts only."
    ),
    version="0.2.1",
    lifespan=lifespan,
)

# CORS:
# - DEBUG=true  → allow all origins for local development only
# - DEBUG=false → only the origins listed in CORS_ORIGINS (must be set explicitly for production)
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


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "0.2.1"}


@app.get("/")
async def root():
    return {
        "message": "AetherArc Backend is running",
        "docs": "/docs",
        "health": "/health",
        "agents": ["manager", "research", "coder", "image"],
        "notes": [
            "Users never need to paste Hugging Face tokens. The key lives only on the server.",
            "ImageAI produces prompts/concepts only — it does not generate real images yet.",
            "OAuth: client sends authorization code; backend verifies with Google/GitHub before issuing JWT.",
        ],
    }
