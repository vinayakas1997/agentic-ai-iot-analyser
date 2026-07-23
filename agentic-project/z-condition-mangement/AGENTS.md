# Condition Management — Agent Process

> This file defines how the AI agent should track and update the conditions status.
> Read this before working on any condition-related tasks.

## File Locations

| File | Purpose |
|---|---|
| `z-condition-mangement/CONDITIONS-STATUS.md` | Main status tracker — conditions table + section-wise discussion + plans |
| `z-condition-mangement/AGENTS.md` | (this file) Agent process instructions |

## How to Update CONDITIONS-STATUS.md

Whenever a condition is discussed, designed, or resolved:

### 1. Update the Status Table

Change the `Status` and `Resolution` columns based on the outcome:

| Situation | New Status | New Resolution |
|---|---|---|
| Condition discussed but no decision yet | 🟡 IN DISCUSSION | ❌ Not resolved |
| Solution designed and agreed | 🟢 DESIGNED | ❌ Not resolved |
| Implementation done | ✅ RESOLVED | ✅ Resolved |
| Found to be already handled | 🟢 DESIGNED | ✅ Already handled |
| Blocked by something else | ❌ BLOCKED | ❌ Not resolved |

### 2. Update the Section Discussion

For each condition section, update these fields:

- **Status badge** at the top
- **Discussion:** Add summary of what was discussed, decisions made, tradeoffs considered
- **Plan:** Add the implementation plan with:
  - Files to modify
  - Changes needed
  - Key decisions

### 3. Update the Table first, then the Section

Always update the summary table **first**, then scroll down and update the detailed section.
This keeps the table as the single source of truth.

## Workflow

1. Read `CONDITIONS-STATUS.md` to understand current state
2. Discuss conditions one by one with user
3. After each discussion:
   - Update status in the table
   - Fill in the Discussion section
   - Write the Plan section
4. When all conditions are designed → proceed to implementation phase
