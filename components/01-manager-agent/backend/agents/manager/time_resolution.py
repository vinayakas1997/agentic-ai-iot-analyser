"""Time phrase normalization: LLM canonical → allowlist → delta."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from agents.manager.json_parse import parse_json_from_message
from agents.manager.llm_client import get_llm as get_llm_client
from agents.manager.prompts import load_prompt

REF = "2026-06-19T12:00:00+00:00"

RELATIVE_RE = re.compile(r"^past (\d+) (hours|days|weeks|months|years)$")
CALENDAR_FORMS = frozenset({"this week", "this month", "this year", "this quarter"})
SINGLE_DAY = frozenset({"today", "yesterday"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
N_MIN, N_MAX = 1, 999

RETRY_REASONS = frozenset(
    {
        "allowlist_fail",
        "relative_missing_canonical",
        "absolute_bad_format",
        "unknown_kind",
    }
)

MOCK_NORMALIZE: dict[str, dict] = {
    "past two days": {"kind": "relative", "canonical": "past 2 days"},
    "last 2 days": {"kind": "relative", "canonical": "past 2 days"},
    "past 2 days": {"kind": "relative", "canonical": "past 2 days"},
    "past 7 days": {"kind": "relative", "canonical": "past 7 days"},
    "yesterday": {"kind": "relative", "canonical": "yesterday"},
    "today": {"kind": "relative", "canonical": "today"},
    "2025-01-01 to 2025-01-31": {
        "kind": "absolute",
        "start": "2025-01-01",
        "end": "2025-01-31",
    },
    "from 2025-01-01 to 2025-01-31": {
        "kind": "absolute",
        "start": "2025-01-01",
        "end": "2025-01-31",
    },
    "jan 5 to jan 7": {
        "kind": "absolute",
        "start": "2026-01-05",
        "end": "2026-01-07",
    },
    "7th jan": {
        "kind": "absolute",
        "start": "2026-01-07",
        "end": "2026-01-07",
    },
    "on 2025-06-15": {
        "kind": "absolute",
        "start": "2025-06-15",
        "end": "2025-06-15",
    },
    "last 3 hours": {"kind": "relative", "canonical": "past 3 hours"},
    "this quarter": {"kind": "relative", "canonical": "this quarter"},
    "last week": {
        "kind": "ambiguous",
        "raw": "last week",
        "interpretations": ["past 7 days", "this week"],
    },
    "recently": {
        "kind": "ambiguous",
        "raw": "recently",
        "interpretations": ["past 7 days", "past 30 days"],
    },
    "garbage time phrase": {
        "kind": "invalid",
        "reason": "'garbage time phrase' is not a time expression.",
    },
    "sort by revenue": {
        "kind": "invalid",
        "reason": "'sort by revenue' is not a time expression.",
    },
}

def set_time_llm(_llm=None) -> None:
    pass


def ref_date(reference_now: str) -> date:
    return datetime.fromisoformat(reference_now.replace("Z", "+00:00")).date()


def _quarter_start(d: date) -> date:
    quarter_month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, quarter_month, 1)


def _week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _normalize_absolute(llm_out: dict) -> tuple[str, str] | None:
    start = llm_out.get("start")
    end = llm_out.get("end")
    if not start or not end:
        return None
    if not DATE_RE.match(start) or not DATE_RE.match(end):
        return None
    if start > end:
        start, end = end, start
    return start, end


def _is_valid_relative_canonical(canonical: str) -> bool:
    if canonical in SINGLE_DAY or canonical in CALENDAR_FORMS:
        return True
    m = RELATIVE_RE.match(canonical)
    if not m:
        return False
    n = int(m.group(1))
    return N_MIN <= n <= N_MAX


def validate_llm_out(llm_out: dict) -> tuple[bool, str]:
    kind = llm_out.get("kind")
    if kind == "invalid":
        if not (llm_out.get("reason") or "").strip():
            return False, "invalid_missing_reason"
        return True, ""
    if kind == "ambiguous":
        raw = (llm_out.get("raw") or "").strip()
        interpretations = llm_out.get("interpretations") or []
        if not raw or not interpretations:
            return False, "ambiguous_missing_fields"
        return True, ""
    if kind == "absolute":
        if _normalize_absolute(llm_out) is None:
            return False, "absolute_bad_format"
        return True, ""
    if kind == "relative":
        canonical = (llm_out.get("canonical") or "").strip().lower()
        if not canonical:
            return False, "relative_missing_canonical"
        if _is_valid_relative_canonical(canonical):
            return True, ""
        return False, "allowlist_fail"
    return False, "unknown_kind"


def apply_delta(canonical: str, reference_now: str) -> tuple[str, str] | None:
    text = canonical.strip().lower()
    today = ref_date(reference_now)

    if text == "today":
        d = today.isoformat()
        return d, d
    if text == "yesterday":
        d = (today - timedelta(days=1)).isoformat()
        return d, d
    if text == "this week":
        start = _week_start_monday(today)
        return start.isoformat(), today.isoformat()
    if text == "this month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()
    if text == "this year":
        start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat()
    if text == "this quarter":
        start = _quarter_start(today)
        return start.isoformat(), today.isoformat()

    m = RELATIVE_RE.match(text)
    if not m:
        return None

    n = int(m.group(1))
    unit = m.group(2)
    if unit == "hours":
        d = today.isoformat()
        return d, d
    if unit == "days":
        start = today - timedelta(days=n)
    elif unit == "weeks":
        start = today - timedelta(weeks=n)
    elif unit == "months":
        start = today - timedelta(days=n * 30)
    elif unit == "years":
        start = today - timedelta(days=n * 365)
    else:
        return None

    return start.isoformat(), today.isoformat()


def resolve_from_llm_out(llm_out: dict, phrase: str, reference_now: str) -> dict:
    ok, reason = validate_llm_out(llm_out)
    if not ok:
        return {
            "input": phrase,
            "llm_out": llm_out,
            "resolved": False,
            "reason": reason,
        }

    kind = llm_out["kind"]
    if kind == "invalid":
        return {
            "input": phrase,
            "llm_out": llm_out,
            "resolved": False,
            "reason": "invalid",
            "detail": llm_out.get("reason"),
        }
    if kind == "ambiguous":
        return {
            "input": phrase,
            "llm_out": llm_out,
            "resolved": False,
            "reason": "ambiguous",
            "interpretations": llm_out.get("interpretations") or [],
        }

    if kind == "absolute":
        start, end = _normalize_absolute(llm_out)  # type: ignore[misc]
        return {
            "input": phrase,
            "llm_out": llm_out,
            "canonical": f"{start} to {end}",
            "start": start,
            "end": end,
            "resolved": True,
        }

    canonical = llm_out["canonical"].strip().lower()
    dates = apply_delta(canonical, reference_now)
    if not dates:
        return {
            "input": phrase,
            "llm_out": llm_out,
            "canonical": canonical,
            "resolved": False,
            "reason": "delta_fail",
        }

    start, end = dates
    return {
        "input": phrase,
        "llm_out": llm_out,
        "canonical": canonical,
        "start": start,
        "end": end,
        "resolved": True,
    }


def mock_normalize(phrase: str) -> dict:
    key = phrase.strip().lower()
    return dict(
        MOCK_NORMALIZE.get(key, {"kind": "invalid", "reason": f"'{phrase}' is not a time expression."})
    )


def _validation_error_block(validation_error: str) -> str:
    if not validation_error:
        return ""
    return (
        f"Previous attempt failed validation: {validation_error}\n"
        "Re-parse the phrase and correct the error."
    )


async def normalize_with_llm(
    phrase: str,
    reference_now: str,
    validation_error: str = "",
) -> dict:
    system = load_prompt(
        "normalize_time",
        reference_now=reference_now,
        time_raw=phrase,
        validation_error_block=_validation_error_block(validation_error),
    )
    llm = get_llm_client()
    response = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=phrase)],
        caller="normalize_time",
    )
    try:
        return parse_json_from_message(response.content or "{}")
    except (json.JSONDecodeError, TypeError):
        return {"kind": "invalid", "reason": "LLM returned malformed JSON."}


async def normalize_time_phrase(
    phrase: str,
    reference_now: str,
    *,
    use_llm: bool = True,
) -> tuple[dict, int]:
    if not use_llm:
        return mock_normalize(phrase), 1

    llm_out = await normalize_with_llm(phrase, reference_now)
    ok, reason = validate_llm_out(llm_out)
    if ok or reason not in RETRY_REASONS:
        return llm_out, 1

    llm_out = await normalize_with_llm(phrase, reference_now, validation_error=reason)
    return llm_out, 2


async def resolve_time_phrase(
    phrase: str,
    reference_now: str,
    *,
    use_llm: bool = True,
) -> dict:
    if not phrase or not phrase.strip():
        return {"input": phrase, "resolved": False, "reason": "no_input"}

    llm_out, attempts = await normalize_time_phrase(
        phrase.strip(), reference_now, use_llm=use_llm
    )
    result = resolve_from_llm_out(llm_out, phrase.strip(), reference_now)
    result["attempts"] = attempts
    return result


def apply_result_to_time_slot(time_slot: dict, result: dict) -> dict:
    """Map resolve_time_phrase output into slots.time fields."""
    updated = dict(time_slot)
    updated["ambiguous"] = False
    updated["interpretations"] = []
    updated["no_filter"] = False
    updated["parse_error"] = None

    if result.get("resolved"):
        updated["start"] = result.get("start")
        updated["end"] = result.get("end")
        updated["resolved"] = True
        updated["canonical"] = result.get("canonical")
        return updated

    reason = result.get("reason")
    updated["resolved"] = False
    updated["start"] = None
    updated["end"] = None

    if reason == "ambiguous":
        updated["ambiguous"] = True
        updated["interpretations"] = result.get("interpretations") or []
    elif reason == "invalid":
        updated["parse_error"] = result.get("detail") or "invalid time phrase"
    elif reason:
        updated["parse_error"] = reason

    return updated


CASES = [
    "past two days",
    "last 2 days",
    "2025-01-01 to 2025-01-31",
    "Jan 5 to Jan 7",
    "7th Jan",
    "on 2025-06-15",
    "last 3 hours",
    "this quarter",
    "yesterday",
    "last week",
    "recently",
    "garbage time phrase",
    "sort by revenue",
    "",
]


def _format_result(result: dict) -> str:
    if result.get("resolved"):
        return (
            f"OK  canonical={result.get('canonical')!r}  "
            f"start={result.get('start')}  end={result.get('end')}  "
            f"attempts={result.get('attempts', 1)}"
        )
    if result.get("reason") == "ambiguous":
        interpretations = result.get("interpretations") or []
        return (
            f"AMBIGUOUS  interpretations={interpretations!r}  "
            f"attempts={result.get('attempts', 1)}"
        )
    if result.get("reason") == "invalid":
        return (
            f"INVALID  detail={result.get('detail')!r}  "
            f"attempts={result.get('attempts', 1)}"
        )
    return f"FAIL  reason={result.get('reason')}  llm_out={result.get('llm_out')}"


async def run_cases(*, use_llm: bool, reference_now: str) -> list[dict]:
    results: list[dict] = []
    for phrase in CASES:
        result = await resolve_time_phrase(phrase, reference_now, use_llm=use_llm)
        results.append(result)
    return results


def _assert_mock_cases(results: list[dict]) -> None:
    by_input = {r["input"]: r for r in results}

    past_two = by_input["past two days"]
    assert past_two["resolved"], past_two
    assert past_two["canonical"] == "past 2 days"
    assert past_two["start"] == "2026-06-17"
    assert past_two["end"] == "2026-06-19"

    last_two = by_input["last 2 days"]
    assert last_two["resolved"], last_two
    assert last_two["start"] == "2026-06-17"

    absolute = by_input["2025-01-01 to 2025-01-31"]
    assert absolute["resolved"], absolute
    assert absolute["start"] == "2025-01-01"
    assert absolute["end"] == "2025-01-31"

    jan_range = by_input["Jan 5 to Jan 7"]
    assert jan_range["resolved"], jan_range
    assert jan_range["start"] == "2026-01-05"
    assert jan_range["end"] == "2026-01-07"

    seventh_jan = by_input["7th Jan"]
    assert seventh_jan["resolved"], seventh_jan
    assert seventh_jan["start"] == seventh_jan["end"] == "2026-01-07"

    single = by_input["on 2025-06-15"]
    assert single["resolved"], single
    assert single["start"] == single["end"] == "2025-06-15"

    hours = by_input["last 3 hours"]
    assert hours["resolved"], hours
    assert hours["canonical"] == "past 3 hours"
    assert hours["start"] == hours["end"] == "2026-06-19"

    quarter = by_input["this quarter"]
    assert quarter["resolved"], quarter
    assert quarter["start"] == "2026-04-01"
    assert quarter["end"] == "2026-06-19"

    yesterday = by_input["yesterday"]
    assert yesterday["resolved"], yesterday
    assert yesterday["start"] == yesterday["end"] == "2026-06-18"

    last_week = by_input["last week"]
    assert not last_week["resolved"]
    assert last_week["reason"] == "ambiguous"

    recently = by_input["recently"]
    assert not recently["resolved"]
    assert recently["reason"] == "ambiguous"

    garbage = by_input["garbage time phrase"]
    assert not garbage["resolved"]
    assert garbage["reason"] == "invalid"

    sort_rev = by_input["sort by revenue"]
    assert not sort_rev["resolved"]
    assert sort_rev["reason"] == "invalid"

    empty = by_input[""]
    assert not empty["resolved"]
    assert empty["reason"] == "no_input"
