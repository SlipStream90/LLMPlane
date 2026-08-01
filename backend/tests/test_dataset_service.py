"""Benchmark dataset parsing and storage-path safety."""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import ValidationProblem
from app.models.enums import DatasetFormat
from app.services.dataset_service import (
    detect_format,
    parse_dataset,
    read_dataset,
    storage_path_for,
    write_dataset,
)


def test_parses_csv_with_a_bom() -> None:
    raw = "﻿question,reference\nWhat is 2+2?,4\nCapital of France?,Paris\n".encode()
    parsed = parse_dataset(raw, DatasetFormat.CSV)

    assert parsed.columns == ["question", "reference"]
    assert parsed.row_count == 2
    # The BOM must not survive into the first column name.
    assert parsed.rows[0]["question"] == "What is 2+2?"


def test_parses_a_json_array() -> None:
    raw = b'[{"question": "a", "reference": "b"}, {"question": "c"}]'
    parsed = parse_dataset(raw, DatasetFormat.JSON)

    assert parsed.row_count == 2
    assert parsed.columns == ["question", "reference"]


def test_parses_the_data_wrapper_form() -> None:
    raw = b'{"data": [{"question": "a"}]}'
    assert parse_dataset(raw, DatasetFormat.JSON).row_count == 1


@pytest.mark.parametrize(
    "raw,fmt",
    [
        (b"", DatasetFormat.CSV),
        (b"[]", DatasetFormat.JSON),
        (b'{"question": "not an array"}', DatasetFormat.JSON),
        (b"[1, 2, 3]", DatasetFormat.JSON),
        (b"{not json", DatasetFormat.JSON),
    ],
)
def test_rejects_unusable_datasets(raw: bytes, fmt: DatasetFormat) -> None:
    with pytest.raises(ValidationProblem):
        parse_dataset(raw, fmt)


def test_rejects_non_utf8_bytes() -> None:
    with pytest.raises(ValidationProblem, match="UTF-8"):
        parse_dataset(b"\xff\xfe\x00binary", DatasetFormat.CSV)


def test_storage_path_ignores_any_caller_supplied_name(monkeypatch, tmp_path) -> None:
    """Paths are derived from the dataset UUID only, so an uploaded filename
    like `../../etc/passwd` cannot escape the upload directory."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "benchmark_upload_dir", str(tmp_path))
    dataset_id = uuid.uuid4()

    path = storage_path_for(dataset_id, DatasetFormat.CSV)

    assert path.endswith(f"{dataset_id}.csv")
    assert str(tmp_path) in path


def test_write_then_read_roundtrip(monkeypatch, tmp_path) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "benchmark_upload_dir", str(tmp_path))
    path = storage_path_for(uuid.uuid4(), DatasetFormat.CSV)
    write_dataset(path, b"question\nhello\n")

    parsed = read_dataset(path, DatasetFormat.CSV)
    assert parsed.rows == [{"question": "hello"}]


def test_read_of_a_missing_file_explains_the_likely_cause(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="volume"):
        read_dataset(str(tmp_path / "nope.csv"), DatasetFormat.CSV)


@pytest.mark.parametrize(
    "filename,content_type,expected",
    [
        ("data.csv", None, DatasetFormat.CSV),
        ("data.json", None, DatasetFormat.JSON),
        ("data", "text/csv", DatasetFormat.CSV),
        ("data", "application/json", DatasetFormat.JSON),
    ],
)
def test_format_detection(filename, content_type, expected) -> None:
    assert detect_format(filename, content_type) is expected


def test_format_detection_fails_loudly_when_unknown() -> None:
    with pytest.raises(ValidationProblem):
        detect_format("data.parquet", "application/octet-stream")
