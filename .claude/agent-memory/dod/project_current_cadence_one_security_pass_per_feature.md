---
name: current-cadence-one-security-pass-per-feature
description: Under the cadence enabled 2026-09-24, every feature (not just change-request fixes) gets exactly one Security pass, right before DoD — a missing security-plan-review.md is expected even when a full plan.md exists
metadata:
  type: project
---

Confirmed on `feature/landform-geomorphons` (WM-B6, DoD 2026-10-02): this branch has a full
Architect `plan.md`, went through Implementer -> Reviewer (3 rounds, including a Performance-
Reviewer change-request loop) -> Security (one deep-analysis pass, `security-review.md`,
`c39ec08`) -> DoD. There is **no `security-plan-review.md`**, and that is correct, not a gap —
root `CLAUDE.md`'s "Agents" section states the cadence enabled 2026-09-24: "`performance-reviewer`
and `security` run once per whole feature, immediately before DoD... not mid-feature." This
supersedes `AGENTS.md`'s general role-sequence diagram (which still shows "Security (plan review)
-> Implementer -> ... -> Security (deep analysis)" as the two-pass template) for any feature
started under the current cadence.

**This is broader than [[change_request_fix_no_security_plan_review_expected]]**, which only covers
branches that exist solely to implement review findings against an already-approved whole-subproject
audit (no plan.md at all). This case is a normal new-feature branch, with a real plan.md Security
never reviewed before implementation started — and that is still correct under the current cadence,
not an oversight to flag.

**How to apply:** before flagging a missing `security-plan-review.md` as a DoD gap, check root
`CLAUDE.md`'s "Agents" section for whatever cadence is currently stated for Security/Performance
Reviewer — don't assume the two-pass AGENTS.md template still applies, and don't assume the prior
change-request-only exception is the only case that excuses it. If the cadence says "once per
feature, before DoD," a single `security-review.md`/`performance.md` pair covering the whole diff is
complete sign-off; require nothing else. If this cadence note is ever revised or ended again (it
itself replaced a prior blanket-skip rule that outlived its premise, per root `CLAUDE.md`'s own
account), re-check this memory against the new wording before relying on it.
