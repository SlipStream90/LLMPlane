"""Provider credential encryption (T009)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.errors import ProblemException
from app.services.credential_service import CredentialService


@pytest.fixture
def service() -> CredentialService:
    return CredentialService(Fernet.generate_key().decode())


def test_roundtrip(service: CredentialService) -> None:
    credentials = {"api_key": "sk-test-1234", "azure_endpoint": "https://x.example"}
    blob = service.encrypt(credentials)

    assert isinstance(blob, bytes)
    # The plaintext must not be recoverable by reading the blob.
    assert b"sk-test-1234" not in blob
    assert service.decrypt(blob) == credentials


def test_decrypt_of_empty_blob_is_empty(service: CredentialService) -> None:
    assert service.decrypt(None) == {}
    assert service.decrypt(b"") == {}


def test_decrypt_under_a_different_key_raises_a_typed_problem() -> None:
    blob = CredentialService(Fernet.generate_key().decode()).encrypt({"api_key": "x"})
    other = CredentialService(Fernet.generate_key().decode())

    with pytest.raises(ProblemException) as excinfo:
        other.decrypt(blob)
    assert excinfo.value.status_code == 500
    # The error must explain the cause without echoing any credential material.
    assert "FERNET_SECRET_KEY" in excinfo.value.detail


def test_merge_applies_a_partial_update(service: CredentialService) -> None:
    blob = service.encrypt({"api_key": "old", "region": "us-east-1"})
    merged = service.merge(blob, api_key="new")

    assert service.decrypt(merged) == {"api_key": "new", "region": "us-east-1"}


def test_merge_of_nothing_onto_nothing_stays_null(service: CredentialService) -> None:
    assert service.merge(None) is None


def test_masked_hint_shows_only_the_last_four(service: CredentialService) -> None:
    blob = service.encrypt({"api_key": "sk-supersecret-tail"})
    hint = service.masked_hint(blob)

    assert hint == "********tail"
    assert "supersecret" not in hint


def test_masked_hint_is_none_without_credentials(service: CredentialService) -> None:
    assert service.masked_hint(None) is None
    assert service.masked_hint(service.encrypt({"region": "eu"})) is None


def test_key_rotation_keeps_old_ciphertext_readable() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    old_blob = CredentialService(old_key).encrypt({"api_key": "rotate-me"})
    # New key first, old key retained for decryption — the documented rotation
    # procedure.
    rotated = CredentialService(f"{new_key},{old_key}")

    assert rotated.decrypt(old_blob) == {"api_key": "rotate-me"}
    reencrypted = rotated.rotate(old_blob)
    assert CredentialService(new_key).decrypt(reencrypted) == {"api_key": "rotate-me"}


def test_a_malformed_key_is_rejected_without_echoing_it() -> None:
    with pytest.raises(ValueError) as excinfo:
        CredentialService("this-is-not-a-fernet-key")
    assert "this-is-not-a-fernet-key" not in str(excinfo.value)
