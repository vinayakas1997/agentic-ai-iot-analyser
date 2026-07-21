# UI/UX Refinement Plan - Manager Agent

**Date:** 2026-07-09  
**Source:** Agent feedback on current UI design  
**Status:** Not urgent - refinement work

## Overview

The current Manager Agent UI is in a solid place with a coherent, intentional system. The three-panel layout (chat center, context left, outputs right) reads clearly with good spatial logic. The orange/Manager color coding is consistent across sidebar, badge, and CTA button.

This plan addresses 5 refinement areas to improve visual hierarchy, information density, and polish.

---

## 1. Visual Weight Imbalance

**Problem:** The Manager card's orange border + orange bullets + orange button all compete; nothing anchors as the primary action.

**Current State:**
- `styles.ts:21-22` - `managerCardClass` has orange border and glow shadow
- `styles.ts:23-24` - `qrPrimaryClass` has full-saturation orange with shadow
- `ManagerDecisionCard.tsx:337` - Orange bullet dots with glow shadow
- `styles.ts:10` - `decisionCardClass` has orange glow shadow

**Proposed Changes:**
1. Reduce `decisionCardClass` border to `border-stage-manager-line/20` (currently `border-stage-manager-line`)
2. Remove glow shadow from `decisionCardClass` and `managerCardClass`
3. Mute orange bullet dots: `bg-stage-manager/50` (currently `bg-stage-manager`)
4. Reserve full-saturation orange only for the "Go - proceed" CTA button

**Files to modify:**
- `frontend/src/lib/styles.ts` - Update `decisionCardClass`, `managerCardClass`
- `frontend/src/components/ManagerDecisionCard.tsx:337` - Mute bullet color

---

## 2. BENEFITS List - Asterisks Leaked from Markdown

**Problem:** Asterisks around each bullet (`* Confirms...*`) look like unrendered markdown leaking through rather than intentional formatting.

**Current State:**
- `ChatSection.tsx:304-320` - Renders `ui.plan.benefits.split("\n")` directly
- `ManagerDecisionCard.tsx:351-354` - Same issue in detail variant

**Root Cause:** This is a **backend/prompt issue**, not CSS. The `benefits` string arrives from the backend with markdown asterisks.

**Proposed Fix:** Strip asterisks client-side before rendering:

```tsx
// Before rendering in both locations:
const cleanBenefits = ui.plan.benefits
  .split("\n")
  .map(s => s.replace(/^\s*\*\s*/, "").replace(/\s*\*$/, ""))
  .filter(Boolean);

// Then render cleanBenefits.map(...)
```

**Files to modify:**
- `frontend/src/sections/ChatSection.tsx:304-320`
- `frontend/src/components/ManagerDecisionCard.tsx:351-354`

---

## 3. Density in Left Sidebar - Aims Description Block

**Problem:** The Aims description block is a wall of italic text at a small size against a busy dark background; italics for that much text hurts readability.

**Current State:**
- `ManagerDecisionCard.tsx:352` - Benefits block: `italic leading-relaxed`
- Small text size (`text-xs`) with dense layout

**Proposed Changes:**
1. Remove `italic` from the benefits block
2. Increase line-height to `leading-relaxed` (already present, but needs emphasis)
3. Add max-height with expand/collapse for long content:
   - Set `max-h-32` with `overflow-y-auto`
   - Add "Show more" button when content exceeds threshold
   - Or truncate with ellipsis and expand on click

**Files to modify:**
- `frontend/src/components/ManagerDecisionCard.tsx:352`

---

## 4. Button Hierarchy

**Problem:** "Go - proceed," "More options," "Change something..." are all roughly the same visual weight (just outline vs filled). Since "Go - proceed" is clearly the happy path, giving it more visual dominance would speed up scanning.

**Current State:**
- `styles.ts:23-24` - `qrPrimaryClass`: `px-3.5 py-1.5 text-xs` with full orange
- `styles.ts:25-26` - `qrSecondaryClass`: `px-3.5 py-1.5 text-xs` with subtle bg

**Proposed Changes:**
1. Make `qrPrimaryClass` larger:
   - Increase padding: `px-4 py-2` (from `px-3.5 py-1.5`)
   - Increase font size: `text-sm` (from `text-xs`)
   - Keep full-saturation orange with shadow

2. Make `qrSecondaryClass` visually lighter (ghost style):
   - Remove border: no `border-border/60`
   - Remove bg: no `bg-white/[0.04]`
   - Use text-muted: `text-muted`
   - Add hover: `hover:text-text`
   - Keep padding: `px-3.5 py-1.5 text-xs`

**Files to modify:**
- `frontend/src/lib/styles.ts:23-26`

---

## 5. Chat Bubble Distinction

**Problem:** The "YOU" message and the Manager response blend into similarly bordered boxes; a subtler visual distinction would make the conversation flow easier to follow at a glance.

**Current State:**
- `styles.ts:19-20` - `BubbleClass`: `border-l-3 border-l-user-blue` with full border
- `styles.ts:21-22` - `managerCardClass`: `border-l-3 border-l-stage-manager` with full border
- Both use similar border styling

**Proposed Changes:**
1. Align messages to the right:
   - Add `ml-auto` to bubble wrapper
   - Reduce max-width: `max-w-[85%]`
   - Reduce border: `border-l-2` (from `border-l-3`)
   - Remove bottom/right borders: `border-b-0 border-r-0`

2. Keep manager card left-aligned with orange branding:
   - Maintain current `managerCardClass` styling
   - Ensure it stays visually distinct from messages

**Files to modify:**
- `frontend/src/lib/styles.ts:19-20` - Update `BubbleClass`
- `frontend/src/sections/ChatSection.tsx:213` - Add alignment classes

---

## Implementation Notes

### Priority Order
1. **High** - Button hierarchy (4) - Most impactful for flow
2. **High** - BENEFITS list (2) - Polishing issue that undermines credibility
3. **Medium** - Visual weight (1) - Improves focus on primary actions
4. **Medium** - Chat bubble distinction (5) - Improves conversation clarity
5. **Low** - Sidebar density (3) - Nice-to-have for long content

### Testing Checklist
- [ ] Orange CTA button is clearly the primary action
- [ ] BENEFITS list renders without asterisks
- [ ] User messages are right-aligned with subtle borders
- [ ] Manager card is left-aligned with orange branding
- [ ] Secondary buttons are visually lighter than primary
- [ ] No visual regression in other components
- [ ] Mobile responsiveness maintained

### Files Summary
- `frontend/src/lib/styles.ts` - Core styling updates (1, 4, 5)
- `frontend/src/sections/ChatSection.tsx` - User bubble alignment, benefits rendering (2, 5)
- `frontend/src/components/ManagerDecisionCard.tsx` - Benefits rendering, visual weight (1, 2, 3)

---

## Expected Impact

After these refinements:
- **Visual clarity:** Users will immediately identify the primary CTA action
- **Professional polish:** Clean rendering without markdown artifacts
- **Better flow:** Right-aligned messages create natural conversation rhythm
- **Reduced cognitive load:** Muted decorations focus attention on key content
- **Improved readability:** Better line-height and text treatment for dense information