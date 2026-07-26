# Bilingual Support Plan (English + Japanese) — Version 1

## Architecture Overview

Only the **LLM response language** changes. All prompts (`.md` files) stay in English. A `language`
field (`"en"` / `"ja"`) flows through every layer: frontend toggle → API → session DB → LangGraph
state → prompt injection → post-response validation.

---

## Phase 1 — Foundation (Data Layer)

### 1.1 Add `language` to ManagerState

**File:** `edas/backend/agents/manager/state.py`

```python
class ManagerState(TypedDict):
    # ... existing fields ...
    language: str  # "en" or "ja", default "en"
```

### 1.2 Add `language` to DB model

**File:** `edas/backend/db/models.py` — `ManagerSession` table

```python
language: Mapped[str] = mapped_column(Text, nullable=False, default="en")
```

### 1.3 Add `language` to API request schema

**File:** `edas/backend/api/routes/manager.py`

```python
class MessageIn(BaseModel):
    message: str = Field(..., min_length=1)
    line_name: str = ""
    language: str = "en"  # ← new, passed from frontend
```

Also add to `SessionCreateOut` and `create_session()` response to return the language.

### 1.4 Persist `language` across session turns

**File:** `edas/backend/agents/manager/session_store.py`

Add `"language"` to `PERSISTED_STATE_KEYS` tuple so it's saved/loaded via `state_to_json()` /
`state_from_json()`.

**File:** `edas/backend/agents/manager/session_db.py`

- `save_session()` — persist `language` to `ManagerSession.language` column
- `load_session()` — restore `language` from `state_json`
- `create_session()` — accept optional `language` parameter, default `"en"`
- `get_session_row()` — already returns full `ManagerSession` row (no change needed)

### 1.5 Return `language` in API responses

**File:** `edas/backend/agents/manager/session_store.py` — `format_turn_response()`

```python
return {
    # ... existing fields ...
    "language": state.get("language", "en"),
}
```

**File:** `edas/backend/agents/manager/session_service.py` — `run_session_turn()`

Accept `language` parameter and pass to `run_manager_agent()`.

**File:** `edas/backend/agents/manager/runner.py` — `run_manager_agent()`

Accept `language` parameter, include in state dict passed to LangGraph.

### 1.6 Update API route to pass language

**File:** `edas/backend/api/routes/manager.py`

```python
@router.post("/sessions/{session_id}/messages")
async def post_manager_message(session_id: str, body: MessageIn) -> dict:
    user_id = get_default_user_id()
    return await run_session_turn(
        user_id=user_id,
        session_id=session_id,
        user_message=body.message,
        line_name=body.line_name,
        language=body.language,  # ← new
    )
```

---

## Phase 2 — Language Detection & Transmission

### 2.1 Frontend language toggle

**File:** `edas/frontend/src/stores/uiStore.ts`

Add:
```ts
language: "en" | "ja";
setLanguage: (lang: "en" | "ja") => void;
toggleLanguage: () => void;
```

**File:** `edas/frontend/src/components/Navbar.tsx`

Add toggle button between `"EN"` and `"日本語"`, reading/writing `language` from `uiStore`.

### 2.2 Pass language in all API calls

**File:** `edas/frontend/src/api/manager.ts`

```ts
export async function createSession(language = "en"): Promise<{...}> {
  const { data } = await managerClient.post("/manager/sessions", { language });
  return data;
}

export async function sendMessage(
  sessionId: string,
  message: string,
  lineName = "",
  language = "en"
): Promise<MessageResponse> {
  const { data } = await managerClient.post(`...`, {
    message,
    line_name: lineName,
    language,
  });
  return data;
}
```

**File:** `edas/frontend/src/stores/sessionStore.ts`

Modify `newSession()` and `sendUserMessage()` to read `language` from `uiStore` and pass to API.

### 2.3 Auto-detect fallback (backend)

**File:** `edas/backend/agents/manager/language_detect.py` (new)

```python
import re

# Japanese Unicode ranges
JA_HIRAGANA = re.compile(r"[\u3040-\u309F]")
JA_KATAKANA = re.compile(r"[\u30A0-\u30FF]")
JA_KANJI = re.compile(r"[\u4E00-\u9FFF]")

def detect_language(text: str) -> str:
    """Detect if text is Japanese by checking for CJK characters."""
    if not text:
        return "en"
    if JA_HIRAGANA.search(text) or JA_KATAKANA.search(text) or JA_KANJI.search(text):
        return "ja"
    return "en"
```

**File:** `edas/backend/agents/manager/runner.py`

In `run_manager_agent()`, if no explicit `language` is provided, call `detect_language(user_message)`:

```python
language = existing.get("language") or kwargs.get("language") or detect_language(user_message)
```

This ensures backward compatibility: old clients that don't send `language` will get auto-detected
from their message.

---

## Phase 3 — LLM Prompt Injection (Core Mechanism)

### 3.1 Create language instructions

**File:** `edas/backend/agents/manager/prompts_lang.py` (new)

```python
LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "en": "",
    "ja": (
        "Respond in Japanese.\n"
        "Keep all JSON keys, dataset names, column names, line names, "
        "and canonical time phrases in English."
    ),
}
```

### 3.2 Modify `load_prompt()` to inject language instruction

**File:** `edas/backend/agents/manager/prompts.py`

```python
from agents.manager.prompts_lang import LANGUAGE_INSTRUCTIONS

def load_prompt(name: str, *, language: str = "en", **kwargs: str) -> str:
    text = (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    if kwargs:
        text = text.format(**kwargs)
    lang_instr = LANGUAGE_INSTRUCTIONS.get(language, "")
    if lang_instr:
        text = text + "\n\n" + lang_instr
    return text
```

### 3.3 Inject language into all 6 prompt callers

Each caller passes `language=state.get("language", "en")`:

| File | Function | Prompt name | Change |
|------|----------|-------------|--------|
| `nodes/extract.py:303` | `extract_slots()` | `extract_slots` | Add `language=state.get("language", "en")` to `load_prompt()` |
| `nodes/explore_aims.py:241` | `propose_or_refine_plans()` | `propose_analysis_plans` | Same |
| `nodes/plan.py:152` | `reorganize_aim()` | `reorganize_aim` | Same |
| `nodes/plan.py:206` | `_generate_plan_benefits()` | `plan_benefits` | Same |
| `nodes/advisory.py:49` | `answer_advisory()` | `advisory_answer` | Same |
| `time_resolution.py:298` | `normalize_with_llm()` | `normalize_time` | Same |

**Important:** For `normalize_time.md`, the instruction must be extra strict:

```python
"ja": (
    "Respond in Japanese.\n"
    "Keep all JSON keys, dataset names, column names, line names, "
    "and canonical time phrases in English.\n"
    "CRITICAL: The 'canonical' field must be an exact match from the "
    "allowed list (e.g. 'past 2 days', 'past 1 weeks'). Do NOT translate it."
),
```

### 3.4 Post-response JSON key validation

**File:** `edas/backend/agents/manager/json_validator.py` (new)

```python
import json
from typing import Any

REQUIRED_KEYS: dict[str, set[str]] = {
    "extract_slots": {
        "clarification", "line_mentions", "scope",
        "line_slots_detail", "line_mention", "time_raw",
        "time_start_raw", "time_end_raw", "aim_raw",
    },
    "reorganize_aim": {"aims", "alias_name", "notes"},
    "normalize_time": {"kind"},
    "propose_analysis_plans": {"proposals"},
}

def validate_parsed_json(
    data: dict,
    prompt_name: str,
) -> tuple[bool, str]:
    """Check all expected keys exist and are in English."""
    expected = REQUIRED_KEYS.get(prompt_name)
    if not expected:
        return True, ""
    missing = expected - set(data.keys())
    if missing:
        return False, f"Missing keys: {missing}"
    # Check all keys are ASCII (no CJK in keys)
    for key in data.keys():
        if isinstance(key, str) and any(ord(c) > 127 for c in key):
            return False, f"Non-ASCII key found: '{key}'"
    return True, ""

def validate_recursive_keys(obj: Any, path: str = "") -> list[str]:
    """Recursively check that all dict keys in nested structure are ASCII."""
    errors: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            current = f"{path}.{key}" if path else str(key)
            if isinstance(key, str) and any(ord(c) > 127 for c in key):
                errors.append(f"Non-ASCII key at '{current}'")
            errors.extend(validate_recursive_keys(val, current))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(validate_recursive_keys(item, f"{path}[{i}]"))
    return errors
```

**Usage in each node that parses JSON:**

```python
from agents.manager.json_validator import validate_parsed_json, validate_recursive_keys

# After parsing:
ok, msg = validate_parsed_json(parsed, "extract_slots")
key_errors = validate_recursive_keys(parsed)
if not ok or key_errors:
    # Fall back: retry with stricter instruction or return empty
    parsed = {}
```

---

## Phase 4 — Time Phrase Translation (Critical Path)

### 4.1 Create Japanese time phrase translator

**File:** `edas/backend/agents/manager/time_translator.py` (new)

```python
"""
Translate Japanese time phrases to English canonical forms
before sending to normalize_time.md.

This uses pattern matching (zero latency, no API call).
"""

import re

_JA_TO_EN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^過去\s*(\d+)\s*日間?$"), r"past \1 days"),
    (re.compile(r"^過去\s*(\d+)\s*週間?$"), r"past \1 weeks"),
    (re.compile(r"^過去\s*(\d+)\s*[ヶか]月$"), r"past \1 months"),
    (re.compile(r"^過去\s*(\d+)\s*年$"), r"past \1 years"),
    (re.compile(r"^過去\s*(\d+)\s*時間$"), r"past \1 hours"),
    (re.compile(r"^今日$"), "today"),
    (re.compile(r"^昨日$"), "yesterday"),
    (re.compile(r"^今週$"), "this week"),
    (re.compile(r"^今月$"), "this month"),
    (re.compile(r"^今年$"), "this year"),
    (re.compile(r"^今四半期$"), "this quarter"),
    (re.compile(r"^最近$"), "recently"),
    (re.compile(r"^先週$"), "last week"),
    (re.compile(r"^先月$"), "last month"),
    (re.compile(r"^先日$"), "recently"),
    # Word-number patterns: 二日 → 2 days
    (re.compile(r"^過去\s*一\s*日間?$"), "past 1 days"),
    (re.compile(r"^過去\s*二\s*日間?$"), "past 2 days"),
    (re.compile(r"^過去\s*三\s*日間?$"), "past 3 days"),
    (re.compile(r"^過去\s*四\s*日間?$"), "past 4 days"),
    (re.compile(r"^過去\s*五\s*日間?$"), "past 5 days"),
    (re.compile(r"^過去\s*六\s*日間?$"), "past 6 days"),
    (re.compile(r"^過去\s*七\s*日間?$"), "past 7 days"),
    (re.compile(r"^過去\s*一\s*週間?$"), "past 1 weeks"),
    (re.compile(r"^過去\s*二\s*週間?$"), "past 2 weeks"),
    (re.compile(r"^過去\s*三\s*週間?$"), "past 3 weeks"),
    # Date patterns: 2025年1月5日 → absolute date
    (
        re.compile(
            r"^(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*"
            r"(?:から|~|〜|[-–])\s*"
            r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日$"
        ),
        lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d} "
                  f"to {m.group(4)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}",
    ),
    (
        re.compile(
            r"^(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日$"
        ),
        lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}",
    ),
]


def translate_time_phrase(phrase: str) -> str:
    """Convert a Japanese time phrase to English. Returns original if not Japanese."""
    stripped = phrase.strip()
    for pattern, replacement in _JA_TO_EN:
        if isinstance(replacement, str):
            match = pattern.fullmatch(stripped)
            if match:
                return match.expand(replacement)
        else:
            match = pattern.fullmatch(stripped)
            if match:
                return replacement(match)
    return phrase  # Not a recognized Japanese pattern — pass through


def needs_translation(phrase: str, language: str) -> bool:
    """Return True if the phrase should be translated before normalization."""
    if language != "ja":
        return False
    if not phrase:
        return False
    # Check if it contains Japanese characters
    return bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", phrase))
```

### 4.2 Wire translator into time resolution

**File:** `edas/backend/agents/manager/time_resolution.py`

```python
from agents.manager.time_translator import translate_time_phrase, needs_translation

async def normalize_time_phrase(
    phrase: str,
    reference_now: str,
    *,
    use_llm: bool = True,
    language: str = "en",  # ← new parameter
) -> tuple[dict, int]:
    # Translate if needed
    if needs_translation(phrase, language):
        translated = translate_time_phrase(phrase)
        if translated != phrase:
            phrase = translated  # Japanese → English

    if not use_llm:
        return mock_normalize(phrase), 1

    llm_out = await normalize_with_llm(phrase, reference_now, language=language)
    ok, reason = validate_llm_out(llm_out)
    if ok or reason not in RETRY_REASONS:
        return llm_out, 1

    llm_out = await normalize_with_llm(phrase, reference_now, validation_error=reason, language=language)
    return llm_out, 2
```

Also update `normalize_with_llm()` to accept and pass `language`:

```python
async def normalize_with_llm(
    phrase: str,
    reference_now: str,
    validation_error: str = "",
    language: str = "en",
) -> dict:
    system = load_prompt(
        "normalize_time",
        language=language,  # ← new
        reference_now=reference_now,
        time_raw=phrase,
        validation_error_block=_validation_error_block(validation_error),
    )
    # ... rest unchanged
```

### 4.3 Update callers of normalize_time_phrase

**File:** `edas/backend/agents/manager/nodes/plan.py` — `resolve_time_filters` function (if exists) or wherever
`normalize_time_phrase` / `resolve_time_phrase` is called, pass `language=state.get("language", "en")`.

---

## Phase 5 — Backend Hardcoded String i18n

### 5.1 Create i18n directory and files

**Directory:** `edas/backend/i18n/`

**Files:**
- `__init__.py` — Translation function `t(key, lang, **kwargs)`
- `en.json` — English strings
- `ja.json` — Japanese strings

#### `__init__.py`

```python
"""
Simple ICU-format translation loader.

Usage:
    from i18n import t
    msg = t("line_missing_hint", lang="ja")
    msg = t("aim_missing_hint", lang="ja", line_name="Vinayaka")
"""

import json
from pathlib import Path
from functools import lru_cache

_TRANSLATIONS: dict[str, dict[str, str]] = {}
_DIR = Path(__file__).parent


def _load(lang: str) -> dict[str, str]:
    path = _DIR / f"{lang}.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def t(key: str, lang: str = "en", **kwargs: str) -> str:
    if lang not in _TRANSLATIONS:
        _TRANSLATIONS[lang] = _load(lang)
    template = _TRANSLATIONS[lang].get(key)
    if template is None and lang != "en":
        template = _load("en").get(key, key)
    elif template is None:
        template = key
    return template.format(**kwargs) if kwargs else template
```

#### `en.json`

```json
{
  "line_missing_hint": "Which production line or machine is this for?\n(e.g. AM307A, ZF228)",
  "aim_examples": "(e.g. sales, downtime, average cost — or ask *what aims can we do*)",
  "aim_missing_hint": "What analysis would you like on **{line_name}**?\n{eaim}",
  "aim_missing_hint_generic": "What analysis would you like to run?\n{eaim}",
  "tier2_explore_nudge": "\n\nFor **3 more analysis options**, say *show me other options*.",
  "line_not_found": "I couldn't find **{mention}** in the IoT catalog.{hint}\n\nPlease try another name or check the spelling.",
  "line_not_found_article_hint": " Try removing the word '{article}' from the name.",
  "line_ambiguous": "Multiple lines match **\"{mention}\"**: {listed}.\n\nPlease reply with the exact line name you want.",
  "time_ambiguous": "Time phrase **\"{raw}\"** is unclear. Did you mean:\n{listed}\n\nPlease reply with one.",
  "time_parse_error": "Could not understand time phrase **\"{raw}\"**: {detail}\n\nPlease rephrase the time range.",
  "no_datasets": "**{line}** is registered but has no active datasets.\n\nPlease contact the IoT team.",
  "suggested_aims_header": "**Suggested aims:**",
  "suggested_aims_more": "  - ... and {count} more in registry",
  "suggested_aims_pending": "\\n*(Benefits from IoT team — coming soon)*",
  "plan_header": "**Plan**",
  "plan_line": "- **Line:** {line}",
  "plan_time": "- **Time:** {time}",
  "plan_aims": "- **Aims:**",
  "plan_benefits": "**Benefits:**",
  "plan_footer": "\n\nReply **go** to proceed, say *more options* for other plans, or tell me what to change.",
  "proposals_header": "Here are 3 analysis options for **{scope}**:",
  "proposals_aims": "- **Aims:** {aims}",
  "proposals_datasets": "- **Datasets:** {datasets}",
  "proposals_join": "- **Join:** {join}",
  "proposals_lines": "- **Lines:** {lines}",
  "proposals_see": "- **You might see:** {see}",
  "proposals_footer": "Say **keep plan 2** to save, **more options** for another batch, or **use saved** to list saved plans.",
  "proposals_empty": "I couldn't generate analysis options right now. Try again, or say *what aims can we do* to browse suggested aims.",
  "saved_success": "Saved **{ids}** to your plan list.",
  "saved_empty": "No plan to save. Run **more options** first, then say **keep plan 2**.",
  "saved_combine_not_found": "Could not find saved plans to combine. Say **use saved** to list them.",
  "advisory_footer_has_plan": "Reply **go** to run this plan, or tell me what to change.",
  "advisory_footer_no_plan": "What analysis would you like on **{line_name}**?",
  "ready_for_planner": "Ready for Planner Agent.\n\n**Line:** {line}\n**Aims:** {aims}",
  "source_label_line_name": "exact line name",
  "source_label_synonym": "synonym",
  "source_label_task_alias": "previous analysis alias",
  "line_matched": "You said **\"{mention}\"** — matched via **{label}** to line **{canonical}**.",
  "time_range_note": "**Time range:** {start} → {end}{raw_note}",
  "web_loaded_options": "I've loaded analysis options for **{canonical}**. You can pick any suggested aim from Context or Outputs, or describe your own analysis in chat.",
  "web_line_loaded": "I've loaded **{canonical}**. See Context for full details.",
  "web_line_loaded_from": "I've loaded **{canonical}** (from **{mention}**). See Context for full details.",
  "line_info_header": "**Line:** {line}",
  "line_info_datasets": "**Datasets:**",
  "line_info_columns": "**Columns:**",
  "line_info_more": "  - ... and {extra} more columns",
  "active_line_info": "**Active line:** {canonical} ({mention})\n\n**Context:**\n{inventory}",
  "multi_missing_fallback": "What would you like to analyze?",
  "confirm_go": "go",
  "confirm_words_list": "go, confirm, yes, proceed, ok",
  "plan_time_no_filter": "all data (no date filter)",
  "plan_time_resolved": "{start} → {end}{note}",
  "plan_time_with_raw": " (from \"{raw}\")",
  "no_time_filter": "No time filter"
}
```

#### `ja.json`

```json
{
  "line_missing_hint": "どの生産ラインまたは機械ですか？\n（例: AM307A, ZF228）",
  "aim_examples": "（例: 売上、ダウンタイム、平均コスト — または *可能な分析を表示* と質問）",
  "aim_missing_hint": "**{line_name}** でどのような分析を行いますか？\n{eaim}",
  "aim_missing_hint_generic": "どのような分析を実行しますか？\n{eaim}",
  "tier2_explore_nudge": "\n\n**さらに3つの分析オプション**をご希望の場合は、*他のオプションを表示* とお伝えください。",
  "line_not_found": "**{mention}** はIoTカタログに見つかりませんでした。{hint}\n\n別の名前を試すか、スペルを確認してください。",
  "line_not_found_article_hint": " 名前から '{article}' を削除してみてください。",
  "line_ambiguous": "**\"{mention}\"** に一致するラインが複数あります: {listed}。\n\n正確なライン名を入力してください。",
  "time_ambiguous": "時間表現 **\"{raw}\"** が不明瞭です。次のうちどれですか？\n{listed}\n\n1つを選択してください。",
  "time_parse_error": "時間表現 **\"{raw}\"** を理解できませんでした: {detail}\n\n時間範囲を言い直してください。",
  "no_datasets": "**{line}** は登録されていますが、アクティブなデータセットがありません。\n\nIoTチームに連絡してください。",
  "suggested_aims_header": "**推奨分析:**",
  "suggested_aims_more": "  - ... 他 {count} 件がレジストリにあります",
  "suggested_aims_pending": "\\n*(IoTチームによる分析メリット — 近日公開予定)*",
  "plan_header": "**計画**",
  "plan_line": "- **ライン:** {line}",
  "plan_time": "- **時間:** {time}",
  "plan_aims": "- **分析目的:**",
  "plan_benefits": "**メリット:**",
  "plan_footer": "\n\n**go** と返信して実行するか、*more options* で他の計画を表示、または変更点をお知らせください。",
  "proposals_header": "**{scope}** の3つの分析オプション:",
  "proposals_aims": "- **分析:** {aims}",
  "proposals_datasets": "- **データセット:** {datasets}",
  "proposals_join": "- **結合:** {join}",
  "proposals_lines": "- **ライン:** {lines}",
  "proposals_see": "- **確認できること:** {see}",
  "proposals_footer": "**keep plan 2** と入力して保存、**more options** で別のバッチ、または **use saved** で保存済み計画を表示します。",
  "proposals_empty": "現在、分析オプションを生成できませんでした。やり直すか、*what aims can we do* と入力して推奨分析を参照してください。",
  "saved_success": "**{ids}** を計画リストに保存しました。",
  "saved_empty": "保存する計画がありません。先に **more options** を実行し、次に **keep plan 2** とお伝えください。",
  "saved_combine_not_found": "保存された計画が見つかりません。**use saved** と入力して一覧を表示します。",
  "advisory_footer_has_plan": "**go** と返信してこの計画を実行するか、変更点をお知らせください。",
  "advisory_footer_no_plan": "**{line_name}** でどのような分析を行いますか？",
  "ready_for_planner": "Plannerエージェントの準備ができました。\n\n**ライン:** {line}\n**分析:** {aims}",
  "source_label_line_name": "正確なライン名",
  "source_label_synonym": "同義語",
  "source_label_task_alias": "過去の分析エイリアス",
  "line_matched": "「{mention}」と入力されました — **{label}** を介してライン **{canonical}** に一致しました。",
  "time_range_note": "**時間範囲:** {start} → {end}{raw_note}",
  "web_loaded_options": "**{canonical}** の分析オプションを読み込みました。ContextまたはOutputsから推奨分析を選択するか、チャットで独自の分析を説明してください。",
  "web_line_loaded": "**{canonical}** を読み込みました。詳細はContextを参照してください。",
  "web_line_loaded_from": "**{canonical}** を読み込みました（**{mention}** から）。詳細はContextを参照してください。",
  "line_info_header": "**ライン:** {line}",
  "line_info_datasets": "**データセット:**",
  "line_info_columns": "**カラム:**",
  "line_info_more": "  - ... 他 {extra} カラム",
  "active_line_info": "**アクティブライン:** {canonical} ({mention})\n\n**コンテキスト:**\n{inventory}",
  "multi_missing_fallback": "何を分析しますか？",
  "plan_time_no_filter": "全データ（日付フィルターなし）",
  "plan_time_resolved": "{start} → {end}{note}",
  "plan_time_with_raw": "（「{raw}」から）",
  "no_time_filter": "時間フィルターなし"
}
```

### 5.2 Replace hardcoded strings in all backend files

Each file needs: `from i18n import t as _t` then replace literal strings with `_t("key", lang, ...)`.

**Complete file-by-file change list:**

| File | Functions to update | Keys needed |
|------|-------------------|-------------|
| `prompt_hints.py` | `LINE_MISSING_HINT`, `_AIM_EXAMPLES`, `TIER2_EXPLORE_NUDGE`, `format_aim_missing_hint()`, `format_advisory_footer()`, `format_suggested_aims_block()`, `format_ask_for_missing()` | `line_missing_hint`, `aim_examples`, `aim_missing_hint`, `aim_missing_hint_generic`, `tier2_explore_nudge`, `advisory_footer_has_plan`, `advisory_footer_no_plan`, `suggested_aims_header`, `suggested_aims_more`, `suggested_aims_pending` |
| `message_format.py` | `_SOURCE_LABELS`, `format_line_match_note()`, `format_web_body_suggested_aims()`, `format_time_range_note()`, `format_line_info_cli()`, `format_web_body_after_line_resolve()` | `source_label_*`, `line_matched`, `web_loaded_options`, `time_range_note`, `line_info_header`, `line_info_datasets`, `line_info_columns`, `line_info_more`, `web_line_loaded`, `web_line_loaded_from` |
| `nodes/plan.py` | `_plan_time_line()`, `ask_line_ambiguous()`, `ask_time_ambiguous()`, `build_plan_message()`, `send_to_planner()` | `line_ambiguous`, `time_ambiguous`, `time_parse_error`, `plan_header`, `plan_line`, `plan_time`, `plan_aims`, `plan_benefits`, `plan_footer`, `plan_time_no_filter`, `plan_time_resolved`, `plan_time_with_raw`, `ready_for_planner` |
| `nodes/registry.py` | `sync_registry_context()`, `line_not_found()` | `no_datasets`, `line_not_found`, `line_not_found_article_hint` |
| `nodes/explore_aims.py` | `format_proposals_message()`, `propose_or_refine_plans()` | `proposals_header`, `proposals_aims`, `proposals_datasets`, `proposals_join`, `proposals_lines`, `proposals_see`, `proposals_footer`, `proposals_empty` |
| `nodes/saved_plans.py` | `save_to_shortlist()`, `combine_saved_plans()` | `saved_success`, `saved_empty`, `saved_combine_not_found` |
| `nodes/multi_line.py` | `ask_multi_missing()`, `show_suggested_aims()` | `multi_missing_fallback`, `active_line_info`, `suggested_aims_header`, `suggested_aims_more` |
| `nodes/advisory.py` | `answer_advisory()` (footer) | `advisory_footer_has_plan`, `advisory_footer_no_plan` |

**Pattern to follow:**

```python
# Before:
msg = (
    f"I couldn't find **{mention}** in the IoT catalog.{hint}\n\n"
    "Please try another name or check the spelling."
)

# After:
from i18n import t
msg = t("line_not_found", lang=state.get("language", "en"), mention=mention, hint=hint)
```

---

## Phase 6 — Frontend i18n

### 6.1 Add dependencies

```bash
cd edas/frontend
npm install i18next react-i18next i18next-browser-languagedetector
```

### 6.2 Create translation files

**Directory:** `edas/frontend/src/i18n/`

#### `en.json`

```json
{
  "app.title": "EDAS",
  "nav.dashboard": "Dashboard",
  "nav.no_session": "No session",
  "nav.new": "+ New",
  "nav.thinking": "Thinking…",
  "nav.ready": "Ready",
  "nav.session_label": "Session",
  "nav.language_en": "English",
  "nav.language_ja": "日本語",
  "chat.title": "Chat",
  "chat.completed": "Completed",
  "chat.placeholder_empty": "What would you like to analyze? Try a line name like Vinayaka or fruits test.",
  "chat.you": "You",
  "chat.manager": "Manager",
  "chat.next": "Next",
  "chat.thinking": "Thinking…",
  "chat.placeholder_input": "Ask anything…",
  "chat.placeholder_done": "Session complete",
  "chat.send": "Send",
  "chat.viewing_step": "Viewing step {step}. Select latest turn to send messages.",
  "output.title": "Outputs",
  "output.empty": "Send a message to start planning.",
  "output.no_snapshot": "No snapshot for this step.",
  "output.step_of": "Step {current} of {total}",
  "output.live": "Live",
  "output.historical": "Historical",
  "output.still_needed": "Still needed",
  "output.suggested_aims": "Suggested aims",
  "output.proposals": "Proposals",
  "output.saved_plans": "Saved plans",
  "output.active_plan": "Active plan",
  "output.ready_for_planner": "Ready for planner",
  "output.line": "Line: {line}",
  "output.aims": "Aims: {aims}",
  "output.session_complete": "Session complete. Start a new analysis from the top bar.",
  "output.actions": "Actions",
  "output.confirm": "Confirm {n}",
  "output.go": "Go",
  "output.show_suggested": "Show suggested aims",
  "output.more_options": "More options",
  "output.list_saved": "List saved plans",
  "output.activate": "Activate {label}",
  "output.all_machines": "1 — All machines",
  "context.title": "Context",
  "context.no_schema": "No schema snapshot.",
  "context.session": "Session",
  "context.turns": "Turns: {count}",
  "context.phase": "Phase: {phase}",
  "context.line_match": "Line match",
  "context.line": "Line",
  "context.datasets": "Datasets",
  "context.in_scope": "In scope",
  "context.excluded": "Excluded",
  "context.time": "Time",
  "context.no_time_filter": "No time filter",
  "context.suggested_aims": "Suggested aims",
  "context.columns": "Columns",
  "context.column_dataset": "Dataset",
  "context.column_name": "Name",
  "context.column_type": "Type",
  "context.column_meaning": "Meaning",
  "context.joins": "Joins"
}
```

#### `ja.json`

```json
{
  "app.title": "EDAS",
  "nav.dashboard": "ダッシュボード",
  "nav.no_session": "セッションなし",
  "nav.new": "+ 新規",
  "nav.thinking": "考え中…",
  "nav.ready": "準備完了",
  "nav.session_label": "セッション",
  "nav.language_en": "English",
  "nav.language_ja": "日本語",
  "chat.title": "チャット",
  "chat.completed": "完了",
  "chat.placeholder_empty": "何を分析しますか？ Vinayaka や fruits test などのライン名を入力してください。",
  "chat.you": "あなた",
  "chat.manager": "マネージャー",
  "chat.next": "次のステップ",
  "chat.thinking": "考え中…",
  "chat.placeholder_input": "質問を入力…",
  "chat.placeholder_done": "セッション完了",
  "chat.send": "送信",
  "chat.viewing_step": "ステップ {step} を表示中。メッセージを送信するには最新のターンを選択してください。",
  "output.title": "出力",
  "output.empty": "メッセージを送信して計画を開始します。",
  "output.no_snapshot": "このステップのスナップショットはありません。",
  "output.step_of": "ステップ {current} / {total}",
  "output.live": "ライブ",
  "output.historical": "履歴",
  "output.still_needed": "不足情報",
  "output.suggested_aims": "推奨分析",
  "output.proposals": "提案",
  "output.saved_plans": "保存済み計画",
  "output.active_plan": "アクティブな計画",
  "output.ready_for_planner": "Planner準備完了",
  "output.line": "ライン: {line}",
  "output.aims": "分析: {aims}",
  "output.session_complete": "セッション完了。上部バーから新しい分析を開始してください。",
  "output.actions": "アクション",
  "output.confirm": "確認 {n}",
  "output.go": "実行",
  "output.show_suggested": "推奨分析を表示",
  "output.more_options": "その他のオプション",
  "output.list_saved": "保存済み計画一覧",
  "output.activate": "有効化 {label}",
  "output.all_machines": "1 — 全マシン",
  "context.title": "コンテキスト",
  "context.no_schema": "スキーマスナップショットはありません。",
  "context.session": "セッション",
  "context.turns": "ターン数: {count}",
  "context.phase": "フェーズ: {phase}",
  "context.line_match": "ライン一致",
  "context.line": "ライン",
  "context.datasets": "データセット",
  "context.in_scope": "スコープ内",
  "context.excluded": "除外",
  "context.time": "時間",
  "context.no_time_filter": "時間フィルターなし",
  "context.suggested_aims": "推奨分析",
  "context.columns": "カラム",
  "context.column_dataset": "データセット",
  "context.column_name": "名前",
  "context.column_type": "型",
  "context.column_meaning": "意味",
  "context.joins": "結合"
}
```

#### `index.ts` — i18next initialization

```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import en from "./en.json";
import ja from "./ja.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en }, ja: { translation: ja } },
    fallbackLng: "en",
    interpolation: { escapeValue: false },
  });

export default i18n;
```

### 6.3 Update frontend components

**Import in `main.tsx`** (or `App.tsx`):
```ts
import "./i18n";
```

**In each component, replace hardcoded strings** with `useTranslation()`:

```tsx
import { useTranslation } from "react-i18next";

const { t } = useTranslation();

// Before: <h2>Chat</h2>
// After:  <h2>{t("chat.title")}</h2>

// Before: <span>You</span>
// After:  <span>{t("chat.you")}</span>

// Before: `Viewing step ${selectedTurnIndex + 1}.`
// After:  {t("chat.viewing_step", { step: selectedTurnIndex + 1 })}
```

**File-by-file change list:**

| Component | Strings to translate |
|-----------|---------------------|
| `Navbar.tsx` | `app.title`, `nav.dashboard`, `nav.no_session`, `nav.new`, `nav.thinking`, `nav.ready`, `nav.session_label` |
| `ChatSection.tsx` | `chat.title`, `chat.completed`, `chat.placeholder_empty`, `chat.you`, `chat.manager`, `chat.next`, `chat.thinking`, `chat.placeholder_input`, `chat.placeholder_done`, `chat.send`, `chat.viewing_step` |
| `OutputSection.tsx` | `output.title`, `output.empty`, `output.no_snapshot`, `output.step_of`, `output.live`, `output.historical`, `output.still_needed`, `output.suggested_aims`, `output.proposals`, `output.saved_plans`, `output.active_plan`, `output.ready_for_planner`, `output.line`, `output.aims`, `output.session_complete`, `output.actions`, `output.confirm`, `output.go`, `output.show_suggested`, `output.more_options`, `output.list_saved`, `output.activate`, `output.all_machines` |
| `ContextSection.tsx` | `context.title`, `context.no_schema`, `context.session`, `context.turns`, `context.phase`, `context.line_match`, `context.line`, `context.datasets`, `context.in_scope`, `context.excluded`, `context.time`, `context.no_time_filter`, `context.suggested_aims`, `context.columns`, `context.column_dataset`, `context.column_name`, `context.column_type`, `context.column_meaning`, `context.joins` |

### 6.4 Pass language in API calls

**File:** `edas/frontend/src/stores/sessionStore.ts`

```ts
import { useTranslation } from "react-i18next";

// Inside newSession:
const lang = i18n.language.startsWith("ja") ? "ja" : "en";
const created = await createSession(lang);

// Inside sendUserMessage:
const lang = i18n.language.startsWith("ja") ? "ja" : "en";
const res = await sendMessage(sessionId, userText, lineName, lang);
```

**File:** `edas/frontend/src/api/manager.ts`

Update `createSession()` and `sendMessage()` to accept and send `language` parameter.

---

## Phase 7 — Font & Layout

### 7.1 Add Noto Sans JP

**File:** `edas/frontend/index.html`

```html
<link
  href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700&display=swap"
  rel="stylesheet"
/>
```

### 7.2 Update CSS font-family

**File:** `edas/frontend/src/index.css`

```css
:root {
  --font-body: "Inter", "Noto Sans JP", sans-serif;
  --font-display: "Space Grotesk", "Noto Sans JP", sans-serif;
}
```

### 7.3 Audit fixed-width containers

Check these elements for potential text overflow with Japanese characters (which are typically
wider than Latin characters):

- `Navbar.tsx` `<select>` — `min-w-[200px]` (line name + phase may be longer in Japanese)
- `ChatSection.tsx` — `<div className="max-w-[95%]">` (generally fine since it's percentage-based)
- `OutputSection.tsx` — action button widths
- `ContextSection.tsx` — column table cells

For `<select>` options, consider using `min-w-[260px]` if Japanese text gets truncated.

---

## Phase 8 — Testing Strategy

### 8.1 Unit tests

**File:** `edas/backend/tests/test_language_detect.py`
- Test `detect_language()` with English, Japanese, mixed, empty inputs

**File:** `edas/backend/tests/test_time_translator.py`
- Test `translate_time_phrase()` with various Japanese time patterns
- Test that non-Japanese phrases pass through unchanged

**File:** `edas/backend/tests/test_json_validator.py`
- Test `validate_parsed_json()` with valid/invalid key sets
- Test `validate_recursive_keys()` detects non-ASCII keys

**File:** `edas/backend/tests/test_i18n.py`
- Test `t()` returns correct strings for both languages
- Test that missing keys fall back to English

### 8.2 Integration tests

- Run a full conversation turn in Japanese: `ユーザー: Vinayakaの過去7日間の平均コスト`
- Verify `agent_message` contains Japanese text
- Verify `task_definition` values contain Japanese text
- Verify JSON keys are in English (extraction, reorganization, proposals)

### 8.3 Frontend tests

- Verify language toggle changes all visible text
- Verify API calls include `language` parameter
- Verify Japanese font renders correctly

---

## Effort & File Summary

| Phase | New files | Modified files | Complexity | Risk |
|-------|-----------|----------------|------------|------|
| 1. Foundation | 0 | 5 | Low | Low |
| 2. Language detection | 1 | 4 | Low | Low |
| 3. Prompt injection | 2 | 8 | Low | Low |
| 4. Time translator | 1 | 1 | Low | Low |
| 5. Backend i18n | 3 | ~18 | Medium | Medium |
| 6. Frontend i18n | 3 | ~6 | Medium | Low |
| 7. Font & Layout | 0 | 2 | Low | Low |
| 8. Tests | 5 | 0 | Low | Low |
| **Total** | **15 new** | **~44 modified** | | |

---

## Execution Order (Recommended)

```
Phase 1  ──►  Phase 2  ──►  Phase 3  ──►  Phase 4
                                                │
                                    ┌───────────┘
                                    ▼
                              Test (Phase 8)
                                    │
                         ┌──────────┴──────────┐
                         ▼                      ▼
                   Phase 5 (Backend)     Phase 6 (Frontend)
                         │                      │
                         └──────────┬───────────┘
                                    ▼
                              Phase 7 (Fonts)
                                    ▼
                              Final Test
```

**Start with Phases 1-4** for minimal viable Japanese support (LLM responses only).
**Add Phases 5-7** for complete i18n including UI and backend hardcoded strings.
