"""Self-contained HTML report generator for scenario runner results."""

from datetime import datetime, timezone
from html import escape
from typing import Any


def _summary_banner(results: list[dict]) -> str:
    total = sum(r["total_checks"] for r in results)
    passed = sum(r["passed"] for r in results)
    failed = sum(r["failed"] for r in results)
    scenarios = len(results)
    ok = failed == 0
    color = "#22c55e" if ok else "#ef4444"
    label = "ALL SCENARIOS PASSED" if ok else f"{failed} FAILURE(S)"
    return f"""
    <div style="background:{color};color:#fff;padding:24px 32px;border-radius:12px;margin-bottom:24px">
      <div style="font-size:28px;font-weight:700">{label}</div>
      <div style="font-size:16px;margin-top:6px">{passed}/{total} checks passed across {scenarios} scenario(s)</div>
    </div>"""


def _scenario_card(scenario: dict) -> str:
    name = escape(scenario.get("scenario", "?"))
    desc = escape(scenario.get("description", ""))
    fname = escape(scenario.get("file", ""))
    err = scenario.get("error")
    sid = escape(scenario.get("session_id", "")[:8])

    if err:
        return f"""
    <div class="card" style="border-left:4px solid #ef4444">
      <h2>{name}</h2>
      <p style="color:#ef4444">ERROR: {escape(err)}</p>
      <p>File: {fname}</p>
    </div>"""

    sp = scenario["passed"]
    sf = scenario["failed"]
    st = scenario["total_checks"]
    status = "PASS" if sf == 0 else "FAIL"
    color = "#22c55e" if sf == 0 else "#ef4444"

    turns_html = "".join(_turn_div(t) for t in scenario.get("turns", []))

    return f"""
    <div class="card" style="border-left:4px solid {color}">
      <div class="scenario-header">
        <h2>{name}</h2>
        <span class="badge" style="background:{color}">{status}</span>
      </div>
      {f'<p style="color:#94a3b8;margin-top:-8px">{desc}</p>' if desc else ''}
      <p style="font-size:14px;color:#94a3b8">File: {fname} &middot; Session: {sid} &middot; <strong>{sp}/{st}</strong> checks passed</p>
      {turns_html}
    </div>"""


def _turn_div(turn: dict) -> str:
    tn = turn.get("turn", "?")
    msg = escape(turn.get("user_message", ""))
    tp = turn.get("passed", 0)
    tf = turn.get("failed", 0)
    status = "PASS" if tf == 0 else "FAIL"
    color = "#22c55e" if tf == 0 else "#ef4444"
    agent = escape(turn.get("agent_message_preview", ""))
    trace_count = turn.get("trace_event_count", 0)
    llm_count = turn.get("llm_calls", 0)

    checks_html = "".join(_check_row(c) for c in turn.get("checks", []))
    routing_html = _routing_html(turn.get("routing_path", []))
    llm_html = _llm_html(turn.get("llm_events", []))

    return f"""
    <details class="turn-details" {'open' if tf > 0 else ''}>
      <summary class="turn-summary" style="border-left:3px solid {color}">
        <strong>Turn {tn}:</strong> &ldquo;{msg}&rdquo;
        <span class="badge" style="background:{color};margin-left:auto">{status}</span>
      </summary>
      <div class="turn-body">
        {f'<div class="agent-msg"><strong>Agent:</strong> {agent}</div>' if agent else ''}
        <div style="font-size:13px;color:#94a3b8;margin-bottom:12px">
          Trace events: {trace_count} &middot; LLM calls: {llm_count}
        </div>
        {routing_html}
        {checks_html}
        {llm_html}
      </div>
    </details>"""


def _routing_html(path: list[str]) -> str:
    if not path:
        return ""
    steps = "".join(
        f'<span class="route-step">{escape(s)}</span>'
        for s in path
    )
    return f"""
    <div class="section">
      <div class="section-title">Routing Path</div>
      <div class="routing-flow">{steps}</div>
    </div>"""


def _check_row(check: dict) -> str:
    name = escape(check.get("name", "?"))
    passed = check.get("passed", False)
    symbol = "&#10003;" if passed else "&#10007;"
    color = "#22c55e" if passed else "#ef4444"
    actual = check.get("actual")
    expected = check.get("expected")
    details = ""
    if not passed and actual is not None:
        a_str = escape(str(actual))
        e_str = escape(str(expected)) if expected is not None else ""
        details = f'<div class="check-detail">expected: {e_str}<br>actual: {a_str}</div>'
    return f"""
    <div class="check-row" style="color:{color}">
      <span class="check-symbol">{symbol}</span>
      <span>{name}</span>
      {details}
    </div>"""


def _llm_html(events: list[dict]) -> str:
    if not events:
        return ""
    rows = ""
    for ev in events:
        et = ev.get("event_type", "?")
        node = escape(ev.get("node", "?"))
        ts = escape(ev.get("timestamp", ""))
        data = ev.get("data", {})
        if et == "llm_input":
            prompt = escape(str(data.get("prompt", "")))
            short = prompt[:120] + ("..." if len(prompt) > 120 else "")
            rows += f"""
      <tr>
        <td><span class="llm-badge in">IN</span></td>
        <td>{node}</td>
        <td>{ts}</td>
        <td class="llm-preview" onclick="this.classList.toggle('expanded')">{short}<pre class="llm-full">{prompt}</pre></td>
      </tr>"""
        elif et == "llm_output":
            resp = escape(str(data.get("response", "")))
            err_text = escape(str(data.get("error", "")))
            display = resp or err_text
            short = display[:200] + ("..." if len(display) > 200 else "")
            rows += f"""
      <tr>
        <td><span class="llm-badge out">OUT</span></td>
        <td>{node}</td>
        <td>{ts}</td>
        <td class="llm-preview" onclick="this.classList.toggle('expanded')">{short}<pre class="llm-full">{display}</pre></td>
      </tr>"""
        elif et == "llm_meta":
            lat = data.get("latency_ms", "?")
            tok = data.get("tokens", "?")
            ok = data.get("success", "?")
            rows += f"""
      <tr>
        <td><span class="llm-badge meta">META</span></td>
        <td>{node}</td>
        <td>{ts}</td>
        <td>{lat}ms &middot; {tok} tokens &middot; ok={ok}</td>
      </tr>"""
    if not rows:
        return ""
    return f"""
    <div class="section">
      <div class="section-title">LLM Trace</div>
      <div style="overflow-x:auto">
        <table class="llm-table">
          <thead><tr><th>Type</th><th>Node</th><th>Time</th><th>Content</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Manager Agent Scenario Report</title>
<style>
  *, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;
          background:#0f172a; color:#e2e8f0; padding:32px; line-height:1.6 }}
  .container {{ max-width:1200px; margin:0 auto }}
  h1 {{ font-size:20px; color:#94a3b8; margin-bottom:8px }}
  .card {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:20px }}
  .scenario-header {{ display:flex; align-items:center; gap:12px; margin-bottom:12px }}
  .scenario-header h2 {{ font-size:20px; flex:1 }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; font-weight:600; color:#fff; white-space:nowrap }}
  .turn-details {{ margin:12px 0 0 0; border-radius:8px; overflow:hidden }}
  .turn-summary {{ display:flex; align-items:center; gap:12px; padding:10px 14px; background:#334155;
                  cursor:pointer; font-size:14px; border-radius:8px; user-select:none }}
  .turn-summary::-webkit-details-marker {{ display:none }}
  .turn-body {{ padding:14px; background:#1e293b; border:1px solid #334155; border-top:none; border-radius:0 0 8px 8px }}
  .agent-msg {{ background:#0f172a; padding:10px 14px; border-radius:6px; margin-bottom:12px; font-size:14px; color:#94a3b8 }}
  .section {{ margin-bottom:16px }}
  .section:last-child {{ margin-bottom:0 }}
  .section-title {{ font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:#64748b; margin-bottom:8px }}
  .routing-flow {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px 0; font-size:13px }}
  .route-step {{ background:#0f172a; padding:4px 10px; border-radius:4px; color:#93c5fd; white-space:nowrap }}
  .route-step + .route-step::before {{ content:"\\2192"; margin-right:0; color:#64748b }}
  .check-row {{ display:flex; align-items:flex-start; gap:8px; padding:4px 0; font-size:14px }}
  .check-symbol {{ font-size:16px; flex-shrink:0; width:20px; text-align:center }}
  .check-detail {{ font-size:12px; color:#94a3b8; margin-top:2px; font-family:monospace }}
  .llm-table {{ width:100%; border-collapse:collapse; font-size:13px }}
  .llm-table th {{ text-align:left; padding:6px 10px; background:#334155; color:#94a3b8; font-weight:500; white-space:nowrap }}
  .llm-table td {{ padding:6px 10px; border-bottom:1px solid #334155; vertical-align:top }}
  .llm-badge {{ display:inline-block; padding:0 6px; border-radius:3px; font-size:11px; font-weight:600; color:#fff }}
  .llm-badge.in {{ background:#3b82f6 }}
  .llm-badge.out {{ background:#22c55e }}
  .llm-badge.meta {{ background:#a855f7 }}
  .llm-preview {{ cursor:pointer; max-width:500px; overflow:hidden }}
  .llm-preview .llm-full {{ display:none; margin-top:8px; background:#0f172a; padding:8px; border-radius:4px;
                            font-size:12px; white-space:pre-wrap; word-break:break-word; max-height:400px; overflow-y:auto }}
  .llm-preview.expanded .llm-full {{ display:block }}
  .llm-preview.expanded {{ cursor:pointer; background:#1e293b }}
  a {{ color:#60a5fa }}
  @media (max-width:768px) {{ body {{ padding:16px }} .card {{ padding:16px }} }}
</style>
</head>
<body>
<div class="container">
  <h1>Manager Agent Scenario Report</h1>
  <p style="color:#64748b;font-size:14px;margin-bottom:24px">Generated: {TIMESTAMP}</p>
  {BANNER}
  {SCENARIOS}
</div>
</body>
</html>"""


def generate_html_report(results: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    banner = _summary_banner(results)
    scenarios = "".join(_scenario_card(r) for r in results)
    return (
        _HTML_TEMPLATE.replace("{TIMESTAMP}", ts)
        .replace("{BANNER}", banner)
        .replace("{SCENARIOS}", scenarios)
    )
