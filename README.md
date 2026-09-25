# Aether v0.8 — Native Aether Brain

Aether is the standalone AI application built by AetherArc, with Redline Interactive Development as the parent company.

## Architecture

The production chat path is now:

`User -> Aether Brain -> understand -> recall -> reason -> plan -> respond`

Aether's front door does not call ChatGPT, Qwen, Claude, Llama, Hugging Face, or another hosted AI model.

### Native brain

`backend/app/core/native_brain.py` is a provider-free local cognitive kernel. It performs deterministic intent detection, local working-state tracking, safe arithmetic, topic detection and response composition.

This is deliberately a small foundation, not a claim that a few Python rules are equivalent to a trained general-purpose neural network. The next stage is to train an Aether-owned neural model that implements the same brain interface. Until then, Aether does not silently substitute another model.

### Specialist team

The previous ManagerAI, ResearchAI, CoderAI and ImageAI integrations remain separate code, but the Aether front door no longer delegates to them. This prevents an external model from becoming Aether's hidden brain.

### Memory

Logged-in conversation history is still stored by the backend and supplied to Aether's native cognitive core as working context. Guest conversations remain unsaved.

## Backend

The FastAPI backend exposes `POST /api/chat` and reports `brain: "aether-native"` with `external_model_used: false`.

## Important limitation

A truly capable neural Aether brain requires training a neural model on suitable licensed data and compute. This commit establishes the ownership boundary and provider-free production path without pretending that a rule-based kernel is already a ChatGPT-level model.

## Build

Open `mobile/` in Android Studio or use the repository's GitHub Actions Android workflow.
