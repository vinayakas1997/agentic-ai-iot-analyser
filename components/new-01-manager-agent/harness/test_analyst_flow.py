#!/usr/bin/env python3
"""Test harness for the agentic analyst flow in new-01-manager-agent.

Tests:
  1. Create session
  2. Extract slots: "analyze Vinayaka cost by fruit"  
  3. Time update: "last month"
  4. Comparison: "which is better, last month or last week?"
  5. Feasibility: "will last year be feasible?"
  6. Plan details: "tell me more about this plan"
"""

import asyncio
import json
import sys
import time
import urllib.request

BASE = "http://localhost:4002"
USER_ID = "98765"


def _req(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("X-User-Id", USER_ID)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ❌ HTTP {e.code}: {body[:300]}")
        sys.exit(1)


def _msg(session_id: str, text: str) -> dict:
    return _req("POST", f"/manager/sessions/{session_id}/messages", {
        "message": text,
        "line_name": "",
    })


def show_turn(step: int, label: str, resp: dict):
    agent = resp.get("agent_message", "") or ""
    phase = resp.get("phase", "?")
    ui = resp.get("ui") or {}
    schema = resp.get("schema") or {}
    print(f"\n{'='*80}")
    print(f"  Step {step}: {label}")
    print(f"  Phase: {phase}")
    if schema.get("line"):
        print(f"  Line: {schema['line']}")
    if schema.get("time"):
        print(f"  Time: {schema['time']['start']} → {schema['time']['end']}")
    if schema.get("no_time_filter"):
        print(f"  Time: NO FILTER")
    if schema.get("datasets"):
        print(f"  Datasets: {[d['name'] for d in schema['datasets']]}")
    aims = (ui.get("plan") or {}).get("aims") or []
    if aims:
        print(f"  Aims: {aims}")
    print(f"  Agent: {agent[:200]}")
    print(f"{'='*80}")


def main():
    print("=== Creating session ===")
    sess = _req("POST", "/manager/sessions", {"title": "Analyst Test"})
    session_id = sess.get("session_id") or sess.get("id", "?")
    print(f"Session: {session_id}")
    print(f"Full response: {json.dumps(sess, indent=2)[:200]}")
    if not session_id or session_id == "?":
        print("ERROR: no session_id")
        sys.exit(1)

    # Step 1: Initial analysis request
    print("\n\n>>> STEP 1: 'analyze Vinayaka cost by fruit'")
    r1 = _msg(session_id, "analyze Vinayaka cost by fruit")
    show_turn(1, "Initial analysis", r1)

    # Wait between calls
    time.sleep(0.5)

    # Step 2: Add time filter
    print("\n\n>>> STEP 2: 'last month'")
    r2 = _msg(session_id, "last month")
    show_turn(2, "Add time filter", r2)

    time.sleep(0.5)

    # Step 3: Comparison question
    print("\n\n>>> STEP 3: 'which is better, last month or last week?'")
    r3 = _msg(session_id, "which is better, last month or last week?")
    show_turn(3, "Time comparison", r3)

    time.sleep(0.5)

    # Step 4: Feasibility question
    print("\n\n>>> STEP 4: 'will last year be feasible?'")
    r4 = _msg(session_id, "will last year be feasible?")
    show_turn(4, "Feasibility check", r4)

    time.sleep(0.5)

    # Step 5: Plan details
    print("\n\n>>> STEP 5: 'tell me more about this plan'")
    r5 = _msg(session_id, "tell me more about this plan")
    show_turn(5, "Plan details", r5)

    print("\n\n=== ALL STEPS COMPLETE ===")


if __name__ == "__main__":
    main()
