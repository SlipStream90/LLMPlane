"""Repository-layer pure logic: cursor pagination and prompt variables."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.errors import ValidationProblem
from app.repositories.base import decode_cursor, encode_cursor
from app.repositories.prompt import extract_variables


class TestCursor:
    def test_roundtrip(self) -> None:
        when = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
        row_id = uuid.uuid4()

        cursor = encode_cursor(when, row_id)
        assert decode_cursor(cursor) == (when, row_id)

    def test_cursor_is_opaque(self) -> None:
        """Clients must not be able to read or forge it by inspection alone;
        base64 is not security, but it does stop accidental coupling to the
        internal ordering key."""
        cursor = encode_cursor(datetime.now(timezone.utc), uuid.uuid4())
        assert "|" not in cursor
        assert ":" not in cursor

    @pytest.mark.parametrize("bad", ["", "!!!!", "bm90LWEtY3Vyc29y", "abc"])
    def test_malformed_cursors_are_client_errors(self, bad: str) -> None:
        with pytest.raises(ValidationProblem):
            decode_cursor(bad)


class TestExtractVariables:
    def test_finds_variables_in_order_without_duplicates(self) -> None:
        content = "Hello {{name}}, welcome to {{ place }}. Bye {{name}}."
        assert extract_variables(content) == ["name", "place"]

    def test_ignores_non_identifier_braces(self) -> None:
        assert extract_variables("JSON: {{ }} and {{1bad}} and {single}") == []

    def test_handles_empty_content(self) -> None:
        assert extract_variables("") == []
        assert extract_variables(None) == []  # type: ignore[arg-type]
