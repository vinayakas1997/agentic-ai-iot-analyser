# Manual UI Test Checklist

Open `http://localhost:7008/`, log in as `testuser1`.

## 4c: TurnBubble banners
- [ ] Trigger a budget-truncated run — check amber banner says "may be incomplete"
- [ ] Trigger an error-truncated run — check amber banner says "LLM error" (turn.truncatedErrorWarning)
> Note: hard to trigger in current state (max_rounds=12/16). Set FOCUS_MAX_ROUNDS=1 and run a complex query.

## 4d: ProcessingPanel progress labels
- [ ] Run a template — check progress steps show "Thinking..." and "Query" labels, not raw "agent_template_round_N" strings.

## 4e: OutputPanel cards — CRUD
- [ ] Create one or more aim cards (FOCUS runs) — check they appear in OutputPanel
- [ ] Create one or more template cards — check they appear with Template badge
- [ ] Expand a card → show details → verify report markdown renders
- [ ] Click Add on a card → appears in selectedAims
- [ ] Click Add again → toggles to "Added"
- [ ] Click × on a card → card removed
- [ ] Click "Clear all" → all cards gone

## 4f: Run button independent of template
- [ ] Apply a template to composer (do not send)
- [ ] Attach an aim via Run button (should run independently)
- [ ] Now send with template → template route runs, ignoring attached aims

## 4h: Translations EN/JA
- [ ] Switch to Japanese in settings
- [ ] Run a template — check Template badge says "テンプレート"
- [ ] Check ProcessingPanel labels in Japanese
- [ ] Switch back to English — labels revert
