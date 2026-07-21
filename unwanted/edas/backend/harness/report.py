"""Report generator for scenario runner results."""

from typing import Any


def generate_report(results: list[dict]) -> str:
    lines = []
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_checks = sum(r["total_checks"] for r in results)

    lines.append("=" * 70)
    lines.append("MANAGER AGENT SCENARIO REPORT")
    lines.append("=" * 70)

    for scenario in results:
        lines.append("")
        lines.append("-" * 70)
        lines.append(f"Scenario: {scenario.get('scenario', '?')}")
        if scenario.get("description"):
            lines.append(f"  {scenario['description']}")
        if scenario.get("file"):
            lines.append(f"  File: {scenario['file']}")
        if scenario.get("error"):
            lines.append(f"  ERROR: {scenario['error']}")
            continue
        lines.append(f"  Session: {scenario.get('session_id', '?')[:8]}...")
        lines.append(f"  Checks: {scenario['passed']}/{scenario['total_checks']} passed")
        if scenario["failed"] > 0:
            lines.append(f"  FAILURES: {scenario['failed']}")
        lines.append("")

        for turn in scenario.get("turns", []):
            _render_turn(lines, turn)

    lines.append("")
    lines.append("=" * 70)
    if total_failed == 0:
        lines.append(f"ALL {len(results)} SCENARIO(S) PASSED ({total_passed}/{total_checks} checks)")
    else:
        lines.append(f"SUMMARY: {total_passed}/{total_checks} passed, {total_failed} failed across {len(results)} scenario(s)")
    lines.append("=" * 70)

    return "\n".join(lines)


def _render_turn(lines: list[str], turn: dict) -> None:
    turn_num = turn.get("turn", "?")
    user_msg = turn.get("user_message", "")
    passed = turn.get("passed", 0)
    failed = turn.get("failed", 0)

    status = "PASS" if failed == 0 else "FAIL"
    lines.append(f"  Turn {turn_num}: \"{user_msg}\" [{status}] ({passed}/{passed+failed})")

    if turn.get("agent_message_preview"):
        preview = turn["agent_message_preview"]
        lines.append(f"    Agent: {preview}")

    lines.append(f"    Trace events: {turn.get('trace_event_count', 0)}")
    lines.append(f"    LLM calls: {turn.get('llm_calls', 0)}")

    routing = turn.get("routing_path", [])
    if routing:
        lines.append("    Routing:")
        for r in routing:
            lines.append(f"      {r}")

    for check in turn.get("checks", []):
        if check["passed"]:
            lines.append(f"    ✓ {check['name']}")
        else:
            lines.append(f"    ✗ {check['name']}")
            lines.append(f"      expected: {check.get('expected', '?')}")
            lines.append(f"      actual:   {check.get('actual', '?')}")

    llm_events = turn.get("llm_events", [])
    if llm_events:
        lines.append("    LLM trace:")
        for ev in llm_events:
            et = ev.get("event_type", "?")
            node = ev.get("node", "?")
            data = ev.get("data", {})
            if et == "llm_input":
                prompt = str(data.get("prompt", ""))[:120]
                lines.append(f"      IN [{node}]: {prompt}...")
            elif et == "llm_output":
                resp = str(data.get("response", data.get("error", "")))[:200]
                lines.append(f"      OUT [{node}]: {resp}")
            elif et == "llm_meta":
                lines.append(f"      META [{node}]: {data.get('latency_ms', '?')}ms, {data.get('tokens', '?')} tokens, ok={data.get('success')}")
    lines.append("")
