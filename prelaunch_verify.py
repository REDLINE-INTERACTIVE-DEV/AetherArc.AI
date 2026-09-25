from pathlib import Path

ROOT = Path(__file__).resolve().parent

required = [
    ".github/workflows/build-android.yml",
    "mobile/settings.gradle",
    "mobile/build.gradle",
    "mobile/app/build.gradle",
    "mobile/app/src/main/AndroidManifest.xml",
    "mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java",
    "mobile/app/src/main/assets/index.html",
]
missing = [p for p in required if not (ROOT / p).exists()]
assert not missing, f"Missing required files: {missing}"

for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in {".git", ".gradle", "build", "__pycache__"} for part in path.parts):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    lower = text.lower()
    assert "onrender.com" not in lower, f"Legacy hosting URL found in {path}"
    assert "render.yaml" not in lower, f"Legacy hosting config reference found in {path}"

mobile = (ROOT / "mobile/app/src/main/assets/index.html").read_text(encoding="utf-8")
assert "POST /api/chat" in mobile
assert "aether_hf_token" not in mobile.lower()

main = (ROOT / "mobile/app/src/main/java/com/aetherarc/aether/MainActivity.java").read_text(encoding="utf-8")
assert "file:///android_asset/index.html" in main
assert "router.huggingface.co/v1/chat/completions" not in main.lower()

brain = (ROOT / "backend/app/core/brain.py").read_text(encoding="utf-8")
native = (ROOT / "backend/app/core/native_brain.py").read_text(encoding="utf-8")
state = (ROOT / "backend/app/core/cognitive_state.py").read_text(encoding="utf-8")
assert "from app.agents.base import AgentMessage, BaseAgent" not in brain
assert "AetherNativeBrain" in brain
assert "external_model_used" in brain
assert "httpx" not in native
assert "AI_API_KEY" not in native
assert "CognitiveState" in native
assert "cognitive_state" in native
assert "router.huggingface.co" not in native.lower()
assert "httpx" not in state.lower()

print("STANDALONE_AETHER_VERIFY_OK")
