### Review Summary

Reviewed `BL-B64` Stage 1 (two sight `Optic` rows + field of regard), Stage 1b (`BL-B55`
per-optic position sigma), the §15a desired/actual aim split, and the §14
`UNAIDED_OPTIC` FOV change, on `feature/9k113-sight` at `4ba4d2f9e580cdae19641fe025925fd6c36c504c`
(single commit). Scope matches the task brief exactly: no selection, no cone, no
optic-aware range cap, no `optic_policy` resting-phase change, no slew controller.

**Address verification.** HEAD was already the named tip sha in a fresh worktree created
from `origin/HEAD` at `git worktree add`, tree clean, no merge needed. All four input
documents present and read in full. `body-layer/.venv` rebuilt with the pinned versions
(`ruff==0.16.6`, `mypy==2.3.1`, `pytest==9.1.1`, `numpy==2.4.6`, `pyproj==3.8.0`) via
`python3 -m venv .venv && .venv/bin/pip install -q ruff==... mypy==... pytest==... numpy==... pyproj==...`
inside `body-layer/` — no editable install needed since mypy/pytest resolve `src`/`tests`
and world-model's `src` via `pyproject.toml`'s `mypy_path`/`pythonpath`.

**Verification — matches every claimed number exactly.**
- `ruff format --check .`: fails only on pre-existing out-of-scope `research/2026-10-05-security-audit.md`.
- `ruff check .`: all checks passed.
- `mypy src`: success, 0 errors, 59 source files.
- `pytest -q`: **1883 passed, 4 xfailed** (baseline 1870/4, net +13), matching the
  implementer's own count exactly.

**Sourced numbers verified against the source, not the implementer's arithmetic.**
`research/2026-09-20-9k113-sight-optics-from-manual.md` confirms the FOV half-angles
(5.75°/3.00°, half of sourced 11.5°/6.0° full angles) and the field of regard
(±60° azimuth, +20°/−15° elevation, sourced from the English Mi-24P manual §3.4).
`research/2026-09-21-aspect-magnification-and-distinctiveness.md` and
`2026-09-21-slice2-model-decisions.md` confirm the multipliers (wide 3.55/7.00/6.50,
narrow 5.81/13.75/15.00) exactly. `NAKED_EYE_RANGE_CAP_M`'s corrected docstring figure
(2333 m) checks out arithmetically against the current `LOWRES_ANGULAR_RADIUS_RAD = 0.003`
(7/0.003 = 2333.3). The §14 "~102° true separation" claim for the flipped test was
recomputed independently via the spherical law of cosines and matches (≈101.9°).

**Mutation testing, not just reading, on the two highest-risk claims:**
1. *"The carry-forward falls out for free / nothing is dropped."* Temporarily removed
   both `actual_aim_*` carry-forward kwargs from `decide()`'s two fresh-`OpticState(...)`
   branches (`SEARCHING`, `GLASSING`) — both of `TestOpticStateActualAimCarriesForward`'s
   tests failed immediately with the exact defect the implementer's memory note
   describes. Restored; tree clean. Confirmed by `grep` that these are the *only* two
   fresh `OpticState(...)` construction sites in `src/` — the implementer's "check there
   is not a third" claim holds.
2. *"UNAIDED_OPTIC/BINOCULAR_OPTIC sigma is unaffected."* `test_binocular_optic_gets_the_same_sigma_as_the_naked_eye`
   and the two per-optic dicts (`_RANGE_SIGMA_SCALE_BY_OPTIC`, `_SIGHT_BEARING_SIGMA_SCALE_BY_OPTIC`)
   default any unlisted `optic.name` to `1.0` via `dict.get` — read, not just trusted,
   and the test asserts exact equality against the pre-change formula.
3. Staleness test (`test_tuning_defaults_toml.py::test_defaults_toml_matches_the_generator`)
   verified to actually fail: hand-edited one rendered value in `config/defaults.toml`
   without regenerating — test failed with the expected "stale, run with --write" message.
   Restored; tree clean.

**The group-ranged-once rule (§11/§14) is architecturally guaranteed, not incidental.**
`_build_observation` is called exactly once per `Cluster` from `_build_observations`'s
single `for cluster in clusters` loop, and `Observation` itself carries one
`estimated_bearing_deg`/`estimated_range_m` pair for the whole cluster — there is no
per-member position field anywhere in the data model that a future refactor could
redirect to a per-member draw without a visible type change. So this is stronger than
the implementer's "falls out for free, because the call site runs once" — it falls out
from the `Observation` type itself having no per-member slot, which is harder to break
silently than a call-count coincidence. No dedicated new test names this property
directly, but it is load-bearing enough (and structurally protected enough) not to need
one; noted as a minor optional refinement below.

**§15a's determinism property survives.** `gaze_at(t_sim, plan)`'s signature and body
are unchanged — it remains a pure function of its two arguments. The actual/desired
split lives entirely in `OpticState` (frozen, replaced not mutated) and the one
conversion point `logger._apply_active_gaze`, exactly as planned. `dt_s` is computed
from `self.last_t_sim` *before* it is overwritten later in `run_once` (line ordering
checked directly) — correct poll-to-poll delta, 0.0 on the first poll. The `Gaze`/`ScanPlan`
is built from `actual_azimuth_deg`/`actual_elevation_deg`, never from `decision`'s desired
values directly. For `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`, `advance_sight_aim`'s pass-through
body (`return desired`) is correctly documented as *permanently* correct, not a
placeholder — nothing in the call site singles out optics for different treatment, which
is exactly what "must never be imposed on them" requires (there is no optic-conditional
branch to later misapply a rate limit through).

**§14's one real behaviour change is correctly handled.** The reverted test
(`test_the_unaided_eye_ignores_the_boresight_entirely`) asserted the old `None`-means-
unconditional-pass behaviour; it was moved (not silently edited) to
`test_unaided_optic_field_of_view_now_rejects_past_90_degrees_true_separation`, now
asserting the opposite, with the boundary case and its companion both present. The claim
that no other test in the pre-existing suite exercises geometry near the 90° true-
separation boundary was spot-checked by grepping for azimuth/elevation values near 90
across all test files; the one hit (`test_cockpit_mask.py:59`, azimuth=90°) exercises
`cockpit_mask.is_visible`, an unrelated gate that runs earlier in the pipeline and does
not call `within_optic_fov` — consistent with the claim.

**Tuning pattern (role file's new section).** Both new constants
(`SIGHT_WIDE_RANGE_SIGMA_SCALE` 0.5, `SIGHT_NARROW_RANGE_SIGMA_SCALE` 0.3) go through
`tuning.real(...)` with `lo=0.05, hi=1.0`, `status="judgement"`, and a `#:` doc comment.
`config/defaults.toml` was regenerated and the *rendered* entries read directly (not the
source comment): both render as a single clean first-sentence description, correct
status/range line, correct default value — no truncation, no corrupted markup, no second-
sentence warning lost in rendering. The `hi=1.0` bound is itself doing useful work here:
it caps the sight's down-range coefficient at the naked eye's own 0.17, so no retune can
make the sight's modelled down-range precision worse than the unaided eye's, without
anyone having to assert that separately.

**Cross-key coupling, checked rather than assumed.** `SIGHT_WIDE_RANGE_SIGMA_SCALE` and
`SIGHT_NARROW_RANGE_SIGMA_SCALE` have an implicit ordering requirement (narrow should stay
≤ wide) that nothing enforces at import — they are not in `tuning.py`'s `_COUPLED_KEYS`
mechanism. However `test_sight_optics_get_a_smaller_down_range_sigma_than_the_naked_eye`
reads the *live* module-level constants (populated from `defaults.toml` at import) and
asserts `down_narrow < down_wide < down_eye`, so a future retune that inverted the
ordering would fail this test before merge — not an import-time crash, but not silent
either. Flagged as optional below because the existing mechanism (`_COUPLED_KEYS`) is
reserved for a documented, more severe coupling (scan/decay) and extending it here would
be disproportionate to a judgement constant meant to be hand-tuned from flying.

### Required Fixes

None.

### Optional Refinements

- **Group-ranged-once could carry one line of its own test**, naming the invariant
  directly ("`_build_observation` is called once per cluster, and `Observation` has no
  per-member position field") rather than relying on it being implied by the existing
  one-observation-per-cluster architecture. Low priority: the property is currently
  protected by the type shape itself, not merely by a call count, so the risk this
  guards against is smaller than it looks (optional).
- **The narrow-≤-wide down-range ordering** between `SIGHT_WIDE_RANGE_SIGMA_SCALE` and
  `SIGHT_NARROW_RANGE_SIGMA_SCALE` is currently defended only by a unit test reading live
  constants, not by any runtime or import-time check. Given both are hand-tunable
  judgement constants meant to move from flying, this is acceptable as-is; a one-line
  comment on each constant noting the sibling it must stay below would make the
  relationship discoverable to whoever retunes it later without having to find the test
  (optional).

### Verdict
APPROVED

### Review Confidence
Full read — plan, direction document, implementation summary, and every file in the
diff read in full; the three highest-risk claims (carry-forward correctness, sigma
no-change, group-ranged-once) verified by mutation or structural inspection rather than
by trusting the implementer's account; all claimed numbers (sourced figures, test counts,
docstring arithmetic) independently recomputed or grepped against source, not accepted on
the author's word.

---

## Pass 2 — Stage 2, the §7 directional cone, the optic-aware range cap

### Review Summary

Reviewed `BL-B64` Stage 2 (`SIGHTING` phase, the 1 s hands-busy suppression, the sight's
own manoeuvre rate limit) and the §7/§12a cone-plus-cap pair, on `feature/9k113-sight` at
`67addd732015acfdcb0f268897c7ad0235ba61bf` (two commits, `5e5f823` then `67addd7`).

**Address verification.** Created the worktree directly from the branch
(`git worktree add /tmp/review-9k113-sight feature/9k113-sight`) rather than from
`origin/HEAD`, so `git rev-parse HEAD` already equalled the named tip sha exactly — no
merge needed, tree clean. All five input documents read in full (plan §10–18, the
direction document in full, `performance-cone-gate.md`, `implementation.md`, this file's
first pass, `BL-B64.md`). `body-layer/.venv` rebuilt with the pinned versions inside
`body-layer/`; world-model present as a sibling checkout at the same relative path the
`pyproject.toml` seam expects.

**Verification — matches every claimed number exactly.**
- `ruff format --check .`: fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md` (same two lines the first pass predicted).
- `ruff check .`: all checks passed.
- `mypy src`: success, 0 errors, 59 source files.
- `pytest -q`: **1929 passed, 4 xfailed** (baseline 1883/4, net +46), matching the
  implementer's own count exactly.
- Test-diff claim ("zero removed, zero modified"): `git diff 118d4dc..67addd7 -- '*/tests/*'`
  shows 797 insertions / **2** deletions across six files — both deletions are import-line
  reformatting (splitting a two-name import across lines to add the new optic names), not a
  removed or altered assertion. The zero-modified-tests claim holds.

**Mutation-tested both highest-risk claims, not just read.**
1. *"The cone and cap are a pair; either alone is a no-op."* Patched
   `filter_player_bubble`'s cone branch to always `continue` (cone effectively removed) —
   `test_sight_cone_admits_a_candidate_beyond_the_player_bubble` failed immediately
   (`assert 0 == 1`). Restored. Separately patched `check_visibility`'s `optic_range_cap_m`
   to always resolve to `NAKED_EYE_RANGE_CAP_M` (cap effectively removed) — the same test
   failed the same way, through the full `poll()` pipeline. Restored; tree clean both
   times. Both halves of "neither works alone" are real and mutation-caught by the
   existing suite, not merely asserted.
2. *"The cone is pointed at ACTUAL aim, never desired, and an OBSERV-off tick pays
   nothing."* Read `association.SightCone`'s construction site in
   `logger._apply_active_gaze` directly: `sight_cone` is built only when
   `optic.regard_azimuth_half_deg is not None` (true only for the two sight optics) *and*
   `updated_state.actual_aim_azimuth_deg is not None` (true only once a look is actually
   committed), and its `azimuth_deg` is read from `updated_state.actual_aim_azimuth_deg` —
   the same field `advance_sight_aim`'s result was just written into, never from
   `decision.look_azimuth_deg` (belief's desired aim). `filter_player_bubble`'s own first
   line inside the branch is `if sight_cone is None or candidate_range_m > sight_cone.depth_m:
   continue` — an OBSERV-off tick (where `sight_cone` is always `None`, by construction, per
   the first check) pays exactly one extra `is None` test per candidate that already failed
   the radius check, confirmed by reading the branch rather than taking the docstring's word
   for it.

**Gate order in `check_visibility` is unchanged.** Read the function in full: the six-gate
sequence (gaze, cockpit mask, optic FOV, angular-radius range/size, terrain LOS, forest) is
untouched; the only edit is `tier_ranges`/`check_visibility`'s shared range-cap resolution
line (`optic.range_cap_m if optic.range_cap_m is not None else NAKED_EYE_RANGE_CAP_M`),
in the same position the old bare constant occupied. Gate 4 (terrain LOS)'s fail-closed
contract from `BL-11` Stage 4 is untouched.

**The `_decide_sighting`/`lower_binoculars` restructuring was read end-to-end, not
sampled.** Both of implementation.md's "Notable Discoveries" (the naive
`phase is home_phase` no-op check silently failing to drop an in-progress sight look; the
first draft of `_decide_sighting` re-running `is_worth_a_look` every poll and ending every
look after one poll) are real, well-described, and each now carries a test
(`test_lowering_while_sighting_is_home_drops_an_active_look`,
`test_the_look_continues_on_the_next_poll`) that fails if the fix is reverted — spot-checked
by reverting each fix in turn and confirming the named test catches it.

**OBSERV-off bit-identical claim: the zero-modified/zero-removed pre-existing-test result
is real evidence, and it is also not sufficient — see the Required Fix below, which is
exactly the kind of path a byte-identical-on-existing-tests claim cannot see.** Every new
branch in `decide()` (hands-busy check, `SIGHTING` dispatch, the `SCANNING`-at-home
split on `home_phase`) is reached only when `state.home_phase is OpticPhase.SIGHTING` or
`state.hands_busy_until_sim` is set, neither of which any pre-existing caller produces —
that part of the claim is correct and verified by the full pre-existing suite passing with
zero edits. But "OBSERV-off is bit-identical" is a claim about the *old* paths being
unchanged; it says nothing about whether the *new* path (`SIGHTING`) correctly returns to
the old one when `home_phase` changes back. It does not, in one case — found by direct
`decide()` mutation testing below, not by reading.

### Required Fixes

- **Commanding "Observ off" while Petrovich is actively in the `SIGHTING` phase does not
  make him stop using the sight — it can take up to `SIGHT_MAX_DWELL_S` (default 30 s,
  tunable 5–120 s) for the phase to actually leave `SIGHTING`, during which the sight
  optic, the look-in-progress (if one was active and not otherwise dropped), and the §7
  cone all keep operating exactly as before the command. The pilot hears "Observ off"
  immediately (`crew_console`'s readback is unconditional) while the system silently keeps
  the sight live underneath that statement.

  **Mechanism.** `logger.py`'s poll loop drains a pilot's "Observ off" into
  `OpticState.home_phase` directly (`replace(runner.optic_state, home_phase=OpticPhase.SCANNING, ...)`),
  the same one-poll-lagged signal shape `attack_run_transition` uses. But `decide()`'s
  dispatch for `state.phase is OpticPhase.SIGHTING` is unconditional:

  ```python
  if state.phase is OpticPhase.SIGHTING:
      return _decide_sighting(state, now_sim, targets, sight_steady)
  ```

  Nothing here, or inside `_decide_sighting`, ever reads `state.home_phase`. The *only*
  ways `_decide_sighting` hands back to home are its own two internal stop conditions —
  the scheduled dwell boundary (`SIGHT_MAX_DWELL_S`, via `_start_glance_away`) and a
  violated `sight_steady` (via `_force_observ_off`). A pilot command that changes
  `home_phase` out from under a phase that is still `SIGHTING` is invisible to both.
  This directly falsifies `_decide_sighting`'s own docstring claim — *"only ever called
  from `decide` while `state.phase is OpticPhase.SIGHTING`, which is only reachable while
  `state.home_phase is OpticPhase.SIGHTING` too"* — the two fields are assumed to move
  together but nothing enforces that once `phase` has already entered `SIGHTING`.

  **Reproduced directly** (not from reading alone): built an `OpticState` with
  `phase=SIGHTING`, `home_phase=SIGHTING`, an active look, then set
  `home_phase=OpticPhase.SCANNING` the way the poll loop does, and called `decide()` in a
  loop for eight simulated seconds. `state.phase` stayed `OpticPhase.SIGHTING` throughout
  (the active look was cleared, `is_worth_a_look`/`choose_look` kept returning `None`
  against an empty target list, so it settled on `SIGHT_WIDE_OPTIC` idle — but the phase
  itself never left `SIGHTING`). It only leaves at the next `SIGHT_MAX_DWELL_S` boundary
  or an unsteady poll — neither of which the pilot's command causes.

  **Contrast with the one path that does work today.** `sight_steady=False` *is* checked
  inside `_decide_sighting` every poll (it is passed as one of `decide()`'s own
  parameters, recomputed fresh from attitude history each call) and correctly forces an
  immediate `_force_observ_off`, tested directly
  (`TestManoeuvreForcesObservOff::test_an_unsteady_poll_while_sighting_turns_observ_off_entirely`).
  The asymmetry is the wiring, not the concept: manoeuvre-triggered exit is a `decide()`
  input re-evaluated every poll; command-triggered exit is a mutation to a field `decide()`
  never reads while `phase is SIGHTING`.

  **Not covered by any existing test.** `TestObservOn`'s two tests
  (`test_setting_home_phase_mid_glassing_does_not_interrupt_the_look`,
  `test_the_look_ending_hands_back_to_sighting_not_scanning`) only exercise `home_phase`
  moving **into** `SIGHTING` while `phase` is `GLASSING`/`SCANNING` — the direction this
  entry's own design intends to tolerate (don't abandon a bounded look mid-sweep).
  `TestLowerBinocularsPreservesObserv`'s four cases all construct `state` with `phase`
  and `home_phase` already *agreeing* (both `SIGHTING`, or `SCANNING`-with-`home_phase`-
  `SIGHTING` for the glance-away case) — none of them starts from the diverged state
  (`phase is SIGHTING`, `home_phase is SCANNING`) that the real "Observ off" command
  actually produces one poll after it lands. Grepped `test_logger.py` for `observ` and
  `SIGHTING` — no hit; the full poll-loop path for turning OBSERV off mid-sight is
  untested end to end.

  **Fix shape** (not prescribing the exact code, since this is the Implementer's call,
  but the gap is precisely located): `decide()`'s `state.phase is OpticPhase.SIGHTING`
  branch needs the same kind of check the `SCANNING`-at-home branch already has in the
  other direction (`if state.home_phase is OpticPhase.SIGHTING:` for the glance-away) —
  something like `if state.home_phase is not OpticPhase.SIGHTING: return _back_to_home(state, now_sim)`
  before dispatching to `_decide_sighting`, so a command-driven `home_phase` change takes
  effect at the very next poll (after `hands_busy_until_sim` elapses) rather than waiting
  for `_decide_sighting`'s own internal stop conditions. Whatever shape is chosen, it
  needs a test built from the diverged state directly (`phase=SIGHTING`,
  `home_phase=SCANNING`), both idle and mid-look, plus one through the full `logger.py`
  poll loop exercising the actual command→drain→decide sequence — the gap this pass
  found was invisible at the unit level precisely because every existing test starts from
  an *agreeing* `phase`/`home_phase` pair.

### Optional Refinements

- **The `SIGHT_STEADY_RATE_LIMIT_DEG_S` lo-bound coupling (`lo=12.0`, pinning it to
  `STEADY_RATE_LIMIT_DEG_S`) is enforced only one-way.** `STEADY_RATE_LIMIT_DEG_S` itself
  is a bare `Final[float] = 12.0`, not a tunable — so the `lo` bound protects against a
  retune of the *sight's* constant going too low, but nothing protects the reverse: if
  `STEADY_RATE_LIMIT_DEG_S` were ever raised above 12.0 in a future code change, the
  `lo=12.0` bound on the sight's tunable would silently stop being the right floor. Low
  priority — any such change is a source edit to a `Final` constant, which a future
  reviewer would see in the same diff; the live-value test
  (`TestSightSteadyRateLimitIsHigherThanBinoculars`) already catches the case that
  actually matters (the two values disagreeing at runtime), same pattern Stage 1's
  down-range-sigma ordering uses (optional).
- **No autonomous wide/narrow switching within one look (design choice 2 in the task
  brief).** Judged against the user's own worked example (*"I use narrow to see more
  detail and wide to see more surrounding"*): this is a real simplification against that
  description, but it is the *same* simplification `GLASSING`/binoculars already made —
  committing to a magnified look already means losing the wide view until that look ends,
  and nobody has flagged that as a problem for binoculars. Narrow-while-looking,
  wide-while-idle is consistent with the established pattern rather than a new gap. Worth
  revisiting after the Stage 3 acceptance sortie if the pilot notices losing situational
  awareness mid-look, as the implementer already flagged, but not a defect against this
  entry's own scope (optional, matches the implementer's own characterisation).
- **The one-poll latency in `_back_to_home` before `SIGHTING` can pick a target (design
  choice 3)** is small (~1 s at today's 1 Hz), explicitly documented, and consistent with
  other scan-boundary latencies already in this module. Not a defect; worth knowing before
  the sortie, as the implementer already flagged (optional).
- **Group-ranged-once and the narrow-≤-wide down-range ordering**, both carried over as
  optional from the first pass, stand unchanged — nothing in this pass touches either
  mechanism.

### Verdict
NEEDS REVISION

One required fix: the `SIGHTING`-phase dispatch in `decide()` must notice when
`state.home_phase` no longer agrees with `state.phase`, so a pilot's "Observ off" takes
effect at the next poll rather than waiting for the sight's own internal dwell/manoeuvre
stop conditions. This is a correctness defect with a pilot-visible consequence (a
readback that says "Observ off" while the sight keeps running), located precisely, and
small to fix — re-enters the Implementer → Reviewer loop per `AGENTS.md`'s change-request
procedure, not a full re-plan.

### Review Confidence
Full read — plan §10–18, the direction document, `performance-cone-gate.md`,
`implementation.md`, and every file in the diff read in full. The two highest-risk claims
named in the task brief (cone+cap pairing, cone pointed at actual aim with zero
OBSERV-off cost) were mutation-tested or verified against the exact construction/branch
code, not accepted on the implementer's account. The required fix was found by direct
`decide()` reproduction (building the diverged state and stepping it), not by reading the
diff — the diff and every existing test agree with each other precisely because every one
of them keeps `phase`/`home_phase` in agreement; the gap only shows up once they are
pushed out of agreement the way the real command path does. No part of this review was
spot-checked due to time-boxing; the only thing not exercised live is the real DCS poll
loop end to end, which is the acceptance sortie's job, not this review's.

---

## Pass 3 — review of the fix for Pass 2's required finding (commit `1a3c6e8`)

Scope: this is a review of the single commit `1a3c6e8338ab62a86d88e355b4aab76019f4aa2a`,
not a re-review of the whole Stage 2 entry. Built on `feature/9k113-sight` directly at the
named tip (HEAD matched exactly, no merge needed).

### What was checked

- **Reran the Pass 2 reproduction myself, not from the report.** Built the diverged state
  (`phase=SIGHTING`, `home_phase=SCANNING`, an active look) and stepped `decide()` for 8
  simulated seconds against the pre-fix code (`git show bd0fae5:…/optic_policy.py` swapped
  into the worktree in place, run, then restored — `git status --porcelain` empty
  afterwards): `phase` stays `SIGHTING`/`sight_wide` for all 8 polls, exactly the reported
  defect. Against the fixed code: `phase` is `SCANNING`/`unaided` from the very first
  poll. Confirmed by execution, not read off the report.
- **The look-in-progress drop.** Read `_back_to_home` directly (`optic_policy.py:912-953`):
  `look_contact_id=None`, `look_started_sim=None`, and `pending_attempted_at_range_m={}`
  are all named in the `replace(...)`, so an in-progress look is discarded, not committed —
  matches the claim. Checked this against `lower_binoculars`'s own "already home → no-op"
  branch (`optic_policy.py:1032-1034`, `if state.phase is state.home_phase: ... return
  state`) for the earlier bug's shape: the new `decide()` check only ever calls
  `_back_to_home` when `state.home_phase is not state.phase` (the opposite condition), and
  it passes `state.home_phase` through unmodified rather than hardcoding a destination, so
  the "already home" no-op case cannot be reached from this new call site. Not the same bug
  recurring from the other direction.
- **The cone stops in the same tick.** Read `_apply_active_gaze` (`logger.py:877-1009`)
  directly rather than taking the implementer's account: `_back_to_home`'s
  `OpticDecision(optic=UNAIDED_OPTIC)` carries no `look_azimuth_deg`, so the first `if`
  branch (desired-aim convergence) is skipped and the `elif` (`updated_state.
  actual_aim_azimuth_deg is not None`) fires, clearing `actual_aim_azimuth_deg` to `None`
  on the same call; `sight_cone` then requires `updated_state.actual_aim_azimuth_deg is not
  None`, which is now false, so `sight_cone` is `None` from that poll with no one-poll gap.
  During the 1 s hands-busy window specifically, `decide()`'s hands-busy branch
  (`optic_policy.py:1273`) returns before the `SIGHTING` dispatch is even reached, with
  `OpticDecision(optic=UNAIDED_OPTIC, suppressed=True)` and no `look_azimuth_deg` either —
  same `elif` clears the cone, and `suppressed_until_sim` additionally blanks the naked-eye
  source's observations for that window. Chain holds in both phases of the transition.
- **The dispatch-branch table.** Independently re-derived rather than just checked against
  the implementer's table: `hands_busy_until_sim` is read unconditionally at the very top
  of `decide()` (`optic_policy.py:1273`), before any phase branch, so it cannot have the
  per-branch asymmetry this defect shape depends on — it already applies to every phase by
  construction. `SEARCHING`/`GLASSING` not reading `home_phase` is pinned by
  `TestObservOn::test_setting_home_phase_mid_glassing_does_not_interrupt_the_look`
  (`test_optic_policy.py:1423`), which does set `home_phase=SIGHTING` mid-`GLASSING` and
  asserts the look is *not* interrupted — read the test body, not just its name, and it
  does construct the diverged state and assert the asymmetric (non-interrupting) outcome.
  Agree with the implementer's judgment: entering OBSERV mid-activity is "start when
  convenient" (the same phase-boundary rule the binocular cycle already enforces for a
  *home*-side scan), leaving it is "stop now" — §6 of the direction document makes both the
  pilot's call, and nothing in the direction document carves out a "let the look finish"
  exception for leaving OBSERV the way it implicitly does for entering it.
- **Is there a seventh?** Checked `hands_busy_until_sim`, `actual_aim_*`,
  `suppressed_until_sim`, `observ_transition` against the same shape. `hands_busy_until_sim`
  is global as above. `actual_aim_*`/`suppressed_until_sim` are recomputed unconditionally
  every poll in `_apply_active_gaze` from the current decision, never read back into a
  phase-dispatch branch, so they cannot go stale the way `home_phase` did.
  `observ_transition` is drained entirely inside `logger.py`'s poll loop into `home_phase`/
  `hands_busy_until_sim` and never read directly by `decide()` — it is the trigger, not a
  second instance of the carried state. No seventh found.
- **Mutation test.** Changed the new condition to `if False and state.home_phase is not
  OpticPhase.SIGHTING:` and reran the new tests: 4 of 5 fail as expected
  (`test_observ_off_while_idle_sighting_exits_on_the_next_poll`,
  `test_observ_off_mid_look_drops_the_look_on_the_next_poll`,
  `test_observ_off_never_reaches_sight_max_dwell_s`,
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop`); the fifth
  (`test_observ_still_on_through_sighting_is_unaffected`, the counter-test for the
  agreeing-state case) correctly still passes, since that case never reaches the mutated
  branch. Reverted; `git status --porcelain` empty afterwards. Did not separately mutate
  the docstring — a docstring change cannot affect test outcomes by construction, and
  stating that is sufficient without re-running the suite to prove a tautology.

### Verification

```
cd body-layer && .venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy src && .venv/bin/pytest -q
```

- `ruff format --check .`: 1 file would be reformatted — the pre-existing, out-of-scope
  `research/2026-10-05-security-audit.md` (code-fence reformatting unrelated to this
  change). Matches the claim.
- `ruff check .`: all checks passed.
- `mypy src`: success, 0 errors, 59 source files.
- `pytest -q`: **1934 passed, 4 xfailed.** Matches the claimed count exactly.
- Zero-removed/zero-modified test claim verified directly: `git diff bd0fae5..1a3c6e8 --
  'body-layer/tests/*'` has no `-` lines outside diff headers — the test diff is purely
  additive.

### Required Fixes

None.

### Optional Refinements

None beyond what Pass 2 already carried forward (group-ranged-once, narrow-≤-wide
ordering) — unchanged by this commit, not re-litigated here.

### Verdict
APPROVED

The fix is correctly scoped (one dispatch-site check, reusing the existing interruption
path rather than inventing a new one), the reproduction confirms the defect is gone, the
look-drop and cone-stop claims both hold on direct inspection of the code they depend on,
the dispatch-branch asymmetry is intentional and correctly pinned by existing tests, no
sibling field has the same exposure, and the mutation test confirms the new tests actually
exercise the fix rather than merely existing. Proceeds to Performance Reviewer and
Security, then DoD.

### Review Confidence
Full read. The fix diff, both doc updates, and all 5 new tests were read in full; the
reproduction was rerun from the actual pre-fix and post-fix source (not from the report)
by swapping file contents in place inside the worktree and restoring; the cone/suppression
chain was traced through `_apply_active_gaze`'s actual branches rather than taken from the
implementation note; the dispatch table was independently re-derived against the cited
tests' bodies, not just their names; and the required fix was confirmed removable by
mutation. Nothing in this pass was spot-checked or time-boxed.

---

## Pass 6 — review of the two field-of-regard security fixes (`aac1828`, `ccda29d`)

Reviewed `feature/9k113-sight` at `ccda29d2bb41b2b4ff62612e93cff87753e23c81` (branch tip matched
the dispatch brief's named sha exactly; worktree checked out directly from the branch, no
fast-forward needed). Scope: the two commits only — `aac1828` (enforce the field of regard at
look selection, the security deep analysis's required fix) and `ccda29d` (close the residual
leak in `look_sweep` the implementer found while fixing it) — not a re-review of the whole
feature, which Pass 1-3 above and `security.md` already cover.

### What was verified, and how (not read-only)

- **Reproduced both leaks from source, not from the reports.** `git show <parent-sha>:<path>`
  into scratch files, swapped into the worktree in place, ran the real functions, restored to
  HEAD, diffed to confirm exact restoration:
  - At `f3668e8` (pre-`aac1828`): a target at 85° azimuth is selected and committed —
    `decision.optic=sight_narrow`, `look_azimuth_deg=85.0` — 25° past `SIGHT_WIDE_OPTIC`'s 60°
    limit. Matches the security report's own reproduction exactly.
  - At `aac1828` (pre-`ccda29d`, i.e. fix 1 only): a target at 55° (5° inside the 60° limit),
    default 15° bearing uncertainty, driven through the real `decide()` for 30 simulated polls —
    `look_azimuth_deg` reaches 67.0°, matching the implementer's own reported reproduction number
    exactly.
  - At `ccda29d` (HEAD, both fixes): same two scenarios re-run — the 85° target is now rejected
    outright (`look_azimuth_deg: None`, optic rests on `sight_wide` idle); the 55°-target sweep
    over the same 30 polls now tops out at exactly 55.0°, never exceeding 60°. Both leaks closed.
- **Mutation-tested both fixes independently**, each by editing the real source (not a stub) and
  re-running the relevant tests, then restoring to a verified-clean `HEAD` diff:
  - Removing the `within_field_of_regard(...)` clause from `_decide_sighting`'s `worth_looking`
    filter (fix 1's guard) makes 4 of the 9 `TestFieldOfRegardEnforcement` tests fail — not with
    a wrong-value assertion but with `IndexError: list index out of range` at `sweep[0]`, because
    the now-unrejected 85° target is chosen and every step the sweep generates around it is
    filtered out by fix 2's own `look_sweep` guard, which is still active. This is itself informal
    confirmation that the two fixes are not redundant: each is independently load-bearing, and
    losing either changes the failure mode, not just the pass/fail count.
  - Removing `regard_optic=SIGHT_WIDE_OPTIC` from the one `look_sweep` call site in
    `_decide_sighting` (fix 2's wiring) reproduces the exact reported defect: 1 test fails with
    `assert 67.0 <= 60.0`, byte-for-byte the number both the security report's "Notable
    Discoveries" and the implementation note cite.
- **Grepped independently for every reader of the aim fields outside `optic_policy.py`/
  `logger.py`** (`look_azimuth_deg`, `look_elevation_deg`, `search_pattern_steps`,
  `look_envelope_azimuth_deg`, `look_envelope_half_width_deg`), across all of `src/` — empty
  result, confirming the widened audit's load-bearing claim rather than taking it on the
  implementer's word.
- **Confirmed the "continuing look" path is covered too, not just asserted.** `state.
  search_pattern_steps[index]` (the mid-look read path, line ~1199) reads from `tuple(sweep)`,
  which is the same already-filtered list the "new look" path's `sweep[0]` reads from — one
  filter, two consumers, as claimed. Read directly, not inferred from the commit message.
- **Checked the "elevation held constant" claim against the actual loop body**, not just the
  docstring: `look_sweep`'s step-construction line is
  `(centre_azimuth_deg + offset, centre_elevation_deg)` for every offset — `centre_elevation_deg`
  is never varied. The claim holds, and the filter does still call `within_field_of_regard` with
  each step's (unvarying) elevation, so a future change that *did* vary it would be caught rather
  than silently exempted, exactly as stated.
- **Stress-tested the "centre step always survives" claim and found it imprecisely stated** (see
  Minor Finding below) but the safety property it is used to support — the sweep is never
  returned empty for a validated centre — holds under direct test across a battery of
  near-boundary centres (59.0°/59.9°/59.99°/60.0°) and uncertainty widths (5°-50°): every case
  retained at least one step, never fewer, confirming truncation never degenerates into "selected
  but never looked at."
- **Checked truncation's behavioural cost directly** (the question the dispatch brief raised): a
  target only fractions of a degree inside the boundary, across widths up to 50°, always keeps at
  least half its originally-generated steps (worst case observed: 1 of 2), and the surviving steps
  are always clustered near the target's own believed position, not scattered. A target can end up
  searched more narrowly than an in-the-clear target would be, but never ends up "selected but
  effectively unsearched" — there is always at least one step near its own position in every case
  tried.
- **Confirmed `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`'s `regard_*` fields are in fact identical**
  (60.0 / 20.0 / −15.0 on both), by reading both dataclass literals directly rather than trusting
  the docstring's claim that they are.
- **Confirmed the GLASSING/SEARCHING `look_sweep` call site (line ~1538) never passes
  `regard_optic`** — read directly; it is the pre-existing binocular sweep, untouched by either
  commit, and the no-op claim is backed by a real `decide()`-level test
  (`test_binocular_cycle_is_unaffected_by_field_of_regard`) that drives an 85° target through the
  actual `SCANNING`→`GLASSING` path, not a unit test on `look_sweep` alone.
- **Confirmed no new `tuning.*` constant was introduced by either commit** (`config/defaults.toml`
  untouched in the diff) — `within_field_of_regard` and `regard_optic` are a predicate and a
  parameter, not numeric constants, so the X-T26 tuning-mechanism check does not apply here; the
  pre-existing four sight-timing constants this feature already declared are unaffected.
- **Confirmed zero removed/modified tests and zero removed/modified `assert`/`def test` lines**
  across both commits' test-file diffs — the only removed line in either diff is one superseded
  docstring sentence in `test_optics.py` noting the sight optics are "not tested here," which this
  change makes false and correctly deletes.
- **Ran the verification commands myself** rather than taking the implementer's reported numbers:
  `ruff format --check .` fails only on the pre-existing out-of-scope
  `research/2026-10-05-security-audit.md`; `ruff check .` and `mypy --strict src` both clean;
  `pytest -q` — **1953 passed, 4 xfailed**, matching the claim exactly.

### Minor Finding (optional)

- **`look_sweep`'s "the centre step always survives" docstring claim is not literally true when
  the generated step count is even.** `_step_centres_deg` only places an exact `0.0` offset when
  `steps_across` (`ceil(2·half_width/fov_full_width)`) is odd; for an even count (e.g.
  `bearing_uncertainty_deg=12.0` with the sight's 6° FOV gives `steps_across=4`, offsets
  `[-9, -3, 3, 9]` — no zero), the sweep never generates a step at the chosen target's own exact
  azimuth at all, with or without the field-of-regard filter. This is pre-existing `look_sweep`
  geometry, not introduced by either commit, and it does not weaken the actual safety property:
  by construction the offsets are symmetric about zero, so whichever of any symmetric pair moves
  *toward* zero from a validated centre always stays within whatever bound the centre already
  satisfies — confirmed directly by stress-testing a battery of near-boundary/even-step-count
  cases (see above), all non-empty. **Optional**: tighten the docstring's claim from "the step at
  offset zero" to "a step at or arbitrarily close to the validated centre," since the current
  wording asserts something about `look_sweep`'s output that is not always true, even though the
  conclusion drawn from it (never empty) is.

### Verdict
**APPROVED.** Both required findings from `plans/9k113-sight/security.md` are closed, the residual
leak the implementer found while fixing the first is independently reproduced and confirmed closed
from source (not from the report), both fixes are confirmed load-bearing by mutation, the widened
audit's "nothing else reads these fields" claim is independently confirmed by grep, reject-not-clamp
and truncate-not-narrow are both honoured with no clamping anywhere including error paths, the
naked-eye/binocular no-op is confirmed by a real `decide()`-level test rather than by construction
alone, and the one imprecision found (the "centre step" docstring claim) does not affect correctness
and is optional. Proceeds to DoD — performance and security have both already passed, and security's
one required finding is what these two commits answer.

### Review Confidence
Full read, including the implementer's own two implementation-note passes and the preceding
security report. Both pre-fix leaks were reproduced directly from source (not read off the
reports), both fixes were independently mutation-tested, the "nothing else reads these fields"
audit was independently re-run via grep rather than trusted, and the truncation behavioural-cost
question was stress-tested across a battery of synthetic cases rather than argued analytically
alone. Nothing in this pass was spot-checked or time-boxed.
