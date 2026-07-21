"""Plan 1 CLI — exercises shared time_resolution module."""

from __future__ import annotations

import argparse
import asyncio

from agents.manager.time_resolution import (
    REF,
    CASES,
    _assert_mock_cases,
    _format_result,
    resolve_time_phrase,
    run_cases,
)
from config import apply_runtime_env

# Re-export test helpers used by this module's assertions
__all__ = ["REF", "CASES", "resolve_time_phrase", "run_cases"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Plan1 time resolution prototype")
    parser.add_argument("--mock", action="store_true", help="Use mock normalize (no LLM)")
    parser.add_argument("--llm", metavar="PHRASE", help="Resolve a single phrase with real LLM")
    parser.add_argument("--ref", default=REF, help="Reference now ISO timestamp")
    args = parser.parse_args()

    apply_runtime_env()

    if args.llm:
        result = await resolve_time_phrase(args.llm, args.ref, use_llm=True)
        print(f"reference: {args.ref}")
        print(f"input: {args.llm!r}")
        print(_format_result(result))
        return

    use_llm = not args.mock
    mode = "mock" if args.mock else "llm"
    print(f"reference: {args.ref}")
    print(f"mode: {mode}\n")

    results = await run_cases(use_llm=use_llm, reference_now=args.ref)
    for result in results:
        label = result["input"] if result["input"] else "(empty)"
        print(f"{label!r:40} -> {_format_result(result)}")

    if args.mock:
        _assert_mock_cases(results)
        print("\nALL MOCK ASSERTIONS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
