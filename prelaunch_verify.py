from pathlib import Path

ROOT = Path(__file__).resolve().parent
required = [
    "backend/app/core/native_brain.py",
    "backend/app/core/cognitive_state.py",
    "backend/app/core/brain.py",
    "backend/app/api/chat.py",
    "backend/app/api/auth.py",
    "backend/app/models/access.py",
    "backend/app/core/access.py",
    "mobile/app/src/main/assets/index.html",
    "mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java",
    "mobile/app/build.gradle",
]
missing = [p for p in required if not (ROOT / p).exists()]
assert not missing, f"Missing required files: {missing}"

mobile = (ROOT / "mobile/app/src/main/assets/index.html").read_text()
activity = (ROOT / "mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java").read_text()
brain = (ROOT / "backend/app/core/brain.py").read_text()
native = (ROOT / "backend/app/core/native_brain.py").read_text()
gradle = (ROOT / "mobile/app/build.gradle").read_text()

assert "Paste your backend URL first" not in mobile
assert "session_id" in mobile
assert "getBackendUrl" in activity
assert "onrender.com" not in mobile.lower()
assert "aether_hf_token" not in mobile
assert "BaseAgent" not in brain
assert "AetherNativeBrain" in brain and "CognitiveState" in native
assert "httpx" not in native and "AI_API_KEY" not in native
assert "findProperty" in gradle and "AETHER_BACKEND_URL" in gradle
assert "api/auth/guest" in mobile
assert "guest_messages_remaining" in mobile
print("AETHER_NATIVE_VERIFY_OK")
