import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.native_brain import AetherNativeBrain

def run(coro): return asyncio.run(coro)

brain = AetherNativeBrain()
assert run(brain.respond("hello"))["intent"] == "greeting"
assert run(brain.respond("2 + 3 * 4"))["content"] == "Yep — that's 14."
assert run(brain.respond("my name is Aether"))["cognitive_state"]["facts"]["name"] == "Aether"
assert "name: Aether" in run(brain.respond("remember"))["content"]
assert run(brain.respond("I want to build a robot"))["cognitive_state"]["goals"]
assert run(brain.respond("yes, continue"))["intent"] == "continue"
emotion = run(brain.respond("I'm frustrated with this"))
assert emotion["emotion"] == "frustrated" and "frustrating" in emotion["content"].lower()
print("NATIVE_BRAIN_TESTS_OK")
