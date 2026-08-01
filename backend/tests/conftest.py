"""Test configuration.

These are unit tests: they exercise pure logic (crypto, config rendering,
parsing, validation, coercion) with no Postgres or Redis. Integration tests
against real datastores belong in the CI pipeline (T034, BOOTHROYD) where
service containers are available.

Environment variables are set before any app module is imported, because
`Settings` fails fast on missing secrets by design.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
# Test-only Fernet key. Not a credential to anything real.
os.environ.setdefault("FERNET_SECRET_KEY", "SFRyx2vEfa7l9GEXY7RXAtnRnJPYq1hAQ9v0RJ5hLxE=")
os.environ.setdefault("BOOTSTRAP_ADMIN_TOKEN", "test-bootstrap-token")
os.environ.setdefault("LITELLM_MASTER_KEY", "test-master-key")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENABLE_STREAM_CONSUMER", "false")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    from app.core.config import get_settings

    return get_settings()
