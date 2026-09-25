from pathlib import Path
p=Path(__file__).resolve().parents[2]/"mobile/app/src/main/assets/index.html"
s=p.read_text()
for x in ["/api/auth/login","/api/auth/register","/api/auth/google/login","/api/auth/guest","Continue with Google","Continue as Guest","Sign in","Create account","__aetherOAuthToken","openExternal","guest_messages_remaining"]:
    assert x in s, x
assert "undefined" not in s
assert "no response text was returned" in s
print("MOBILE_AUTH_CHAT_CONTRACT_OK")
