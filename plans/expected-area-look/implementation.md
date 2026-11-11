### Implementation Summary

Implemented in full, tested, committed: Stage 0 (promote the probe), Stage 1
(aircraft-layer point-probe query, both sides), and the pure mechanism half of
Stages 2–3 (`belief.expected_area` plus the `ContactStore` primitives it
needs). **Not completed**: the trigger's actual insertion into
`ContactStore.ingest` (the one call site that would make the mechanism run
live), `body.py` wiring (probe push/clear, `OpticState`/`LookTarget.area_check`
flagging, `resolve_checks` being called each poll), `callouts.py`'s hold-check
and merge-echo-skip wiring, `CONTACT_RELOCATED`/`CONTACT_ABSENT` event kinds
and their speech templates, `groups.py`/`mission_memory/admission.py` skip
predicates, `forest.py` parameterisation for a settlement mask, and Stage 3c's
production acceptance measurement. Stage 4 (docs/roadmap/cards) was explicitly
out of scope for this dispatch.

**The central finding, and why the trigger is not wired in:** `eligible_
trigger_target`'s precondition for the gate-fold/ambiguous-fold path — "A was
not seen this poll" — is `a.last_seen_sim < now_sim`, which is true of nearly
every ordinary gate match by construction (a passing candidate's own
`last_seen_sim` is always from a strictly earlier poll than the percept being
matched against it right now). Wired into `ingest` exactly as the plan
specifies ("look every time a gate-path sighting lands on... a remembered
group he can't see right now"), this intercepts *every* gate-path
reacquisition, not only a genuine "out of view" case — confirmed by running it
against this repo's own existing suite: it broke
`test_slow_directional_drift_never_reports_a_range_beyond_the_detection_cap`
and `test_position_runaway_does_not_corrupt_a_second_contacts_cardinality`,
both of which exercise a same-object sequence of **gate-path, not continuity**
reacquisitions specifically (no `continues_observation_id` in their fixtures)
to isolate the spatial gate's own robustness. In real flight this scenario is
rare (ordinary continuous tracking resolves via object-permanence continuity,
per `association_over_time.py`'s own docstring — the gate is "the exception
path"), which is exactly the plan's own Finding 1 reasoning for why a broad
trigger is acceptable — but these two tests deliberately bypass continuity, so
the new trigger fires on them where it should not, by the letter of what they
test.

Per this project's own escalation rule ("existing tests must be rewritten
rather than extended" needs explicit sign-off, root `CLAUDE.md`'s "Escalation
Rules"), I did not narrow the trigger or rewrite those two tests unilaterally.
I reverted the `ingest` call site back to its original, pre-`BL-B111` form and
left a dated comment there explaining exactly this, pointing back to this
file. Two ways to resolve it, for the Architect/user:

1. **Narrow the trigger's own eligibility condition** — e.g. require that the
   matched percept's own `continues_observation_id` is `None` or failed/expired
   continuity (i.e. only fire when the gate is reached for the reason the
   project's own docstring says it normally is: a genuine founding or a real
   gap), rather than every bare gate match regardless of why continuity did not
   apply.
2. **Accept that these two tests' premise has changed** and rewrite their
   expectations under the new trigger (they would need `continues_observation_id`
   wired into their fixtures, or a different scenario to isolate the same
   property).

Everything else in the mechanism (`belief.expected_area`'s trigger
*predicates* themselves, `area_visibility`, composition/displacement,
`resolve_checks`, `ContactStore`'s `open_check`/`release_check`/`close_check`/
`callout_held`/`has_open_check`/`record_believed_distinct`/`is_believed_
distinct`/`merge_contact`/`mark_lost_now`) is built, dormant (nothing calls
`open_check` yet), and unit-tested — once the trigger question above is
settled, wiring it in is the one remaining call site described above, plus
the `body.py`/`callouts.py`/`events.py`/`speech.py` work listed below.

### Files Changed — aircraft-layer (Stage 1, complete)

- `dcs-export/petrobrain-line-of-sight-hook.lua` — new inbound op
  `probe_points` on the existing 7797 listener (`pollInbound`, renamed from
  `pollLookDirection`); `SET_PROBES_TEMPLATE` (14 `%d` conversions, no other
  specifier) applies up to `MAX_PROBE_POINTS` (6) clamped points via
  `_applyProbePoints`; the LOS chunk evaluates them after the unit loop,
  fail-closed (empty token on any `pcall` failure, never a guessed `1`/`0`);
  the answer rides the single `dostring_in` return separated by an ASCII SOH
  byte, split on the Lua side before the JSON envelope is built, so `payload`
  stays byte-identical to the pre-Stage-1 wire and `probes` is a new,
  independent, optional envelope key.
  - **Found and fixed while syntax-checking the bridged chunk in isolation**
    (the subproject's own documented caveat: `luac5.1 -p` on the outer file
    never looks inside a `dostring_in` string literal): the bridged chunk runs
    in a different Lua state and cannot see the outer file's own `local`s, so
    `MAX_PROBE_POINTS`/the target height needed the same load-time splice
    `MAX_SIGHTLINES_PER_CALL`/`PLAYER_BUBBLE_RADIUS_M` already get. Without the
    fix (a third spliced line, `MAX_PROBES`) the chunk read a nil global and
    every LOS poll — not just the probe part — would have errored. The target
    height uses the file's existing literal `2.0` convention instead of a
    fourth splice.
  - Also found the same way: the doc comment's own `"points":[[x,z],...]}` text
    inside the file's top `--[[ ... --]]` block opened a nested long-bracket
    (`[[` is the Lua long-bracket token, even inside a comment), which
    `luac5.1 -p` flagged as a real parse error. Fixed by spacing it
    (`[ [x,z], ... ]`).
- `src/schema/line_of_sight.py` — `ProbeAnswer`/`ProbeAnswers`
  (fail-closed: a missing index is `None`, never `False`), `MAX_PROBE_POINTS`,
  `LineOfSightSnapshot.probes: ProbeAnswers | None` (shares the snapshot's own
  `dcs_model_time_s`, not a second wire timestamp); a malformed `probes_raw`
  drops only the probes field, never the already-parsed LOS payload.
- `src/collector/line_of_sight_receiver.py` — passes the envelope's `"probes"`
  key through (absent/non-string both read as "no probe answers").
- `src/collector/command_sender.py` — `LookDirectionSender.send_probe_points`,
  same socket `send_look_direction` already uses, no validation (the
  collector/Hook do that).
- `src/api/server.py` — `POST /command/probe_points`, three-deep validation
  (seq bound, point count bound, per-point coordinate bound) matching the
  schema/Hook constants exactly, reuses `look_direction_sender`.
- `tests/test_line_of_sight_hook_lua.py`, `test_line_of_sight_schema.py`,
  `test_line_of_sight_receiver.py`, `test_line_of_sight_api.py`,
  `test_look_direction_sender.py` — new tests per the above; two existing
  assertions updated for the `pollLookDirection` → `pollInbound` rename
  (`pcall(pollInbound)`, `_applyLookDirection(latestLook)`) and the three-line
  `LOS_CODE` splice guard was extended from two lines to three.
- **Not live-verified** — no DCS available in this environment, per the
  dispatch. The Windows test card from the plan's Stage 1 (push probe points by
  hand, confirm `dcs.log`/`/line_of_sight/latest.probes`, a paused-state check,
  `bridge_call_ms` unmoved) is still owed.

### Files Changed — body-layer

- `src/aircraft_client.py` — `post_probe_points` (raise-on-failure, same
  posture as `post_look_direction`). `get_line_of_sight_latest` needed no
  change (plain dict pass-through already carries the new key).
- `tools/measure_expected_area_look.py` — Stage 0's promotion of
  `plans/expected-area-look/probe_b111.py`, unchanged behaviour. The
  `--production` mode Stage 3c calls for (replacing the modelled harness with
  the real `ContactStore`/`belief.expected_area` check) is **not built** —
  it depends on the trigger wiring above.
- **New `src/belief/expected_area.py`**:
  - `ExpectedAreaCheck` (state).
  - `EXPECTED_AREA_MAX_HALF_WIDTH_DEG`, `COMPOSITION_MATCH_RATIO` — the two
    tuning keys the plan calls for, via `tuning.real`, `config/defaults.toml`
    regenerated and its **rendered** first sentences read (not just the source
    comment).
  - `area_half_width_deg`/`area_fits_one_look` — Decision 1's feasibility gate,
    the same formula the architect probe used.
  - `b_is_threat` — Q2's release-at-once condition.
  - `probe_points_for` — centre + along-line ±2σ (Decision 4).
  - `eligible_trigger_target`/`merge_echo_or_beside_lost_target` — the trigger
    predicates (not wired into `ingest`; see above).
  - `area_visibility` — Stage 2's full verdict, pure, fail-closed, every
    clause required.
  - `composition_compatible`/`displacement_plausible`/`is_same` — Stage 3b's
    "same" predicate.
  - `relocation_warranted` — Decision 3's two-condition relocation test.
  - `resolve_checks` — the one "when" function, taking a `_StoreLike`
    `Protocol` (not a concrete `ContactStore` import — see the module's own
    `TYPE_CHECKING` note on why that would be a real import cycle,
    `contacts → expected_area → optic_policy → enrichment → contacts`, caught
    by running the test suite, not by `mypy`, which tolerates the cycle under
    lazy annotations).
  - `LookEvidence`/`CheckOutcome`/`Verdict` — the state-param/result shapes.
  - Module docstring states plainly that "hold" is not a separate action —
    just opening a check — correcting an earlier draft that implied four
    free-standing action functions (`hold`/`release_as_new`/`merge_into_
    remembered`/`mark_absent`); the real actions are four `ContactStore`
    methods, listed below.
- `src/belief/contacts.py` (`ContactStore`) — `_checks`/`_believed_distinct`
  fields; `checks`/`check_for`/`has_open_check`/`callout_held`/`open_check`/
  `release_check`/`close_check`/`record_believed_distinct`/`is_believed_
  distinct`/`merge_contact`/`mark_lost_now`. `merge_contact` replays B's own
  `contributing_observation_ids` through A's existing `Contact.record`, in
  order, remaps `_observation_id_to_contact_id`, drops B's open check and any
  believed-distinct pair naming B — deliberately emits **no** lifecycle event
  itself; a `CONTACT_REACQUIRED` for a lost A falls out of the very next
  `tick()` call comparing A's refreshed `last_seen_sim`, the same unmodified
  mechanism every other re-observation uses. `mark_lost_now` is a **named,
  stated simplification**: `certainty_of` has no stored state of its own (it
  is a pure function of `now_sim - last_seen_sim`), so rather than add a
  second "declared absent" concept, this rewinds `last_seen_sim` far enough
  that the existing threshold already reads "lost" — the cost (a later query
  of "how long ago was A really last seen" would read the rewound value) is
  named in that method's own docstring rather than hidden.
- **`ingest`'s own gate branch is unchanged from before this feature** (the
  trigger finding above) — restored to its pre-`BL-B111` form with a dated
  comment explaining why, pointing at this file.

### Not built (beyond the trigger wiring above)

- `belief/callouts.py` — the hold check before `CALLOUT_MAX_AGE_S`, the
  merge-echo skip for a believed-distinct pair, holding a merge-echo B with an
  open check.
- `belief/events.py`/`belief/speech.py` — `CONTACT_RELOCATED`/`CONTACT_ABSENT`
  event kinds and their templates. (Designed, not written: `CONTACT_RELOCATED`
  as a bespoke `_render_lifecycle_text` branch — *"That group, now <clock>
  o'clock, <range>."* — and `CONTACT_ABSENT` as *"That group is no longer at
  its last place."*, both added to `_TEMPLATED_KINDS`, neither watched-only nor
  observability-exempt, same posture as `CONTACT_REACQUIRED`.)
- `belief/optic_policy.py` — `LookTarget.area_check: bool`, `choose_glass_look`
  ranking it first, `OpticState.area_look_report`. I deliberately did not wire
  the last of these: faithfully threading a new field through every
  `GLASSING` construction/interrupt site in a 3745-line module I had not fully
  audited risked a silent regression I could not have caught in the time
  available. `area_visibility`'s own `look_completed_naturally` parameter is
  written to accept this as a state param from whatever mechanism eventually
  supplies it — a deadline-based approximation (bounded by the plan's own
  "≤17 s worst" framing) would preserve the fail-closed property but is a
  real fidelity reduction from "the look genuinely dwelled on A's envelope to
  a natural end," and should not be read as equivalent without the Architect's
  sign-off.
- `src/body.py` — pushing/clearing probe points, flagging A's `LookTarget`,
  calling `resolve_checks` once per poll, ATGM/attack-run pause wiring. None of
  this was attempted — `body.py` is 5379 lines and I judged guessing at its
  poll-loop integration points, under the time remaining, a worse risk than
  reporting the gap plainly.
- `belief/groups.py` (`reconcile` skip) / `mission_memory/admission.py` (skip)
  — `ContactStore.has_open_check` exists for exactly this; the two call sites
  are not added.
- `perception/forest.py` — not parameterised for a settlement mask; `area_
  visibility`'s `occluded` parameter is ready to accept it as a state param.
- Stage 3c's production acceptance grid — not run; depends on everything
  above.
- `body-layer/docs/STRUCTURE.md`, `body-layer/CLAUDE.md`'s "Tuning" section,
  roadmap/entry updates, test cards — Stage 4, explicitly out of scope for
  this dispatch per the orchestrator's instructions.

### Tests Added

- `aircraft-layer/tests/test_line_of_sight_hook_lua.py` — `SET_PROBES_
  TEMPLATE`'s 14-`%d` guard, the three-line `LOS_CODE` splice guard (extended),
  the fail-closed-token guard, the `pollInbound` coalescing guard.
- `aircraft-layer/tests/test_line_of_sight_schema.py` — `ProbeAnswers.
  from_wire` parsing, fail-closed on missing/malformed, `LineOfSightSnapshot.
  probes` optionality and `to_dict` round-trip.
- `aircraft-layer/tests/test_line_of_sight_receiver.py` — the envelope's
  `"probes"` key passed through, absent/non-string both read as "no probes".
- `aircraft-layer/tests/test_line_of_sight_api.py` — `POST /command/
  probe_points` validation (seq bound, point count bound, per-point
  coordinate bound), 503/500 postures matching `/command/look_direction`.
- `aircraft-layer/tests/test_look_direction_sender.py` — `send_probe_points`
  wire shape and failure posture.
- `body-layer/tests/test_aircraft_client.py` — `post_probe_points`.
- `body-layer/tests/test_expected_area.py` (new, 50 tests) — table-driven,
  one test per `area_visibility` clause (including every probe-`None` case,
  per E5/E11's fail-closed contract); `eligible_trigger_target`/`merge_echo_
  or_beside_lost_target`; `probe_points_for`'s centre/symmetry; `composition_
  compatible` (including the plan's own "3 and 8" example); `relocation_
  warranted` (including the bucket-edge-jitter-alone negative case); `resolve_
  checks`'s full verdict sequencing (different/same/absent/cannot_look for
  both fold and echo kinds/still_open/paused) against a fake store double.
- `body-layer/tests/test_contacts.py` (9 new tests) — `ContactStore`'s new
  primitives: `open_check`/`check_for`/`has_open_check`/`callout_held`
  (before and after release)/`release_check`'s idempotence/`close_check`/
  `record_believed_distinct`'s order-independence/`merge_contact` (percept
  replay order, no fresh `Contact` for A, observation-id remap, open-check and
  believed-distinct cleanup)/`mark_lost_now`.

### Checks

**aircraft-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `cd aircraft-layer && .venv/bin/mypy src`: pass (26 files)
- `pytest aircraft-layer/tests -q`: pass (702 passed)
- `luac5.1 -p` on the touched Hook file, outer and the extracted bridged
  chunk separately: pass (both found real bugs before this, see above)

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (80 files)
- `pytest body-layer/tests -q`: pass (full suite, 3097+ tests — the only
  pre-existing failure, `test_defaults_toml_matches_the_generator`, was fixed
  by regenerating `config/defaults.toml` for the two new tuning keys)

No subproject check failed at any point after the trigger-wiring revert.

### Notable Discoveries

- **The central one**: the plan's trigger, read literally, breaks two
  existing `contacts.py` tests because its "not seen this poll" precondition
  is nearly tautological against any bare gate match. See "Implementation
  Summary" above for the two ways to resolve it.
- **A second-order import-cycle hazard, not in the plan**: `belief.optic_
  policy` imports `belief.enrichment`, which imports `belief.contacts` — so
  the new `belief.expected_area` module cannot import anything from `belief.
  optic_policy` (I needed `LOOK_SWEEP_SIGMA`'s value) without `belief.contacts`
  importing `belief.expected_area` creating a real cycle. Resolved the same
  way `LOOK_SWEEP_SIGMA` itself resolves its own sibling-constant tension
  (`GATE_SIGMA_THRESHOLD`): declared independently, not imported, with a
  comment stating why. `mypy --strict` did not catch this at all (lazy
  annotations under `from __future__ import annotations` make it invisible to
  the type checker); only running the test suite surfaced it.
- **The Hook file's own documented caveat earned its keep twice in one
  session**: `luac5.1 -p` on the outer file does not look inside a
  `dostring_in` string literal, and extracting that literal to check it
  separately caught both the missing `MAX_PROBES` splice (a guaranteed
  every-poll failure) and the nested-`[[`-in-a-comment syntax error, neither
  of which the outer-file check saw.
- **`ContactStore.mark_lost_now`'s rewound `last_seen_sim`** is a real,
  reusable pattern this codebase does not otherwise have (a "declared known
  state" overriding a derived decay reading) — worth the Architect's attention
  if a future feature needs the same thing without the stated cost.

### Pass 1 (belief side: the check opens, holds and is spoken — no `body.py`)

**STOPPED mid-pass and reporting, per the escalation rule ("existing tests
must be rewritten rather than extended" needs sign-off) — the trigger is
wired exactly as the plan's amended Stage 3a specifies, the two named
"hard rule" tests pass unchanged, but ten other pre-existing tests across
three files now fail for the same single, deliberate-by-design reason, and
that blast radius was not covered by the plan's own "Measured" section.**
`callouts.py`, `events.py`/`speech.py`, `groups.py`/`admission.py`, and the
new `test_contacts.py` trigger tests (item 6 of Pass 1's own list) are
**not yet built** — I stopped before them rather than build more on top of
a mechanism whose eligibility window this finding puts in question.

**What was built, exactly as specified:**
- `belief/expected_area.py`: `a_out_of_view(a, now_sim)` — `(now_sim -
  a.last_seen_sim) > FOCUS_DWELL_S` — extracted as its own named function
  (the plan's own code block), with `eligible_trigger_target` calling it in
  place of the literal `a.last_seen_sim < b_percept_t_sim`. Import added:
  `from perception.gaze import FOCUS_DWELL_S` (no cycle — `perception.gaze`
  imports nothing from `belief`; confirmed both by `import belief.contacts;
  import belief.expected_area` succeeding and by the full test run below).
- `belief/contacts.py` `ingest`'s gate branch: the dated "deliberately NOT
  enabled" comment is gone. A gate-path fold (single passing candidate, or
  the ambiguous-fold target) against an `eligible_trigger_target` A, with
  fewer than `MAX_OPEN_CHECKS` (2) already open, founds B fresh and opens a
  `kind="fold"` check instead of folding — "never fold while a check could
  run" (plan, Stage 3a's own "Action"). A founded-fresh B (no gate match at
  all) is then scanned via `merge_echo_or_beside_lost_target` for an
  eligible, earlier A it could be an echo of or sit beside, under the same
  cap; at the cap, both paths fall through to today's unchanged behaviour
  exactly as the plan's "Third concurrent check" section specifies (a fold
  simply folds; a fresh-founded B with no scan room stays founded, which is
  already "silent"/"B called new" for the echo/beside-lost cases
  respectively — no extra code needed to honour that half of the cap).
  `b_is_threat` is evaluated once at open time (Q2's immediate release).
  Restructured the surrounding `if`/`elif`/`else` from the reverted code's
  two independent `if` statements into one exhaustive chain so `mypy
  --strict` can prove `contact` is always assigned a concrete `Contact` —
  the two-independent-`if` shape (one setting a flag, a second checking its
  negation) type-checked fine by eye but `mypy` could not follow it
  (`Item "None" of "Contact | None" has no attribute "id"` three times);
  worth remembering as its own small pattern, not worth a memory file on
  its own.

**The central finding.** `eligible_trigger_target`'s amended precondition
(`a_out_of_view`, `now_sim - last_seen_sim > FOCUS_DWELL_S` = 2.0 s) fixes
the tautology the previous pass found (confirmed: `test_contacts.py` and
`test_expected_area.py` — 138 tests — all pass, including both named "hard
rule" tests, run individually and as part of the full suite below) — but
it is **not narrow enough to avoid catching this codebase's own existing
same-group, cross-optic, few-seconds-apart reacquisition test pattern**,
which is a different, much larger population than the two named tests'
own 1 s/poll continuous-tracking sequences. Ten tests now fail, all for
the identical reason — a gate-path fold at `gap_s` in {4.0, 6.0} between an
eligible A and a plausible same-group B, previously resolved as an
immediate, synchronous fold (`len(store.contacts) == 1` right after
`ingest`), now opens a held check instead (two contacts; the "same"
verdict that would eventually re-merge them is never reached inside these
tests, because `resolve_checks` is not wired into any production or test
loop until Pass 2/`body.py`):

- `tests/test_expected_area_trigger.py` (4): both parametrised cases of
  `test_residual_fold_rate_for_far_binocular_near_unaided_matches_honest_rate`
  and `test_residual_fold_rate_for_far_unaided_near_binocular_stays_high` —
  a **pre-existing `BL-B110`-era characterisation test** for a different,
  never-shipped mechanism (`[[BL-B110]]` Stage 2's `as_if_optic_class`,
  the module's own docstring: "Stage 2 ... re-evaluates `passes_gate` *as
  if* ..."; this plan's own intro says "Stage 2's trigger was never
  built"). Its `_rates` helper calls `store.ingest` directly and reads
  `honest_fold = len(store.contacts) == 1` as its baseline — exactly the
  line this pass's wiring changes, at `gap_s=6.0`. Measured: residual fold
  rate dropped to 0.00% (floor asserts ≥ 55%/70%) — meaning *every* trial
  that used to fold now opens a check instead, which is the plan's own
  stated design ("fires on ~99% of same-group gate re-sightings"), just
  not previously checked against this file's own baseline measurement.
- `tests/test_relative_distance_scenarios.py` (2):
  `test_e3_group_seen_unaided_then_through_binoculars_stays_one_contact`
  (`gap_s=4.0`, range 3000 m — the exact shape `a_out_of_view`'s own 2.0 s
  threshold is sized to *not* protect: this is a genuine, intentional
  reacquisition through a different optic 4 s later, asserting `len(store
  .contacts) == 1` immediately) and
  `test_cross_optic_fuse_along_sigma_never_beats_the_tighter_optics_own_sigma`.
- `tests/test_relative_distance_sweep.py` (4):
  `test_e3_same_and_unaided_then_binocular_folds_at_least_as_often_as_measured`,
  `test_e3_binocular_then_unaided_folds_almost_always`,
  `test_no_omniscience_fused_sigma_never_beats_the_tighter_optics_own_sigma`,
  `test_no_omniscience_fused_mean_never_extrapolates_past_either_look` — all
  via `_fuse_two_looks`'s own `gap_s: float = 4.0` default. One directly
  measured: `unaided→binocular`, 30/30 trials "did not fold" (ceiling 15%).

**Why the plan's own "Measured" section did not catch this.** Stage 3a's
amendment (`1a6c1e55`) measured the two named `test_contacts.py` tests
(1 s/poll, 18 matches each) and the architect's own 144-cell harness
(6 s/700 s gaps, the plan's own scenario geometry: a believed group A and a
*second*, possibly-different group B). Neither touches the population these
ten tests exercise: **one real group, reacquired seconds later through a
different optic — the ordinary, core cross-optic fusion path this
codebase's own test suite characterises extensively**, which sits squarely
inside `a_out_of_view`'s 2 s window at `gap_s` 4–6 s. The amendment's own
"Not chosen" list considered `OBSERVED_WINDOW_S` (16 s, rejected for
missing the 6 s *ridge* case) and a store-held previous-poll set, but not a
window wide enough to exclude "two looks of the same thing, four seconds
apart, through two different optics" — which is a different, and in this
codebase evidently much more heavily tested, scenario than either.

**What I did not do.** I did not narrow `a_out_of_view`'s window, rewrite
any of these ten tests' expectations, or revert the `ingest` call site —
each is exactly the kind of unilateral call the escalation rule reserves
for the Architect/user, and this is a different, larger-blast-radius
version of the same question the previous pass already escalated once.
Two concrete directions, for whoever picks this up:

1. **Widen the trigger's own exemption window** past `FOCUS_DWELL_S`
   (2.0 s) to something that also covers an ordinary few-seconds-apart
   cross-optic reacquisition of the *same* group — at the cost of giving
   up more of the "ridge" case (A masked and B appearing on its bearing
   within that same window) the amendment itself already accepted as an
   unmeasured risk. `OBSERVED_WINDOW_S` (16 s) was already considered and
   rejected for a different reason (the 6 s ridge case); a value between
   2 s and 16 s, newly measured against *this* suite specifically, is the
   open middle ground.
2. **Accept that these ten tests' premise has changed** (a same-group,
   cross-optic reacquisition now defers through a hold, resolving only
   once Pass 2 wires `resolve_checks` into a poll loop) and have Pass 2
   either (a) rewrite them to call `resolve_checks` and assert the
   eventual merged state, or (b) give each its own fake `_StoreLike`-driven
   resolution step matching the plan's own `test_resolve_checks_same_...`
   pattern already in `test_expected_area.py`.

Not raised as a third option, because the plan's own Stage 3a text is
explicit about it ("never fold while a check could run"): narrowing which
*candidates* open a check (e.g. only an A whose certainty has decayed past
`"observed"`) rather than widening the *time* window was already
considered and rejected in the amendment's own "Not chosen" list
(`certainty_of(A) != "observed"`, 16 s) for missing the 6 s ridge case —
the same tension applies here, just discovered against a different test
population.

**Checks, this pass:**
- `ruff format --check src tests`: pass.
- `ruff check src tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass (80 source files).
- `pytest tests/test_contacts.py tests/test_expected_area.py -q`: pass (138
  passed) — both named "hard rule" tests confirmed unchanged among them.
- `pytest tests -q` (full suite): **3096 passed, 4 xfailed, 10 failed** —
  the ten tests named above. No other file affected.

**Files changed, this pass:** `src/belief/expected_area.py` (`a_out_of_view`
extracted, `eligible_trigger_target` amended), `src/belief/contacts.py`
(`ingest`'s gate/founding branches wired to the trigger, per above),
`tests/test_contacts.py` (the Expected-area-look section header comment
updated to no longer say the trigger "is not wired into `ingest` yet" —
no new tests added this pass; see "What I did not do").

### Pass 1, continued — resolved the blast-radius stop, finished the pass

**Main-loop resolution (local, reversible — no further user decision
needed), stated before any code changed:** in flight, a same-group
re-sighting seconds later through a different optic carries object
continuity (`perception.naked_eye_source`'s majority-vote
`continues_observation_id`), so it resolves at `ContactStore.
_resolve_continuity` and never reaches the gate at all — the ten failing
tests drive the gate path directly, bypassing continuity by construction
(their own `_observation`-style helpers default `continues_observation_id
=None`), which is a legitimate way to characterise the gate's own
fold/fusion math but not a scenario that recurs in flight under this
trigger. The fix: make the expected-area trigger a `ContactStore`
capability, **off unless enabled** (`expected_area_checks: bool = False`
constructor parameter), so the ten gate-characterisation tests (and every
other pre-existing `ContactStore()` call site) are unaffected, and a
caller that wants the trigger passes the flag explicitly. `body.py`
(Pass 2) is the one production call site; Pass 1's own new trigger tests
pass it explicitly.

**Verified the premise before relying on it, per the dispatch's own
instruction, rather than assuming it:**
- `perception/naked_eye_source.py`'s `_object_id_to_last_observation_id`
  map (keyed by DCS `object_id`, module docstring point 6) is a field on
  the `NakedEyePerceptionSource` instance itself, cleared only on a
  genuine mission restart (`reset_for_new_mission`) — never per-poll, and
  never on an optic change.
- `body._apply_active_gaze` (the one place `body.py` drives perception
  each poll) sets `source.optic = optic` directly on that same instance
  (`for source in sources: if isinstance(source, NakedEyePerceptionSource):
  ... source.optic = optic`) — unaided and binocular/sight observations
  both flow through the *same* instance and the *same* persistent map, so
  a cluster's majority-vote correlation survives the optic switch by
  construction, not by any expected-area-specific wiring.
- The trust window for that correlation is `belief.decay.
  object_id_continuity_valid`'s `OBJECT_ID_MEMORY_S` (= `IDENTITY_
  HALF_LIFE_S`, 600 s default) — two orders of magnitude wider than the
  4–6 s gaps the ten failing tests use, confirmed by reading the constant
  directly rather than assuming its scale.
- Confirmed the inverse directly: `belief.optic_policy.py` (the binocular
  "GLASSING" look machinery) contains no `Observation(` construction at
  all — the binocular look's own `Observation`s are produced by this same
  `NakedEyePerceptionSource._build_observation`, with `self.optic` simply
  swapped beforehand, not a second, independent construction path that
  might have its own (missing) continuity wiring.
- The premise holds. Had it not — had binocular glassing produced
  `Observation`s through an independent path with no continuity map —
  this resolution would have been wrong (the trigger would fire on
  ordinary glassing in production too), and this would have stopped here
  to report it instead of proceeding.

**Finished the rest of Pass 1 on that resolution**, all in
`feature/expected-area-look`'s own continuation of this work:

1. `belief/contacts.py`: `ContactStore.__init__(self,
   expected_area_checks: bool = False)`; both trigger call sites in
   `ingest` gated on `self._expected_area_checks`.
2. `belief/callouts.py`: `store.callout_held(event.contact_id)` checked
   first in `tick`'s own per-event filter loop, ahead of `CALLOUT_
   MAX_AGE_S` and the merge-echo suppression inside `_render_event` — a
   held contact's events are deferred, never consumed. A released
   contact's events now age from `max(event.t_sim, check.released_sim)`.
   `_is_merge_echo_of_earlier_contact` now excludes a believed-distinct
   pair (`store.is_believed_distinct`).
3. `belief/events.py`: `CONTACT_RELOCATED`/`CONTACT_ABSENT` constants —
   minted directly by their caller (`resolve_checks`), not derived from a
   before/after comparison like every other kind in this module.
   `belief/contacts.py`: `ContactStore.record_relocation`/`record_
   absence`, each a one-line event mint, deliberately separate from
   `mark_lost_now` (the state rewind and the "say something" decision
   stay two actions). `belief/expected_area.py`: `_StoreLike` extended;
   `resolve_checks`'s "same" branch mints `CONTACT_RELOCATED` when
   `relocation_line` fires, "absent" mints `CONTACT_ABSENT` only when
   `a_was_announced` was already true. `belief/speech.py`: the two
   templates — *"That group, now &lt;clock&gt; o'clock, &lt;range&gt;."*
   (neutral lead, not `_contact_report_text`'s unit-type lead) and the
   fixed *"That group is no longer at its last place."* `belief/
   callouts.py`: both kinds added to `_TEMPLATED_KINDS` (the module's own
   "breadth" comments updated 5/6 → 7/8 to match); the same-tick
   suppression rule — when a `CONTACT_REACQUIRED` candidate is actually
   rendered, any unacknowledged `CONTACT_RELOCATED` for the same contact
   is acknowledged without being spoken.
4. `belief/contacts.py`'s `tick` extends its existing not-`lost` filter
   on `self._groups.reconcile`'s input with `not self.has_open_check(...)`.
   `mission_memory/admission.py`'s `step` skips a held contact's admission
   entirely, same primitive.
5. Tests: six new trigger-wiring tests in `test_contacts.py` (fold at 6 s/
   700 s, never on continuous ≤2 s even with the flag on, beside-lost with
   immediate threat release, merge-echo for a not-yet-lost target, the
   two-open-checks cap falling through to an ordinary fold); two in
   `test_callouts.py` (E3's "a held callout never silently becomes no
   callout", the believed-distinct exemption, the `CONTACT_RELOCATED`/
   `CONTACT_REACQUIRED` same-tick suppression); four in
   `test_expected_area.py` (`record_relocation`/`record_absence` minted
   only under their stated conditions, plus the SAM vignette — a SAM held
   across a 700 s gap, B is A, resolves "same" — driving `resolve_checks`
   directly with a hand-built, all-clear `LookEvidence`); three in
   `test_speech.py` (the two new templates' wording, the missing-bearing
   fallback); two in `test_contacts.py`/`test_mission_memory_admission.py`
   (a held contact excluded from group membership and from mission-memory
   admission). Every new negative-space assertion (the suppression rule,
   the believed-distinct exemption) was confirmed red for the stated
   reason by temporarily breaking the fix and re-running, then restored.

**No existing test needed rewriting** — the ten previously-failing tests,
and every other pre-existing test, pass unchanged now that the trigger is
off by default.

**Checks, this continuation:**
- `ruff format --check src tests`: pass.
- `ruff check src tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass (80 source files).
- `pytest tests -q` (full suite, run twice across this continuation as
  code landed): 3124 passed, 4 xfailed (first run, through the groups/
  admission step); a final run including the SAM vignette test was
  in flight at hand-off — see the implementer's own final report for its
  result.

**What Pass 2 needs to know:**
- `body.py` must construct its `ContactStore` with `expected_area_checks
  =True` — the trigger stays silent in production until that one argument
  is added.
- `resolve_checks`'s "same"/"absent" branches already mint `CONTACT_
  RELOCATED`/`CONTACT_ABSENT` — Pass 2 does not need to add that minting
  itself, only to call `resolve_checks` once per poll and supply its
  `LookEvidence`/`a_observed`/`relocation_warranted_by_b`/`a_was_announced`
  state params from real optic/enrichment state.
- The callout-suppression rule depends on `CalloutScheduler.tick` actually
  rendering a `CONTACT_REACQUIRED` candidate in the same poll the merge
  happened — true whenever `resolve_checks` and `CalloutScheduler.tick`
  run in the same poll loop iteration (the ordinary case), but if Pass 2's
  own poll ordering ever separates them across polls, re-check this rule's
  premise.
