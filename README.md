# Aether v0.6 — Standalone AI Team App

Aether is the independent AI team application built by AetherArc, with Redline Interactive Development as the parent company.

## Architecture

`Android APK -> native network bridge -> Hugging Face Inference Providers -> one AI model`

There is **no Render deployment, no always-on server, and no separate backend to wake up**. The APK contains the Aether UI and a tiny native HTTPS bridge. The user enters one Hugging Face User Access Token in Aether's settings; it stays local to the device.

Aether currently uses `Qwen/Qwen2.5-7B-Instruct`. Hugging Face provides an OpenAI-compatible chat endpoint and routes requests through supported inference providers with one token. Free-tier credits/limits can change.

## AI team

- **ManagerAI** — default coordinator and front door.
- **ReasonAI** — reasoning and analysis specialist.
- **CodeAI** — software engineering specialist.
- **ResearchAI** — research and evidence specialist.
- **OfflineAI** — future project.

All four current AIs use the same model connection; their specialist behavior comes from their system instructions.

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
