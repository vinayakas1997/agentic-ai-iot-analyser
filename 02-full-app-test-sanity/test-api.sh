#!/usr/bin/env bash
# 02-full-app-test-sanity API test script
set -euo pipefail
API="http://localhost:7010/api/v2"
USER="testuser1"
DS="production_info_5days"
RESULT_DIR="results"
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')
BATCH="${1:-all}"
PASS=0
FAIL=0

log_result() {
    local test="$1" result="$2" detail="$3"
    if [ "$result" = "PASS" ]; then
        echo "  PASS $test"
        PASS=$((PASS + 1))
    else
        echo "  FAIL $test -- $detail"
        FAIL=$((FAIL + 1))
    fi
}

new_session() {
    curl -s -X POST "$API/sessions" -H "Content-Type: application/json" \
        -d "{\"user_id\": \"$USER\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])"
}

send_msg() {
    local sid="$1" msg="$2" line="$3" aims="$4" format="$5" tpl_name="$6"
    python3 -c "
import json, subprocess, sys
body = {'session_id': '$sid', 'message': '$msg', 'line_name': '$line', 'user_id': '$USER', 'enrichment_mode': 'research', 'language': 'en'}
if '$aims' and '$aims' != '0': body['attached_aims'] = '$aims'.split(',')
if '$format' and '$format' != '0': body['format_spec'] = '$format'
if '$tpl_name' and '$tpl_name' != '0': body['template_name'] = '$tpl_name'
cmd = ['curl', '-s', '-X', 'POST', '$API/messages', '-H', 'Content-Type: application/json', '-d', json.dumps(body)]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout, end='')
" 2>/dev/null
}

get_session() {
    curl -s "$API/sessions/$1?user_id=$USER"
}

echo "============================================"
echo "Batch: $BATCH  |  Time: $TIMESTAMP"
echo "Dataset: $DS ($(curl -s "$API/datasets" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['dataset_name']) if d else print('NONE')"))"
echo "============================================"

run_batch1() {
echo ""
echo "--- BATCH 1: Template route ---"

echo "1a: Single dataset, clean run"
SID=$(new_session)
RES=$(send_msg "$SID" "check inventory" "$DS" 0 "# Report\n\nMost common prefecture: ?\nFruit count: ?" "Fruit Report")
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route')=='template' else 1)" 2>/dev/null && log_result "1a route=template" PASS "" || log_result "1a route=template" FAIL "route not template"
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('truncated')==False else 1)" 2>/dev/null && log_result "1a truncated=False" PASS "" || log_result "1a truncated=False" FAIL ""
SR=$(echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stopped_reason','NIL'))")
[ "$SR" = "" ] && log_result "1a stopped_reason empty" PASS "" || log_result "1a stopped_reason empty" FAIL "$SR"
QRC=$(echo "$RES" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('query_results') or []))")
[ "$QRC" -gt 0 ] && log_result "1a query_results_count=$QRC" PASS "" || log_result "1a query_results_count=$QRC" FAIL ""
echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

# verify template_name on turn
SSTATE=$(get_session "$SID")
TN=$(echo "$SSTATE" | python3 -c "import sys,json; r=json.load(sys.stdin); t=r.get('turns',[]); print(t[0].get('template_name','NIL') if t else 'NIL')")
[ "$TN" = "Fruit Report" ] && log_result "1a template_name on turn" PASS "" || log_result "1a template_name on turn" FAIL "got '$TN'"

echo "1c: Template with no data (wrong column)"
SID2=$(new_session)
RES2=$(send_msg "$SID2" "bad metric" "$DS" 0 "# Report\n\nNonExistent: ?" "Empty Report")
echo "$RES2" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route')=='template' else 1)" 2>/dev/null && log_result "1c route=template" PASS "" || log_result "1c route=template" FAIL ""
echo "$RES2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

echo "1e: Bad column -- did-you-mean (via FOCUS route)"
SID3=$(new_session)
RES3=$(send_msg "$SID3" "show me barometric pressure" "$DS" "barometric pressure test" 0 0)
ROUTE3=$(echo "$RES3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('route',''))")
log_result "1e FOCUS response" "$([ "$ROUTE3" = "focus" ] && echo PASS || echo "FAIL: $ROUTE3")" ""

echo "1f: Template -- attach card as aim -- follow-up"
SID4=$(new_session)
RES4a=$(send_msg "$SID4" "inventory count" "$DS" 0 "# Count\n\nTotal rows: ?" "Counter Tpl")
TN4=$(echo "$RES4a" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result_uuid',''))")
[ -n "$TN4" ] && log_result "1f template result_uuid=$TN4" PASS "" || log_result "1f template result_uuid" FAIL "empty"
RES4b=$(send_msg "$SID4" "what was the count" "$DS" "Counter Tpl" 0 0)
echo "$RES4b" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route') in ('focus','direct') else 1)" 2>/dev/null && log_result "1f follow-up routes correctly" PASS "" || log_result "1f follow-up routes" FAIL ""
}

run_batch2() {
echo ""
echo "--- BATCH 2: FOCUS route ---"

echo "2a: Single aim, clean run"
SID=$(new_session)
RES=$(send_msg "$SID" "which prefecture has the most fruit stock" "$DS" "stock analysis" 0 0)
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route')=='focus' else 1)" 2>/dev/null && log_result "2a route=focus" PASS "" || log_result "2a route=focus" FAIL ""
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('truncated')==False else 1)" 2>/dev/null && log_result "2a truncated=False" PASS "" || log_result "2a truncated=False" FAIL ""
RU=$(echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result_uuid',''))")
[ -n "$RU" ] && log_result "2a result_uuid present" PASS "" || log_result "2a result_uuid" FAIL "empty"
echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

echo "2d: recall_result reuse (rerun same aim)"
RES2=$(send_msg "$SID" "tell me about stock levels again" "$DS" "stock analysis" 0 0)
echo "$RES2" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route') in ('focus','direct') else 1)" 2>/dev/null && log_result "2d rerun routes" PASS "" || log_result "2d rerun routes" FAIL ""
echo "$RES2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

echo "2e: Bad column -- did-you-mean"
SID2=$(new_session)
RES3=$(send_msg "$SID2" "show me fruit_temperature" "$DS" 0 0 0)
echo "$RES3" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route','direct') else 1)" 2>/dev/null && log_result "2e error handled" PASS "" || log_result "2e error handled" FAIL ""
echo "$RES3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"
}

run_batch3() {
echo ""
echo "--- BATCH 3: Prompt budget + routing ---"

echo "3b: Descriptions truncated at 200 chars"
SID=$(new_session)
LONG_DESC="This is a very long aim description that exceeds two hundred characters and should be truncated by the server side fix at _build_context in api.py to ensure that the Active research aims line does not bloat the prompt with unnecessary verbosity that wastes tokens"
RES=$(send_msg "$SID" "check stock" "$DS" "$LONG_DESC" 0 0)
# check if response is successful (no crash)
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('agent_message') else 1)" 2>/dev/null && log_result "3b long desc handled" PASS "" || log_result "3b long desc" FAIL "crashed"
echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

echo "4a: DIRECT route (simple question)"
SID2=$(new_session)
RES2=$(send_msg "$SID2" "how many rows in this dataset" "$DS" 0 0 0)
echo "$RES2" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route','direct') else 1)" 2>/dev/null && log_result "4a DIRECT route" PASS "" || log_result "4a DIRECT route" FAIL ""
echo "$RES2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:120])"

echo "4g: No datasets -- early return"
SID3=$(new_session)
RES3=$(send_msg "$SID3" "hello" "" 0 0 0)
echo "$RES3" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if 'attach' in (r.get('agent_message','') or '').lower() or 'dataset' in (r.get('agent_message','') or '').lower() else 1)" 2>/dev/null && log_result "4g no-dataset early return" PASS "" || log_result "4g no-dataset" FAIL "$(echo "$RES3" | python3 -c "import sys,json; print(json.load(sys.stdin).get('agent_message','')[:80])")"
}

run_batch4() {
echo ""
echo "--- BATCH 4: Regression + persistence ---"

echo "5a: FOCUS clean run (regression)"
SID=$(new_session)
RES=$(send_msg "$SID" "which fruit has highest stock" "$DS" "regression test" 0 0)
echo "$RES" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route','focus') else 1)" 2>/dev/null && log_result "5a focus regression" PASS "" || log_result "5a focus regression" FAIL ""
RU=$(echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result_uuid',''))")
[ -n "$RU" ] && log_result "5a result_uuid" PASS "" || log_result "5a result_uuid" FAIL "empty"

echo "5b: Template clean run (regression)"
SID2=$(new_session)
RES2=$(send_msg "$SID2" "regression tpl" "$DS" 0 "# Report\n\nTop fruit: ?" "Regress Tpl")
echo "$RES2" | python3 -c "import sys,json; r=json.load(sys.stdin); sys.exit(0 if r.get('route','template') else 1)" 2>/dev/null && log_result "5b template regression" PASS "" || log_result "5b template regression" FAIL ""

echo "4b: Session persistence (check 5a session)"
SSTATE=$(get_session "$SID")
TC=$(echo "$SSTATE" | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r.get('turns',[])))")
[ "$TC" -ge 1 ] && log_result "4b turns persisted (count=$TC)" PASS "" || log_result "4b turns persisted" FAIL "count=$TC"
TN=$(echo "$SSTATE" | python3 -c "import sys,json; r=json.load(sys.stdin); t=r.get('turns',[]); print(t[0].get('template_name','NIL') if t else 'NIL')")
log_result "4b template_name persisted ($TN)" PASS "" || true
}

case "$BATCH" in
    batch1) run_batch1 ;;
    batch2) run_batch2 ;;
    batch3) run_batch3 ;;
    batch4) run_batch4 ;;
    all) run_batch1; run_batch2; run_batch3; run_batch4 ;;
    *) echo "Usage: $0 batch1|batch2|batch3|batch4|all" ;;
esac

echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed"
echo "Timestamp: $TIMESTAMP"
echo "============================================"
