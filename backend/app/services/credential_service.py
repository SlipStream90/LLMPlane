"""Provider credential encryption (T009).

Provider API keys are encrypted at rest with Fernet (AES-128-CBC + HMAC),
keyed from `FERNET_SECRET_KEY`. ARCHITECTURE.md 4.1 permits either pgcrypto or
app-level Fernet; Fernet is chosen because the key never enters the database,
so a Postgres dump alone does not disclose provider credentials.

Invariants, all of them load-bearing (Article XII):
  * plaintext credentials are never logged, never returned by an API response,
    and never written to the rendered gateway config on disk;
  * anything user-visible goes through `masked_hint()`, which shows at most the
    last 4 characters;
  * `FERNET_SECRET_KEY` is read from the environment and never persisted.

Key rotation: `FERNET_SECRET_KEY` may be a comma-separated list. The first key
encrypts; all keys are accepted for decryption (MultiFernet), so rotating is
"prepend the new key, re-save providers, drop the old key" with no downtime.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import get_settings
from app.core.errors import ProblemException
from app.core.security import mask_secret

logger = logging.getLogger(__name__)

#: Key inside the encrypted JSON blob that holds the primary provider API key.
API_KEY_FIELD = "api_key"


class CredentialDecryptionError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            500,
            "Stored provider credentials could not be decrypted. This usually "
            "means FERNET_SECRET_KEY changed without re-encrypting existing "
            "rows.",
            title="Credential Decryption Failed",
            type_="https://llmplane.dev/problems/credential-decryption",
        )


class CredentialService:
    def __init__(self, secret_key: str | None = None) -> None:
        raw = secret_key if secret_key is not None else get_settings().fernet_secret_key
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys:
            raise ValueError("FERNET_SECRET_KEY is empty")
        try:
            self._fernet = MultiFernet([Fernet(k.encode("utf-8")) for k in keys])
        except (ValueError, TypeError) as exc:
            # Do not echo the value — only that it was malformed.
            raise ValueError(
                "FERNET_SECRET_KEY is not a valid urlsafe base64-encoded 32-byte "
                "key (generate one with `Fernet.generate_key()`)"
            ) from exc

    # -- encryption --------------------------------------------------------
    def encrypt(self, credentials: dict[str, Any]) -> bytes:
        """Encrypt a credentials mapping into an opaque blob."""
        payload = json.dumps(credentials, separators=(",", ":")).encode("utf-8")
        return self._fernet.encrypt(payload)

    def decrypt(self, blob: bytes | None) -> dict[str, Any]:
        """Decrypt a blob written by `encrypt`. Returns {} for a null blob."""
        if not blob:
            return {}
        try:
            return json.loads(self._fernet.decrypt(bytes(blob)).decode("utf-8"))
        except InvalidToken as exc:
            logger.error(
                "Provider credential decryption failed — the ciphertext does not "
                "verify under any configured key. No credential material is "
                "included in this log line."
            )
            raise CredentialDecryptionError() from exc

    def rotate(self, blob: bytes) -> bytes:
        """Re-encrypt an existing blob under the current primary key."""
        return self._fernet.rotate(bytes(blob))

    # -- building / merging ------------------------------------------------
    @staticmethod
    def build(
        api_key: str | None, extra: dict[str, str] | None = None
    ) -> dict[str, Any]:
        credentials: dict[str, Any] = {}
        if api_key:
            credentials[API_KEY_FIELD] = api_key
        if extra:
            credentials.update(extra)
        return credentials

    def merge(
        self,
        existing_blob: bytes | None,
        *,
        api_key: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> bytes | None:
        """Apply a partial credential update without requiring the caller to
        resend fields it is not changing."""
        current = self.decrypt(existing_blob)
        if api_key:
            current[API_KEY_FIELD] = api_key
        if extra:
            current.update(extra)
        if not current:
            return None
        return self.encrypt(current)

    # -- display -----------------------------------------------------------
    def masked_hint(self, blob: bytes | None) -> str | None:
        """Last-4 mask of the stored API key, for UI identification only."""
        if not blob:
            return None
        try:
            api_key = self.decrypt(blob).get(API_KEY_FIELD)
        except ProblemException:
            return None
        return mask_secret(api_key) if api_key else None

    def api_key_of(self, blob: bytes | None) -> str | None:
        """Plaintext API key, for outbound provider/gateway calls only.

        The one legitimate consumer set: provider health checks and gateway
        config rendering. Never let a return value of this reach a response
        body, a log, or a file on disk.
        """
        return self.decrypt(blob).get(API_KEY_FIELD) if blob else None


def get_credential_service() -> CredentialService:
    """FastAPI dependency / worker helper."""
    return CredentialService()
