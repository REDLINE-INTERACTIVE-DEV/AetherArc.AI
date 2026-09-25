# Aether Android client

This is the standalone Aether Android application.

## Architecture

`Aether APK -> Aether backend -> Aether native brain`

The Android client sends chat requests to `POST /api/chat`. The backend's Aether front door does not route those messages through ChatGPT, Qwen, Claude, Llama, Hugging Face or another hosted model.

## Setup

On first launch, enter your Aether backend URL. No AI-provider token is required. A JWT is optional for saved conversation history.

The current native brain is intentionally small and deterministic. It is the first provider-free Aether cognitive kernel; a future trained Aether neural model can replace the kernel behind the same interface.

## Build

Open this `mobile/` folder in Android Studio and build the debug APK, or use the repository's Android GitHub Actions workflow.
