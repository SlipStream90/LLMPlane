"""API key generation, verification and masking."""

from __future__ import annotations

import uuid

from app.core.security import (
    KEY_NAMESPACE,
    PREFIX_LENGTH,
    constant_time_compare,
    generate_api_key,
    mask_secret,
    project_short_id,
    verify_api_key,
)


def test_generated_key_has_expected_shape() -> None:
    project_id = uuid.uuid4()
    raw, prefix, key_hash = generate_api_key(project_id)

    assert raw.startswith(f"{KEY_NAMESPACE}_{project_short_id(project_id)}_")
    assert prefix == raw[:PREFIX_LENGTH]
    assert len(prefix) == PREFIX_LENGTH
    # The raw secret must never be recoverable from what is stored.
    assert raw not in key_hash
    assert key_hash.startswith("$argon2id$")


def test_verify_accepts_the_right_key_and_rejects_others() -> None:
    raw, _, key_hash = generate_api_key(uuid.uuid4())
    other, _, _ = generate_api_key(uuid.uuid4())

    assert verify_api_key(raw, key_hash) is True
    assert verify_api_key(other, key_hash) is False
    assert verify_api_key("", key_hash) is False


def test_verify_returns_false_for_a_malformed_hash() -> None:
    """A corrupt stored hash must be an auth failure, not a 500."""
    assert verify_api_key("anything", "not-a-hash") is False


def test_keys_are_unique_per_call() -> None:
    project_id = uuid.uuid4()
    keys = {generate_api_key(project_id)[0] for _ in range(20)}
    assert len(keys) == 20


def test_mask_secret_never_reveals_more_than_last_four() -> None:
    assert mask_secret("sk-abcdefghijklmnop") == "********mnop"
    assert mask_secret("abc") == "***"
    assert mask_secret("") == ""
    assert "abcdefghijkl" not in mask_secret("sk-abcdefghijklmnop")


def test_constant_time_compare() -> None:
    assert constant_time_compare("token", "token") is True
    assert constant_time_compare("token", "token ") is False
    assert constant_time_compare("", "") is True
