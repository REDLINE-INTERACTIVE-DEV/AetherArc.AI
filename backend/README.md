# AetherArc Backend

Cloud FastAPI backend for Aether.

## Native brain

The production `POST /api/chat` path uses Aether's provider-free native cognitive core. It does not call a hosted language model.

The backend can still contain legacy specialist modules for future native implementations, but Aether's central brain does not delegate to them.

## What this solves

- No Hugging Face/OpenAI/Claude/Qwen/etc. model call is required for Aether chat.
- Users do not paste an AI-provider token.
- Logged-in users can keep conversation history.
- Google + GitHub login skeleton remains available.

## Quick start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env for DATABASE_URL, SECRET_KEY, and OAuth values as needed
python run.py
```

Open http://localhost:8000/docs
