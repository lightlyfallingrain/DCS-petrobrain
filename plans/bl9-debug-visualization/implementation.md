### Implementation Summary

Built the trace-only slice the plan recommended: `check_visibility` now records which of its
three gates decided each candidate's fate (or that it was admitted), `NakedEyePerceptionSource`
annotates admitted candidates with cluster/observation detail once clustering and emission have
run, a new read-only module joins that against belief to resolve `Contact` ids, `logger.py` wires
it behind `--detection-trace PATH` (requires `--console` or `--crew-text`), and
`tools/summarize_detection_trace.py` reduces a raw trace into the per-object first-admitted-range
table and the never-admitted-but-in-FOV list the plan specified as the actual deliverable.

### Files Changed
- `body-layer/src/perception/detection_trace.py` (new) — `GateOutcome`, `DetectionTrace`
  (mutable, so a poll's cluster/observation detail can be added after the fact),
  `DetectionTraceCollector` (`record`/`annotate_admission`). Pure perception-layer types, no
  `belief/` import.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains `trace:
  DetectionTraceCollector | None = None`. `range_threshold_m`/`threshold_bound` are computed and
  recorded unconditionally (even on a `COCKPIT_MASK` failure), since the angular-size/range-cap
  threshold only depends on `object_type`, not on which gate actually ran — this gives every trace
  row a uniform shape rather than leaving those fields `None` on the two earlier-firing gates.
  `threshold_bound` is `"range_cap"` vs `"size_curve"` depending which term of the existing
  `min()` binds. No change to the function's existing return value or gate order.
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains
  `trace_sink: DetectionTraceCollector | None = None`, threaded into every `check_visibility` call.
  After `_build_observations` runs, `poll()` annotates each admitted candidate's trace entry
  (`annotate_admission`) with its cluster's member `object_id`s and the emitted `Observation.id`,
  using `zip(clusters, observations)` (index-aligned by construction). A candidate that cleared
  the gate but got throttled out of `to_emit` by `NAKED_EYE_MAX_NEW_PER_POLL` stays `ADMITTED`
  with no cluster/observation detail — intentional, and itself useful debrief information
  ("visible, but throttled"), not a gap.
- `body-layer/src/detection_trace_writer.py` (new) — `DetectionTraceWriter`, the one module
  allowed to see both sides: joins a poll's `DetectionTraceCollector` records against a
  `ContactStore` by scanning `Contact.contributing_observation_ids` for each entry's
  `observation_id` (rebuilt fresh every poll — an accepted `O(contacts × history)` cost for a
  single-sortie debug artifact, not a standing index), writes one JSON line per record, and clears
  the collector. Buffers `DEFAULT_FLUSH_EVERY_N_POLLS` (5) polls before flushing. Never calls
  anything that mutates `ContactStore`; `belief/` gains no import of this module or of
  `detection_trace.py`.
- `body-layer/src/logger.py` — `--detection-trace PATH` (`parser.error` without `--console` or
  `--crew-text`). `_build_sources` gains an optional `trace_sink` parameter, only ever wired into
  `NakedEyePerceptionSource`. Both `_run_console_poll_loop` and `_run_crew_text_poll_loop` build a
  collector + writer when the flag is set, and call `writer.write_poll(collector, runner.store)`
  immediately after `runner.run_once()` — after that poll's `ingest`/`tick` have already run, so
  writing the trace can never influence what was ingested. Writer is closed in the loop's
  `finally`, alongside the world-model connection.
- `body-layer/tools/summarize_detection_trace.py` (new) — reads a `--detection-trace` JSONL file
  and prints: per object, first-admitted range at each tier (presence/class/type); and the list of
  objects that cleared the cockpit mask (`outcome != "cockpit_mask"` at least once) but never
  reached `"admitted"` — labelled in its own output as an approximation, not a verified claim, per
  the plan's Risks section. Not a test, matching `speak_samples.py`'s precedent.
- `body-layer/tests/test_detection_trace.py` (new) — gate-outcome classification (all four
  outcomes, including which term of `min()` binds for both a size-curve-bound and a
  range-cap-bound candidate), the cluster/observation annotation (including the
  admitted-but-throttled case), the belief join against a small in-memory `ContactStore`, and the
  behavioral-equivalence check (see below).
- `body-layer/CLAUDE.md` — documents `--detection-trace` and the three new modules, following this
  file's existing per-flag/per-module convention; added a short cross-reference note to the
  `visibility.py` and `naked_eye_source.py` entries.

### Tests Added
- `test_cockpit_mask_failure_is_recorded_with_no_achieved_tier`,
  `test_range_or_size_failure_records_size_curve_bound`,
  `test_range_or_size_failure_records_range_cap_bound`, `test_terrain_los_failure_is_recorded`,
  `test_admission_records_achieved_tier`, `test_trace_none_is_a_true_no_op` — one per gate outcome
  plus the two `threshold_bound` branches.
- `test_admitted_candidates_are_annotated_with_cluster_and_observation_id`,
  `test_gate_rejected_candidates_are_never_annotated`,
  `test_admitted_but_throttled_candidate_stays_unannotated` — the annotation step, including the
  cap-throttle edge case the plan's Stage 3 explicitly called out.
- `test_trace_sink_does_not_perturb_the_observation_contact_or_event_streams` — the plan's own
  "how will I know it doesn't perturb what it measures" answer: `replay.py` driven twice over the
  same fixture sequence (trace attached vs. not), asserting identical `Observation` streams
  (all fields except the legitimately-varying wall-clock `t_wall`), identical `Contact.id`
  ordering/`last_position`/`classification`/`contributing_observation_ids`, and identical `Event`
  streams.
- `test_writer_joins_admitted_entry_to_its_contact`, `test_writer_leaves_contact_id_null_when_never_admitted`,
  `test_write_poll_clears_the_collector` — the belief join and the writer's per-poll buffer
  discipline.

### Checks
(`body-layer/`)
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (run as `cd body-layer && mypy src`, per this project's mypy-CWD gotcha): pass, 37
  source files
- `pytest tests -q`: pass, 732 tests (13 new)

### Verified against real data
No live DCS session was available (per this project's execution-boundary rule, a real full-theatre
or live-DCS run is never something this agent executes). Instead, drove `NakedEyePerceptionSource`
+ `DetectionTraceWriter` through `replay.py` over the committed `tests/fixtures/telemetry_frames.json`
sequence with three synthetic world-objects (one admitted at `hires`, one admitted only at
`lowres`, one rejected by the range cap), producing a real 3050-byte JSONL trace, then ran
`tools/summarize_detection_trace.py` against it. Output:

```
First-admitted range per object (metres, nearer-tier-first):
 object_id  type                        presence       class        type
       101  Infantry                           -           -          50
       102  T-72B                           2023           -           -
       103  Kilo                               -           -           -

Cleared the cockpit mask (plausibly on screen) but never admitted at any tier -- an approximation, not a verified claim (see module docstring):
  object_id=103  object_type=Kilo
```

This confirms the reducer correctly separates "admitted, first at this range" from "cleared the
mask but never admitted" using only a synthetic replay trace, not a live sortie. Real-sortie
volume/pacing (`t_sim` gaps, poll cadence under real network jitter) is still unverified — first
real flight is the actual test of that.

### Notable Discoveries
- The plan's own worked example ("failed medres at 3.4 km, passed at 2.1 km") describes a
  *tier-boundary* crossing on one still-admitted object. The reducer as specified instead reports
  the first-admitted range *per tier* (presence/class/type), which is the more useful reduction of
  the same underlying data (it directly answers "at what range did he first say X") but does not
  literally print a rejected-then-passed pair the way the example phrasing suggests. Flagging this
  in case a future debrief wants an explicit tier-transition table as a second view — not built
  here, since the plan's own Affected Modules section only asked for the first-admitted-range
  table and the never-admitted list.
- `DetectionTrace.range_threshold_m`/`threshold_bound` being computed unconditionally (even before
  the cockpit-mask gate runs) is a deliberate departure from the absolute-minimum-computation
  reading of "no change to gate order" — it moves two cheap, pure-function calls
  (`object_model.profile_for`, one `min()`) earlier than they'd otherwise run, always, regardless
  of whether `trace` is set. This was chosen over gating the eager computation behind
  `trace is not None` because the cost is negligible (a dict lookup and one arithmetic
  expression) and duplicating the whole gate ladder into a traced/untraced branch would have been
  a much larger, more error-prone diff for no measurable benefit — the behavioral-equivalence test
  is what actually backs this judgment call, not just the reasoning.

### Open decisions (per the plan, not settled by this implementation)
- **Trace-only vs. trace-plus-live-view**: built trace-only, per the plan's own recommendation.
  Not affirmed by the user (they were flying, per the task brief) — still open. If the first real
  sortie shows the post-flight trace insufficient (e.g. needing to correlate a gate outcome with
  what was on screen at that instant), a live/replay-driven visual becomes a justified follow-up
  slice, not a guess built ahead of evidence.
- **Flush cadence and default path**: implemented `flush_every_n_polls=5` (`DEFAULT_FLUSH_EVERY_N_
  POLLS` in `detection_trace_writer.py`) and no default path — `--detection-trace` requires an
  explicit `PATH`, matching `--mission-understanding`'s existing convention. Both are picked, not
  confirmed: 5 polls (~5s at the default 1s poll interval) favors "a few polls" over "as rarely as
  possible" per the plan's own risk note, but is otherwise an uncalibrated placeholder, same debt
  class as `visibility.py`'s tier constants or `F10_SCAN_RADIUS_M`.
