# Aether Android client

This is the standalone Aether Android application.

## Architecture

`Aether APK -> native HTTPS bridge -> Hugging Face Inference Providers`

The APK no longer loads a remote web server. `MainActivity` opens the bundled `assets/index.html` locally, so launching Aether cannot send you to a hosting service.

## Setup

On first launch, tap the gear icon and enter a Hugging Face User Access Token with Inference Providers permission. The token is stored locally by the app and sent only over HTTPS when Aether makes a model request.

The current model is `openai/gpt-oss-20b`, served automatically by whichever Hugging Face inference provider currently hosts it (no provider is hard-coded). When talking to ManagerAI, Aether may silently consult ReasonAI/CodeAI/ResearchAI first and fold their real answers into ManagerAI's reply.

## Build

Open this `mobile/` folder in Android Studio and build the debug APK, or use the repository's Android GitHub Actions workflow.