# Aether v0.3 — AI Team App

Aether is an independent local AI application built as an orchestration layer by AetherArc.

## What is implemented
- **ManagerAI** is the default agent and team orchestrator.
- **ReasonAI**, **CodeAI**, and **ResearchAI** can each be selected and chatted with independently.
- ManagerAI can call specialist agents as a team when a real model backend is configured.
- Live activity panel shows what each agent/team stage is doing while a request runs.
- Email/password registration and login.
- Guest mode; guest conversations are not saved.
- Logged-in conversation history stored in local SQLite.
- ResearchAI can use Google Custom Search (if existing credentials are configured), Google News RSS, and location-specific Google News queries.
- Local model support through **Ollama** so the app can run without a paid API.
- OpenAI-compatible provider support for cloud/self-hosted models.
- One-click `Start_Aether.bat` launcher for Windows.

## Important model note
The app itself is the **team/orchestration software**, not a newly trained frontier model. To get real model-generated answers, configure Ollama or an OpenAI-compatible endpoint in `.env`.

### Free/local option
Install Ollama separately, make sure it is running, pull a model, then set:

`OLLAMA_URL=http://127.0.0.1:11434`
`OLLAMA_MODEL=your-model-name`

The app will use that local model for all four agents.

## ResearchAI note
Google's official documentation says the Custom Search JSON API requires a Programmable Search Engine and API key, but its current overview says the API is closed to new customers; existing customers have until January 1, 2027 to transition. Aether therefore also includes Google News RSS for news/local-news retrieval and treats CSE as optional.

## Windows launch
1. Install Python 3.11+.
2. Extract this folder.
3. Double-click **Start_Aether.bat**.
4. The launcher creates a local environment, installs the free Python dependencies, starts Aether, and opens its own Aether interface.

No ChatGPT app is opened by Aether.

## OAuth
The Google and GitHub buttons are wired as configuration points but still require you to create your own OAuth applications and add their credentials. The email/password and guest paths work without OAuth.

## Architecture
`frontend/` = Aether UI
`backend/app.py` = API, auth, agent orchestration, research, model adapters
`storage/aether.db` = local logged-in history
`Start_Aether.bat` = one-click Windows launcher

## Android mobile app

The `mobile/` folder is an Android Studio project. It is a real Aether Android client, while the Aether backend remains the shared team brain. Start the Windows backend with `Start_Aether.bat`, then on the phone open Aether → Backend URL and enter the PC's LAN address, such as `http://192.168.1.10:8000`. The backend now binds to `0.0.0.0:8000` for LAN access. For internet access, deploy the backend behind HTTPS and use that server URL.

The mobile app keeps the same ManagerAI/ReasonAI/CodeAI/ResearchAI interface, authentication, history and live activity stream because it talks to the same backend API.

## v0.4 mobile + server deployment

Aether v0.4 adds a shareable Android client, Docker deployment files, and GitHub Actions workflows. The APK asks for the Aether backend HTTPS address on first launch, so the same APK can be used by multiple people against the same hosted Aether backend.

For a laptop-free setup, deploy the backend container to a server and configure the model provider there. Keep all model/API secrets on the server; never put them in the APK.
