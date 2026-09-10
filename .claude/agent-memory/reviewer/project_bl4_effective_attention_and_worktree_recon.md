---
name: bl4-effective-attention-and-worktree-recon
description: BL-4 review findings — effective-vs-direct attention event semantics, and a disposable-worktree technique for reconciling per-commit test counts.
metadata:
  type: project
---

BL-4 (`plans/bl4-attention-events/plan.md`, approved 2026-09-10, `plans/bl4-attention-events/review.md`):

- `Contact.last_emitted_attention` intentionally stores *effective* attention (direct mark folded
  with `AttentionArea` membership), not the raw direct mark. This means a contact can fire
  `CONTACT_ATTENTION_CHANGED` purely from ownship/area geometry with zero belief-state change on
  the contact's own direct mark — confirmed deliberate (plan's area-attention design section,
  tested by `test_area_membership_raises_effective_attention_without_a_direct_mark`). If BL-5/BL-6
  event volume becomes a complaint, this is the first place to look — it's a real, flagged design
  tradeoff, not a bug to "fix."
- `belief.attention` cannot take a `Contact` in its function signatures (e.g. `effective_attention`)
  because `belief.contacts` already imports `belief.attention` — a `Contact`-typed parameter there
  would be circular. Any future BL-x module accepting `Contact.attention`-adjacent state should
  check this import direction before assuming a `Contact` param is the natural signature.
- Reusable verification technique: to independently reconcile a claimed per-commit test-count
  delta (e.g. "291 → 300 → 326 → 333 across three commits") without touching the working tree, use
  `git worktree add <scratch-dir> <commit-sha>` per commit, then run the *main* repo's `.venv`
  pytest against the worktree's `tests`/`src` via explicit `PYTHONPATH`/`--rootdir`/`-c
  <worktree>/pyproject.toml` — avoids any `git checkout`/`stash` risk to the real working tree.
  Clean up with `git worktree remove --force` after.
