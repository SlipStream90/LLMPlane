"""Benchmark dataset parsing and storage.

Shared by the upload API (`api/v1/benchmark_datasets.py`) and the benchmark
worker (`workers/tasks/benchmark.py`), which must read rows back in exactly the
format the uploader wrote — one parser, one truth.

Storage is a local Docker volume (infrastructure.md 4). File names are
server-generated from the dataset UUID; the uploaded filename is never used to
build a path, so a crafted name cannot traverse out of the upload directory.
"""

from __future__ import annotations

import csv
import io
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.errors import ValidationProblem
from app.models.enums import DatasetFormat


@dataclass(frozen=True)
class ParsedDataset:
    rows: list[dict[str, Any]]
    columns: list[str]

    @property
    def row_count(self) -> int:
        return len(self.rows)


def parse_dataset(raw: bytes, source_format: DatasetFormat) -> ParsedDataset:
    """Parse an uploaded CSV or JSON dataset into rows of column->value.

    Rejects anything that is not a flat list of records: a benchmark grid needs
    addressable rows, and silently accepting a nested document would fail later
    inside a worker with a far less useful error.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationProblem(
            "Dataset file must be UTF-8 encoded text (CSV or JSON)."
        ) from exc

    if source_format is DatasetFormat.CSV:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise ValidationProblem("CSV dataset has no header row.")
        columns = [c for c in reader.fieldnames if c]
        rows = [{k: v for k, v in row.items() if k} for row in reader]
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationProblem(f"Dataset is not valid JSON: {exc.msg}") from exc

        # Accept both a bare array and the common {"data": [...]} wrapper.
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            payload = payload["data"]
        if not isinstance(payload, list):
            raise ValidationProblem(
                "JSON dataset must be an array of objects, or an object with a "
                "'data' array."
            )
        rows = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValidationProblem(
                    f"JSON dataset row {index} is not an object; every row must "
                    "be a flat object of column/value pairs."
                )
            rows.append(item)
        columns = list(dict.fromkeys(k for row in rows for k in row))

    if not rows:
        raise ValidationProblem("Dataset contains no rows.")
    if not columns:
        raise ValidationProblem("Dataset contains no columns.")
    return ParsedDataset(rows=rows, columns=columns)


def storage_path_for(dataset_id: uuid.UUID, source_format: DatasetFormat) -> str:
    """Server-generated path. Never derived from user input."""
    directory = get_settings().benchmark_upload_dir
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{dataset_id}.{source_format.value}")


def write_dataset(path: str, raw: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(raw)


def read_dataset(path: str, source_format: DatasetFormat) -> ParsedDataset:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset file is missing at '{path}'. The upload volume may not be "
            "mounted into this container."
        )
    with open(path, "rb") as handle:
        return parse_dataset(handle.read(), source_format)


def delete_dataset_file(path: str) -> bool:
    try:
        os.unlink(path)
        return True
    except FileNotFoundError:
        return False


def detect_format(filename: str, content_type: str | None) -> DatasetFormat:
    lowered = (filename or "").lower()
    if lowered.endswith(".csv"):
        return DatasetFormat.CSV
    if lowered.endswith((".json", ".jsonl")):
        return DatasetFormat.JSON
    if content_type:
        if "csv" in content_type:
            return DatasetFormat.CSV
        if "json" in content_type:
            return DatasetFormat.JSON
    raise ValidationProblem(
        "Could not determine dataset format. Upload a .csv or .json file."
    )
