# Aether v0.5 — AI Team App

Aether is the independent AI team application built by AetherArc, with Redline Interactive Development as the parent company. The Android client talks to this FastAPI backend.

## Team
- **ManagerAI** — receives the user request and coordinates the team.
- **ReasonAI** — reasoning and analysis.
- **CodeAI** — software engineering and optional real GitHub edits through Composio.
- **ResearchAI** — web/news research and source synthesis.
- **OfflineAI** — future project.

## Core features now wired
- Normal AI chat through a server-side model provider.
- ManagerAI orchestration across ReasonAI, CodeAI and ResearchAI.
- Research via Google News RSS and optional Google Custom Search.
- Image generation through the server-side Pollinations API.
- Optional Composio tool layer for real GitHub reads/edits.
- Android client can display generated images in-chat.

## Required backend secrets
1. Copy `.env.example` to `.env`.
2. Add a model key, such as `GROQ_API_KEY`.
3. Add `POLLINATIONS_API_KEY` for image generation.
4. Add `COMPOSIO_API_KEY` and `COMPOSIO_USER_ID` if you want CodeAI to make real GitHub edits.
5. Never put these secrets in the APK or Git repository.

Pollinations documents an OpenAI-compatible image API and server-side secret keys; Aether keeps that key on the backend.

## Start
`python START_AETHER_SERVER.py`

The API listens on `0.0.0.0:8000`.

## Android
The `mobile/` directory is a buildable Android client. It targets Android 16 / API 36 and includes image-result rendering. Android's current Play requirement for new apps/updates is API 36+.

## GitHub tool layer
When the user explicitly asks Aether to fix/edit a GitHub file and supplies a GitHub file URL, CodeAI reads the file through Composio, asks the configured model for a complete replacement, then writes it back through Composio. This is opt-in and server-side.

## Architecture
`Android APK -> FastAPI -> ManagerAI -> ReasonAI / CodeAI / ResearchAI -> model + web + image + Composio tools`
