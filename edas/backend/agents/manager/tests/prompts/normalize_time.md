You extract and normalize a time phrase from a user query into a strict canonical JSON form for downstream parsing.

Reference now: {reference_now}
(Use only for context — do NOT compute calendar dates for relative phrases yourself.)

User time phrase:
{time_raw}

{validation_error_block}

---

## Output format

Return ONLY raw JSON — no markdown fences, no explanation, no trailing commas.
Exactly one of these four shapes:

### 1. Relative — rolling or calendar-bound window
{{
  "kind": "relative",
  "canonical": "<form from allowed list below>"
}}

### 2. Absolute — explicit date or date range
{{
  "kind": "absolute",
  "start": "YYYY-MM-DD",
  "end": "YYYY-MM-DD"
}}

### 3. Ambiguous — valid time expression but meaning is unclear
{{
  "kind": "ambiguous",
  "raw": "<original phrase>",
  "interpretations": ["past 7 days", "this week"]
}}

### 4. Invalid — input is not a time expression at all
{{
  "kind": "invalid",
  "reason": "<one sentence explaining why>"
}}

---

## Allowed relative canonical forms

Units: hours, days, weeks, months, years
Always use plural form even for N=1 (e.g. "past 1 days", "past 1 hours").
N must be a positive integer between 1 and 999.

- past N hours
- past N days
- past N weeks
- past N months
- past N years
- today
- yesterday
- this week
- this month
- this year
- this quarter

---

## Normalization rules

**Word numbers → digits**
two → 2, three → 3, a/an → 1
("a week ago" → "past 1 weeks", "an hour" → "past 1 hours")

**Synonym mapping → canonical**
| User says | Canonical |
|-----------|-----------|
| last N days / previous N days | past N days |
| last N weeks / past N weeks | past N weeks |
| last N months | past N months |
| last N hours / previous N hours | past N hours |
| last N years | past N years |
| recently / lately | ambiguous |
| last week | ambiguous |
| last month | ambiguous |

**Casing and punctuation**
Ignore leading/trailing spaces, punctuation, and casing.
"Past 2 Days." → "past 2 days"
"LAST 3 HOURS" → "past 3 hours"

**Absolute ranges**
Normalize any date format to YYYY-MM-DD.
Accepted input formats: YYYY-MM-DD, MM/DD/YYYY, DD-MM-YYYY,
"Jan 1 2025", "1st January 2025", "January 1st to January 31st 2025", "7th Jan"

If no year is given, infer from reference now.
If start > end, swap them before output.
Single date ("on 2025-06-15", "7th Jan") → start and end are the same date.

**Out-of-bounds N**
N < 1 or N > 999 → return invalid with reason.

---

## Examples

Input: past two days
Output: {{"kind":"relative","canonical":"past 2 days"}}

Input: last 3 hours
Output: {{"kind":"relative","canonical":"past 3 hours"}}

Input: a week ago
Output: {{"kind":"relative","canonical":"past 1 weeks"}}

Input: this quarter
Output: {{"kind":"relative","canonical":"this quarter"}}

Input: last week
Output: {{"kind":"ambiguous","raw":"last week","interpretations":["past 7 days","this week"]}}

Input: Jan 1 to Jan 31 2025
Output: {{"kind":"absolute","start":"2025-01-01","end":"2025-01-31"}}

Input: Jan 5 to Jan 7
Output: {{"kind":"absolute","start":"2026-01-05","end":"2026-01-07"}}

Input: 7th Jan
Output: {{"kind":"absolute","start":"2026-01-07","end":"2026-01-07"}}

Input: on 2025-06-15
Output: {{"kind":"absolute","start":"2025-06-15","end":"2025-06-15"}}

Input: 2025-06-01 to 2025-01-01
Output: {{"kind":"absolute","start":"2025-01-01","end":"2025-06-01"}}

Input: sort by revenue
Output: {{"kind":"invalid","reason":"'sort by revenue' is not a time expression."}}

Input: recently
Output: {{"kind":"ambiguous","raw":"recently","interpretations":["past 7 days","past 30 days"]}}
