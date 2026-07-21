"""HTTP-based scenario runner for the manager agent.

Usage:
    python -m harness.scenario_runner [--base-url http://localhost:4002] [--scenario scenarios/01_vinayaka_ask_flow.yaml]

Runs the specified scenario(s) against a running backend, fetches the trace
after each turn, and returns a structured report.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

from harness.html_report import generate_html_report
from harness.report import generate_report

HERE = Path(__file__).parent


def _load_scenario(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _find_scenarios(pattern: str | None) -> list[Path]:
    if pattern:
        return list(HERE.glob(pattern))
    return sorted(HERE.glob("scenarios/*.yaml"))


async def _create_session(client: httpx.AsyncClient, base_url: str, title: str | None = None) -> str:
    payload = {"title": title} if title else {}
    resp = await client.post(f"{base_url}/manager/sessions", json=payload)
    resp.raise_for_status()
    return resp.json()["session_id"]


async def _post_message(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
    message: str,
) -> dict:
    resp = await client.post(
        f"{base_url}/manager/sessions/{session_id}/messages",
        json={"message": message, "line_name": ""},
    )
    resp.raise_for_status()
    return resp.json()


async def _fetch_trace(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
) -> list[dict]:
    resp = await client.get(f"{base_url}/manager/sessions/{session_id}/trace")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


async def _clear_trace(
    client: httpx.AsyncClient,
    base_url: str,
    session_id: str,
) -> None:
    await client.delete(f"{base_url}/manager/sessions/{session_id}/trace")


def _check_expectations(
    turn_result: dict,
    trace: list[dict],
    expectations: dict[str, Any],
) -> list[dict]:
    checks = []

    if "interrupt_node" in expectations:
        expected = expectations["interrupt_node"]
        last_node = _last_interrupt_node(trace)
        passed = last_node == expected
        checks.append({
            "name": f"interrupt_node == {expected}",
            "passed": passed,
            "actual": last_node,
        })

    if "phase" in expectations:
        expected = expectations["phase"]
        actual = turn_result.get("phase")
        passed = actual == expected
        checks.append({
            "name": f"phase == {expected}",
            "passed": passed,
            "actual": actual,
        })

    if "slots" in expectations:
        for key_path, expected_val in _flatten_dict(expectations["slots"]):
            actual_val = _get_nested(turn_result.get("slots", {}), key_path)
            passed = actual_val == expected_val
            checks.append({
                "name": f"slots.{'.'.join(key_path)} == {expected_val}",
                "passed": passed,
                "actual": actual_val,
            })

    if "routing_path" in expectations:
        actual_path = _extract_routing_path(trace)
        expected_path = expectations["routing_path"]
        passed = actual_path == expected_path
        checks.append({
            "name": "routing_path matches",
            "passed": passed,
            "actual": actual_path,
            "expected": expected_path,
        })

    if "trace_contains" in expectations:
        for cond in expectations["trace_contains"]:
            found = _trace_has_event(trace, cond)
            checks.append({
                "name": f"trace contains {cond.get('event_type', '?')}/{cond.get('node', '?')}",
                "passed": found,
                "actual": "found" if found else "not found",
            })

    if "trace_does_not_contain" in expectations:
        for cond in expectations["trace_does_not_contain"]:
            found = _trace_has_event(trace, cond)
            checks.append({
                "name": f"trace does NOT contain {cond.get('event_type', '?')}/{cond.get('node', '?')}",
                "passed": not found,
                "actual": "found" if found else "not found",
            })

    if "conditions" in expectations:
        for cond in expectations["conditions"]:
            key = cond.get("key", "")
            expected_val = cond.get("value")
            actual_val = _find_condition_value(trace, key)
            passed = actual_val == expected_val
            checks.append({
                "name": f"condition {key} == {expected_val}",
                "passed": passed,
                "actual": actual_val,
            })

    return checks


def _last_interrupt_node(trace: list[dict]) -> str | None:
    # The turn's last node_state event's node name
    turn_events = [e for e in trace if e.get("event_type") == "node_state"]
    if not turn_events:
        return None
    return turn_events[-1].get("node")


def _extract_routing_path(trace: list[dict]) -> list[str]:
    return [
        f"{e.get('node', '?')} -> {e.get('data', {}).get('target', '?')}"
        for e in trace
        if e.get("event_type") == "routing"
    ]


def _trace_has_event(trace: list[dict], condition: dict) -> bool:
    for event in trace:
        for key, val in condition.items():
            if key == "event_type" and event.get("event_type") != val:
                break
            if key == "node" and event.get("node") != val:
                break
            if key == "data" and isinstance(val, dict):
                event_data = event.get("data", {})
                for dk, dv in val.items():
                    if event_data.get(dk) != dv:
                        break
                else:
                    continue
                break
        else:
            return True
    return False


def _find_condition_value(trace: list[dict], key: str) -> Any:
    for event in trace:
        data = event.get("data", {})
        if key in data:
            return data[key]
    return None


def _flatten_dict(d: dict, prefix: list[str] | None = None) -> list[tuple[list[str], Any]]:
    result = []
    for k, v in d.items():
        path = (prefix or []) + [k]
        if isinstance(v, dict):
            result.extend(_flatten_dict(v, path))
        else:
            result.append((path, v))
    return result


def _get_nested(d: dict, path: list[str]) -> Any:
    for key in path:
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


async def run_scenario(
    client: httpx.AsyncClient,
    base_url: str,
    scenario_path: Path,
) -> dict:
    scenario = _load_scenario(scenario_path)
    title = (scenario.get("name") or "")[:60]
    session_id = await _create_session(client, base_url, title=title)

    results = {
        "scenario": scenario["name"],
        "description": scenario.get("description", ""),
        "file": str(scenario_path.name),
        "session_id": session_id,
        "turns": [],
        "passed": 0,
        "failed": 0,
        "total_checks": 0,
    }

    for step_idx, step in enumerate(scenario["steps"]):
        user_msg = step["user"]

        turn_result = await _post_message(client, base_url, session_id, user_msg)
        trace = await _fetch_trace(client, base_url, session_id)
        await _clear_trace(client, base_url, session_id)

        checks = _check_expectations(
            turn_result,
            trace,
            step.get("expect", {}),
        )

        passed_checks = sum(1 for c in checks if c["passed"])
        failed_checks = sum(1 for c in checks if not c["passed"])
        results["passed"] += passed_checks
        results["failed"] += failed_checks
        results["total_checks"] += len(checks)

        llm_events = [
            e for e in trace
            if e.get("event_type") in ("llm_input", "llm_output", "llm_meta")
        ]

        node_groups: dict[str, dict[str, Any]] = {}
        for ev in llm_events:
            n = ev.get("node", "?")
            if n not in node_groups:
                node_groups[n] = {"node": n, "inputs": [], "outputs": [], "metas": []}
            if ev["event_type"] == "llm_input":
                node_groups[n]["inputs"].append(ev)
            elif ev["event_type"] == "llm_output":
                node_groups[n]["outputs"].append(ev)
            elif ev["event_type"] == "llm_meta":
                node_groups[n]["metas"].append(ev)

        results["turns"].append({
            "turn": step_idx + 1,
            "user_message": user_msg,
            "interrupt_node": turn_result.get("phase"),
            "agent_message_preview": turn_result.get("agent_message", "")[:200],
            "checks": checks,
            "passed": passed_checks,
            "failed": failed_checks,
            "trace_event_count": len(trace),
            "llm_calls": len([e for e in llm_events if e.get("event_type") == "llm_meta"]),
            "llm_events": llm_events[:20],
            "node_groups": list(node_groups.values()),
            "routing_path": _extract_routing_path(trace),
        })

    return results


async def run_all(
    base_url: str,
    scenario_pattern: str | None,
) -> list[dict]:
    scenarios = _find_scenarios(scenario_pattern)
    if not scenarios:
        print(f"No scenarios found matching: {scenario_pattern or 'scenarios/*.yaml'}")
        return []

    async with httpx.AsyncClient(timeout=120.0) as client:
        all_results = []
        for path in scenarios:
            print(f"Running: {path.name} ...")
            try:
                result = await run_scenario(client, base_url, path)
                all_results.append(result)
                status = "PASS" if result["failed"] == 0 else "FAIL"
                print(f"  {status} ({result['passed']}/{result['total_checks']} checks passed)")
            except Exception as e:
                print(f"  ERROR: {e}")
                all_results.append({
                    "scenario": path.stem,
                    "file": path.name,
                    "error": str(e),
                    "passed": 0,
                    "failed": 999,
                    "total_checks": 0,
                    "turns": [],
                })
        return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run manager agent scenarios")
    parser.add_argument("--base-url", default="http://localhost:4002")
    parser.add_argument("--scenario", help="Glob pattern for scenario files")
    parser.add_argument("--json", action="store_true", help="Output raw JSON report")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    parser.add_argument("--output-dir", default=str(HERE / "outputs"), help="Directory for HTML reports")
    args = parser.parse_args()

    results = asyncio.run(run_all(args.base_url, args.scenario))

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    elif args.html:
        html = generate_html_report(results)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        path = out_dir / f"report_{ts}.html"
        path.write_text(html, encoding="utf-8")
        print(f"HTML report written to {path.resolve()}")
    else:
        print(generate_report(results))


if __name__ == "__main__":
    main()
