---
name: feedback_diverged_dual_field_state_untested
description: When a state machine has a "current" field and a "target/home" field (phase vs home_phase, actual vs desired), every existing test may construct them already agreeing — grep for and hand-build the diverged case before trusting a byte-identical-on-existing-tests claim.
metadata:
  type: feedback
---

A state machine that tracks both "where I am now" (`phase`) and "where I should end up"
(`home_phase`) typically has one function that moves the two back into agreement at a boundary
(`_back_to_home`), and relies on nothing else needing to know about `home_phase` once `phase` has
already entered the mode `home_phase` names. That reliance is the bug: a later external mutation to
`home_phase` alone (a pilot command, a mode toggle) does not retroactively notify the dispatch
branch that already committed to the old mode.

**Concrete case**: `BL-B64` Stage 2 (`body-layer/src/belief/optic_policy.py`). Commanding "Observ
off" writes `OpticState.home_phase = SCANNING` directly (the same one-poll-lagged signal shape
`attack_run_transition` uses), but `decide()`'s `state.phase is OpticPhase.SIGHTING` dispatch branch
never reads `home_phase` — the only exits from `SIGHTING` are its own internal stop conditions
(a scheduled dwell boundary, or a manoeuvre-triggered rate-limit violation). The result: the pilot
hears "Observ off" immediately, but the sight keeps operating — cone, optic, look-in-progress — for
up to `SIGHT_MAX_DWELL_S` (30 s default) afterward. This directly falsified the implementer's own
docstring invariant claim ("only reachable while `home_phase` is `SIGHTING` too") the moment the two
fields were pushed apart.

**Why reading the diff and the full test suite both missed it**: the "OBSERV-off is bit-identical"
claim was proven by every *pre-existing* test passing unchanged — true, and irrelevant to this gap,
because that claim is about old paths staying untouched, not about the new path correctly exiting.
Every new test in the suite (including the ones explicitly testing "lower binoculars preserves
OBSERV") constructs `phase` and `home_phase` *already agreeing*  none starts from the diverged
state the real command sequence actually produces one poll after landing.

**How to apply**: whenever a plan or diff adds a second field that is supposed to track a first one
(home/current, desired/actual, committed/pending), don't just confirm each field's own update path
in isolation — construct the state with the two fields **disagreeing** (the exact combination a
real external event produces, e.g. "already mid-mode, but the mode-select field was just flipped
externally") and step the pure decision function forward several ticks. If nothing brings them back
into agreement before the slowest internal stop condition fires, that is a required fix, not an
edge case — a pilot-facing command that silently takes effect tens of seconds late (or never, if the
internal stop condition itself depends on the diverged field) is a correctness defect with a
user-visible symptom (a readback that lies about system state), not a cosmetic latency.

Related but distinct from [[feedback_boundary_only_tested_via_fixture]] (that one is about a single
threshold lacking a dedicated test; this one is about two *fields* whose relationship is assumed
rather than checked, and the gap only appears once they're deliberately pushed out of sync).
