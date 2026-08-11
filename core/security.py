"""Password hashing and simple CSRF helpers (no extra packages needed)."""

import hmac
import secrets
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def verify_password(plain: str, stored: str) -> bool:
    """Accept both legacy plaintext and werkzeug hashes during migration."""
    if not stored:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        return check_password_hash(stored, plain)
    return hmac.compare_digest(stored, plain)


def is_hashed(stored: str) -> bool:
    if not stored:
        return False
    return stored.startswith(("pbkdf2:", "scrypt:", "argon2:"))


def generate_csrf_token() -> str:
    return secrets.token_hex(32)


def validate_csrf(session_token: str, form_token: str) -> bool:
    if not session_token or not form_token:
        return False
    return hmac.compare_digest(session_token, form_token)

from collections import defaultdict
from time import time

# username/ip -> list of failed attempt timestamps
_failed_attempts = defaultdict(list)
_MAX_ATTEMPTS = 5          # ৫ বার ভুল
_LOCK_SECONDS = 5 * 60     # ৫ মিনিট লক


def _prune(attempts, now):
    return [t for t in attempts if now - t < _LOCK_SECONDS]


def is_login_blocked(key: str) -> bool:
    now = time()
    attempts = _prune(_failed_attempts.get(key, []), now)
    _failed_attempts[key] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def record_login_failure(key: str) -> None:
    now = time()
    attempts = _prune(_failed_attempts.get(key, []), now)
    attempts.append(now)
    _failed_attempts[key] = attempts


def clear_login_failures(key: str) -> None:
    _failed_attempts.pop(key, None)