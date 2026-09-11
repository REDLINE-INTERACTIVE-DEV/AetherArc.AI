# Aether Android client

This is the standalone Aether Android application.

## Architecture

`Aether APK -> native HTTPS bridge -> Hugging Face Inference Providers`

The APK no longer loads a remote web server. `MainActivity` opens the bundled `assets/index.html` locally, so launching Aether cannot send you to a hosting service.

## Setup

On first launch, tap the gear icon and enter a Hugging Face User Access Token with Inference Providers permission. The token is stored locally by the app and sent only over HTTPS when Aether makes a model request.

The current model is `Qwen/Qwen2.5-7B-Instruct`.

## Build

Open this `mobile/` folder in Android Studio and build the debug APK, or use the repository's Android GitHub Actions workflow.
