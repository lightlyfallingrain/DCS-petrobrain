---
name: bl26-stage10-confidence-decay-fix
description: Fixing a docs-vs-code gap where IDENTITY_HALF_LIFE_S was documented as consumed but no function ever consumed it
metadata:
  type: project
---

BL-2.6's Stage 10 review found `body-layer/CLAUDE.md`/`plans/body-layer/plan.md` §6 documented
`decay.classification_confidence_at` as already decaying `Contact.classification.confidence`
over `IDENTITY_HALF_LIFE_S`, but no such function existed anywhere in `body-layer/src/` (Stages
1-9 never built it, despite `plans/classification-refinement/plan.md`'s Affected Modules section
scoping it into `decay.py`). Fixed 2026-09-10 by implementing the function rather than walking
the docs back — see [[feedback_agent_memory_path]] pattern of "make docs true" over "revert
docs to match code" when the described behavior is small and clearly intended.

Key implementation facts if this area is touched again:
- `classification_confidence_at(contact, now_sim)` keys off
  `contact.classification.established_sim`, NOT `contact.last_seen_sim` — a `hold` fold outcome
  leaves `established_sim` frozen while `last_seen_sim` keeps advancing, so using the wrong
  timestamp would silently reset decay on every poll.
- BL-3's `position_confidence` (the pattern this mirrors: `confidence * 0.5**(elapsed/half_life)`)
  is merged to `main` but was **not yet present** on `feature/classification-refinement` at the
  time of this fix — that branch predates BL-3's merge. Don't assume a branch has main's latest
  state; check `git merge-base` before trusting a "already merged" claim in a task prompt.
- `tools.py`'s `_classification_facts` needed a `now_sim` parameter added (it didn't take one
  before) to call through the decay function — a small signature change, not just a new call.
- `console.py` needed zero changes — it never reads `Contact.classification.confidence` directly,
  only `tools.py`'s already-decayed `facts` dict.
