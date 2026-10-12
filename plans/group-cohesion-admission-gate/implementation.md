### Implementation Summary

BL-12 Stage 3.5 (`BL-B58`), implemented as planned in `plan.md`: three commits, split by module
seam rather than mechanism/calibration (there is no calibration half — no new constant).

**Commit 1** — `Contact.fold_displacement_m`, provenance only, behaviour-neutral. Written at
`ContactStore.ingest`'s one fold call site (`fold_target is not None`), **accumulated** (`+=`)
rather than overwritten across repeat folds with no intervening clean look, and reset to `0.0` on
either unambiguous branch (object-permanence continuity, or a single passing gate candidate).
Nothing reads it yet.

**Commit 2** — the admission gate. `_cluster_contacts` gains `prior_rosters: Sequence[frozenset[
str]]`. For a candidate pair, co-membership of one and the same prior roster gets today's rule
unchanged; any other pair (an admission) is tested as
`gap + fold_displacement_m[i] + fold_displacement_m[j] <= min(relative_threshold, pair_backstop)`
— no new constant. `GroupStore.reconcile` passes `[g.member_contact_ids for g in
self._groups.values()]`, read before `self._groups` is reassigned at the method's end — confirmed
by reading the method directly (`persisted = dict(self._groups)` at line 1232, reassignment
(`self._groups = new_groups`) at line 1378), not assumed from the plan's description.

**Commit 3** — `tests/test_callouts.py`'s 2C fixture, rewritten to match an actual run (not
predicted): 3 spoken lines, not 4; `GROUP_1` settles at `{CONTACT_1, CONTACT_2, CONTACT_3}`.
`test_2c_transcript_fixture_renders_four_lines_not_seven` renamed to
`..._renders_three_lines_not_seven`.

---

### Files Changed

- `body-layer/src/belief/contacts.py` — `Contact.fold_displacement_m: float = 0.0` field
  (docstring states the no-omniscience boundary: derived entirely from `Contact.position` deltas,
  never ground truth). `ContactStore.ingest`'s three resolution branches updated: the continuity
  branch and the `len(passing) == 1` branch now reset the field to `0.0` after `record()`; the
  `fold_target is not None` branch captures `position_before = contact.position` before `record()`
  and accumulates `math.hypot(contact.position.x - position_before.x, contact.position.z -
  position_before.z)` into it afterward.
- `body-layer/tests/test_contacts.py` — one new test,
  `test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record`, reusing
  `test_ambiguous_candidates_fold_within_a_group_else_found_a_new_contact`'s own D/E/F geometry.
  Pins: zero before any fold; a nonzero value matching an independent `fold_position`-based
  re-derivation after the first fold; **accumulation** (not replacement) across a second fold onto
  the same contact; reset to exactly `0.0` after an unambiguous continuity-resolved re-observation.
- `body-layer/src/belief/groups.py` — `_cluster_contacts` gains `prior_rosters` (4th positional
  parameter); the edge loop flattens it once into `dict[str, frozenset[str]]` before the O(n²) loop
  (contact id → its one prior roster), then computes `effective_gap` per the rule above. Docstring
  extended citing the plan's §1 no-op measurement and §3's seam justification, so the superseded
  sketch is not rediscovered as the fix. `GroupStore.reconcile`'s one call site updated to build
  and pass `prior_rosters` from `self._groups` before that dict is reassigned.
- `body-layer/tests/test_groups.py` — `_contact()` test helper gains an optional
  `fold_displacement_m` kwarg (default `0.0`, unchanged for every pre-existing caller). Six new
  tests, one per row of the plan's §4 table, each calling `_cluster_contacts` directly with the
  plan's own probe geometry/budgets:
  - `test_admission_gate_excludes_the_2c_incidents_absorbed_member` (Row A)
  - `test_admission_gate_excludes_incident_2s_absorbed_air_defence_member` (Row B)
  - `test_admission_gate_leaves_a_first_formation_chained_infantry_line_identical` (Row C, invariant)
  - `test_admission_gate_leaves_an_existing_three_member_group_identical` (Row D, invariant)
  - `test_admission_gate_leaves_a_genuine_unfolded_joiner_identical` (Row E, invariant)
  - `test_admission_gate_still_chains_around_a_tainted_member_via_single_link` (Row F)
- `body-layer/tests/test_callouts.py` — `test_2c_transcript_fixture_renders_four_lines_not_seven`
  renamed to `..._renders_three_lines_not_seven`; its assertion drops the fourth spoken line and the
  group-membership assertion drops `CONTACT_4`; docstring gets a fourth-rewrite paragraph recording
  the mechanism and that this is the planned fix for the exact path the third rewrite flagged, not
  a new finding. Module docstring's own reference to the test name updated to match.
- `body-layer/ROADMAP/BL-B58.md` — implementation note added (pending Reviewer/DoD), checkbox moved
  to `[~]` in-progress.
- `body-layer/ROADMAP/BL-B59.md` — disposition recorded per the user's decision 2 (out of Stage
  3.5, prioritised next, not parked unprioritised), plus the post-fix re-run confirming the
  eviction half is still live.
- `body-layer/ROADMAP/BL-B50.md` — recheck note added per the user's decision 3: the 2C fixture's
  line-count drop is accepted, with the condition that consecutive-tick flipping on this fixture's
  shape be re-examined once `BL-B59` is taken up.
- `plans/group-cohesion-admission-gate/scratchpad/probe_b58_geometry.py` — one-line fix: its
  internal `_cluster_contacts` call updated to the new 4-argument signature (`[]` — this probe's
  purpose is the raw gap/backstop/threshold table, independent of the gate; see "Probes re-run"
  below for the gate itself verified against probe 2 and the real pipeline instead).
- `plans/group-contact-identity/plan.md` — **no edit needed.** Amendment A9 (pointer to this plan,
  the A6 stage-table Stage 3.5 row) already existed at this branch's tip (`7932fb3`), written by
  the Architect pass that produced this plan.

---

### Tests Added

- `test_fold_displacement_m_is_written_on_a_fold_and_reset_on_an_unambiguous_record`
  (`test_contacts.py`) — covers commit 1: zero before any fold, correct value after a fold
  (independently re-derived via `fold_position`), accumulation across a second fold, reset to
  `0.0` on an unambiguous continuity-resolved record.
- Six admission-gate tests (`test_groups.py`), one per row of the plan's §4 table — see Files
  Changed above for the list. Rows A/B assert the predicted exclusion; rows C/D/E assert byte
  -identical output to the ordinary (no-gate) rule; row F asserts single-link routing around one
  tainted member.
- `test_2c_transcript_fixture_renders_three_lines_not_seven` (renamed, `test_callouts.py`) — the
  end-to-end acceptance test: the real `ContactStore`/`CalloutScheduler`/`GroupStore` pipeline, not
  an isolated predicate, now excludes `CONTACT_4` and speaks three lines instead of four.

---

### Checks

**body-layer/** (only subproject touched):

- `ruff format --check`: pass (120 files already formatted after one `ruff format` pass on
  `groups.py` and `test_groups.py` mid-implementation)
- `ruff check .`: pass
- `mypy src` (strict, run from inside `body-layer`): pass, no issues in 55 source files
- `pytest -q`: pass

Per-commit numbers, since commit 1 claiming "unchanged" is the point of splitting it:

| commit | result |
|---|---|
| 1 (provenance) | **1677 passed / 4 xfailed** (1676 baseline + 1 new test; zero regressions, zero behaviour change) |
| 2 (admission gate) | **1682 passed / 4 xfailed**, with exactly one *expected* failure left outstanding for commit 3 (`test_2c_transcript_fixture_renders_four_lines_not_seven`, now rendering 3 lines) — `test_the_eager_cap_still_chains_a_long_infantry_line` stayed green, unmodified |
| 3 (2C fixture rewrite) | **1683 passed / 4 xfailed**, no remaining failures |

---

### Probes re-run against the implementation (plan's task 4)

Not predicted — paste of actual output:

**Probe 2** (`probe_b58_second_incident.py`, unmodified — it drives the real `ContactStore.tick()`
→ `GroupStore.reconcile()` pipeline, so it exercises the shipped gate without any probe-side
change):

```
=== t=20, after the fold   relative_threshold=169.0
  GROUP GROUP_1 members=['CONTACT_1', 'CONTACT_3'] air_defence=[]
=== t=30, persistence check   relative_threshold=169.0
  GROUP GROUP_1 members=['CONTACT_1', 'CONTACT_3'] air_defence=[]
```

Before the fix this read `members=['CONTACT_1', 'CONTACT_3', 'CONTACT_4']
air_defence=[('OP_SPAAG', 1)]` (plan §2b). The gate now excludes `CONTACT_4` end-to-end, through the
real pipeline, not just the isolated predicate — `air_defence_composition` stays `[]` rather than
asserting air defence the group does not contain. **`CONTACT_2`'s eviction is unchanged and still
fires** (`BL-B59`, confirmed still live, recorded in that entry).

**Probe 1** (`probe_b58_geometry.py`, one-line signature fix, `[]` passed for `prior_rosters`) —
the raw gap/backstop/threshold table at t=15 is byte-identical to the plan's own numbers (81.9 m
gap against an 88.0 m backstop on `CONTACT_1-CONTACT_4`, etc.) — confirms the fix changes the
*admission test*, not the underlying geometry, exactly as the plan's §1 argues.

**Probe 3** (`probe_b58_candidate.py`, unmodified — it reimplements only the predicate against the
real module's constants) — re-run output matches the plan's §4 table exactly, row for row,
including every `gap`/`eff`/`thresh` value and every `cur -> new` verdict. Its own
`relative_threshold` prints (372.9 for Row A, 169.5 for Row B) differ in the last digit from probe
1's geometry replay (373.8) and probe 2's real-pipeline run above (169.0) — a small
floating-point/rounding difference between the two position inputs (probe 1/2 run the real fused
positions through `ContactStore`/`GroupStore`; probe 3's Row A/B positions are hand-transcribed from
probe 1/2's own printed output, rounded to one decimal), immaterial to any verdict in either row.

---

### Notable Discoveries

- **The eviction half (`BL-B59`) reproduces cleanly against the shipped code, not just in the
  pre-fix measurement.** Running probe 2 after commit 3 confirms `CONTACT_2` (a real,
  correctly-identified infantry member) still drops out of `GROUP_1` at the same tick the gate
  correctly excludes `CONTACT_4` — the gate's "only ever blocks an admission, never an eviction"
  property holds exactly as designed, which means this sibling defect is untouched and current.
  Recorded in `BL-B59.md` per the user's decision 2.
- **No surprises in `reconcile`'s ordering.** The plan's claim that `self._groups` still holds the
  previous tick's rosters at the point `_cluster_contacts` is called (because reassignment happens
  at the method's very end) held exactly as stated — confirmed by reading the method rather than
  trusting the plan's line-number citation, which is good practice given the project's own
  "re-derive figures a review hands you" lesson (`.claude/agent-memory/implementer/
  feedback_re_derive_the_figures_a_review_hands_you.md`).
- **The 2C fixture's line count did drop from four to three, exactly as the plan predicted** (it
  explicitly declined to assert this, "stated as a prediction... the implementer reads it off a run
  and records the actual result") — confirmed by running the fixture with temporary `print()`
  instrumentation before writing the new assertion, not by trusting the prediction.
