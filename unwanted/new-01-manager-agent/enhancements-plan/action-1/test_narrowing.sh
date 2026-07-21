#!/bin/bash
# test_narrowing.sh — verify confirm N narrowing end-to-end
# Tests both: initial narrowing AND narrowing after "more options"

set -euo pipefail
API="${API:-http://localhost:4002/manager}"
PASS=0
FAIL=0

red()   { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
blue()  { echo -e "\033[34m$1\033[0m"; }

api() {
  curl -sf -X POST "$API/sessions/$SID/messages" \
    -H "Content-Type: application/json" \
    -d "{\"message\":\"$1\"}" 2>/dev/null
}

extract() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))" 2>/dev/null || echo ""
}
extract_props() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('ui',{}).get('proposals') or []))" 2>/dev/null || echo "0"
}
extract_plan() {
  python3 -c "import sys,json; d=json.load(sys.stdin); d2=d.get('ui',{}).get('plan') or {}; print('yes' if d2.get('aims') else 'no')" 2>/dev/null || echo "no"
}
extract_phase() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('phase','no_phase'))" 2>/dev/null || echo "no_phase"
}

check() {
  if [ "$2" = "$3" ]; then
    green "  PASS: $1 (got: $2)"
    ((PASS++))
  else
    red "  FAIL: $1 (expected: $3, got: $2)"
    echo "    Full response: $4"
    ((FAIL++))
  fi
}

# ── Setup ──
blue "=== Creating session ==="
SESS=$(curl -sf -X POST "$API/sessions" -d '{}' -H "Content-Type: application/json")
SID=$(echo "$SESS" | extract "session_id")
echo "Session: $SID"

# ── Phase 1: Send FRUITS_TEST to get initial proposals ──
blue "=== Phase 1: Get initial proposals ==="
echo "Sending FRUITS_TEST..."
R=$(api "FRUITS_TEST")
AGENT=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:80])")
echo "  agent: $AGENT"

# Continue until we get proposals
for i in 1 2 3 4 5; do
  P=$(extract_props <<< "$R")
  PH=$(extract_phase <<< "$R")
  echo "  check $i: phase=$PH proposals=$P"
  [ "$P" -ge 2 ] && break
  R=$(api "yes")
done

echo "Initial proposals: $P"

# ── Phase 2: Test confirm 1 narrowing ──
blue "=== Phase 2: confirm 1 (initial narrowing) ==="
R=$(api "confirm 1")
P=$(extract_props <<< "$R")
PH=$(extract_phase <<< "$R")
PL=$(extract_plan <<< "$R")
echo "  phase=$PH proposals=$P plan=$PL"
check "Confirm 1 → phase=ask" "$PH" "ask" "$R"
check "Confirm 1 → 1 proposal" "$P" "1" "$R"
check "Confirm 1 → has plan" "$PL" "yes" "$R"

# ── Phase 3: "more options" → fresh proposals ──
blue "=== Phase 3: 'more options' ==="
R=$(api "more options")
P=$(extract_props <<< "$R")
PH=$(extract_phase <<< "$R")
echo "  phase=$PH proposals=$P"
if [ "$P" -ge 2 ]; then
  green "  PASS: Got $P fresh proposals"
  ((PASS++))
else
  red "  FAIL: Expected >=2 proposals, got $P"
  ((FAIL++))
fi

# ── Phase 4: confirm 1 again (from fresh batch) ──
blue "=== Phase 4: confirm 1 (from fresh batch) ==="
R=$(api "confirm 1")
P=$(extract_props <<< "$R")
PH=$(extract_phase <<< "$R")
PL=$(extract_plan <<< "$R")
echo "  phase=$PH proposals=$P plan=$PL"
check "Confirm 1 (round 2) → phase=ask" "$PH" "ask" "$R"
check "Confirm 1 (round 2) → 1 proposal" "$P" "1" "$R"
check "Confirm 1 (round 2) → has plan" "$PL" "yes" "$R"

# ── Phase 5: Try confirm 2 and confirm 3 from fresh batch ──
# (they should all work individually since each creates its own narrowed plan)
blue "=== Phase 5: confirm 2 (from fresh batch) ==="
R=$(api "confirm 2")
P=$(extract_props <<< "$R")
PH=$(extract_phase <<< "$R")
PL=$(extract_plan <<< "$R")
echo "  phase=$PH proposals=$P plan=$PL"
check "Confirm 2 → phase=ask" "$PH" "ask" "$R"
check "Confirm 2 → 1 proposal" "$P" "1" "$R"

blue "=== Phase 6: __confirm__ (execute) ==="
R=$(api "__confirm__")
PH=$(extract_phase <<< "$R")
echo "  phase=$PH"
check "Execution → phase=man" "$PH" "man" "$R"

echo ""
echo "=============================="
if [ $FAIL -eq 0 ]; then
  green "All $PASS tests passed!"
else
  red "$FAIL tests failed"
  echo
  echo "Debug:"
  echo "  curl -s $API/sessions/$SID | python3 -m json.tool | head -50"
fi
exit $FAIL
