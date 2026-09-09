# Sharing Aether

Aether now has two pieces:

1. **Aether APK** — the Android client.
2. **Aether backend** — the server running ManagerAI, ReasonAI, CodeAI and ResearchAI.

For a genuinely laptop-free setup, deploy the backend to a server and configure its model provider. Then share the APK and the server's HTTPS address.

The APK remembers the server address, so the other person does not need your laptop or local Wi-Fi.

## Security before public sharing

- Use HTTPS.
- Use a strong production secret configuration.
- Do not put model/API keys inside the APK.
- Keep API keys only on the backend.
- Do not expose a development server directly to the public internet.
- Test authentication and rate limiting before inviting other users.
