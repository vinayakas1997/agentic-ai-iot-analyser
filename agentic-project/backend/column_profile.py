"""Per-column profiling for uploaded CSV data.

Scans the parsed rows and computes lightweight statistics so the
user (and later the LLM in _build_context) understands what each
column actually contains.
"""

import re

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+(\.\d+)?$")


def profile_columns(columns: list[str], rows: list[dict]) -> dict[str, dict]:
    """Return a dict keyed by sanitized column name with profiling results.

    Each entry::
      {
        "datatype": "INTEGER" | "REAL" | "TEXT",
        "null_pct": float,          # percentage of rows that are null
        "distinct_count": int,
        "is_constant": bool,        # all non-null values are identical
        "zero_pct": float | None,   # only for INTEGER/REAL
        "min": str | None,          # only for INTEGER/REAL
        "max": str | None,          # only for INTEGER/REAL
        "common_samples": list[str],# up to 3 most frequent non-null values
      }
    """
    n = len(rows)
    if n == 0:
        return {c: _empty_profile() for c in columns}

    profiles: dict[str, dict] = {}
    for col in columns:
        vals = [r.get(col) for r in rows]
        non_null = [v for v in vals if v is not None]

        null_pct = round((len(vals) - len(non_null)) / n * 100, 1)
        distinct = set(str(v) for v in non_null)

        # Type detection from non-null values
        datatype = _detect_type(non_null)

        is_constant = len(distinct) <= 1

        zero_pct: float | None = None
        minimum: str | None = None
        maximum: str | None = None

        if datatype in ("INTEGER", "REAL"):
            nums = []
            for v in non_null:
                try:
                    nums.append(float(v))
                except (ValueError, TypeError):
                    pass
            if nums:
                zeros = sum(1 for x in nums if x == 0)
                zero_pct = round(zeros / len(vals) * 100, 1)
                minimum = str(int(min(nums)) if datatype == "INTEGER" else min(nums))
                maximum = str(int(max(nums)) if datatype == "INTEGER" else max(nums))

        common_samples = _most_common(non_null, 3)

        profiles[col] = {
            "datatype": datatype,
            "null_pct": null_pct,
            "distinct_count": len(distinct),
            "is_constant": is_constant,
            "zero_pct": zero_pct,
            "min": minimum,
            "max": maximum,
            "common_samples": common_samples,
        }

    return profiles


def _empty_profile() -> dict:
    return {
        "datatype": "TEXT",
        "null_pct": 100.0,
        "distinct_count": 0,
        "is_constant": True,
        "zero_pct": None,
        "min": None,
        "max": None,
        "common_samples": [],
    }


def _detect_type(values: list) -> str:
    """Detect INTEGER / REAL / TEXT from a list of non-null values."""
    if not values:
        return "TEXT"
    all_int = True
    all_num = True
    for v in values:
        s = str(v).strip()
        if not _INT_RE.match(s):
            all_int = False
        if not _FLOAT_RE.match(s):
            all_num = False
        if not all_int and not all_num:
            break
    if all_int:
        return "INTEGER"
    if all_num:
        return "REAL"
    return "TEXT"


def _most_common(values: list, k: int) -> list[str]:
    """Return up to k most frequent non-null value strings."""
    freq: dict[str, int] = {}
    for v in values:
        s = str(v)
        freq[s] = freq.get(s, 0) + 1
    sorted_items = sorted(freq.items(), key=lambda x: -x[1])
    return [val for val, _cnt in sorted_items[:k]]
