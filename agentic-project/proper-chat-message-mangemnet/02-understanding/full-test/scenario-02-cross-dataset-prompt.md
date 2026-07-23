# Scenario 02: Cross-Dataset Analysis Prompt

## ID
`SCENARIO-02`

## Name
Cross-Dataset Analysis — LLM Prompt Enhancement

## What It Tests
- LLM prompt contains "Cross-Dataset Analysis" section when multiple datasets attached
- LLM identifies common columns across datasets
- LLM proposes cross-dataset analysis ideas
- 3 suggestions when user has no clear intention
- 1 comprehensive analysis when user has specific intent
- Conversational flow — one suggestion at a time, not overwhelming

## Why This Matters
Cond-3 enhancement. The LLM must proactively identify join opportunities and propose combined analyses when multiple datasets are attached.

## Preconditions
- Backend running
- Frontend running
- Fresh session
- Database has at least 2 datasets with related columns (e.g., common `date`, `product_id`, `region`)

## Steps

### Step 1 — Attach multiple datasets
| Action | Expected |
|--------|----------|
| Search and select 2+ datasets | Both datasets attached, chips shown |
| Verify cross-dataset prompt | Check backend logs for "Cross-Dataset Analysis" in prompt |

### Step 2 — Exploratory question (no clear intent)
| Action | Expected |
|--------|----------|
| Type "What can I do with this data?" and send | LLM suggests **3 analysis ideas** |
| Check response | Each idea involves combining datasets |
| Check each idea | Specifies which columns to join, why valuable |

### Step 3 — Specific intent question
| Action | Expected |
|--------|----------|
| Type "Show me sales trends across regions" and send | LLM gives **1 comprehensive analysis** |
| Check response | Deep analysis, specific column references, join explanation |

### Step 4 — Conversational follow-up
| Action | Expected |
|--------|----------|
| Ask "Can you elaborate on that?" | LLM drills deeper into previous analysis |
| Check response | Natural conversation, not repeating suggestions |
| Check no overwhelming | One suggestion at a time |

### Step 5 — Single dataset fallback
| Action | Expected |
|--------|----------|
| Detach one dataset | Only 1 dataset attached |
| Type "What analysis is possible?" | LLM responds with single-dataset analysis ideas |
| Check no cross-dataset section | Prompt should not contain cross-dataset instructions |

## Bugs to Watch
- If LLM hallucinates column names → check prompt "Only reference columns listed"
- If LLM gives 5+ suggestions for exploratory → check "3 suggestions" rule
- If LLM gives multiple analyses for specific intent → check "1 comprehensive" rule

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
