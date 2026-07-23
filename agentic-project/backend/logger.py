"""Structured debug logger with Level 0/1/2 support."""
import os
import logging
from datetime import datetime
from config import get_settings

logger = logging.getLogger("debug")

_log_dir = None

def _get_log_dir():
    global _log_dir
    if _log_dir is None:
        _log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(_log_dir, exist_ok=True)
    return _log_dir

def log_route(question: str, route: str, elapsed: float):
    settings = get_settings()
    if settings.log_level >= 1:
        print(f"[ROUTE] \"{question[:80]}\" → {route} ({elapsed:.2f}s)")
    if settings.log_level >= 2:
        _write_file(f"[ROUTE] \"{question}\" → {route} ({elapsed:.2f}s)\n")

def log_llm_call(step: str, elapsed: float, tokens: int = 0, detail: str = ""):
    settings = get_settings()
    if settings.log_level >= 1:
        print(f"[LLM] {step}: {elapsed:.2f}s, {tokens} tokens {detail}")
    if settings.log_level >= 2:
        _write_file(f"[LLM] {step}: {elapsed:.2f}s, {tokens} tokens {detail}\n")

def log_sql(step: str, detail: str):
    settings = get_settings()
    if settings.log_level >= 1:
        print(f"[SQL] {step}: {detail}")
    if settings.log_level >= 2:
        _write_file(f"[SQL] {step}: {detail}\n")

def log_aims(count: int, detail: str = ""):
    settings = get_settings()
    if settings.log_level >= 1:
        print(f"[AIMS] {count} proposals {detail}")
    if settings.log_level >= 2:
        _write_file(f"[AIMS] {count} proposals {detail}\n")

def log_response(route: str, result_uuid: str = "", proposals: int = 0):
    settings = get_settings()
    if settings.log_level >= 1:
        uuid_short = result_uuid[:8] if result_uuid else "none"
        print(f"[RESP] route={route}, result_uuid={uuid_short}, proposals={proposals}")
    if settings.log_level >= 2:
        _write_file(f"[RESP] route={route}, result_uuid={result_uuid or 'none'}, proposals={proposals}\n")

def log_full_prompt(session_id: str, step: str, prompt: str, response: str):
    settings = get_settings()
    if settings.log_level >= 2:
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_id = session_id[:8] if session_id else "unknown"
        filename = f"{ts}_{safe_id}.log"
        filepath = os.path.join(_get_log_dir(), filename)
        with open(filepath, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{step}] {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n")
            f.write(f"PROMPT:\n{prompt[:4000]}\n")
            f.write(f"{'─'*40}\n")
            f.write(f"RESPONSE:\n{response[:4000]}\n")

def _write_file(text: str):
    try:
        ts = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(_get_log_dir(), f"debug_{ts}.log")
        with open(filepath, "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
    except Exception:
        pass
