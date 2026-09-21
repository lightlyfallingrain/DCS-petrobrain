# DoD Check — Cones Slice 2A (per-tier multipliers, distinctiveness, clamp)

Branch: `feature/cones-2a-tiers-distinctiveness`. Implementation commit `ba4e40f`. Review commit
`b284f27` (Reviewer: **APPROVED, no required fixes**, full-read confidence).

## Code Quality

- **Subprojects touched**: `git diff --name-only $(git merge-base main HEAD)...HEAD` shows only
  `body-layer/` source/tests, `plans/detection-cones-slice2/`, and `.claude/agent-memory/`
  entries. `world-model/` and `aircraft-layer/` are untouched by this branch — the three untracked
  files at repo root (`world-model/run.sh`, `world-model/syria-full-build.log`,
  `world-model/syria-theatre-unfiltered.osm.pbf`) are pre-existing, unrelated build artifacts, not
  part of this diff, and were **not** staged.
- Ran the full body-layer verification sequence myself, from `body-layer/.venv`, per
  `body-layer/CLAUDE.md` "Commands":
  - `ruff format --check src tests` → **81 files already formatted** (PASS)
  - `ruff check src tests` → **All checks passed!** (PASS)
  - `cd body-layer && mypy src` → **Success: no issues found in 38 source files** (PASS)
  - `pytest tests -q` → **778 passed, 4 xfailed** (PASS — exact match to the claimed/expected result)
- No debug output or TODO/FIXME/pdb/breakpoint introduced: `git diff` over the touched source
  files grepped for `print(`/`TODO`/`FIXME`/`pdb.set_trace`/`breakpoint(` — no hits.
- No unhandled errors/panics in data paths — this slice touches pure geometry/threshold
  functions only (`optics.py`, `object_model.py`, `visibility.py`, `clustering.py`,
  `naked_eye_source.py`), no new I/O.

## Scope & Correctness

- Matches the 2A sections of `plans/detection-cones-slice2/plan.md` exactly: per-tier optic
  multipliers, the distinctiveness default+exception field, the `min()` clamp with tier
  monotonicity, and the clustering-floor parameterisation (hard part 4). Confirmed independently
  via the diff (not just the commit message) — same files the Reviewer checked, spot-verified
  arithmetic in this pass and cross-checked the reviewer's own derivations.
  - Correction to the task framing: the plan calls the clustering-floor issue "hard part 4" in the
    consolidated slice-2 plan doc's numbering, but the invariant is real regardless of numbering —
    `_separable`'s floor (A) now takes the active optic's `presence_range_mult` instead of the
    hardcoded `BINOCULAR_RANGE_MULTIPLIER` constant, and a regression test
    (`test_floor_would_have_broken_under_the_old_hardcoded_constant`) demonstrates the old constant
    would have silently merged two separable contacts at `presence_range_mult = 5.81`.
- No unplanned scope: no `gaze.py`, no `ScanPlan`, no scan-loop code exists on this branch (2B/2C/2D
  are plan-only). `belief/decay.py` has no diff. No `perception → belief` import introduced.
- No CLAUDE.md invariants violated: DCS/ground-truth stays authoritative (thresholds derived from
  measured sorties, not invented); provenance is preserved (every derived constant carries its
  arithmetic in a code comment, matching the "estimate flags must reach the code" standard from
  prior review findings); no multiplayer scope; no world-model data committed.
- All new/modified files staged with `git add` — confirmed via `git status --short`: only the
  three unrelated pre-existing untracked `world-model/` files remain untracked; nothing from this
  branch's work is unstaged.

## Testing

- Core logic covered: `test_tier_thresholds_never_invert` (property test across every profile ×
  every shipped optic), `test_infantry_class_clamps_to_presence_at_every_optic`,
  `test_floor_would_have_broken_under_the_old_hardcoded_constant`, plus updated
  `test_visibility.py`/`test_vision_calibration.py`/`test_clustering.py`/`test_optics.py`/
  `test_object_model.py` cases. These are meaningful — they assert the actual measured pattern
  (infantry class == presence at both shipped optics), not just "doesn't crash."
- Two new `xfail`s in `test_vision_calibration.py`, each with a full worked derivation in its own
  docstring, are an honest regression record (per-tier multipliers individually undercut the old
  flat 4.0 at two specific calibration points), not a silently weakened suite. Vehicle rows (the
  plan's own explicit regression guard) were re-checked and are unmoved.
- No existing tests broken: 778 passed / 4 xfailed matches the pre-stated expectation exactly.

## Documentation

- Reviewer findings: **none required.** Two Optional Refinements were logged (a fixture that now
  exercises `BINOCULAR_OPTIC` rather than the production `UNAIDED_OPTIC` call path, and the
  unshipped 9K113 figures living only in prose/tests) — both explicitly optional, no defect today,
  and both already carry their own documentation of the gap. Not blocking.
- Non-obvious behaviour is explained in-code: every derived constant (infantry 5.0, S-300 2.6, the
  clamp's `min()` chain, the floor's slackness proof) carries its derivation as a comment at the
  declaration site, plus the decisions doc (`body-layer/research/2026-09-21-slice2-model-decisions.md`)
  and `implementation.md` for the full narrative.

## Security

- Project posture (`CLAUDE.md` "Agents"): security review is explicitly skipped for this project
  phase (offline, single-user, local pipeline, no hot path, no untrusted-input surface) unless the
  user asks for it. Not requested for this feature. No `security-plan-review.md`/`security-review.md`
  expected or present — consistent with every other recent merge in this repo.

## Verdict: DoD PASSED

---

## Acceptance boundary — what 2A's fixtures structurally cannot reach

2A is a pure-function model correction: given a range/size/distinctiveness/optic, does the
threshold arithmetic come out right. The fixture suite proves the *arithmetic* reproduces the
already-measured pattern (infantry class collapses onto presence; the clamp holds under nested
`min()`s by construction). It cannot prove two things a fixture has no way to see:

1. **Whether the corrected thresholds change what Petrovich actually calls out in a live sortie**
   in a way that reads correctly to the user's ear — a fixture asserts a number, not a callout's
   timing or tone.
2. **The remaining absolute-range gap.** The plan states this explicitly and it is worth repeating
   here rather than letting a fixture pass be mistaken for "ranges are now correct": **2A does not
   fix the measured 1.33× presence shortfall for vehicles**, and separately, the class/type ranges
   this slice computes for infantry (naked 600 m via the clamp) and the S-300 (per-type 2.6) still
   sit below the directly-observed sortie figures once the clamp's computed value is compared
   against the *measured* value rather than the *modelled-before* value — the review's own
   arithmetic shows infantry's binocular class computes to 1452 m against a directly-observed
   2.0 km, narrow to 3486 m against 4.5 km. The **structural** collapse (ratio 1.00, i.e. class no
   longer trails presence) is proven; the **absolute** range is not calibrated to match the sortie
   numbers exactly, by design — recalibrating `LOWRES`/`MEDRES`/`HIRES` themselves is explicitly
   out of scope for 2A (plan, "Explicitly out of scope").

No fixture can distinguish "the shape is right and the absolute number is knowingly short" from
"the shape is wrong" — that distinction requires reading the plan's own scope cut, which is why
it's stated here rather than left implicit in a passing test suite.

## Live acceptance position

**What is verified now, without a new sortie:** the structural claim this slice exists to prove —
class-tier ranges collapse onto presence-tier ranges for indistinct-by-default-turned-distinct
object classes (infantry, and the S-300 via its per-type exception) — is reproduced by the shipped
arithmetic at both optics 2A actually ships (`UNAIDED_OPTIC`, `BINOCULAR_OPTIC`), verified two ways:
by `test_infantry_class_clamps_to_presence_at_every_optic` and by the Reviewer's independent
hand-check of the same arithmetic against `object_model.py`'s inline derivation comments. This
reproduces the *shape* of the already-flown 2026-09-21 sortie's measurement (ratio 1.00 at all four
instruments the user actually flew — naked/binocular/9K113-wide/9K113-narrow, 0.6/0.6, 2.0/2.0,
2.0/2.0, 4.5/4.5 km) for the two instruments this slice puts in the live code path. The 9K113
wide/narrow rows are **not** live-reachable this slice (no selectable 9K113 optic exists yet, by
explicit scope cut) — their agreement was checked by hand against the unshipped constants, not
exercised by running code, and that is a documented, deliberate gap, not an oversight.

**What still needs a sortie, and is not claimed done here:** the plan's own acceptance gate for 2A
(the "Gate to the next slice" column) is "A sortie with BL-9 tracing: infantry class ≈ presence;
S-300 class within ~1.5× of 4500 m; vehicle class/presence unchanged within noise." **That flight
has not happened since 2A landed** — the 2026-09-21 sortie the decisions doc and this slice's
constants are derived from was flown *before* 2A's code existed, to gather the numbers 2A now
encodes; it confirms the model decisions, not this implementation of them. Flying with BL-9 tracing
against 2A's actual code is the outstanding item, and it belongs on `body-layer/ROADMAP.md`'s "Live
acceptance debt" list once this branch merges — it is deferred, not waived, per the plan's own
acceptance-gate language.

**This does not block the merge decision.** Per root `CLAUDE.md`'s "Live Verification" guidance,
live acceptance happens in bursts and the user's Windows-box access governs when. Nothing about 2A
needs to be re-verified before 2B can start — 2B is behaviour-preserving by construction (default
`FULL_GAZE`) and does not depend on 2A having been flown.

## Answers to the milestone-completion question (root `CLAUDE.md`)

**1. Does 2A's outcome still support 2A-before-2C sequencing, or does anything argue for a
different next slice?** It still supports it, more strongly than before. The ordering rationale was
that 2C's calibration is unreadable if a sortie can't attribute a changed detection range to *either*
"whether" (2A) or "when" (2C). 2A landed clean, with no scope drift and no surprises the plan didn't
already carry (the vehicle-row movement was explicitly flagged as an unavoidable, xfailed
consequence, not a defect). Nothing in the actual implementation changes that reasoning. The next
slice per the plan's own ordering is **2B** (gaze as a filter) — it is explicitly behaviour-preserving
(`FULL_GAZE` default) and cost-neutral, so it can land and be tested on fixtures alone before 2C's
scan loop (which is where the real subjective/feel risk and the cost saving both land together, per
hard part 3). No reason surfaced here to reorder ahead of 2B.

**2. Is threshold recalibration now unblocked?** No. The plan named three reasons recalibration was
deferred: tier-dependent magnification, silhouette distinctiveness, and the unanswered
calibration-target question. 2A implements the first two and both are now live and tested. The
third is **not** resolved by 2A, and it is two separate open items, not one — both must clear, and
clearing one does not clear the other:

- **The calibration-target question itself is still unanswered by the user**: whether presence
  should be fit to what a player sees on a monitor, or kept conservative for what a real crewman in
  the cockpit would see. This is a decision only the user can make, and nothing in 2A resolves it —
  2A's own arithmetic (infantry binocular computing to 1452 m against a directly-observed 2.0 km) is
  itself downstream of this unanswered choice, not independent of it.
- **The 2026-09-17 screenshot calibration ladder is separately compromised** (plan, Risks &
  Unknowns): DCS detection-aid dots were enabled during capture, so `LOWRES`/`MEDRES`/`HIRES` remain
  pinned to optimistic ground truth regardless of which target the user eventually picks. A clean
  (dots-off) re-capture is needed independent of the target question.

So recalibration now sits behind **both** the contaminated ladder **and** the unanswered
calibration-target question, with 2A having cleared only the two model-*shape* reasons
(tier-dependent magnification, distinctiveness). Clearing the ladder alone would not be sufficient —
the target question would still block. Consistent with the plan's explicit scope cut ("Threshold
recalibration beyond what the decisions doc fixes" is out of scope for the whole milestone, not just
2A).

**3. Does anything in 2A make the `OBSERVED_WINDOW_S = 16.0` derivation (2C) wrong?** No. That
derivation depends only on `SCAN_CYCLE_PERIOD_S`/`FOCUS_DWELL_S` (both 2C constants, not yet
declared) and `belief/decay.py`'s existing `POSITION_HALF_LIFE_S`. 2A has zero diff in
`belief/decay.py` (confirmed above and independently by the Reviewer's own grep) and does not touch
scan cadence, gaze, or attention timing in any way — it only changes *which* range a tier is
achieved at, not *when* a poll looks in a given direction. Nothing here bears on that derivation.

---
---

## DoD Check — Cones Slice 2A.5 (intake cap counts groups, not objects)

Branch: `feature/cones-2a5-group-intake`. Implementation commits `1d501c0`, `43c67aa`, `b973784`,
`02d2abd`. Review commit `8f7b1d0` (Reviewer: **APPROVED WITH MINOR FIXES**, full-read confidence,
both fixes applied in the same commit).

Ran against commit `8f7b1d061` (checked out detached in this agent's own worktree, since the branch
tip was already checked out in the shared checkout this agent is isolated from — same tree, no
divergence).

### Code Quality

- **Subprojects touched**: `git diff --name-only 46b0e3c...8f7b1d0` (merge-base of `main`) shows
  only `body-layer/CLAUDE.md`, `body-layer/src/perception/{detection_trace,naked_eye_source}.py`,
  `body-layer/tests/test_{detection_trace,naked_eye_source}.py`, and
  `plans/detection-cones-slice2/{implementation,review}.md`. `world-model/` and `aircraft-layer/`
  untouched. The three untracked files under `world-model/` at repo root (`run.sh`,
  `syria-full-build.log`, `syria-theatre-unfiltered.osm.pbf`) are pre-existing, unrelated to this
  branch, and were **not** staged.
- Ran the full body-layer verification sequence myself, per `body-layer/CLAUDE.md` "Commands" (had
  to build a fresh `.venv` in this isolated worktree first — `pip install -e . ruff mypy pytest`):
  - `ruff format --check src tests` → `81 files already formatted` (PASS)
  - `ruff check src tests` → `All checks passed!` (PASS)
  - `cd body-layer && mypy src` → `Success: no issues found in 38 source files` (PASS)
  - `pytest tests -q` → **780 passed, 4 xfailed** (PASS — exact match to review's and
    implementation.md's claimed result)
  - All 4 2A.5-specific tests also run individually and confirmed passing:
    `test_a_dense_group_larger_than_the_cap_admits_whole_in_one_poll`,
    `test_a_capped_out_group_is_retried_and_the_backlog_drains_over_polls`,
    `test_continuity_survives_a_cluster_whose_membership_grows_between_polls`,
    `test_more_new_candidates_than_the_cap_emits_only_the_cap_nearest_first` → `4 passed`.
  - Confirmed the 4 xfails via `pytest tests -q -rx`: all four carry explicit reasons naming slice
    **2A**'s `presence_range_mult=2.42` vs. `LOWRES_ANGULAR_RADIUS_RAD`'s old-flat-4.0 derivation
    (`test_visibility.py::test_armored_vehicle_is_visible_at_the_farthest_photographed_range`,
    `test_vision_calibration.py::test_computed_tier_matches_ground_truth[C-1000m]`,
    `test_gate_admits_every_photographed_range[C-8890m]`, `[C-6580m]`). None reference 2A.5,
    clustering, or the group-intake cap. **2A.5 added zero new xfails, as claimed.**
- No debug output/TODO/FIXME/`pdb`/`breakpoint` introduced: grepped the diff over touched
  `body-layer/src`/`body-layer/tests` for `print(`/`TODO`/`FIXME`/`pdb.set_trace`/`breakpoint(` —
  no hits.
- No unhandled errors/panics in data paths — pure reordering of an existing pure-function pipeline
  (`poll()`'s gate → cluster → cap → emit sequence); no new I/O.
- **Review's stale-constant fix verified landed**: grepped `body-layer/` for
  `NAKED_EYE_MAX_NEW_PER_POLL` post-fix — the three remaining hits are all "renamed from X"
  historical references in comments/docstrings (`CLAUDE.md:350`, `test_detection_trace.py:264`,
  `naked_eye_source.py:77,175`), not stale live usages. The one the review flagged as wrong
  (`test_detection_trace.py:259`'s old comment) now correctly reads
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` and explains why that scenario is unaffected by the unit
  change.
- **Review's cost-verification fix verified landed**: `implementation.md`'s new "Cost verification
  (plan step 6d)" section states the measured figure (17,487 admissions / 4,719 polls, ~3.7/poll)
  the review asked for.

### Scope & Correctness

- Matches the plan's 2A.5 sections exactly (slicing table row, "2A.5 sits where it does" rationale,
  hard part 6a, implementation steps 6a-6d): `poll()` reorders to gate → cluster all survivors →
  cap clusters → emit; acquisition state stays keyed on `object_id` per hard part 6a (clusters have
  no stable cross-poll identity); the constant is renamed, value unchanged at 3, per step 6c
  ("changing unit and value together makes the sortie unattributable").
- **The real defect fix is in scope, not scope creep**: `naked_eye_source.py`'s own pre-existing
  docstring already recorded "a capped-out object is never retried" as a known limitation, and step
  6b explicitly calls for fixing it as part of this slice.
- No unplanned scope: confirmed via diff — no `gaze.py`, no `ScanPlan`, no scan-loop/dwell code
  (2B/2C/2D untouched), no touches to `visibility.py`/`optics.py`/`object_model.py`/`decay.py`, no
  `perception → belief` import.
- No CLAUDE.md invariants violated: no omniscience leak (review hand-traced that `visible` — what
  gets clustered — is built strictly from candidates that already individually cleared
  `check_visibility`, and every acquired object traces back to a per-candidate `ADMITTED` gate
  outcome recorded before clustering runs); single-player scope untouched; no world-model data
  committed.
- **The one escalation-worthy item was correctly escalated, not silently done**: 2A.5 rewrites a
  pinned test (`test_candidates_dropped_by_the_cap_are_not_retried_next_poll` →
  `test_a_capped_out_group_is_retried_and_the_backlog_drains_over_polls`) rather than extending it,
  which the plan itself flags against `AGENTS.md`'s escalation list ("existing tests must be
  rewritten rather than extended"). Plan records explicit user approval, dated 2026-09-21, before
  implementation proceeded.
- All new/modified files staged with `git add` — confirmed via `git status --short` in the checked-
  out commit: clean (the one untracked item, `body-layer/src/dcs_body_layer.egg-info/`, is this
  agent's own local `pip install -e .` build artifact from setting up a venv in an isolated
  worktree that had none checked out — gitignored via `.venv/`'s sibling entries, not part of the
  branch, not staged).

### Testing

- Core logic covered: the four new/rewritten tests exercise exactly the headline claims — a
  cap-exceeding dense group admits whole in one poll; a capped-out group is retried and the backlog
  drains over subsequent polls (the real defect fix, with counts derived from the model rather than
  observed); acquisition-state continuity survives a cluster whose membership grows between polls
  (proving the `object_id`-keyed design decision actually works); angularly-separated singleton
  groups are still capped at N per poll (renamed-constant regression coverage).
- Tests are meaningful, not decorative: reviewer independently hand-traced the acquisition-state
  split and hand-derived the rewritten test's expected counts (3, then 2, then 0) against the code
  rather than trusting the stated derivation, and confirmed no path exists for an object to be
  marked acquired without its observation being emitted or vice versa.
- No existing tests broken: 780 passed vs. 2A's baseline of 778 (net +2: one pinned test replaced
  1:1, two new tests added), 4 xfails unchanged and all attributable to 2A, not 2A.5.

### Documentation

- Reviewer findings addressed: both required fixes (stale constant-name comment, missing
  cost-verification line) applied in `8f7b1d0`, confirmed above by re-reading the actual diff, not
  just the commit message.
- Non-obvious behavior explained: `naked_eye_source.py`'s module docstring points 3-5 rewritten to
  describe the new order and the cap's new unit; `body-layer/CLAUDE.md`'s Structure entries for
  `naked_eye_source.py`/`detection_trace.py` updated to describe 2A.5's actual behavior rather than
  the superseded per-object cap.

### Security

- `plans/detection-cones-slice2/` has no `security-plan-review.md` or `security-review.md`, and
  none is expected: root `CLAUDE.md` "Agents" section exempts Security for this project phase
  ("this phase is an offline single-user local pipeline with no hot path and no untrusted-input
  surface yet... Only run either when the user explicitly asks for it") — not requested here. N/A,
  not a gap.

### Verdict

**PASS.** No FAILs. Two reviewer-required fixes both verified landed by re-reading the diff, not
the commit message.

---

### Acceptance boundary — what this feature's fixtures structurally cannot reach

The headline claim — a dense group admits whole in one poll instead of trickling over three — is
**fully verifiable at fixture level and was just verified above.** The clustering geometry, the
gate-then-cluster-then-cap ordering, and the retry/backlog-drain fix are all deterministic pure
functions over synthetic candidate positions; nothing about them requires a live DCS session to
exercise correctly.

What fixtures **cannot** reach: whether the cap's *value* (still 3, unchanged) is right for real
group sizes and real angular geometry Petrovich will actually encounter, and whether "reported
whole in one poll" reads correctly in the crew-facing callout language once it reaches
`belief`/`CrewConsole`. The plan is explicit that this is deliberately deferred, not overlooked:
step 6c keeps the value unchanged specifically so a future sortie can attribute any felt difference
to the unit change alone, not a conflated unit-and-value change. The user's own existing sortie
data (referenced throughout the plan's calibration sections) was gathered on **single units at
known ranges** — it contains no group-density scenarios and cannot retroactively validate or refute
this slice's group behavior.

### Milestone-completion question

1. **Is 2B still genuinely next and behaviour-preserving?** Yes. 2A.5's entire purpose was to land
   *before* 2B specifically because it changes the default path (plan: "it changes the default
   path, so it cannot ride in 2B without destroying 2B's acceptance gate"). With 2A.5 now reviewed
   and its default behavior settled, 2B's acceptance gate ("with no command issued, the trace is
   identical to the previous slice") now correctly means *identical to 2A.5's trace*, not 2A's.
   Confirmed via diff that 2A.5 touched nothing 2B's plan depends on (`gaze.py` doesn't exist yet;
   `visibility.py`, `optics.py` untouched). The ordering premise holds.

2. **Is the intermediate-density prediction still sound, and is it recorded where the 2C sortie
   will be read against it?** Sound — it's a structural consequence of what was actually built, not
   a separate claim: dense groups now admit whole (cap doesn't bind), sparse objects spread across
   the whole envelope also spread across cones (few groups per cone), so only "many
   angularly-resolvable groups inside one 30° cone at similar range" can still bind the cap. Yes, it
   is recorded — in `plans/detection-cones-slice2/plan.md`'s "Risks & Unknowns" section ("The
   intake limit under a 2 s cone dwell — and the earlier finding here inverts"), which is the same
   document the plan's own slicing table designates as where 2C's sortie gets judged. No action
   needed; flagging here only to confirm it wasn't left to be rediscovered.

3. **Does 2A.5 affect `OBSERVED_WINDOW_S` or the 9-3 scan-coverage decision?** No. Confirmed by
   diff: `belief/decay.py` (home of `OBSERVED_WINDOW_S`) and the scan-coverage table (plan hard
   part 8, not yet implemented — 2C is plan-only on this branch) are both untouched. The group-
   intake cap and the scan-cycle timing answer genuinely different questions per the plan's own
   "third intake limiter would double-count" risk note, and 2A.5 only touches the former.

---

### Acceptance Testing Plan: Cones Slice 2A.5 — Group-Level Intake Cap

**Goal:** Verify that a dense group of objects is now admitted whole in one poll instead of
trickling in over multiple polls, and that a capped-out group is retried rather than dropped
permanently — at the level this can actually be checked today (fixture/desk level; **not** a live
DCS sortie — see boundary above).

**Prerequisites**
- [x] Type-checked and importable: `cd body-layer && mypy src` → `Success: no issues found in 38
      source files` (ran above, PASS).
- [x] Full test suite green: `pytest tests -q` → `780 passed, 4 xfailed` (ran above, PASS).

**Test Cases (already run, results below — not hypothetical)**

1. Ten co-located Infantry candidates (single-link-chained, 10 m spacing) polled once — expected:
   one `Observation` covering all ten. **Result: PASS**
   (`test_a_dense_group_larger_than_the_cap_admits_whole_in_one_poll`).
2. Five angularly-separated singleton groups with cap=3, polled across three polls — expected:
   poll 1 admits 3 nearest, poll 2 admits the remaining 2 (not dropped), poll 3 emits nothing new.
   **Result: PASS** (`test_a_capped_out_group_is_retried_and_the_backlog_drains_over_polls`).
3. A 3-member cluster observed, then a 4th member joins on the next poll — expected: continuity
   resolves via object-id majority vote to the original observation. **Result: PASS**
   (`test_continuity_survives_a_cluster_whose_membership_grows_between_polls`).
4. Five angularly-separated singleton groups, cap=3 — expected: only 3 nearest admitted this poll.
   **Result: PASS** (`test_more_new_candidates_than_the_cap_emits_only_the_cap_nearest_first`).

**Edge Cases Probed**
- No-omniscience-leak: every member of an admitted cluster individually reached
  `GateOutcome.ADMITTED` before clustering ran — verified via `DetectionTraceCollector` assertions
  inside test 1, and independently hand-traced by the Reviewer against the code.
- Stale-comment regression: `test_a_cluster_splitting_gives_the_majority_child_continuity`'s
  4-candidate fixture, which happens to produce the same `len(first)==1` result under both the old
  per-object and new per-group cap (for different reasons) — comment corrected, assertions
  unaffected. Re-ran, still passes.

**Pass Criteria**
All four test cases produce the expected result (they do) and the full suite shows no regressions
against 2A's 778-passed baseline (confirmed: 780 passed, same 4 xfails, all attributable to 2A).

**What this plan does NOT and cannot cover (see boundary above):** whether the cap value of 3
groups per fixation feels right against a real mission's group density and geometry, and whether
the resulting callout phrasing ("ten trucks" vs. three separate reports growing over time) sounds
right in the cockpit. Both require the group-behavior sortie the plan defers to 2B/2C's flights.
No test-card artifact is published for this slice — there is nothing new for the user to *do* in
DCS specifically for 2A.5 that isn't already covered by whatever sortie eventually exercises the
group-intake cap in practice; publishing one now would be inventing a thin live test the instructions
explicitly warn against.

---

## DoD Check — Cones Slice 2B (gaze as a filter)

Branch: `feature/cones-2b-gaze-filter`. Implementation commit `5728841`, plan correction `e520e8b`
(the `FULL_GAZE`→`None` default fix, filed by the implementer after catching the plan's own
internal contradiction). Review commit `b2d76e6` (Reviewer: **APPROVED**, full-read confidence,
zero required fixes).

Ran against commit `b2d76e6`, checked out detached in this agent's own isolated worktree (the
branch tip was already checked out in the shared main checkout this agent is isolated from — same
tree, confirmed no divergence: `git log feature/cones-2b-gaze-filter --oneline` and `git merge-base
main b2d76e6` both resolve to `c4d4f22`, current `main` tip, so the branch forked cleanly with
nothing else landed on `main` since).

### Code Quality

- **Subprojects touched**: `git show 5728841 --stat` shows only `body-layer/` (`src/perception/
  {gaze.py (new), geometry.py, optics.py, visibility.py, detection_trace.py, naked_eye_source.py}`,
  `src/belief/attention.py`, `src/logger.py`, six test files) plus `plans/detection-cones-slice2/
  implementation.md` and `todo/todo.md`. `world-model/` and `aircraft-layer/` untouched — confirmed
  by `git diff --name-only` against the merge-base.
- Ran the full body-layer verification sequence myself (using the pre-built venv at
  `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, since this worktree had none and this
  environment has no Python 3.11/3.12 interpreter to build a fresh one — same interpreter/deps the
  main checkout's venv uses, confirmed by `python --version` → 3.14.7 matching both):
  - `ruff format --check body-layer/src body-layer/tests` → `83 files already formatted` (PASS)
  - `ruff check body-layer/src body-layer/tests` → `All checks passed!` (PASS)
  - `cd body-layer && mypy src` → `Success: no issues found in 39 source files` (PASS)
  - `pytest body-layer/tests -q` → **810 passed, 4 xfailed** (PASS — exact match to
    `implementation.md`'s and the review's claimed result; baseline before 2B was 780
    passed/4 xfailed, so 2B added exactly 30 new tests and zero new xfails)
  - Confirmed via `pytest -q -rx`: all four xfails carry reasons naming slice **2A**'s
    `presence_range_mult=2.42`/`type_range_mult=3.00` vs. `LOWRES_ANGULAR_RADIUS_RAD`'s
    flat-4.0 derivation (`test_visibility.py::
    test_armored_vehicle_is_visible_at_the_farthest_photographed_range`,
    `test_vision_calibration.py::test_computed_tier_matches_ground_truth[C-1000m]`,
    `test_gate_admits_every_photographed_range[C-8890m]`/`[C-6580m]`). None mention `gaze`,
    `peripheral`, `Optic.boresight`, or anything 2B touched. **2B added zero new xfails, as claimed
    by both the implementer and the reviewer.**
- No debug output/TODO/FIXME/`pdb`/`breakpoint` introduced: grepped the full diff for `print(`,
  `TODO`, `FIXME`, `pdb.set_trace`, `breakpoint(` — no hits in any touched source or test file.
- No unhandled errors/panics in data paths: `within_gaze`, `gaze_for`, `gaze_from_relative_sector`
  are pure functions over floats/enums; the one new I/O-adjacent path (`logger._active_gaze`
  reading `TaskStore.tasks`) is a plain iteration with no exception-suppressing `except` added.
- **`Optic.peripheral` field addition verified inert by default**: `peripheral: bool = True` on the
  dataclass, so the three pre-existing synthetic `Optic(...)` call sites in `test_visibility.py`
  construct unchanged — confirmed by reading the diff to `test_visibility.py`, not just trusting
  the implementer's note. Only `BINOCULAR_OPTIC` sets it `False` explicitly.

### Scope & Correctness

- Matches the plan's 2B sections exactly (slicing table row 2B, hard parts 1/2a/3/4/5, Implementation
  Plan steps 6-10): `Gaze`/`within_gaze`/`gaze_for`/`gaze_from_relative_sector` in a new
  `perception/gaze.py`; `RelativeSector` vocabulary moved down from `belief/attention.py`;
  `check_visibility(gaze=...)` evaluated first in the gate chain; `Optic.peripheral` plus the
  bypass rule; F10 scan commands wired through `logger._active_gaze`/`_apply_active_gaze`. No
  `ScanPlan`, `gaze_at`, `FOCUS_DWELL_S`, or `SCAN_CYCLE_PERIOD_S` anywhere in source — grepped
  myself, confirming the reviewer's own claim rather than trusting it. `clustering.py`,
  `object_model.py`, `decay.py`, `association.py`, `belief/contacts.py` untouched (2C/2D scope,
  correctly not touched).
- **The one deliberate deviation from the plan's literal text is correctly scoped, not scope
  creep**: the plan's Implementation Plan step 9 and Hard Part 3 both said the 2B default is
  `FULL_GAZE` (±90°) and called it a no-op; the implementer found this false against
  `cockpit_mask.py`'s measured `rear_cutoff_deg=130.0` and shipped `gaze=None` instead — read
  `e520e8b`'s diff to `plan.md` myself, and it corrects exactly this without adding, removing, or
  softening any other requirement. This is a plan *correction*, filed transparently as its own
  commit, not a silent implementation shortcut — exactly the "if you find yourself changing an
  expected value, stop and report it" instinct working as intended.
- No unplanned scope added: diffed the full file list against the plan's own 2B "Affected Modules"
  list (13 files named, 13 files touched, one-to-one).
- No CLAUDE.md invariants violated: **no-omniscience checked specifically**, since a bypass rule is
  exactly the shape of leak this invariant guards against — `gaze_for`'s bypass clears the gaze gate
  only, never cockpit mask/range/terrain LOS (`test_bypassed_gaze_still_respects_the_cockpit_mask`,
  read and re-traced against `visibility.py`'s actual gate order, not just the test name); single-
  player scope untouched; no world-model data committed; `perception` still does not import `belief`
  (checked via grep, matching the reviewer's own claim).
- All new/modified files staged with `git add`: confirmed via `git status --porcelain` at the
  reviewed commit — clean.

### Testing

- Core logic covered: `test_gaze.py` (13 tests: shape, boundary, a genuinely non-axis-aligned
  37°/42° case, a 180°-seam wraparound, the bypass rule under both optics plus a synthetic
  non-peripheral optic, all four relative-sector mappings); gate-ordering/rejection/admission/
  bypass-invariant/boresight-follows-gaze tests in `test_visibility.py`; filter/default/bypass tests
  in `test_naked_eye_source.py`; `_active_gaze`/`_apply_active_gaze`/one `run_once` integration test
  in `test_logger.py` that wires a real pending `scan_area` task onto a real
  `NakedEyePerceptionSource` through the actual poll loop, not just a unit-level mock.
- Tests are meaningful, not decorative: the reviewer independently traced `FULL_GAZE`'s definition
  against `cockpit_mask.py`'s `rear_cutoff_deg` rather than trusting the implementer's claim, and
  the wraparound/non-axis-aligned angle tests exist specifically because (per the plan's own
  standing note) a prior bug in this codebase hid behind an axis-aligned-only test suite — read that
  test's assertions myself and confirmed they'd actually catch the class of bug they're named for.
- No existing tests broken: every change to a pre-existing test file is either a pure addition or a
  mechanical call-site update forced by `within_optic_fov` gaining a required `boresight_azimuth_deg`
  parameter (same expected values, new parameter threaded through) — confirmed by reading the diff,
  not the commit message. 810 passed vs. 780 baseline (net +30, all additions), 4 xfails unchanged
  and all attributable to 2A.

### Documentation

- Reviewer findings addressed: **zero required fixes** — nothing to address. The review's two
  "Optional Refinements" (peripheral=False not exercised through FOV-gate tests; `_active_gaze`'s
  insertion-order assumption undocumented in its own docstring) are correctly optional — neither is
  a defect in the reviewed commit, and leaving them unaddressed does not block DoD.
- Non-obvious behavior explained: `GateOutcome.GAZE`'s own docstring records the trace-attribution
  cost (a rear-hemisphere rejection now records `GAZE` instead of `COCKPIT_MASK` once a gaze is
  active) and why that's accepted rather than "fixed" by reordering — read it, it's there.
  `plan.md`'s "What is unprotected until the capture channel exists, stated plainly" section names
  the peripheral-channel gap directly (see milestone-completion answers below). `implementation.md`'s
  2B section is thorough and its "Notable Discoveries" correctly flags the plan-contradiction finding
  as worth a plan correction before 2C.

### Security

- No `security-plan-review.md`/`security-review.md` exists for this feature, and none is expected:
  root `CLAUDE.md` "Agents" section exempts Security for this project phase, unrequested here. N/A,
  not a gap.

### Verdict

**PASS.** No FAILs. Reviewer approved with zero required fixes; nothing for this gate to send back.

---

### Acceptance boundary — what 2B's fixtures structurally cannot reach

**2B's own defining property is that it changes nothing observable by default** — the trace with no
scan command issued is byte-identical to 2A.5's. That property is fully provable at fixture level
and was just proven above (`test_default_gaze_is_none_and_does_not_narrow_the_cockpit_envelope` and
its `NakedEyePerceptionSource`-layer twin, both placing a candidate specifically in the 90°–130°
band a wrong default would have silently dropped). Fixtures cannot reach past that: whether a real
"scan left" command, issued mid-flight, actually changes what the pilot hears reported, on real DCS
geometry, on the real `logger.py` poll loop wired to a real aircraft-layer feed — that is a live-DCS
question by nature, and 2B's own fixtures were never going to answer it. Naming the two prior
sortie-found defects that no fixture caught for exactly this reason: `Scan` driving the wrong
subsystem (9K113 sight instead of naked-eye perception — the bug 2B exists to fix, found only by
flying it), and `Cancel Task` speaking a raw task id aloud (only a defect when a human *hears* it;
as text in a log it looked correct). Neither class of gap is closed by more unit tests; both are
closed by a flight.

### Answers to the milestone-completion question (root `CLAUDE.md`)

1. **2B is behaviour-preserving, so nothing observable changed for the pilot. Does that make 2C
   genuinely next, and is 2C still the slice that makes the difference audible?** Yes to both.
   2B's entire acceptance gate was "identical trace with no command issued" — confirmed structurally
   above — so there is, by design, nothing for a sortie to feel yet from 2B alone. 2C (default gaze
   becomes the 12-11-10-9-12-1-2-3 o'clock scan loop, 2 s/sector, 16 s cycle) is exactly the slice
   the plan's own slicing table marks "Yes — this is the big one" for live acceptance, judged on
   whether the user finds things at a plausible rate and whether callout language stays stable as
   contacts cycle in and out of gaze. Confirmed via diff that 2B touched nothing 2C's plan depends
   on (`ScanPlan`, `FOCUS_DWELL_S`, `SCAN_CYCLE_PERIOD_S` don't exist in source yet) — the ordering
   premise from 2A.5's own DoD check still holds one slice later.

2. **2C moves `decay.OBSERVED_WINDOW_S` from 5.0 to 16.0. Does anything in 2B affect that
   derivation?** No. `body-layer/src/belief/decay.py` is untouched by 2B — confirmed both by `git
   show 5728841 --stat` (not in the file list) and by reading the file directly:
   `OBSERVED_WINDOW_S: Final[float] = 5.0`, unchanged. The derivation depends on the 16 s scan-cycle
   period and the two bounds named in the task (`CYCLE − DWELL = 14` below, `POSITION_HALF_LIFE_S =
   30` above); 2B introduces gaze-as-a-filter but not the scan cycle itself, so none of the three
   quantities the 2C derivation depends on moved.

3. **`Optic.peripheral` exists with the bypass rule wired but no triggers. Is that gap recorded
   somewhere a later reader will find it, and is the exposure stated plainly?** Yes, on both counts.
   `plans/detection-cones-slice2/plan.md`'s "What is unprotected until the capture channel exists,
   stated plainly" section (read directly, not taken on the implementer's word): "from 2C onward, an
   incoming missile or a muzzle flash outside the current 30° focus cone is simply not noticed,"
   explicitly noting this doesn't regress anything working today (nothing detects incoming weapons
   yet) but adds a second, independent reason it won't work, and that the capture channel "must land
   alongside whatever finally builds the weapon detector, not after it." `GateOutcome.GAZE`'s
   docstring and `gaze_for`'s own module-level placement in `gaze.py` reinforce this at the code
   level. This is recorded in the one place a later reader planning the capture channel or the
   weapon-detector work would actually look — the plan document itself, in the section named for
   exactly this purpose — not buried in a commit message or a review aside.

---

### Acceptance Testing Plan: Cones Slice 2B — Gaze as a Filter

**Goal:** Verify 2B is behaviour-preserving by default (desk-verifiable now) and identify what
should wait for a live sortie rather than being tested prematurely.

**Prerequisites**
- [x] Type-checked and importable: `cd body-layer && mypy src` → `Success: no issues found in 39
      source files` (ran above, PASS).
- [x] Full test suite green: `pytest body-layer/tests -q` → `810 passed, 4 xfailed` (ran above,
      PASS, exact match to claimed result).

**What is desk-verifiable now, and was just verified above (not hypothetical):**

1. With no scan command issued, `check_visibility`'s gaze gate is a true no-op — proven by
   `test_default_gaze_is_none_and_does_not_narrow_the_cockpit_envelope` and its
   `NakedEyePerceptionSource`-layer twin, both against a candidate placed specifically in the
   90°–130° band a wrong default would silently drop. **Result: PASS.**
2. A narrow gaze correctly filters an off-axis candidate and admits an on-axis one, at both the
   `check_visibility` unit layer and the `NakedEyePerceptionSource` integration layer. **Result:
   PASS** (`test_gaze_gate_rejects_outside_wedge_and_admits_inside_it` and
   `test_naked_eye_source.py`'s narrow-gaze filter test).
3. `GateOutcome.GAZE` fires ahead of `GateOutcome.COCKPIT_MASK` in the trace when both would reject
   the same candidate — proven directly, not just by pass/fail outcome. **Result: PASS**
   (`test_gaze_gate_runs_before_the_cockpit_mask`).
4. The peripheral bypass clears the gaze gate only, never cockpit mask/range/terrain LOS. **Result:
   PASS** (`test_bypassed_gaze_still_respects_the_cockpit_mask`).
5. A pending `scan_area` F10 task actually reaches a real `NakedEyePerceptionSource.gaze` through
   `ConsolePerceptionRunner.run_once`'s actual poll loop, not a mock. **Result: PASS**
   (`test_logger.py`'s `run_once` integration test).

**What is live-testable today but should wait for 2C's sortie, and why:**

An F10 "scan left"/"scan right" command now genuinely steers what naked-eye perception reports —
that is a real, live-testable behaviour change today, not one artificially deferred. But it is a
poor sortie on its own: with only a fixed narrow gaze available (no free-scan default yet), the
pilot has nothing to contrast the scanned state against except memory of an earlier, different
flight — exactly the attribution problem the plan's own slicing table names for why 2A/2C were
split ("flown together, a sortie cannot attribute a changed range to either"). The same reasoning
applies here in miniature: a scan command's effect reads clearly only against a baseline the pilot
can fly in the same sortie, and 2C's free-scan gaze *is* that baseline. Recommend folding this into
2C's flight rather than flying it in isolation now.

**No test-card artifact is published for 2B.** There is genuinely something new the user *could* do
in DCS (issue a scan command and notice a change), but flying it in isolation before 2C would
produce a weaker signal than the same test flown alongside 2C's scan-loop sortie, and publishing a
card now risks the user flying a thin test and drawing a conclusion from it that 2C's sortie would
have made clearer. This is the "deferred, not waived" case from `body-layer/ROADMAP.md`'s Live
acceptance debt section — it belongs on that list at merge time, pointing at 2C's sortie as the
flight that clears it, not treated as a standalone card.

**Pass Criteria**
All five desk-verifiable cases above produce the expected result (they do) and the full suite shows
no regressions against 2A.5's 780-passed baseline (confirmed: 810 passed, same 4 xfails, all
attributable to 2A). Live acceptance for the scan-steers-perception behaviour itself is explicitly
**not** part of this slice's pass criteria — see above.
