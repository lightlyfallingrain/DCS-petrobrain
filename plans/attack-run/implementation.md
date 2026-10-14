### Implementation Summary

Stages 1-3 of `plans/attack-run/plan.md` (BL-14, the attack run), per the orchestrator's explicit
scope. Stages 4-7 (`step`, wiring the loop/gaze claim, tier 2, projected position) are **not**
built — `drain_attack_run` exists but is called from no poll loop, and `attack_run.decide` only
derives tier 1.

### Files Changed

**body-layer**

- `src/perception/geometry.py` — `signed_angular_delta_deg(from_deg, to_deg) -> float` in
  `(-180, 180]` (Decision 6); `alignment_direction(observer, target, *, heading_true_deg,
  pitch_deg)`, a named wrapper over `body_relative_direction(..., bank_deg=0.0)` (Decision 3).
- `src/perception/clustering.py` — `Cluster.centroid_alt_m`, the mean of the members' own
  `alt_m`, computed in `_build_cluster` alongside `centroid_x`/`centroid_z`.
- `src/perception/estimation.py` — `RELATIVE_DIRECTION_SIGMA_DEG: Final[float] = 0.0` and
  `perturbed_relative_direction(*, observation_id, forward_m, right_m, up_m)`, an identity
  function at the current sigma (the angular perturbation it would otherwise apply is written but
  unreachable at `0.0`).
- `src/perception/source.py` — `RelativeDirection(forward_m, right_m, up_m)` and
  `Observation.relative_direction: RelativeDirection | None = None`.
- `src/perception/naked_eye_source.py` — `_build_observation` populates `relative_direction` for
  an admitted cluster whose fold-level `live_los_clear is True`, from truth-to-truth geometry
  (the cluster's own `centroid_alt_m`, not ownship's), yaw-only rotated at the observing poll's
  own heading, run through `perturbed_relative_direction`. `trace_sink.annotate_admission` gained
  a `relative_direction_set` keyword threaded from the same call site.
- `src/perception/detection_trace.py` — `DetectionTrace.relative_direction_set: bool = False`
  and the matching parameter on `DetectionTraceCollector.annotate_admission`.
- `src/belief/percept.py` — `Percept.relative_direction: RelativeDirection | None = None`,
  carried through unchanged by `percept_of`.
- `src/belief/contacts.py` — `Contact.last_percept: Percept | None = None`, set unconditionally
  (overwrite, not fold) in both `record()` and `from_percept()`. This is the mechanism Decision
  16 calls "`ContactStore` already keeps the latest percept per contact" — it did not, until this
  field existed; it is the whole `Percept`, not a pulled-out field, specifically so `belief.
  attack_run` has one place to read `relative_direction` from without a second store and without
  `contacts.py` itself ever mentioning that field by name (see "Notable Discoveries" below).
- `src/belief/speech.py` — `Template` gains `"attack_run"`; `render_target_readback(facts)`
  (Stage 1's "Target, armour, 2 o'clock." readback, no range); the `render_alignment` family
  (`_alignment_phrase_for`, `_alignment_clock_hour`, `_ALIGNMENT_CLOCK_WORDS`, `render_alignment`)
  — the ongoing guidance utterance, tier as an argument, the two word tables passed in as data
  rather than imported, so `belief.speech` never depends on `belief.attack_run`.
- `src/belief/attack_run.py` (new) — `AttackRunState`, the three named constants, the two word
  tables, `_tier1_alignment` (the re-rotation: undo the observing poll's own yaw rotation, add
  ownship's translation since the look, re-rotate via `geometry.alignment_direction`),
  `_should_emit` (Decision 7's change-driven rule), and `decide`.
- `src/belief/tasks.py` — `TaskKind` gains `"attack_target"`.
- `src/belief/tools.py` — `attack_target_task`, mirroring `watch_contact_task` with attention
  `"priority"` instead of `"watch"`.
- `src/belief/crew_console.py` — `_resolve_attack_target` (Decision 14's tie-break, reusing
  `_report_scope` directly, not `_resolve_follow_target`), `_parse_target_slots`,
  `_handle_select_target`, `_handle_drop_target`, `drain_attack_run` (Stage 3, unwired); dispatch
  branches for `select_target`/`drop_target`; both added to `DISPATCHED_COMMAND_TOKENS`;
  `_describe_task_for_speech`/`_describe_token_for_confirm` branches for the new kind/token.
- `src/belief/console.py` — `attack-target <id>` debug command, mirroring `watch-task <id>`
  (needed so the pre-existing `test_console_module_contains_no_belief_logic` structural check,
  which requires every public `tools.py` function to be referenced somewhere in `console.py`,
  keeps passing against the new `attack_target_task`).
- `docs/STRUCTURE.md`, `CLAUDE.md` (module map), `ROADMAP/BL-14.md` — registered.

**audio-adapter**

- `src/vocabulary.py` — `select_target`/`drop_target` added to `VOICE_ONLY_TOKENS`; `PHRASES`
  entries for both (slots parsed, not enumerated, for `select_target`; one exact phrase for
  `drop_target`).
- `src/command_matcher.py` — `_SELECT_TARGET_VERBS = ("select", "set")`, `_parse_select_slots`
  (the same five-slot schema `_parse_report_slots` already parses, requiring the literal word
  `"target"`), and a `match_transcript` branch tried before the generic phrase table, after
  `follow`/`report`.

### Tests Added

- `body-layer/tests/test_attack_run.py` (new) — the grep fence (word-boundary-aware regex, so it
  does not false-positive on `body_relative_direction`/`alignment_direction`); `decide`'s silence
  cases (no percept, stale relative observation); dead-ahead lining-up and the once-then-silence
  rule; outside-sector o'clock; the 9°-heading-apart re-rotation pin (Decision 16's own named
  test); the banked-vs-level agreement (the bank-stabilisation no-regression claim); the
  change-driven cadence resuppressing an unchanged repeat; `render_alignment`'s register switch
  (o'clock / come / a bit / lined up / left-right sign / elevation combination / elevation-only);
  tier 2 raising `NotImplementedError`; both axes sharing one table-lookup helper; the three
  constants' values.
- `body-layer/tests/test_geometry.py` — `signed_angular_delta_deg` (right-positive,
  left-negative, the `+180` boundary, zero); `alignment_direction` agreeing with
  `body_relative_direction(..., bank_deg=0.0)`, and an oblique-heading/banked-observer case
  distinguishing it from the full bank-mixed frame.
- `body-layer/tests/test_estimation.py` — `RELATIVE_DIRECTION_SIGMA_DEG == 0.0`;
  `perturbed_relative_direction` is a true identity at that sigma, including the degenerate
  zero-offset case (no division by zero).
- `body-layer/tests/test_clustering.py` — `Cluster.centroid_alt_m` is the mean of two members'
  own altitudes (not ownship's).
- `body-layer/tests/test_naked_eye_source.py` — an admitted single-candidate cluster with clear
  live LOS carries a `relative_direction` with the expected yaw-removed offset; the detection
  trace records `relative_direction_set=True` on the same admission; a blocked candidate never
  reaches emission at all (so there is no reachable "admitted but unclear" case to test a fold
  disagreement against — gate 4 is fail-closed, confirmed by reading `visibility.py` rather than
  assumed).
- `body-layer/tests/test_tools.py`, `test_tasks.py` — `attack_target_task` mirrors
  `watch_contact_task`'s own three tests (marks + registers, unknown contact, cancel returns
  attention to normal) plus the never-resolves-via-`tick` test.
- `body-layer/tests/test_crew_console.py` — `select_target` resolving and setting `"priority"`;
  no-qualifiers say-again; no-match; group-mates tagged `"watch"` not `"priority"`; `drop_target`
  cancelling; `drop_target` with nothing selected; the existing all-modes `cancel_task` also
  dropping the target.
- `audio-adapter/tests/test_command_matcher.py` — `select target`/`set target` resolving with
  slots; the `"target"`-word requirement (an adversarial `"set the throttle to idle"` must not
  false-fire); `drop target`'s exact-phrase match.

### Checks

**body-layer/**

- `ruff format --check src tests`: pass (126 files formatted)
- `ruff check src tests`: pass
- `mypy src` (CWD-only config, run from `body-layer/`): pass, no issues in 58 source files
- `pytest`: pass — 1790 passed, 4 xfailed

**audio-adapter/**

- `ruff format --check src tests`: pass (29 files formatted)
- `ruff check src tests`: pass
- `mypy src` (CWD-only config, run from `audio-adapter/`): pass, no issues in 15 source files
- `pytest`: pass — 261 passed, 1 skipped

(`mypy tests` on both subprojects reports pre-existing failures unrelated to this change — not
part of the mandated gate per each subproject's own `CLAUDE.md` "Commands" section, which names
`mypy src` only. `test_attack_run.py` itself is clean under `mypy` regardless.)

### Notable Discoveries

- **The plan's Decision 16 claim that "`ContactStore` already keeps the latest percept per
  contact" was not true before this change.** `Contact` only ever pulled individual fields out of
  a `Percept` (`last_class_raw`, `live_los_clear`, ...); nothing retained the whole object. Adding
  `Contact.last_percept` was necessary to make that sentence true, and it had to be done carefully
  against the plan's own grep fence: a field literally named anything containing
  `relative_direction`, or importing the `RelativeDirection` type, inside `contacts.py` would
  itself violate Decision 16 item 4's "no file under `belief/` may mention `relative_direction`
  except `percept.py`/`attack_run.py`". Storing the whole `Percept` (a name `contacts.py` already
  uses constantly) sidesteps this: `contacts.py` never writes the literal string
  `relative_direction` anywhere, and `belief.attack_run` reaches the field through `contact.
  last_percept.relative_direction` instead of a dedicated per-field store.
- **A naive grep fence would have false-positived on `body_relative_direction`/
  `alignment_direction`.** Both legitimately contain the substring `relative_direction` (and
  `contacts.py` already imports/uses `body_relative_direction`). The fence test uses a
  word-boundary-aware regex (`\brelative_direction\b|\bRelativeDirection\b`) rather than a bare
  substring check for this reason — `_` is a word character in Python's regex engine, so `\b`
  correctly does not fire inside `body_relative_direction`.
- **Gate 4 (`visibility.check_visibility`'s terrain-LOS check) is fail-closed as of `BL-11`
  Stage 4**, confirmed by reading `visibility.py` rather than assumed: a candidate's own
  `live_los_clear` must be exactly `True` to be admitted at all. This means the cluster-level
  "members disagree on LOS" case `naked_eye_source._build_observation`'s own docstring describes
  (`live_los_clear = next(iter(member_los)) if len(member_los) == 1 else None`) can never actually
  be reached by an *emitted* observation — every member that made it into `visible` already had
  `True`. A planned negative test (blocked member in an otherwise-admitted cluster) was dropped
  for this reason; it would have tested nothing beyond the pre-existing gate-rejection behaviour.
- **`render_alignment` and the two word tables could not both live where the plan's Affected
  Modules section literally places them without a circular import.** The plan assigns the
  `render_alignment_*` family to `speech.py` and the constants/tables to `attack_run.py`
  (Decision 11 REVISED: "declared in `attack_run.py`"). If `speech.py` imported the tables from
  `attack_run.py` to build its own copies, and `attack_run.py` imported `render_alignment` from
  `speech.py` to render with them, the two modules would import each other. Resolved by having
  `attack_run.py` pass its own tables into `render_alignment` as plain data arguments
  (`azimuth_table=`/`elevation_table=`) rather than `speech.py` importing them — `belief.speech`
  ends up with zero dependency on `belief.attack_run`, and `belief.attack_run` has exactly one
  dependency on `belief.speech` (importing `render_alignment`/`OutgoingSpeech`). Not called out
  anywhere in the plan; worth knowing before Stage 6 adds the tier-2 renderer, which should follow
  the same data-in shape.
- **Decision 5's `callouts.py` gate (`_WATCHED_ONLY_KINDS` suppression for the attack-run
  target) is explicitly Stage 5 work, not Stage 1-3**, confirmed by re-reading the plan's own
  staging rather than assumed from the decision text alone. This means selecting a target in
  Stages 1-3 sets its attention to `"priority"`, which — since `effective_attention in ("watch",
  "priority")` already gates `_WATCHED_ONLY_KINDS` — *does* enrol it in watched-only callouts
  (`CONTACT_RANGE_CROSSED` included) with no suppression yet. That is the intended, documented
  gap this stage leaves open, not an oversight: Decision 5's own gate closes it, and that gate is
  Stage 5.

### Stage 4/5 Implementation Summary (2026-10-14, second pass)

Stages 4 (`step`) and 5 (`engage`/`disengage`, the wired tier-1 guidance loop, the gaze claim, the
suppression gate, the speech-log fields) of `plans/attack-run/plan.md`, per the orchestrator's
explicit scope. Stages 6-7 (tier 2, projected position) are **not** built — `render_alignment`
still raises `NotImplementedError` for `tier=2` and no caller ever passes it.

#### Files Changed

**body-layer**

- `src/belief/tasks.py` — `PendingIntent.descriptor: str | None = None` (Decision 6) — the
  `<what>` descriptor heard on the selecting command, remembered so `step` can filter its
  candidate set the same way without re-parsing the original text. `TaskStore.create` gained a
  matching `descriptor` keyword.
- `src/belief/tools.py` — `attack_target_task` gained `descriptor: str | None = None`, threaded
  into `tasks.create`.
- `src/belief/speech.py` — `render_engage_readback(facts)` (range spoken once, plus the terrain
  acquisition fragment, deliberately **not** sharing `_contact_report_text`'s count/motion
  clauses, which this milestone's vocabulary never calls for); `render_attack_run_off()`
  (`"Attack run off."`); two new `_UNABLE_TEMPLATES` entries (`NO_GROUP_MEMBERS`/`LAST_IN_ORDER`,
  Decision 6's own two closed `step` reasons — the plan's pseudocode phrases are not themselves a
  valid `render_unable` argument, since that function only maps a closed reason token to text);
  `render_alignment`'s `tier` parameter narrowed from `int` to `Literal[1]` (the Stage 1-3 review's
  first optional refinement).
- `src/belief/crew_console.py` — `attack_run_transition: Literal["engage", "disengage"] | None`
  field (the one-shot signal to the poll loop, since `AttackRunState` lives on `logger.
  ConsolePerceptionRunner`, not this class); reset alongside `last_command_target_contact_id` at
  the top of every `handle_command` dispatch; `_active_attack_target_task()` (factored out of
  `drain_attack_run`'s own lookup, now shared with `_handle_step`/`_handle_engage`);
  `_step_candidates`/`_handle_step` (Decision 6's ordering primitive); `_handle_engage`/
  `_handle_disengage` (Decision 15/2); `drain_attack_run` extended with Decision 13's end
  condition (contact record vanished -> `render_lost_contact` once, cancel the task, return
  `None`) and the speech-log `attack_run_fields` payload; `drain_events` now resolves the current
  attack-run target id and passes it to `scheduler.tick`; `_print`/`speech_log_sink` gained a
  fourth/third `attack_run_fields` parameter; `step`/`engage`/`disengage` added to `handle_command`'s
  dispatch table, `DISPATCHED_COMMAND_TOKENS`, and `_describe_token_for_confirm`;
  `_handle_select_target` now passes `descriptor=` through to `attack_target_task`.
- `src/belief/callouts.py` — `CalloutScheduler.tick` gained `attack_run_target_contact_id: str |
  None = None`; one narrow check at the top of the `_WATCHED_ONLY_KINDS` branch suppresses (lost,
  not deferred — `_consumed.add`) any watched-only event about that one contact id, Decision 5's
  gate.
- `src/belief_truth_log.py` — `BeliefTruthLogWriter.write_speech` gained four optional keyword
  arguments (`attack_run_target_contact_id`/`attack_run_tier`/`attack_run_azimuth_deg`/
  `attack_run_elevation_deg`), absent-not-null like the existing gaze/optic fields.
- `src/logger.py` — `ConsolePerceptionRunner.attack_run_state: AttackRunState | None = None`;
  `_active_gaze` gained `store`/`ownship`/`attack_run_engaged` keyword-only parameters and a
  branch, checked before the `scan_area` loop, that returns a `ScanPlan.fixed_look_at` toward the
  target's own believed bearing/elevation (`perception.geometry.alignment_direction`, bank
  removed) while engaged (Decision 9 REVISED); `run_once`'s own call site updated to pass them;
  `_speech_log_sink`'s callable type and closure gained the `attack_run_fields` parameter,
  forwarded into `write_speech`'s four new keywords; `_run_crew_text_poll_loop` applies the
  `engage`/`disengage` transition and calls `drain_attack_run` immediately before `drain_events`.
- `src/belief/voice_commands.py` — `drop_target`/`disengage` added to `CANCEL_TOKENS`.

**audio-adapter**

- `src/vocabulary.py` — `"step"`, `"engage"`, `"disengage"` added to `VOICE_ONLY_TOKENS` with
  `PHRASES` entries; `STEP_DIRECTION_WORDS`/`parse_step_direction`, `parse_step_count` (digits and
  number words 1-9); `WEAPON_WORDS`/`parse_weapon`.
- `src/command_matcher.py` — `_STEP_VERB`, `_ENGAGE_VERBS`, `_parse_step_slots`,
  `_parse_engage_slots`, and two new branches in `match_transcript`, ordered after the
  `select_target` branch and before the generic phrase table (the plan's own stated ordering
  rule).

#### A plan gap found and resolved: `attack`/`attack-run` as an `engage` synonym

The plan's own Decision 15 and the spec document (`docs/concept/Attacking target.md`) both name
`attack`/`attack-run` as legal synonyms for `engage` — `"engage/attack/attack-run <what>
<where>"`. Implementing that (both as a bare phrase and as `_ENGAGE_VERBS`' second verb) made
`vocabulary._derive_verb_anchor_words()` pick up `"attack"` as a `VERB_ANCHOR_WORDS` member (its
derivation takes the first word of every phrasing of every token, the module's own documented,
deliberate behaviour). Measured directly: `difflib.SequenceMatcher(None, "tanks",
"attack").ratio() == 0.545`, just over `command_matcher.VERB_FLOOR` (0.5). That flips audio-
adapter's own pinned adversarial-sentence test,
`test_non_command_speech_enqueues_with_null_token` (`"the tanks are on the ridge"`), from
`verb_anchored=False` (falls through to free speech, the correct behaviour for an ordinary
descriptive remark) to `verb_anchored=True, token=None` ("say again") — a real behaviour change
for that sentence, not a cosmetic one, since `verb_anchored` is part of `MatchResult`'s own public
contract and decides which disposition the caller takes.

Per this role's own rules ("do not modify existing tests without explicit permission"; the
Escalation Rules' "existing tests must be rewritten rather than extended" case), this was not
resolved by editing the pinned test. **`attack`/`attack-run` are not admitted as `engage`
synonyms in this implementation** — `engage`/`engage target` (the tokens Stage 5's own wiring
actually dispatches) are built, `disengage`/`stop attack`/`abort` are unaffected (none of them
make `"attack"` a first word), and the gap is recorded in `vocabulary.PHRASES["engage"]`'s own
comment and `command_matcher._ENGAGE_VERBS`' comment so it is not silently rediscovered. Flagging
this explicitly rather than quietly narrowing scope: if the user wants the `attack`/`attack-run`
synonym badly enough to accept weakening that adversarial test's guarantee (or to find a
differently-worded fix), that is a decision for Architect/the user, not one to make unilaterally
inside an implementation pass.

#### Tests Added

- `body-layer/tests/test_crew_console.py` — `_observation_at_xz`/`_enrichment_context_with_
  ownship`/`_inject_group`/`_target_left_right_fixture` (new helpers); `step` right/left picking
  the correct bearing-ordered neighbour and swapping which is "watch"/"priority";
  **`test_step_recomputes_order_from_ownships_present_position`** — the task's own named
  requirement: the identical `step right` command, same standing selection, picks a *different*
  unit when ownship has moved to the far side of the formation (verified by direct computation of
  `signed_angular_delta_deg` from both vantage points before the fixture was written, not
  assumed); stop-at-the-end (`render_unable("LAST_IN_ORDER")`, no wrap); ungrouped target
  (`render_unable("NO_GROUP_MEMBERS")`); no target selected; `near`/`far` ordering by range,
  reusing the existing `_cohering_contacts_across_a_band_boundary` fixture (with `descriptor=None`
  — see "Notable Discoveries" below for why); `engage` with slots (select-then-engage), bare
  `engage` (resumes selection), the weapon slot accepted and ignored, no target selected;
  `disengage` keeping the selection while clearing `attack_run_transition`, and speaking
  unconditionally with no run active; `drain_attack_run`'s no-op while unengaged and Decision 13's
  end condition (contact record deleted mid-run -> `render_lost_contact`, task cancelled).
- `body-layer/tests/test_callouts.py` — the attack-run target's own `CONTACT_RANGE_CROSSED` is
  suppressed when named via `attack_run_target_contact_id`, and a second, differently-id'd
  `"priority"` contact's own range crossing is unaffected (Decision 5's narrow scope).
- `body-layer/tests/test_logger.py` — `_active_gaze`'s attack-run branch: claims a `fixed_look`
  at the target's believed position while engaged (overriding a standing `scan left`, the case
  that settled Decision 9 REVISED), falls through when not engaged, and is a true no-op when
  `store`/`ownship` are omitted; `_speech_log_sink` forwards the four attack-run fields (and
  omits them, as `None`, for an ordinary line) — this function had no pre-existing test at all.
- `body-layer/tests/test_tasks.py`/`test_tools.py` — `attack_target_task`'s new `descriptor`
  parameter, stored and defaulting to `None`.
- `body-layer/tests/test_voice_commands.py` — `drop_target`/`disengage` are members of
  `CANCEL_TOKENS` (the existing `test_every_cancel_token_is_held_to_the_higher_floor` already
  asserts the *behaviour* generically; this pins the *membership*).
- `body-layer/tests/test_speech.py` — `render_engage_readback` (range/clock, terrain fragment,
  the no-`relative_now` degrade), `render_attack_run_off`, the two new `render_unable` reasons.
- `body-layer/tests/test_belief_truth_log.py` — `write_speech`'s four new fields, present and
  absent.
- `audio-adapter/tests/test_command_matcher.py` — `step`'s slotted resolution (direction, count,
  near/far synonyms), no-direction fallthrough; `engage`'s slotted resolution, the weapon slot,
  the bare-form fallthrough to the phrase table with `slots=None`, the `attack` synonym's
  deliberate absence; `disengage`'s three phrasings.
- `audio-adapter/tests/test_vocabulary.py` — `parse_step_direction`/`parse_step_count`/
  `parse_weapon` against every table entry, the band-style transcript-order tie-break, and the
  no-match cases.

Not added: a threaded integration test of `_run_crew_text_poll_loop`'s own engage/disengage-
transition-and-`drain_attack_run` wiring block. The precedent for driving that function in a real
thread (`test_crew_text_poll_loop_logs_the_coverage_summary_in_its_finally_block`) needs a built
world-model region and a live aircraft-layer-client fake; every piece the wiring composes
(`drain_attack_run`, `_active_gaze`'s branch, the `attack_run_transition` signal/consumption) is
unit-tested directly instead, the same proportionality `_apply_active_gaze`'s own existing tests
already apply to a comparable glue block.

#### Checks

**body-layer/**

- `ruff format src tests`: pass (4 files reformatted)
- `ruff check src tests`: pass
- `mypy src` (CWD-only config, run from `body-layer/`): pass, no issues in 58 source files
- `pytest tests -q`: pass — 1820 passed, 4 xfailed (baseline 1790 passed / 4 xfailed + 30 new
  tests)

**audio-adapter/**

- `ruff format src tests`: pass (no files needed reformatting)
- `ruff check src tests`: pass
- `mypy src` (CWD-only config, run from `audio-adapter/`): pass, no issues in 15 source files
- `pytest tests -q`: pass — 277 passed, 1 skipped (baseline 261 passed / 1 skipped + 16 new
  tests)

(`mypy tests` on both subprojects reports pre-existing failures unrelated to this change, the
same non-mandated-gate note the Stage 1-3 pass recorded — confirmed again this pass: every
reported line in `test_speech.py`/`test_crew_console.py`/`test_logger.py`/`test_callouts.py`
that is not one of this pass's own new lines was already failing before this branch, and this
pass's own three new `# type: ignore[attr-defined]` comments on direct `_groups`/`_contacts`
dict access match the exact style `test_callouts.py`'s own pre-existing `Group` injection already
uses, line for line.)

#### Notable Discoveries

- **`step`'s "recomputed from ownship's present position" claim needed a geometry fixture no
  existing test helper could build.** `_observation_for_follow`'s clock-quantised placement (30°
  per hour) is far too coarse to place two candidates a few degrees apart, and reconciling a real
  `belief.groups.Group` at that separation would fight (or accidentally satisfy for the wrong
  reason) the real cohesion-gap formula `GroupStore.reconcile` uses. `_observation_at_xz` (explicit
  `x`/`z`) plus `_inject_group` (direct `store._groups._groups[...]` injection, mirroring
  `test_callouts.py`'s own precedent for the identical reason) sidestep both: the candidate
  geometry is exact and the group membership is asserted rather than fought for. The mirror-flip
  construction (ownship on the *opposite* side of the target from where it started, along the
  same axis) was verified by running `perception.geometry.bearing_deg`/`signed_angular_delta_deg`
  directly before the fixture was written, not derived by hand — trigonometry sign conventions are
  exactly the kind of thing worth checking against the real function rather than assumed.
- **The near/far ordering test's first draft was wrong for a reason that is itself worth
  recording**: reusing `_cohering_contacts_across_a_band_boundary`'s three-type group
  (armour/truck/infantry) with `descriptor="armor"` set on the task made `_step_candidates` filter
  out the truck/infantry members as `"wrong"` before range ordering ever ran — Decision 6's own
  descriptor filter working exactly as designed, not a bug. The fix was `descriptor=None` on the
  task, which is also the more honest test: it isolates the range-ordering mechanism from the
  descriptor filter, which is `select_target`'s own concern and already covered elsewhere.
- **The gaze claim's geometry test did not need a full `run_once()`/`NakedEyePerceptionSource`
  end-to-end drive.** `_active_gaze` already took `heading_true_deg` as a plain argument before
  this change, and the new `store`/`ownship`/`attack_run_engaged` parameters are read the same
  way — a direct unit test against a two-task `TaskStore` (one `attack_target`, one `scan_area
  left`, so the override is actually proven, not merely the absence of a competing claim) and a
  one-contact `ContactStore` is enough to pin the override order precisely, matching this file's
  own existing `_active_gaze` test convention (every one of its ~15 pre-existing tests calls it
  directly, none through `run_once`).

### Stage 4-5 review fixes (2026-10-14)

Both required fixes from `plans/attack-run/review.md`'s Stage 4-5 pass, applied to
`body-layer/src/belief/crew_console.py::CrewConsole.drain_attack_run`. No other file changed;
no constants tuned; no stage 6/7 work added.

**Fix 1 (occupancy falsely marks a line "spoken").** `decide_attack_run` always returns a
`new_state` with `last_spoken_*` already updated for the line it wants to say, before the caller
ever checks `self.scheduler.busy_until_sim`. `drain_attack_run` used to return that `new_state`
unconditionally, so a line suppressed by occupancy was recorded as if it had been heard, and
`_should_emit`'s change-driven baseline then measured against a baseline nobody actually spoke.

Fix: branch on whether the print actually happened. `speech is None` returns `new_state`
unchanged (no-op path, same as before). `speech is not None` and the channel is free: print and
return `new_state`, unchanged behaviour. `speech is not None` and the channel is busy: return the
**previous** `state` (not `new_state`), so `last_spoken_*` stays at whatever was last actually
spoken.

**Decision: drop the suppressed line, do not queue it.** The task explicitly ruled out adding a
queue (the scheduler's own deferral machinery is for the push path, not the reply lane this method
is on), so the only two options were drop-and-rely-on-re-evaluation or build a pending-line marker.
Dropping is correct here because carrying the previous `state` forward is self-correcting: the next
`drain_attack_run` call re-derives the same (or a further-drifted) alignment from live geometry —
tier 1 has no memory of what it *meant* to say, only what it last *did* say — and `_should_emit`
compares against the untouched baseline, which still differs from the current text/azimuth/
elevation exactly as much as it did on the suppressed tick (or more, if the geometry kept moving).
So the same change is re-offered on the very next tick the channel is free, with no gap in
coverage and no stale backlog to drain once it is. Verified directly in
`test_drain_attack_run_reoffers_the_line_once_the_channel_frees` and
`test_drain_attack_run_first_utterance_after_engage_survives_a_busy_channel`.

**Fix 2 (`drop target`/generic `cancel`/`stop` never clear the gaze claim).** `drain_attack_run`'s
top-of-function guard — "is there still an active `attack_target` task?" — used to `return state`
(the unchanged, still-non-`None` state) once the task was gone, rather than `None`. `disengage` and
the vanished-contact branch both already correctly produce `None`; this guard was the one path that
did not, and it is the single chokepoint every task-gone case (not only `drop target` — the generic
all-kinds `cancel_task` token hits the identical guard, since it cancels every active task
regardless of kind) passes through. Fix: return `None` instead of `state`. `logger.py`'s poll loop
assigns the return value straight onto `runner.attack_run_state`, so this is also what
`_active_gaze`'s `attack_run_engaged` flag reads — the single-guard fix is therefore what makes it
hold for the generic cancel path too, without a second change anywhere.

**Fail-then-pass evidence (both fixes).** For each fix, the new tests were run once against the
code with only that fix reverted (the other fix left in place), confirmed to fail for the exact
stated reason, then the fix was restored and the full `drain_attack_run`-selected test set
re-confirmed green:

- Fix 1 reverted: `test_drain_attack_run_reoffers_the_line_once_the_channel_frees` and
  `test_drain_attack_run_first_utterance_after_engage_survives_a_busy_channel` both failed on
  `assert busy_state == AttackRunState()` — the busy-tick return value carried a non-`None`
  `last_spoken_azimuth_deg=5.71...`/`last_spoken_text='A bit right.'` though nothing had been
  printed, exactly the "marked spoken but never heard" defect the review named. The other four
  `drain_attack_run` tests (including both Fix 2 tests) stayed green.
- Fix 2 reverted: `test_drain_attack_run_ends_the_run_after_drop_target` and
  `test_drain_attack_run_ends_the_run_after_the_generic_cancel_task` both failed on
  `assert result is None`, returning the stale `AttackRunState(...)` instead — the engaged flag
  surviving a cancelled task, exactly as reported. The other four stayed green.

### Tests Added (Stage 4-5 review fixes)

All in `body-layer/tests/test_crew_console.py`, alongside a new local helper
`_attack_run_contact_off_boresight` (mirrors `test_attack_run.py`'s own
`_contact_with_relative_direction`, inserted directly into `store._contacts` the same way the
existing vanished-contact test already reaches into that dict):

- `test_drain_attack_run_reoffers_the_line_once_the_channel_frees` — busy tick (nothing printed,
  state unchanged) followed by a freed tick with the same unchanged geometry (line now spoken).
  No `engage` involved; isolates the occupancy mechanism from the command path.
- `test_drain_attack_run_first_utterance_after_engage_survives_a_busy_channel` — the realistic
  casualty the review named: `engage`'s own readback claims the channel via `note_reply`, and the
  very next `drain_attack_run` tick (same `now_sim` the readback was spoken at) must not be lost
  once the channel frees. The percept is refreshed to a current `t_sim` immediately before the
  freed-tick call (same geometry) to stay inside `ATTACK_RUN_RELATIVE_MAX_AGE_S` — the engage
  readback's own realistic occupancy duration (~5 s, from its word count) is longer than tier 1's
  2 s staleness window, which a live naked-eye channel would never hit since it re-observes every
  poll; the test approximates that by re-inserting a contact with the identical relative offset at
  the later `t_sim`.
- `test_drain_attack_run_ends_the_run_after_drop_target` — `engage` then `drop_target`; asserts
  the standing task is cancelled and the next `drain_attack_run` call returns `None`.
- `test_drain_attack_run_ends_the_run_after_the_generic_cancel_task` — same shape, through the
  generic `cancel_task` token instead, confirming the single-guard fix covers that path too.

### Checks (Stage 4-5 review fixes)

**body-layer/**:
- `ruff format --check src tests`: pass (126 files)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 58 source files`
- `pytest tests -q`: **1824 passed, 4 xfailed** (baseline 1820 passed / 4 xfailed + 4 new tests)

**audio-adapter/** (no file in this subproject touched by this pass; run anyway to confirm no
regression):
- `ruff format --check src tests`: pass (29 files)
- `ruff check src tests`: pass
- `mypy src`: `Success: no issues found in 15 source files`
- `pytest tests -q`: **277 passed, 1 skipped** — matches the baseline exactly

### Notable Discoveries (Stage 4-5 review fixes)

- **The engage readback's own realistic occupancy duration exceeds tier 1's staleness window.**
  `estimate_speech_duration_s`'s placeholder rate (`MIN_UTTERANCE_S` + word_count /
  `SPEECH_RATE_WPS`) puts the `engage` readback used in these tests (11 words) at ~5.0 s of
  claimed channel time, while `ATTACK_RUN_RELATIVE_MAX_AGE_S` is 2.0 s. In a live flight this never
  collides — the naked-eye channel re-observes every poll, so the percept backing tier 1's
  alignment is never more than one poll interval old regardless of how long the channel stays busy
  — but it meant the busy-then-free test fixture needed to refresh the contact's percept before
  the freed tick, or the channel freeing would coincide with tier 1 going silent for an unrelated
  reason (staleness, not occupancy) and the test would not isolate what it claims to. Worth
  flagging for whoever next touches either constant: the two numbers are not currently related by
  any invariant, and a slower placeholder speech rate or a longer typical readback would make this
  collision real rather than a test-fixture artifact.
