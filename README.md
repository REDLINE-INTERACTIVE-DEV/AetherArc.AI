# Aether v0.7 — Aether Core

Aether is the standalone AI application built by AetherArc, with Redline Interactive Development as the parent company.

## Architecture

Aether now has a central **Aether Brain**. The brain owns the interaction loop:

`understand -> recall context -> plan -> delegate -> synthesize -> respond`

The underlying model/provider is replaceable. The model is a reasoning engine used by Aether; it is not Aether's identity.

### Aether Brain responsibilities

- understand the user's message and recent conversational context
- detect conversational tone and adapt response style
- decide whether specialist help is actually needed
- delegate research, coding, image-concept and project-management work
- combine specialist results into one response
- keep private planning separate from the user-facing answer
- use logged-in conversation history as working memory

### Specialist team

- **ManagerAI** — project/team-management specialist
- **ResearchAI** — research and evidence specialist
- **CoderAI** — software engineering specialist
- **ImageAI** — image prompts and visual concepts only
- **OfflineAI** — future project

Aether is now the default front door; specialists remain directly selectable.

## Backend

The FastAPI backend keeps the AI provider key server-side. The Android client sends requests to `POST /api/chat`.

Logged-in users get persistent conversation history. Guests can chat without saving history.

## Important distinction

Aether's "brain" is an architectural intelligence layer, not a newly trained foundation model. This keeps Aether model-agnostic while giving it its own identity, working memory, planning, delegation and response behavior.

## Build

Open `mobile/` in Android Studio or use the repository's GitHub Actions Android workflow.
