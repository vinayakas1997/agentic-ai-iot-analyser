import json


def parse_json_from_message(raw: str) -> dict:
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            chunk = part.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                result = json.loads(chunk)
                return result if isinstance(result, dict) else {}
    result = json.loads(raw.strip())
    return result if isinstance(result, dict) else {}
