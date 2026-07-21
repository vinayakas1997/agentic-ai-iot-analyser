import json


def parse_json_from_message(raw: str) -> dict:
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            chunk = part.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                return json.loads(chunk)
    return json.loads(raw.strip())
