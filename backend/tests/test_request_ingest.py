"""Gateway event coercion (ADR-004).

Redis Stream fields are always strings and the emitter lives in another
container. Nothing here may trust the shape of an incoming value.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models.enums import RequestStatus
from app.services.request_ingest_service import (
    _decimal,
    _int,
    _int_or_none,
    _status,
    _tags,
    _timestamp,
    _truncate,
    _uuid_or_none,
)


@pytest.mark.parametrize(
    "value,expected",
    [("12", 12), ("12.9", 12), (7, 7), (None, 0), ("", 0), ("abc", 0)],
)
def test_int_coercion_never_raises(value, expected) -> None:
    assert _int(value) == expected


def test_int_or_none_distinguishes_absent_from_zero() -> None:
    assert _int_or_none(None) is None
    assert _int_or_none("") is None
    assert _int_or_none("0") == 0


@pytest.mark.parametrize(
    "value,expected",
    [("0.0031", Decimal("0.0031")), (None, Decimal("0")), ("junk", Decimal("0"))],
)
def test_decimal_coercion(value, expected) -> None:
    assert _decimal(value) == expected


def test_status_defaults_to_success_and_maps_unknown_to_error() -> None:
    assert _status("success") is RequestStatus.SUCCESS
    assert _status("timeout") is RequestStatus.TIMEOUT
    assert _status(None) is RequestStatus.SUCCESS
    # An unrecognised status must not be recorded as a success.
    assert _status("weird") is RequestStatus.ERROR


def test_uuid_coercion() -> None:
    value = uuid.uuid4()
    assert _uuid_or_none(str(value)) == value
    assert _uuid_or_none("not-a-uuid") is None
    assert _uuid_or_none(None) is None
    assert _uuid_or_none("") is None


def test_tags_accepts_json_arrays_lists_and_bare_strings() -> None:
    assert _tags('["playground","benchmark"]') == ["playground", "benchmark"]
    assert _tags(["a"]) == ["a"]
    assert _tags("playground") == ["playground"]
    assert _tags(None) == []


def test_timestamp_parsing_defaults_to_now_and_is_timezone_aware() -> None:
    parsed = _timestamp("2026-08-01T12:00:00Z")
    assert parsed == datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

    naive = _timestamp("2026-08-01T12:00:00")
    assert naive.tzinfo is timezone.utc

    assert _timestamp("garbage").tzinfo is not None
    assert _timestamp(None).tzinfo is not None


def test_truncate_bounds_untrusted_text() -> None:
    assert _truncate("x" * 5000, 2000) == "x" * 2000
    assert _truncate("", 10) is None
    assert _truncate(None, 10) is None
