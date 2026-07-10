Extract structured data analysis slots from a user message.

Reference today: {reference_now}

Session state:
{session_state_json}

Return ONLY valid JSON:
{{
  "line_mention": "machine or line name, or null",
  "line_mentions": ["all machine/line names mentioned"],
  "time_raw": "time phrase like 'last month', 'past 7 days', or null",
  "aim_raw": "analysis aim like 'cost by fruit', or null",
  "scope": {{
    "intent_mode": "single" | "joint" | "per_slot"
  }}
}}

Rules:
- Extract line_mention for the primary machine.
- Extract ALL machine names into line_mentions.
- Keep time_raw as the user said it — do not compute dates.
- Keep aim_raw as the user said it — do not modify.
- If a field is not mentioned, use null.
- Do not invent values.