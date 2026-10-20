## Security Review: 9k113-narrow-search

Reviewed at tip `5e9178406c65d13b90097fd527851f4f300775ad` (`feature/9k113-narrow-search`), detached.
Two parts in one pass, run together because the plan-review step was skipped after Architect:
a retroactive Mode 1 plan review, and a Mode 2 deep analysis of the whole batch
(`git diff 78aebc04..5e917840 -- body-layer/`). Inputs: `plans/9k113-narrow-search/{plan,
implementation,review}.md`, `docs/acceptance/2026-10-20-sortie-feedback.md` F4/F5, and this
project's own prior finding on this sight, `.claude/agent-memory/security/
project_bl_b64_field_of_regard_unenforced.md`.

---

## Part 1 — Retroactive Plan Review (Mode 1)

### Dependencies Checked

No new dependency. `git diff 78aebc04..5e917840 -- '*/pyproject.toml'` is empty, and the plan's
only "dependency" mention (`plan.md:256`, "no DCS/ownship dependency") is pure geometry prose, not
a package claim. CVE search is a no-op.

### Design Findings

- **The plan's design intent for no-omniscience and field-of-regard is correct and explicit.**
  Stage 1 reuses `within_field_of_regard` (already enforced at look-target selection, the BL-B64
  security fix) rather than inventing a second mechanism; Stage 2/3's geometry
  (`_split_sector_by_regard`, `max_half_width_deg=regard`) is designed to keep the idle search's
  *azimuth* inside the sight's own ±60° by construction. The "Co-moving Fields" table and the
  "Decisions Requiring User Input" section show real design discipline, not an afterthought.
  — low risk, no action.
- **Design gap, found retroactively: the plan designs regard enforcement for azimuth only, never
  raises elevation as a question for the new active search sweeps.** F5 (the defect this plan
  closes) was itself reported and reasoned about purely in azimuth terms ("-90° ±15°... limit is
  ±60°"), and every regard-related sentence in the plan (Stage 1's fix shape, Stage 2's split
  geometry, the Risks section) follows that framing through to a design that only ever reasons
  about the azimuth bound. `search_pattern`'s own docstring addresses the *sky* side of elevation
  ("do not scan at sky is a property of the geometry... never a clamp bolted on afterwards") but
  the plan never asks the symmetric question for the *down* side against the sight's own
  `regard_elevation_down_deg=-15.0` — a bound that, unlike the sky side, is not a free consequence
  of "range is the vertical axis" geometry. This is what let the Mode 2 finding below land
  unflagged through implementation and two review passes. — see Part 2, Required Fix.
- **`search_pattern`'s field-of-regard cap is azimuth-only `(max_half_width_deg)`; the plan never
  asks whether the same function, now driving a *regard-bound* optic for the first time, needs an
  elevation cap too.** `search_pattern` predates this plan and was written for `BINOCULAR_OPTIC`,
  which has no field-of-regard in elevation at all (`regard_elevation_*_deg` both `None`) — so the
  function's own silence on elevation bounds was a true no-op for every pre-existing caller. Stage 3
  is this function's first caller for an optic (`SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`) whose
  elevation *is* bounded, and the plan does not carry that distinction into the design.

### Verdict
**APPROVED**, with the gap above noted rather than blocking retroactively — the code is already
built and reviewed twice; the gap converts into a Mode 2 Required Fix below rather than being
re-litigated as a plan rejection after the fact. The plan's overall shape (reuse
`within_field_of_regard`, reuse `look_sweep`'s "reject, not clamp" precedent, keep azimuth
provably in-regard by construction) is sound and is exactly what the Mode 2 fix extends to
elevation — this is a gap in the plan's own analysis, not in its architecture.

---

## Part 2 — Deep Analysis (Mode 2)

### Dependency Status
No dependency change. Verified via `git diff 78aebc04..5e917840 -- '*/pyproject.toml'` (empty).

### No-omniscience invariant — checked directly, holds

Traced every input to the new idle-search-cycle and candidate-admission code:

- `sight_can_still_improve`/`sight_look_optic` (new, `optic_policy.py`) read only
  `target.object_type`/`target.range_m`/`target.current_level` — fields of `LookTarget`, built in
  `logger._look_targets` from `ContactStore`'s **believed** class (`contact.last_class_raw`,
  `contact.classification.level`), never ground truth. `_look_targets`'s own docstring makes the
  same claim explicitly ("uses the contact's believed type, not ground truth... the honest model").
- The idle search cycle's aim (`_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`,
  `_commanded_or_default_sector`) is driven only by `scan_plan.commanded_sector` (player-commanded)
  and `ownship.heading_true_deg`/`ownship.alt_agl_m` (ownship's own state) — no target or world
  data enters this path at all. Confirmed by reading every parameter these functions take; none
  references a `WorldObjectCandidate`, a DCS object id, or anything from `Observation.
  derived_world_position`.
- `within_field_of_regard` at the candidate filter (`optic_policy.py:1873`) still gates admission
  on `target.azimuth_deg`/`target.elevation_deg` — belief's own bearing estimate, unchanged
  mechanism, unchanged invariant.

No path found where ground truth or an unseen unit's true position drives the search pattern, the
aim, or the "worth a look" gate. This part of the task's brief is clean.

### Field-of-regard bound (±60°/+20°/−15°) — **violated on one path, confirmed by direct
calculation, not only by reading**

**Required Fix.** The idle search cycle's three in-regard legs (`wide`, `narrow_near`,
`narrow_far`, all granting `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`) commit an elevation that is
never checked against the sight's own `regard_elevation_down_deg=-15.0`, and is reachable past
that bound at realistic cruise/orbit altitudes — not an edge case.

**Where.** `logger._sight_in_regard_sweep` builds its steps by calling
`belief.optic_policy.search_pattern`, whose elevation is derived purely from range/altitude
geometry (`atan2(altitude_agl_m, range_m)`, always ≤ 0°) with **no clamp against
`regard_elevation_down_deg`/`regard_elevation_up_deg` at all** — only `sector_half_width_deg` is
capped (`max_half_width_deg=regard`, azimuth only). Contrast with `look_sweep` (used once a target
is actually chosen), which explicitly filters its generated steps through `within_field_of_regard`
(`optic_policy.py:825`, the `BL-B64` security follow-up) — the one function in this module that
already does what `search_pattern`'s new caller needs and does not get.

**Confirmed by calculation**, using this branch's own tuned constants
(`SIGHT_SEARCH_NEAR_M=2333.0`, the near edge shared by the `wide` and `narrow_near` legs):

| ownship AGL | near-edge depression (wide/narrow_near leg) | within −15° down-regard? |
|---|---|---|
| 120 m (this feature's own test default, `test_logger.py:1113`) | 2.9° | yes |
| 500 m | 12.1° | yes |
| **625 m** | **15.0°** | **boundary** |
| 1000 m | 23.2° | **no — 8.2° past the limit** |
| 1500 m | 32.7° | **no — 17.7° past the limit** |

(`math.degrees(math.atan2(alt, 2333.0))`, i.e. exactly `search_pattern`'s own formula.) A Mi-24P
at an ordinary transit/orbit altitude above ~625 m AGL — not NOE, not a stress case, an entirely
routine cruise/holding altitude — commands the sight to an elevation it cannot mechanically reach
the moment the idle search cycle's near edge is stepped.

**Why this matters beyond "a wrong number": it becomes the real perception boresight, not a
cosmetic display value.** `decision.look_elevation_deg` flows through `_apply_active_gaze`
unchanged (`advance_sight_aim` is still an identity pass-through, `logger.py:1246`) into
`OpticState.actual_aim_elevation_deg`, then into `ScanPlan.fixed_look_at(elevation_deg=
actual_elevation_deg)`, which becomes `Gaze.center_elevation_deg` — the real
`boresight_elevation_deg` `perception.optics.within_optic_fov` tests candidates against for the
naked-eye/sight detection gate. An elevation past the sight's own physical envelope therefore does
not just mis-point a debug value: it changes which real candidates the detection gate admits, at
an elevation the 9K113 cannot physically reach — the same "perceive from a direction the mount
cannot point" shape `.claude/agent-memory/security/project_bl_b64_field_of_regard_unenforced.md`
already names as this project's prior finding on this exact optic, reintroduced on a path that
finding's own fix never touched. (One check: the player-bubble `SightCone` exemption
(`association.py`) is azimuth/depth-only, no elevation field, so that specific mechanism is not
further widened by this — the live-detection-gate path above is the one that is.)

**Why three passes (implementer, reviewer, re-review) did not catch it — the same shape as the
BL-B64 lesson, not a new failure mode.** Both tests that assert the `within_field_of_regard`
invariant on a `SIGHTING`-idle decision
(`test_idle_sighting_rests_with_an_aim_inside_regard_with_nothing_worth_looking_at` and
`TestIdleAimInvariant::test_idle_rest`, `test_optic_policy.py`) call `decide()`/`decide_optic()`
with **no** `sight_wide_search`/`sight_narrow_near_search`/`sight_narrow_far_search` argument —
all four default to `()`. `_idle_sight_search`'s `first_nonempty_leg` immediately finds every leg
empty and falls through to `_idle_sight_rest`, the trivial "hold last position or `(0.0, 0.0)`"
fallback — which trivially satisfies `within_field_of_regard` regardless of altitude, because it
never calls `search_pattern` at all. The tests that *do* exercise real, altitude-driven sequences
(`TestSearchCycle`, `TestSightInRegardSweep`) check leg ordering and that steps "stay inside their
own sub-spans" — **azimuth** sub-spans, from `_split_sector_by_regard`'s own clamp — never
elevation. The regard-invariant test and the real-geometry test exist side by side and never
overlap on the one case that needed both. (`test_logger.py:1113`'s own fixture altitude, 120 m
AGL, is also comfortably under the ~625 m threshold, so even a test that *did* thread real
sequences through would not have hit this at that altitude.)

**Recommended fix shape** — apply `look_sweep`'s own established "reject, not clamp" pattern to
the one producer that lacks it, rather than inventing a second mechanism:

- Filter `_sight_in_regard_sweep`'s returned steps through `within_field_of_regard(optic, azimuth,
  elevation)` before returning them (dropping out-of-regard steps, not clamping them to the
  boundary — consistent with `within_field_of_regard`'s own docstring and this project's standing
  "reject, not clamp" reasoning, `.claude/agent-memory/implementer/
  feedback_declared_bound_check_at_selection_not_at_consumer.md`). This is the one choke point:
  every caller of `_sight_in_regard_sweep`'s output (`run_once`'s three `sight_*_search=` keywords)
  reads from what it returns, so filtering in the producer protects all of them without a second
  check anywhere else.
- A leg that filters down to zero steps composes safely with the existing cycle-skip logic
  (`_idle_sight_search`'s `first_nonempty_leg` already treats an empty leg as "advance to the
  next one," and `_idle_sight_rest` is the existing full-fallback) — no new state needed.
- **Required test**: drive `_sight_in_regard_sweep`/the full idle cycle with a realistic altitude
  above the ~625 m threshold (e.g. `alt_agl_m=1000.0`) and assert every generated
  `(azimuth, elevation)` step satisfies `within_field_of_regard(SIGHT_WIDE_OPTIC, azimuth,
  elevation)` — the existing `within_field_of_regard` invariant tests must be extended to pass
  real, non-empty `sight_*_search` sequences (not left at the all-default `()` shape that
  currently makes them exercise `_idle_sight_rest` instead of the geometry this fix touches).

### Tunable bounds — reviewed, no new issue

`SIGHT_SEARCH_NEAR_M`/`MID_M`/`FAR_M` are declared via `tuning.real` with `lo`/`hi` and a `#:`
comment each; checked the **rendered** `defaults.toml` directly (not the source comment) — all
three lines are intact, matching the implementer's own note about the earlier backtick-asymmetry
defect not recurring here. The disclosed cross-key coupling (`NEAR < MID < FAR` not enforced by
per-key bounds) is the same shape as `belief.decay`'s existing, accepted coupling and is already
flagged in both the tunable's own comment and the plan's Risks — acceptable as scoped, consistent
with prior reviews on this branch. `_SIGHT_WIDE_SEARCH_FAR_M` (the F4-follow-up commit) is
correctly *not* a tunable — it is a pure function of an already-tunable constant
(`SIGHT_SEARCH_NEAR_M`) and fixed optic calibration, which is exactly the case root `CLAUDE.md`'s
tuning policy carves out from needing its own `tuning.real` declaration.

### Poll loop — no new crash/hang path found

- `_next_search_leg`/`_idle_sight_search`'s `first_nonempty_leg` loop is bounded to
  `len(_SEARCH_LEG_ORDER)` (4) iterations and always terminates (returns `None` on exhaustion,
  handled by `_idle_sight_rest`) — no infinite loop.
- Every `fov_full_width_deg <= 0.0` division guard is present at every new `search_pattern`
  caller (`_sight_in_regard_sweep`, `_sight_out_of_regard_sweep`), matching the existing
  `_search_sweep` guard.
- `_apply_guidance`'s new aim-safety condition (Stage 1's fourth path) was verified by mutation by
  the Reviewer already (reverting it fails `TestIdleAimInvariant::
  test_guidance_override_during_glance_away`) — re-read here, reasoning holds.
- The search-cycle starvation case the Reviewer found (a contact stuck at `presence` forever can
  fully starve the idle search cycle, measured 88% busy / 3% idle over 900s) is real but not a
  crash/hang — it degrades gracefully to "the sight keeps looking," never to an unhandled
  exception or a stalled poll loop. Filed as **`BL-B85`** (not previously tracked — the Reviewer's
  own recommendation to note it was present but had no ID attached; see Backlog Items Filed below).

### Pre-existing finding re-confirmed fixed on this branch, not re-filed

`logger._search_sweep`'s `SCANNING`-at-home caller used to discard the commanded sector's own
centre (architect's own memory note,
`.claude/agent-memory/architect/project_search-pattern-centre-dropping.md`, and the plan's own
Risks section, which recommended filing it separately). **Confirmed fixed on this branch**:
`git diff` shows `_search_sweep` now passes `center_azimuth_deg=center_deg` (Amendment 2, user:
"fix the binocular search sector"). Not filed as a backlog item — the fix is already in the code
under review, so an open item would immediately be stale/duplicate work.

### Backlog Items Filed

- **`BL-B85`** — a contact stuck at `presence` forever can fully starve the sight's idle search
  cycle (Reviewer's own measured, disclosed, non-blocking finding; previously had a risk
  description but no ID). `body-layer/ROADMAP/BL-B85.md`, indexed in
  `body-layer/ROADMAP/body-layer-backlog.md`.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/logger.py`, `_sight_in_regard_sweep` (calls `belief.optic_policy.search_pattern`) | Field-of-regard elevation bound unchecked on a path that grants `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC` | Confirmed reachable at realistic AGL (>~625 m for the shared near edge); becomes the real detection-gate boresight via `_apply_active_gaze` → `Gaze.center_elevation_deg` → `within_optic_fov` | **Required fix** — filter `_sight_in_regard_sweep`'s output through `within_field_of_regard`, same "reject, not clamp" pattern as `look_sweep`; add an altitude-realistic test |
| `body-layer/src/belief/optic_policy.py`, `_decide_sighting`/`_idle_sight_search`/`_apply_guidance` | No-omniscience (belief-only inputs) | Verified clean — every new function's inputs trace to belief/commanded state, never ground truth | None |
| `body-layer/src/belief/optic_policy.py`, tunables | Tuning bounds/coupling disclosure | Declared correctly, rendered `defaults.toml` checked directly, coupling disclosed per existing precedent | None |
| `body-layer/src/logger.py`, idle search cycle (poll loop) | New failure modes | No crash/hang path found; one disclosed starvation risk (non-blocking) | Filed as `BL-B85` |
| `*/pyproject.toml` | Dependency | No change | None |

### Verdict
**NEEDS FIXES**

### Required Fixes
1. **Enforce the sight's own elevation field of regard (`regard_elevation_up_deg`/
   `regard_elevation_down_deg`) on the idle search cycle's generated steps**, not only its
   azimuth — `body-layer/src/logger.py`'s `_sight_in_regard_sweep` (and/or
   `belief.optic_policy.search_pattern` itself, if a shared fix is preferred), filtering through
   `within_field_of_regard` the same way `look_sweep` already does. Required test: a realistic
   AGL above ~625 m (e.g. 1000 m) driving the real `wide`/`narrow_near`/`narrow_far` sequences
   through `decide()`, asserting every committed `(azimuth, elevation)` satisfies
   `within_field_of_regard`. This re-enters the normal loop per `AGENTS.md` — Implementer, then
   Reviewer on the fix, then DoD — not straight to DoD.

Everything else in this review stands independent of this fix: the no-omniscience invariant, the
tunable declarations, and the rest of the mechanically-clean checks already confirmed by the
Reviewer (ruff/mypy/pytest all pass on this tip) are unaffected by it.

---

## Deep analysis — batch 2

Scope: `git diff 5e917840..8cb3c527 -- body-layer/src`, restricted to this feature's own
commits (`git log --first-parent 5e917840..8cb3c527` — excludes `cce0b57a`/`88ac4200`'s merged-in
main content, which is already-reviewed and out of scope here; confirmed none of the other
first-parent commits in the range touch `body-layer/src`). Five commits change source:
`bb6364b0` (Required Fix 1 from Part 1 above — the elevation regard filter), `451c5c45`/`9cba4943`/
`135e2414` (`BL-B85` stall cooldown, the glance-away commit rule, and the import-time-crash floor),
and `49f92738` (boresight-relative regard, F5). Checked out detached at `8cb3c52759bafdc6f6a020e
605462b1e3131b346` in this worktree (`HEAD` confirmed a strict ancestor of the tip before checkout,
clean tree before and after).

### Required Fix 1 (elevation regard filter, `bb6364b0`) — confirmed correctly closed

`_sight_in_regard_sweep` now filters `search_pattern`'s output through `within_field_of_regard`
before returning (reject, not clamp — the same pattern `look_sweep` already uses). Matches the
Required Fix as specified in Part 1 above, with the committed test
(`TestSightInRegardSweepElevation`) built against the real production wiring at the review's own
measured failing altitude (1000 m AGL). No residual gap at this commit alone — closed by `49f92738`
below in a more general form (see next section), not superseded incorrectly.

### Boresight-relative regard (F5, `49f92738`) — every sight-aim producer checked, all consistent

F5's correction (*"it is not about distance, but angles relative to boresight... the limits are
the mechanical rotation limits around aircraft axis"*) is a sharper form of exactly the recurring
gap named in `.claude/agent-memory/security/project_bl_b64_field_of_regard_unenforced.md` and
`.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md`: `bb6364b0`'s own
fix checked elevation against the mount's bound, but did so on ground-anchored, level-flight-only
geometry — correct only at zero pitch/bank. Traced every path that can grant a sight aim, in the
body frame:

| producer | body-relative conversion | regard-checked | verified |
|---|---|---|---|
| `_search_sweep` (binocular search) | `_to_body_relative_steps` | n/a — `BINOCULAR_OPTIC` has no `regard_*` fields (all `None`, confirmed by reading `optics.py:246-253`) | read |
| `_sight_in_regard_sweep` (sight wide/narrow search legs) | `_to_body_relative_steps`, applied *before* `within_field_of_regard` | yes | read + the commit's own mutation (zeroing the pitch/bank term, confirmed red) |
| `_sight_out_of_regard_sweep` (binocular excursion within the sight's idle cycle) | `_to_body_relative_steps` | n/a, same reason as `_search_sweep` | read |
| `look_target_for` (believed-contact aim, feeds `is_worth_a_look`/`choose_look`) | calls `body_relative_direction` directly with real `pitch_deg`/`bank_deg` (`_look_targets` passes `ownship.pitch_deg`/`ownship.bank_deg`) | yes, via the existing `within_field_of_regard` filter in `_decide_sighting`'s `worth_looking` comprehension — now operating on correctly-transformed coordinates | read + traced call site |
| `look_sweep` (sweep around a chosen look target) | operates on `chosen.azimuth_deg`/`elevation_deg`, already body-relative from `look_target_for` — no second conversion needed | yes (`regard_optic` truncation, pre-existing from `BL-B64`'s follow-up) | read |
| `_idle_sight_rest` (defensive fallback, "never reached in production" per its own docstring) | none needed — holds the last *already-validated* aim, or `(0.0, 0.0)` (dead ahead, trivially inside any regard envelope) | n/a by construction | read |

No producer found that commits a sight aim without either a body-frame conversion or a documented,
verified reason it needs none. `heading_relative_to_body_relative` reuses `body_relative_direction`
(the same conversion `check_visibility` uses) rather than re-deriving the rotation — checked the
algebra directly rather than taking the docstring's "exact inverse" claim on trust: constructing
`(north, east)` from `(forward, right)` via the stated rotation and substituting back into
`body_relative_direction`'s own yaw-removal step confirms `forward0 == forward`, `right0 == right`
algebraically (the `sin`/`cos` cross terms cancel), so the synthetic yaw cancels exactly and only
the pitch/bank rotation survives — no sign error, no stale copy of the rotation.

### No-omniscience — clean

`ownship.pitch_deg`/`bank_deg` (`perception/source.py:116-117`, populated from `pitch_rad`/
`bank_rad` telemetry) are ownship's own attitude, not derived from any unseen unit — legitimate
per the task's own framing and unrelated to the `Percept`/no-omniscience boundary, which governs
contact data, not ownship state. `target.current_level` (the new `BL-B85` stall-cooldown key) comes
from `contact.classification.level.name.lower()` via `_look_targets` — belief-derived, same as
every other `LookTarget` field. No path in this batch reads `Observation.derived_world_position` or
a DCS object id; `belief/percept.py` is untouched by this diff.

### Stall-cooldown state (`attempted_at_level`/`pending_attempted_at_level`) — bounded, not pruned, low risk

Checked whether `OpticState`'s per-contact dicts can grow unboundedly. They are **never pruned for
lost contacts** — confirmed by grep (`attempted_at_range_m`/`attempted_at_level`/`attempted_at_
time_sim` are read and written only in `optic_policy.py`; nothing removes a key once added). This
predates this batch: `attempted_at_range_m`/`pending_attempted_at_range_m` already existed,
unpruned, at `5e917840` (the previous pass's baseline) — this batch's `attempted_at_level`/
`pending_attempted_at_level` (`451c5c45`) extend the same shape to a second pair of dicts rather
than introducing a new growth mechanism.

Two things bound it in this project's actual context, checked rather than assumed:
- `ConsolePerceptionRunner.reset_for_new_mission` re-invokes `__init__`, which rebuilds `optic_state`
  via its `field(default_factory=OpticState)` — a fresh, empty `OpticState()` — on every genuine DCS
  mission (re)start (`logger.py:518-556`, confirmed `optic_state` is *not* in the preserved-field
  list). So growth is bounded to one mission's lifetime, not the process's.
- Within one mission, the key space is the set of distinct `contact_id`s Petrovich ever attempted a
  sight look at — bounded by the mission's own unit count, which in this single-player,
  non-adversarial context is author-controlled, not attacker-controlled (no external actor can
  inflate it by, e.g., spawning unbounded contacts against Petrovich's will).

**Probability:** low — requires an unusually long single mission with an unusually large number of
distinct looked-at contacts to matter at all, and even then the entries are a handful of
floats/short strings each.
**Impact:** low — worst case is a few hundred KB in a single-player process with no adversary able
to drive the count, not a resource-exhaustion vector.

**Not filed as a backlog item, intentionally.** Reasoning: (1) the growth-without-pruning shape is
pre-existing and was not flagged as a finding when `attempted_at_range_m` was first introduced,
so this batch's extension of the same shape to a second field is consistent with an already-accepted
pattern, not a new one; (2) the mission-restart reset and the non-adversarial single-player context
both independently bound the practical impact to negligible; (3) filing it would ask Implementer to
add pruning logic (on what basis — contact loss? a TTL?) for a risk that, measured against this
project's actual scope, does not currently justify the design question. If this project's scope
ever widens past single-player (explicitly out of scope today, root `CLAUDE.md`), or a mission with
genuinely unusual contact churn is flown and measured, this disposition should be revisited — same
lapse-condition discipline root `CLAUDE.md`'s "Rate a fallback by how often it fires when nothing is
wrong" asks of any rating that rests on a context that could change.

### Tuning policy — the import-time-crash violation introduced and then corrected within this batch

`9cba4943` added a bare `assert OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S` at import time,
reachable by a single, realistic, in-bounds `SIGHT_STALL_COOLDOWN_S` override (e.g. `40.0`,
comfortably inside its own declared `lo=30.0, hi=400.0`) — this violates `body-layer/CLAUDE.md`'s
own tuning policy ("a bad value warns and continues on the code default — it never refuses to
start"), which is exactly the self-inflicted-availability class this policy exists to prevent.
**Fully corrected within the same batch**, by `135e2414`: replaced with
`_EFFECTIVE_SIGHT_STALL_COOLDOWN_S = max(SIGHT_STALL_COOLDOWN_S, OPTIC_RETRY_INTERVAL_S)`, a floor
rather than a crash. Confirmed by grep that no bare assert on this pair remains in the file at the
tip. No action required — noting it here only because the sequence (introduced, then fixed, same
batch) is worth recording for continuity rather than silently skipping over.

### Dependency Status

No dependency change in this batch.

### Code Findings (batch 2)

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/perception/geometry.py`, `heading_relative_to_body_relative` | New body-frame conversion, reused by every sight/binocular sweep producer | Verified algebraically (yaw cancels exactly) and by the commit's own mutation; consistent with `body_relative_direction`'s existing convention | None |
| `body-layer/src/logger.py`, `_to_body_relative_steps` and its three callers | Regard-check correctness after F5 | Every sight-aim producer either converts to body-relative before `within_field_of_regard`, or is a documented no-regard optic, or holds an already-validated prior aim | None |
| `body-layer/src/belief/optic_policy.py`, `OpticState.attempted_at_level`/`pending_attempted_at_level` | Per-contact dict, never pruned | Bounded by per-mission reset and single-player, non-adversarial unit count; same shape as pre-existing, previously-unflagged dicts | Not filed (see above) — note only |
| `body-layer/src/belief/optic_policy.py`, `_EFFECTIVE_SIGHT_STALL_COOLDOWN_S` | Import-time crash introduced then fixed, same batch | Confirmed fixed by direct read (no bare assert remains) and by the Reviewer's own independent mutation | None |
| `*/pyproject.toml` | Dependency | No change | None |

### Checks run

- `pytest body-layer/tests -q`: 2360 passed, 4 xfailed, 0 failed (full subproject suite, not just
  the touched modules).
- `cd body-layer && .venv/bin/mypy src`: Success, no issues in 68 source files.
- `/security-grep` run project-wide: no new hit in any category attributable to this batch's diff
  (no `eval`/`exec`/`pickle`, no new `type: ignore`/`noqa`, no new bare `except: pass`, no new
  credential-shaped literal; the one `assert` this batch added was removed within the same batch,
  confirmed above).

### Verdict
**APPROVED**

No required fixes. One finding (per-contact dict growth) is disposed as "not filed, intentionally"
with reasoning above rather than left as unresolved prose.
