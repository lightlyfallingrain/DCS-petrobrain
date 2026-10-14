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
