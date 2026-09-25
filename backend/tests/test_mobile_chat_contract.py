import re
from pathlib import Path
p=Path(__file__).resolve().parents[2]/"mobile/app/src/main/assets/index.html"
s=p.read_text()
assert "quotaText" in s
assert "responseText" in s
assert "messages_remaining??" in s
assert "d?.content??d?.message??d?.response??d?.reply??d?.text??" in s
assert "Aether received your message" in s
print("MOBILE_CHAT_FALLBACK_TEST_OK")
