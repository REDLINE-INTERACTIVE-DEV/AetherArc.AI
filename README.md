# Aether v0.6 — Standalone AI Team App

Aether is the independent AI team application built by AetherArc, with Redline Interactive Development as the parent company.

## Architecture

`Android APK -> native network bridge -> Hugging Face Inference Providers -> one AI model`

There is **no Render deployment, no always-on server, and no separate backend to wake up**. The APK contains the Aether UI and a tiny native HTTPS bridge. The user enters one Hugging Face User Access Token in Aether's settings; it stays local to the device.

Aether currently uses `openai/gpt-oss-20b`. Hugging Face's OpenAI-compatible chat endpoint (`https://router.huggingface.co/v1/chat/completions`) automatically picks a serverless inference provider for the model — no provider is hard-coded. Free-tier credits/limits can change.

## AI team

- **ManagerAI** — team lead. The user is Aether's highest authority; ManagerAI coordinates the team on the user's behalf, and can silently consult a teammate (see below) before answering.
- **ReasonAI** — reasoning and analysis specialist.
- **CodeAI** — software engineering specialist.
- **ResearchAI** — research and evidence specialist.
- **OfflineAI** — future project.

All four current AIs use the same model connection; their specialist behavior comes from their system instructions. When you talk to ManagerAI, it first runs a lightweight internal routing call to decide whether ReasonAI, CodeAI, or ResearchAI (up to two) should be consulted for that message; if so, it calls them with a specific sub-task and synthesizes their real answers into its final reply to you, crediting whichever teammate it actually used. Simple messages skip delegation and get a direct answer with no extra calls.

## First-time setup

1. Create a Hugging Face account if you are eligible to use it.
2. Create a User Access Token with the permission needed for Inference Providers.
3. Open Aether and tap the gear button.
4. Paste the token once and tap **Save & start**.
5. Talk to ManagerAI.

Never put the token in GitHub, source files, screenshots, or a public APK. Rotate/revoke it if exposed.

## Build

Open `mobile/` in Android Studio and build the debug APK, or use the repository's GitHub Actions Android workflow.

The APK launches `file:///android_asset/index.html` directly. It never opens a hosting dashboard or server URL.