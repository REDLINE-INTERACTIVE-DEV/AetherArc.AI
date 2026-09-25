from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
mobile=(ROOT/"mobile/app/src/main/assets/index.html").read_text()
gradle=(ROOT/"mobile/app/build.gradle").read_text()
for x in ['backendUrl+"/api/auth/"',"register","login","Continue with Google","Continue as Guest","Sign in","Create account","__aetherOAuthToken","openExternal","guest_messages_remaining","ManagerAI","ReasonAI","CodeAI","ResearchAI","Settings","Purple theme","/api/chat/conversations","Thinking…"]:
    assert x in mobile, x
assert "Guest · undefined" not in mobile
assert "no response text was returned" not in mobile
assert "Aether received your message" not in mobile
assert "Hey. I'm Aether. My native brain is online." not in mobile
assert "versionCode 24" in gradle
assert "versionName '0.9.1'" in gradle
print("MOBILE_UI_AUTH_CHAT_CONTRACT_OK")
