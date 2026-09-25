import asyncio, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.models.user import hash_password, verify_password
assert verify_password("CorrectPass123", hash_password("CorrectPass123"))
assert not verify_password("WrongPass123", hash_password("CorrectPass123"))
html=(ROOT/"mobile/app/src/main/assets/index.html").read_text()
for x in ["/api/auth/login","/api/auth/register","/api/auth/google/login","/api/auth/guest","Continue with Google","Continue as Guest","Sign in","Create account"]:
    assert x in html, x
print("AUTH_SURFACE_OK")
