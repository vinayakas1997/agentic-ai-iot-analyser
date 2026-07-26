"""CSV pre-check pipeline for personal (user-uploaded) datasets.

Hard rules (reject the whole file, nothing is imported):
- oversized file
- undecodable bytes
- no header row / empty header cells / duplicate header names
- more than `max_bad_row_pct` of data rows have a mismatched column count

Everything else (individual bad rows) is dropped and reported, not fatal.
"""

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    status: str  # "pass" | "fail"
    filename: str
    table_name: str = ""
    columns: list[str] = field(default_factory=list)
    column_types: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    row_count: int = 0
    bad_row_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_SQL_RESERVED = {
    "select", "from", "where", "table", "insert", "update", "delete", "drop",
    "order", "group", "by", "join", "and", "or", "not", "null", "primary", "key",
}


def _sanitize_identifier(name: str, used: set[str], fallback_prefix: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip()).strip("_")
    if not cleaned:
        cleaned = f"{fallback_prefix}_col"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    cleaned = cleaned.lower()
    if cleaned in _SQL_RESERVED:
        cleaned = f"{cleaned}_col"
    base = cleaned
    i = 2
    while cleaned in used:
        cleaned = f"{base}_{i}"
        i += 1
    used.add(cleaned)
    return cleaned


def _decode(raw: bytes) -> str | None:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


_DATA_LIKE_CELL = re.compile(r"^-?\d+(\.\d+)?$|^\d{4}-\d{2}-\d{2}")


def _looks_like_data_row(header: list[str], sample_text: str) -> bool:
    """Header rows are names; data rows contain numbers/dates. If any header cell
    itself looks like a number or a date, or csv.Sniffer agrees there's no header,
    treat the first row as data (headerless file) rather than column names."""
    if any(_DATA_LIKE_CELL.match(h.strip()) for h in header):
        return True
    try:
        return not csv.Sniffer().has_header(sample_text[:8192])
    except csv.Error:
        return False


def _infer_column_type(values: list[str]) -> str:
    non_empty = [v for v in values if v.strip() != ""]
    if not non_empty:
        return "TEXT"
    if all(re.fullmatch(r"-?\d+", v.strip()) for v in non_empty):
        return "INTEGER"
    if all(re.fullmatch(r"-?\d+\.\d+", v.strip()) for v in non_empty):
        return "REAL"
    return "TEXT"


def validate_csv(raw: bytes, filename: str, max_size_mb: int = 50, max_bad_row_pct: float = 5.0) -> ValidationResult:
    result = ValidationResult(status="fail", filename=filename)

    size_mb = len(raw) / (1024 * 1024)
    if size_mb > max_size_mb:
        result.errors.append(f"File exceeds the {max_size_mb}MB size limit ({size_mb:.1f}MB).")
        return result

    text = _decode(raw)
    if text is None:
        result.errors.append("Could not decode file — unsupported or corrupted encoding.")
        return result

    stripped = text.strip("﻿ \n\r")
    if not stripped:
        result.errors.append("File is empty.")
        return result

    delimiter = _detect_delimiter(stripped[:4096])
    reader = csv.reader(io.StringIO(stripped), delimiter=delimiter)
    try:
        raw_header = next(reader)
    except StopIteration:
        result.errors.append("File has no rows.")
        return result

    # Header hard-gate: every column must have a non-empty name, and it must
    # not look like a headerless data row.
    if not raw_header or any(not h.strip() for h in raw_header):
        result.errors.append(
            "This file cannot be processed — column headers are missing (found an empty column name)."
        )
        return result
    if _looks_like_data_row(raw_header, stripped):
        result.errors.append(
            "This file cannot be processed — column headers are missing (first row looks like data, not names)."
        )
        return result

    seen_raw = set()
    for h in raw_header:
        key = h.strip().lower()
        if key in seen_raw:
            result.errors.append(f"Duplicate column name '{h.strip()}' — rename before re-uploading.")
            return result
        seen_raw.add(key)

    used_names: set[str] = set()
    table_stem = re.sub(r"\.csv$", "", filename, flags=re.IGNORECASE)
    columns = [_sanitize_identifier(h, used_names, f"f{i}") for i, h in enumerate(raw_header)]
    n_cols = len(columns)

    good_rows: list[list[str]] = []
    bad_row_count = 0
    total_rows = 0
    for raw_row in reader:
        if not raw_row or all(cell.strip() == "" for cell in raw_row):
            continue  # fully blank line, not counted as a data row at all
        total_rows += 1
        if len(raw_row) != n_cols:
            bad_row_count += 1
            continue
        good_rows.append(raw_row)

    if total_rows == 0:
        result.errors.append("File has a header but no data rows.")
        return result

    bad_pct = (bad_row_count / total_rows) * 100
    if bad_pct > max_bad_row_pct:
        result.errors.append(
            f"{bad_pct:.1f}% of rows have a mismatched column count "
            f"(more than the {max_bad_row_pct}% limit) — file looks malformed."
        )
        return result
    if bad_row_count:
        result.warnings.append(f"Dropped {bad_row_count} malformed row(s) (wrong column count).")

    column_types = [
        _infer_column_type([row[i] for row in good_rows[:1000]])
        for i in range(n_cols)
    ]

    dict_rows = []
    for row in good_rows:
        d = {}
        for i, col in enumerate(columns):
            val = row[i].strip()
            d[col] = None if val == "" else val
        dict_rows.append(d)

    null_counts = [sum(1 for r in dict_rows if r[c] is None) for c in columns]
    for col, nc in zip(columns, null_counts):
        if dict_rows and nc / len(dict_rows) > 0.95:
            result.warnings.append(f"Column '{col}' is over 95% empty.")

    result.status = "pass"
    result.table_name = _sanitize_identifier(table_stem, set(), "t")
    result.columns = columns
    result.column_types = column_types
    result.rows = dict_rows
    result.row_count = len(dict_rows)
    result.bad_row_count = bad_row_count
    return result
