---
name: sortie-2026-09-26-fixes
description: Fix A/B1/B2/C implementation — a grace-window field needed different semantics than the plan's literal prose to make the committed test pass; two pre-existing tests needed mechanical field-rename updates from a pending/committed split.
metadata:
  type: project
---

Implemented `plans/sortie-2026-09-26-fixes/plan.md` in full (Stages 1-4). All checks pass:
`body-layer` ruff format/check, mypy --strict, pytest 1303 passed/4 xfailed (baseline 1292/4).

**Grace-window field semantics: "last confirmed observable", not "duration since it started
failing".** The plan's prose described `Contact.unobservable_since_sim` as mirroring
`los_masked_since_sim` (time a failing run started, reset on success) with the gate `now_sim -
unobservable_since_sim < GRACE`. That literal reading fails the plan's own committed test: a
contact permanently astern *since founding* would still get a full grace window of callouts
starting from its first evaluated tick, because elapsed-since-first-failure trivially starts at
0. The fix: track `last_observable_sim` (time last confirmed observable, `None` = never), and
deny grace unconditionally when `None`. This is the general pattern worth remembering — **a
"grace window on becoming unobservable" needs to distinguish "recently lost a real sighting" from
"never had one to begin with"**, and a naive mirror of an existing similar-sounding field
(`los_masked_since_sim`) can silently encode the wrong one, because that field's own polarity was
chosen for a different purpose (fail-open toward "still dangerous", not fail-closed toward "don't
report unseen things").

**A committed/pending state split changes what pre-existing tests assert immediately after a
state transition, and this is expected, not a scope violation.** Splitting `OpticState.
attempted_at_range_m` into `pending_attempted_at_range_m` (look-in-progress) +
`attempted_at_range_m` (committed on natural completion) meant two pre-existing tests asserting
"the mark exists immediately after a look starts" broke, because that immediate mark is now
`pending`, not `committed`. Updated the field name in the assertion (preserving the test's
original intent exactly) rather than treating this as "existing tests must be rewritten" (an
escalation trigger) — a purely mechanical consequence of a plan-directed field split is not the
same class of change as a semantic test rewrite.

See `plans/sortie-2026-09-26-fixes/implementation.md` for the full writeup.
