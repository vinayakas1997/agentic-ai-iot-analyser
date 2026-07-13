"""Self-contained HTML report generator for scenario runner results.
Features: Mermaid graph diagram, step narrative, per-node eye toggle.
"""

from datetime import datetime, timezone
from html import escape
from typing import Any

_GRAPH_MMD = """graph TD
    inject["inject_reference_time"] --> analyst["analyst"]
    analyst -->|"extract_slots"| tool_extract["tool_extract_slots"]
    analyst -->|"resolve_line"| tool_line["tool_resolve_line"]
    analyst -->|"resolve_time"| tool_time["tool_resolve_time"]
    analyst -->|"fetch_schema"| tool_schema["tool_fetch_schema"]
    analyst -->|"reorganize_aims"| tool_reorg["tool_reorganize_aims"]
    analyst -->|"generate_plans"| tool_plans["tool_generate_plans"]
    analyst -->|"answer_advisory"| tool_adv["tool_answer_advisory"]
    analyst -->|"confirm_plan"| tool_confirm["tool_confirm_plan"]
    tool_extract -->|"loop"| analyst
    tool_line -->|"loop"| analyst
    tool_time -->|"loop"| analyst
    tool_schema -->|"loop"| analyst
    tool_reorg -->|"loop"| analyst
    tool_plans -->|"loop"| analyst
    tool_adv -->|"loop"| analyst
    tool_confirm --> END
    analyst -->|"respond"| END"""


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

    turns_html = "".join(_turn_div(t, name) for t in scenario.get("turns", []))

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


def _turn_narrative(turn: dict) -> str:
    """Generate a human-readable 'what happened' summary."""
    parts = []
    routing = turn.get("routing_path", [])
    if routing:
        unique_nodes = set()
        for r in routing:
            target = r.split(" -> ")[-1] if " -> " in r else r
            if target not in ("analyst (loop back)", "__end__ (responded)", "__end__ (tool responded)"):
                unique_nodes.add(target)
        node_list = ", ".join(sorted(unique_nodes)) if unique_nodes else "responded directly"
        parts.append(f"Routed through: {node_list}")
    ng = turn.get("node_groups", [])
    if ng:
        llm_nodes = [g["node"] for g in ng if g.get("node")]
        parts.append(f"LLM invoked: {', '.join(llm_nodes)}")
    checks = turn.get("checks", [])
    failed_checks = [c for c in checks if not c.get("passed")]
    if failed_checks:
        parts.append(f"Failed checks: {len(failed_checks)}")
    return ". ".join(parts) if parts else "No data"


def _turn_div(turn: dict, scenario_name: str = "") -> str:
    tn = turn.get("turn", "?")
    msg = escape(turn.get("user_message", ""))
    tp = turn.get("passed", 0)
    tf = turn.get("failed", 0)
    status = "PASS" if tf == 0 else "FAIL"
    color = "#22c55e" if tf == 0 else "#ef4444"
    agent = escape(turn.get("agent_message_preview", ""))
    trace_count = turn.get("trace_event_count", 0)
    llm_count = turn.get("llm_calls", 0)
    narrative = escape(_turn_narrative(turn))

    checks_html = "".join(_check_row(c) for c in turn.get("checks", []))
    routing_html = _routing_html(turn.get("routing_path", []))
    nodes_html = _node_groups_html(turn.get("node_groups", []))

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
        <div class="narrative-box"><strong>What happened:</strong> {narrative}</div>
        {routing_html}
        {checks_html}
        {nodes_html}
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
    clr = "#22c55e" if passed else "#ef4444"
    actual = check.get("actual")
    expected = check.get("expected")
    details = ""
    if not passed and actual is not None:
        a_str = escape(str(actual))
        e_str = escape(str(expected)) if expected is not None else ""
        details = f'<div class="check-detail">expected: {e_str}<br>actual: {a_str}</div>'
    return f"""
    <div class="check-row" style="color:{clr}">
      <span class="check-symbol">{symbol}</span>
      <span>{name}</span>
      {details}
    </div>"""


def _node_groups_html(groups: list[dict]) -> str:
    if not groups:
        return ""
    sections = ""
    for g in groups:
        node = escape(g.get("node", "?"))
        inp = g.get("inputs", [])
        out = g.get("outputs", [])
        meta = g.get("metas", [])

        latency = ""
        tokens = ""
        if meta:
            m = meta[0].get("data", {})
            lat = m.get("latency_ms", "")
            tok = m.get("tokens", "")
            latency = f"{lat:.0f}ms" if isinstance(lat, (int, float)) else str(lat)
            tokens = str(tok) if tok else ""

        io_html = ""
        for ev in inp:
            prompt = escape(str(ev.get("data", {}).get("prompt", "")))
            io_html += f"""
            <div class="io-entry">
              <span class="io-badge in">IN</span>
              <pre class="io-content">{"<em>empty</em>" if not prompt else prompt}</pre>
            </div>"""
        for ev in out:
            resp = escape(str(ev.get("data", {}).get("response", ev.get("data", {}).get("error", ""))))
            io_html += f"""
            <div class="io-entry">
              <span class="io-badge out">OUT</span>
              <pre class="io-content">{"<em>empty</em>" if not resp else resp}</pre>
            </div>"""

        if not io_html:
            io_html = '<div style="color:#64748b;font-size:13px;padding:8px">No LLM I/O recorded</div>'

        meta_str = f"{latency} {tokens}" if latency or tokens else ""
        meta_label = f'<span class="node-meta">{escape(meta_str)}</span>' if meta_str else ""

        sections += f"""
        <div class="node-group">
          <div class="node-header" onclick="toggleNode(this)">
            <span class="eye-icon">&#128065;</span>
            <span class="node-name">{node}</span>
            {meta_label}
            <span class="node-toggle">&#9654;</span>
          </div>
          <div class="node-body" style="display:none">
            {io_html}
          </div>
        </div>"""

    if not sections:
        return ""

    return f"""
    <div class="section">
      <div class="section-title">Per-Node LLM Inspection</div>
      {sections}
    </div>"""


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Manager Agent Scenario Report</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true,theme:"dark",themeVariables:{{fontSize:"14px",primaryColor:"#1e293b",primaryTextColor:"#e2e8f0",primaryBorderColor:"#475569",lineColor:"#64748b",secondaryColor:"#334155",tertiaryColor:"#0f172a"}}}});</script>
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
  .narrative-box {{ background:#0f172a; padding:10px 14px; border-radius:6px; margin-bottom:12px; font-size:13px; color:#93c5fd; border-left:3px solid #3b82f6 }}
  .section {{ margin-bottom:16px }}
  .section:last-child {{ margin-bottom:0 }}
  .section-title {{ font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:#64748b; margin-bottom:8px }}
  .routing-flow {{ display:flex; flex-wrap:wrap; align-items:center; gap:4px 0; font-size:13px }}
  .route-step {{ background:#0f172a; padding:4px 10px; border-radius:4px; color:#93c5fd; white-space:nowrap }}
  .route-step + .route-step::before {{ content:"\\2192"; margin-right:0; color:#64748b }}
  .check-row {{ display:flex; align-items:flex-start; gap:8px; padding:4px 0; font-size:14px }}
  .check-symbol {{ font-size:16px; flex-shrink:0; width:20px; text-align:center }}
  .check-detail {{ font-size:12px; color:#94a3b8; margin-top:2px; font-family:monospace }}
  .node-group {{ background:#0f172a; border-radius:6px; margin-bottom:8px; overflow:hidden }}
  .node-header {{ display:flex; align-items:center; gap:10px; padding:10px 14px; cursor:pointer;
                 background:#1e293b; user-select:none; transition:background 0.15s }}
  .node-header:hover {{ background:#334155 }}
  .eye-icon {{ font-size:18px; flex-shrink:0 }}
  .node-name {{ font-weight:600; font-size:14px; flex:1 }}
  .node-meta {{ font-size:12px; color:#64748b; margin-right:8px }}
  .node-toggle {{ font-size:12px; color:#64748b; transition:transform 0.2s }}
  .node-body {{ padding:10px 14px; border-top:1px solid #334155 }}
  .io-entry {{ margin-bottom:8px }}
  .io-entry:last-child {{ margin-bottom:0 }}
  .io-badge {{ display:inline-block; padding:1px 6px; border-radius:3px; font-size:10px; font-weight:600; color:#fff; margin-bottom:4px }}
  .io-badge.in {{ background:#3b82f6 }}
  .io-badge.out {{ background:#22c55e }}
  .io-content {{ background:#0f172a; padding:8px; border-radius:4px; font-size:12px; font-family:monospace;
                white-space:pre-wrap; word-break:break-word; max-height:300px; overflow-y:auto; color:#cbd5e1; line-height:1.5 }}
  a {{ color:#60a5fa }}
  .mermaid-container {{ background:#0f172a; border-radius:8px; padding:16px; margin-bottom:24px; overflow-x:auto }}
  @media (max-width:768px) {{ body {{ padding:16px }} .card {{ padding:16px }} }}
</style>
</head>
<body>
<div class="container">
  <h1>Manager Agent Scenario Report</h1>
  <p style="color:#64748b;font-size:14px;margin-bottom:24px">Generated: {TIMESTAMP}</p>
  <div class="mermaid-container">
    <div class="mermaid">
{GRAPH_MMD}
    </div>
  </div>
  {BANNER}
  {SCENARIOS}
</div>
<script>
function toggleNode(header) {{
  var body = header.nextElementSibling;
  var toggle = header.querySelector('.node-toggle');
  if (body.style.display === 'none') {{
    body.style.display = 'block';
    toggle.innerHTML = '&#9660;';
  }} else {{
    body.style.display = 'none';
    toggle.innerHTML = '&#9654;';
  }}
}}
</script>
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
        .replace("{GRAPH_MMD}", _GRAPH_MMD)
    )
