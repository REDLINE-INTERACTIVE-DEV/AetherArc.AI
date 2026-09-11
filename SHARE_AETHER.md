# Sharing Aether

Aether v0.6 is a standalone Android app.

- The APK contains the Aether interface and native network bridge.
- There is no Render server and no server URL to configure.
- Each device can keep its own Hugging Face token locally.
- Do not publish a personal Hugging Face token inside an APK, Git repository, screenshot, or public post.
- For a public production release, move authentication to a secure server-side design before distributing a shared token.

The current build is intentionally optimized for a simple private/demo setup: one AI provider token, one APK, no server deployment.
