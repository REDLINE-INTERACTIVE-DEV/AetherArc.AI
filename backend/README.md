# AetherArc Backend

Cloud FastAPI backend for the Aether AI team.

## What this solves
- Users no longer paste Hugging Face tokens
- Server holds the AI key once
- ManagerAI can run Research / Coder / Image specialists in parallel and return a final report
- Google + GitHub login skeleton
- Chat history saved only when the user is logged in

## Quick start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → put your AI_API_KEY and SECRET_KEY
python run.py
```

Open http://localhost:8000/docs
