"""
Phase 7, Part D/U: password hashing and JWT auth.

Password hashing: Argon2 (via argon2-cffi) for all NEW/updated
passwords - never raw SHA-256. verify_password() also accepts the OLD
sha256 hex-digest scheme so existing accounts keep working, and signals
needs_upgrade=True on a successful legacy match so the caller can
transparently re-hash with Argon2 and save it (a standard, safe rolling
migration - there is no way to "batch migrate" a one-way hash without
the plaintext password, so this lazy-upgrade-on-login approach is the
correct one, not a shortcut).
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_hasher = PasswordHasher()

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "43200"))  # 30 days


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _legacy_sha256(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> tuple:
    """Returns (matches: bool, needs_upgrade: bool)."""
    if stored_hash.startswith("$argon2"):
        try:
            _hasher.verify(stored_hash, password)
            return True, False
        except (VerifyMismatchError, InvalidHash):
            return False, False

    # Legacy scheme: 64-char sha256 hex digest, no $ prefix.
    if _legacy_sha256(password) == stored_hash:
        return True, True
    return False, False


class JwtNotConfiguredError(RuntimeError):
    pass


def create_access_token(user_id: int, email: str) -> str:
    if not JWT_SECRET:
        raise JwtNotConfiguredError(
            "JWT_SECRET is not configured. Copy backend/.env.example to backend/.env "
            "and set a real secret (e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`)."
        )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    if not JWT_SECRET:
        raise JwtNotConfiguredError("JWT_SECRET is not configured.")
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
