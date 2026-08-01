"""API key generation, hashing and verification.

Key format (ARCHITECTURE.md 4.1): ``llcp_{project_short_id}_{secret}``

  * ``project_short_id`` — first 8 hex chars of the project UUID, so a leaked
    key is attributable to a project without a DB lookup.
  * ``secret`` — 32 bytes of `secrets.token_urlsafe` entropy.

Only the argon2id hash is stored. `key_prefix` (the first 8 characters of the
whole key, i.e. ``llcp_xxx``-style leading segment) is stored separately purely
as a UI identifier and as an index-friendly narrowing filter for verification —
it is never treated as a secret and never used alone to authenticate.
"""

from __future__ import annotations

import hmac
import secrets
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

KEY_NAMESPACE = "llcp"
PREFIX_LENGTH = 8
_SECRET_BYTES = 32

# argon2id defaults from argon2-cffi are OWASP-aligned; kept explicit so a
# future tuning change is a visible diff rather than a library-default drift.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def project_short_id(project_id: uuid.UUID) -> str:
    return project_id.hex[:8]


def generate_api_key(project_id: uuid.UUID) -> tuple[str, str, str]:
    """Return ``(raw_key, key_prefix, key_hash)``.

    The raw key is returned to the caller exactly once and is never persisted.
    """
    raw = f"{KEY_NAMESPACE}_{project_short_id(project_id)}_{secrets.token_urlsafe(_SECRET_BYTES)}"
    return raw, raw[:PREFIX_LENGTH], _hasher.hash(raw)


def hash_api_key(raw_key: str) -> str:
    return _hasher.hash(raw_key)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Constant-time-ish verification. Any argon2 failure mode is a `False`,
    never an exception escaping into a 500."""
    try:
        return _hasher.verify(key_hash, raw_key)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(key_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(key_hash)
    except InvalidHashError:
        return False


def key_prefix_of(raw_key: str) -> str:
    return raw_key[:PREFIX_LENGTH]


def constant_time_compare(a: str, b: str) -> bool:
    """For the bootstrap admin token, which is a shared secret compared
    directly rather than a hashed credential."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def mask_secret(value: str, keep: int = 4) -> str:
    """Mask a credential for display: never return more than the last `keep`
    characters of anything secret (ARCHITECTURE.md 4.1, Article XII)."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * 8}{value[-keep:]}"
