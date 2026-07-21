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
- A line/machine mention is USUALLY a proper noun or short code the user names directly — it does not have to appear in a specific sentence pattern like "run a report on X". Purely conversational or informational framing ("tell me about X", "what do you know about X", "show me X", "how's X doing") still counts — extract X as line_mention. A separate lookup step validates the name against the registry afterward, so a wrong guess is harmless; leaving line_mention null when the user clearly named something is the costly mistake (it stalls the conversation).
- Only use null for line_mention when the message genuinely contains no candidate name at all (e.g. "what can you help me with", "hello", "yes").

Examples:
- "tell me about vinayaka" → line_mention: "vinayaka"
- "what do you know about FRUITS_TEST" → line_mention: "FRUITS_TEST"
- "show me AM307A" → line_mention: "AM307A"
- "average cost by fruit" (no name mentioned, only an analysis request) → line_mention: null, aim_raw: "average cost by fruit"
- "hi, what can this tool do" → line_mention: null