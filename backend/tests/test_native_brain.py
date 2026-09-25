import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.native_brain import AetherNativeBrain


def run(coro):
    return asyncio.run(coro)


brain = AetherNativeBrain()
result = run(brain.respond("hello"))
assert result["intent"] == "greeting"
assert result["content"]

result = run(brain.respond("2 + 3 * 4"))
assert result["content"] == "The answer is 14."

result = run(brain.respond("my name is Aether"))
assert result["cognitive_state"]["facts"]["name"] == "aether"

result = run(brain.respond("remember"))
assert "name=aether" in result["content"]

print("NATIVE_BRAIN_TESTS_OK")
