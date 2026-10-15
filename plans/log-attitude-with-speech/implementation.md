### Implementation Summary

Added ownship attitude (pitch, bank, true heading, altitude MSL) to `belief_truth_log.py`'s
`kind: "speech"` rows, so the next sortie can reconstruct the cockpit-mask verdict at the moment
of a guidance utterance after the fact — the gap identified while investigating the 2026-10-15
attack-run sortie's `", obstructed"` flicker
(`docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §3).

No plan.md existed for this task (it arrived as a direct, fully-specified orchestrator brief
rather than through an Architect pass), so this directory holds only the implementation log.

### Files Changed
- `body-layer/src/belief_truth_log.py` — `write_speech` gained four new optional keyword
  arguments (`ownship_pitch_deg`, `ownship_bank_deg`, `ownship_heading_true_deg`,
  `ownship_alt_m`), each `None` by default and omitted from the written row when `None` (the
  existing absent-not-null convention `gaze_label`/`gaze_center_deg`/`optic_name` already use).
  No existing field renamed or removed; no non-speech row touched.
- `body-layer/src/logger.py` — `_speech_log_sink`'s inner `sink` closure now reads
  `runner.last_ownship_state` (already maintained by the poll loop, used elsewhere by
  `_render_eyesight_frame`) and forwards its four attitude fields to `write_speech`. `None` when
  no poll has completed yet (mirrors the existing `last_ownship_state is None` guard elsewhere in
  this file) rather than fabricating `0.0`.
- `body-layer/tests/test_belief_truth_log.py` — two new tests (see below).
- `body-layer/tests/test_logger.py` — two new tests (see below).

### Tests Added
- `test_write_speech_carries_ownship_attitude` — all four fields round-trip through
  `write_speech` into the JSON row with an exact-dict equality check (same style as the existing
  `test_write_speech_carries_attack_run_fields`).
- `test_write_speech_omits_ownship_attitude_when_unknown` — calling `write_speech` without the
  new kwargs omits all four fields from the row rather than writing `null`/`0.0`.
- `test_speech_log_sink_forwards_ownship_attitude` — `_speech_log_sink`'s closure reads
  `runner.last_ownship_state` live and forwards pitch/bank/heading/altitude correctly.
- `test_speech_log_sink_omits_ownship_attitude_before_first_poll` — with
  `runner.last_ownship_state` still `None` (no poll has completed), all four fields come through
  as `None`, never a fabricated `0.0`.

### Checks
(body-layer/ is the only subproject touched)
- `ruff format --check .`: fails only on the pre-existing, out-of-scope
  `research/2026-10-05-security-audit.md` (unrelated to this change, named in the task brief as
  an expected exception).
- `ruff check .`: pass
- `mypy src` (strict): pass, 59 source files
- `pytest -q`: **1957 passed, 4 xfailed** (baseline 1953 passed, 4 xfailed + 4 new tests; no
  regressions, no existing test touched).

A real rendered row was produced by exercising the actual `_speech_log_sink` →
`BeliefTruthLogWriter.write_speech` path end-to-end (not a mock), confirming the fields appear
correctly alongside the pre-existing gaze/optic/attack-run fields:

```json
{"kind": "speech", "t_sim": 580.3, "text": "Lined up, obstructed.", "urgent": false,
 "gaze_label": "10_oclock", "gaze_center_deg": -60.0, "optic_name": "unaided",
 "ownship_pitch_deg": -8.2, "ownship_bank_deg": 6.0, "ownship_heading_true_deg": 271.4,
 "ownship_alt_m": 412.0, "attack_run_target_contact_id": "CONTACT_42",
 "attack_run_tier": 2, "attack_run_azimuth_deg": 2.2, "attack_run_elevation_deg": -0.8}
```

### Judgement call: target geometry and mask verdict were NOT added

The task asked me to judge whether also recording the guidance target's body-relative
azimuth/elevation and the cockpit-mask verdict itself, at the moment of each utterance, would
make the open question answerable directly rather than by reconstruction — and to ship that only
if it is cheap and does not distort the module's read-only posture, saying plainly if it is
awkward.

**It is not merely awkward here — it would be actively misleading, and I did not add it.**
For attack-run speech specifically the target contact *is* already known at the call site
(`attack_run_target_contact_id`), so "don't know which contact" is not the obstacle the task
anticipated. The real obstacle is a rotation mismatch I verified by reading both call sites:

- `belief_truth_log.write_speech`'s existing `attack_run_azimuth_deg`/`attack_run_elevation_deg`
  come from `belief.attack_run._tier1_alignment`/`_tier2_alignment`, which call
  `perception.geometry.alignment_direction` **without** passing `bank_deg` — that function's own
  docstring says so explicitly ("re-rotating by current attitude via geometry.alignment_direction
  (bank removed)").
- The actual cockpit-mask check that produces the "obstructed" behaviour
  (`perception.visibility`, line ~920) builds its body-relative azimuth/elevation **with**
  `ownship.bank_deg` included, then passes that into `perception.cockpit_mask.is_visible`.

So the two azimuth/elevation values already in this log answer a *different geometry question*
than the one the cockpit mask was actually evaluated against. Recomputing a "mask verdict" from
the attack-run's own bank-stripped axis values at speech time would produce a value that looks
authoritative but is wrong whenever bank is non-trivial — exactly the kind of landmine this
project's own sign-convention history already flags (`OwnshipState`'s docstring calls the bank
sign "the riskiest open assumption" in the cockpit-visibility work). Shipping it would risk
certifying a wrong answer to the open question rather than leaving it open.

The four ownship attitude fields added here are sufficient to answer the question properly: a
reader can now take `ownship_heading_true_deg`/`pitch_deg`/`bank_deg` from a speech row together
with the attack target's ground-truth bearing/range from the belief-truth rows at the same
`t_sim` (already logged, Euclidean positions, in the same file) and independently recompute the
*actual* bank-inclusive cockpit-mask body-relative azimuth/elevation that
`perception.visibility` would have produced — which is the real question, not a proxy for it. A
future task could add a dedicated mask-verdict field, but it would need to be computed from the
same rotation `perception.visibility` actually uses (bank included), not from attack-run's own
axis values, and that is new code in the perception path rather than a field threaded straight
through — out of scope for a logging-only change.

### Notable Discoveries
- `belief.attack_run._tier1_alignment`/`_tier2_alignment`'s alignment is deliberately
  bank-stripped while `perception.visibility`'s cockpit-mask check is not. This is an existing,
  intentional divergence (each serves a different purpose — attack-run guidance vs. visibility
  gating) but it means the two azimuth/elevation values already present in a `kind: "speech"` row
  for an attack-run line (`attack_run_azimuth_deg`/`attack_run_elevation_deg`) must never be read
  as the cockpit mask's own input. Anyone reusing those fields for a mask reconstruction later
  needs to recompute with bank included, from `ownship_bank_deg` now also on the row, not reuse
  the attack-run pair directly.
