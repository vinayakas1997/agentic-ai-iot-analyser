# Session 1 — Human Testing Checklist

**Date:** 2026-07-24
**Project:** agentic-project
**URL:** http://localhost:7008
**Docker logs:** `docker compose logs -f backend`

## How to Use
1. Open the app in your browser at `http://localhost:7008`
2. Open DevTools Console (`F12` → Console tab) — to see any `console.error` messages
3. In a terminal, run `docker compose logs -f backend` to watch backend logs
4. Go through each scenario below in order
5. Mark `[x]` if it worked, `[ ]` if it didn't
6. If something fails, paste the following here:
   - Which scenario failed
   - What you saw vs what was expected
   - Any console error messages

## Pre-Check: Services Running

All 3 containers should be healthy:

```
$ docker compose ps
NAME                          STATUS
agentic-project-backend-1     Up (healthy)
agentic-project-db-1          Up (healthy)
agentic-project-frontend-1    Up
```

- [x] Confirmed

---

## S1: Attach dataset + DIRECT message (Fixes 1, 5, 8)

**What:** Open a session, attach a dataset, ask a question that triggers DIRECT route (a specific factual question).

**Steps:**
1. Search for "FRUITS_TEST" in the search bar and select it
2. Click "Attach" to attach it to the session
3. In the chat input, type: `"show me the top 10 fruits by quantity"`
4. Press Enter and wait for the response

**Expected:**
- Status messages cycle ("Analyzing...", "Generating response...")
- A response comes back (not stuck loading)
- A table with fruit data renders below the message
- No "generate_aim is not defined" error in backend logs
- No `console.error` messages in browser DevTools
- Table name displayed correctly (should show "fruits_test" or similar)

- [x] Worked
- [ ] Didn't work — what happened:

---

## S2: SUGGEST route (Fixes 8, 12)

**What:** Ask an exploratory question that triggers the SUGGEST route.

**Steps:**
1. Still attached to FRUITS_TEST (or re-attach if needed)
2. Type: `"what can I analyze with this data?"`
3. Press Enter and wait

**Expected:**
- Returns 3 exploration ideas (not a SQL query)
- Each idea has a name, description, and datasets listed
- No "no datasets attached" nonsense in the proposals
- No "Missing LIMIT clause" warning in backend logs

- [ ] Worked
- [ ] Didn't work — what happened:
       I created the new session but in dthe summary mode from where do I select teh aim this is some thing or i dont know ?
---

## S3: Attach aims without datasets guard (Fix 12)

**What:** Test what happens when you attach aims but no datasets.

**Steps:**
1. Create a NEW session (click the + or "New Session" button)
2. Do NOT attach any datasets
3. In "SUMMARY" mode, select some aim proposals if they exist (from recent conversations)
4. Switch back to "RESEARCH" mode
5. Type a question and press Enter

**Expected:**
- A message appears saying aims are attached but datasets are needed
- The app does not crash or show a generic error

- [x] Worked: when select the 
- [ ] Didn't work — what happened:
     
---

## S4: FOCUS route (Fix 8)

**What:** Ask a deep-dive question that triggers FOCUS route.

**Steps:**
1. Attach FRUITS_TEST dataset
2. Type: `"analyze fruit quality trends in detail"`
3. Press Enter and wait

**Expected:**
- Generates a SQL query with LIMIT
- Executes it and returns a detailed interpretation
- No "Missing LIMIT clause" warning in backend logs

- [x] Worked
- [ ] Didn't work — what happened:

---

## S5: DEEP route — multi-step research (Fix 13)

**What:** Ask a multi-step research question that triggers DEEP route.

**Steps:**
1. Attach FRUITS_TEST dataset
2. Type: `"research all fruit patterns — start with sales, then quality"`
3. Press Enter and wait (this takes longer — up to 30 seconds)

**Expected:**
- Runs multiple iterations (check backend logs for `DEEP` route)
- Returns a final summary message
- No "final_msg" errors in backend logs
- Server does not crash

- [x] Worked
- [ ] Didn't work — what happened:

---

## S6: Page reload — chatQueryResults persistence (Fix 2)

**What:** After getting results, reload the page and verify they're still there.

**Steps:**
1. After S1 or S4 completed successfully, note the results
2. Reload the page (`F5` or `Ctrl+R`)
3. Wait for the page to load completely

**Expected:**
- The session reloads with all previous turns visible
- The query results (tables) are still visible below the messages
- You do NOT need to re-run the query to see results
- No `console.error` messages in DevTools

- [x] Worked
- [ ] Didn't work — what happened:

---

## S7: Conversation history across turns (Fix 9)

**What:** Make a second message in the same session — the LLM should remember the first message.

**Steps:**
1. After S1 completed (you asked about top fruits), still in the same session
2. Type: `"now show me only apples"` (a follow-up question)
3. Press Enter and wait

**Expected:**
- The LLM understands "now" refers to the previous question about fruits
- Returns filtered results for apples only (not a fresh response as if no context)
- Backend log shows "Conversation History" with the previous turn

- [x] Worked
- [ ] Didn't work — what happened:

---

## S8: SUMMARY mode (Fix 9)

**What:** Test SUMMARY mode with context summaries.

**Steps:**
1. In an existing session with at least 2-3 messages
2. In the mode dropdown, switch to "SUMMARY" mode
3. Type: `"summarize what we did so far"`
4. Press Enter and wait

**Expected:**
- The LLM references previous conversation context
- Returns a coherent summary of the session
- No errors in backend logs

- [x] Worked
- [ ] Didn't work — what happened:

---

## S9: Auto-naming new sessions (Fix 15)

**What:** When you send the first message in a new session, it should auto-name.

**Steps:**
1. Create a new session
2. Type: `"analyze fruit quality between suppliers"`
3. Press Enter

**Expected:**
- After the response comes back, the session title updates to "analyze fruit quality between suppliers" (or truncated version)
- In the left sidebar, the session list shows the new title

- [x] Worked
- [ ] Didn't work — what happened:

---

## S10: Dead code removal — no WebSocket warnings (Fixes 6, 10)

**What:** Verify no WebSocket-related errors or warnings appear.

**Steps:**
1. Check browser DevTools Console
2. Also check backend logs for any `/ws` connection attempts

**Expected:**
- No "WebSocket connection failed" errors in Console
- No `/ws` URL connection attempts
- No "wsStatus" related errors

- [x] Worked
- [ ] Didn't work — what happened:

---

## Final Summary

At the end, fill this:

| Scenario | Status |
|----------|--------|
| S1: Attach + DIRECT | Done |
| S2: SUGGEST route | Done |
| S3: Aims without datasets guard | Done |
| S4: FOCUS route | Done |
| S5: DEEP route | Done |
| S6: Page reload persistence | Done |
| S7: Conversation history | Done |
| S8: SUMMARY mode | Done |
| S9: Auto-naming sessions | Done |
| S10: No WebSocket warnings | Done |

**Any other observations:**
<!-- Paste anything unexpected you noticed -->
