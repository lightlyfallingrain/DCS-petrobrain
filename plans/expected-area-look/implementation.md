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
