from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models.user import hash_password, verify_password
assert verify_password("CorrectPass123", hash_password("CorrectPass123"))
encoded = hash_password("CorrectPass123")
assert not verify_password("WrongPass123", encoded)
assert encoded.startswith("scrypt$16384$8$1$")
print("AUTH_PASSWORD_TESTS_OK")
