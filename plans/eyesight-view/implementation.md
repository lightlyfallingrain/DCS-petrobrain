### Implementation Summary

Real-time ASCII eyesight view (`--eyesight-view`) plus a ground-truth/belief
consistency log (`--belief-truth-log`), both flag-gated and additive
(true no-op when absent), built directly from the orchestrator's brief and
two mid-task corrections (5km default radius with off-edge indication;
the belief-truth-log addition). No architect plan preceded this — the
brief itself carried the design; implementation decisions not already
settled by the brief are recorded below and in the modules' own
docstrings.

### Files Changed

- `body-layer/src/eyesight_view.py` (new) — pure renderer: `render_frame`,
  `GroundTruthMarker`/`BeliefMarker`, `contact_label` (the `AA`/`AR`/`TR`/
  `G`/`U` mapping — `G` is driven by `Contact.cardinality.lo > 1`, not by
  classification, because `PRESENCE_CLASS` and `DEFAULT_OP_CLASS` are
  literally the same string and cannot otherwise be told apart from an
  ordinary presence-level contact), `believed_markers_from_contacts`
  (live), `ground_truth_markers_from_trace`, `believed_markers_from_trace_rows`
  (offline approximation). Top-down plan view, ownship near (not at) the
  bottom of the canvas — a few rows are reserved below it for the
  90°–130° sliver the cockpit mask's real rear cutoff (130°, not 90°)
  still admits, rather than clipping it. Draw order: rings/cone, then
  ownship, then ground truth, then believed markers last and
  unconditional, so a believed contact always wins its cell over the gaze
  cone.
- `body-layer/src/logger.py` — wired `--eyesight-view`
  [`--eyesight-view-radius-m`, default 5000m per user correction] and
  `--belief-truth-log PATH` into both `_run_console_poll_loop` and
  `_run_crew_text_poll_loop`, mirroring `--detection-trace`'s existing
  additive shape exactly. All three features now share one
  `DetectionTraceCollector`, built whenever *any* is set; each reads it in
  a fixed order (render eyesight frame → belief-truth-log join →
  `DetectionTraceWriter.write_poll` if present, else a manual
  `trace_collector.records.clear()`) so exactly one consumer clears it,
  always last. `_render_eyesight_frame`/`_print_eyesight_frame` added as
  thin helpers (the latter untested by design — same live-process-entrypoint
  posture as the rest of `main()`).
- `body-layer/src/belief_truth_log.py` (new) — `BeliefTruthLogWriter`,
  `evaluate_pair`. Reuses `detection_trace_writer.
  observation_id_to_contact_id` (made public, was `_observation_id_to_contact_id`)
  rather than a second join. Compares position (Euclidean error vs.
  `Contact.last_position`), cardinality (ground-truth count from
  `DetectionTrace.cluster_member_object_ids` vs. `Contact.cardinality`'s
  held interval — outside the interval is a discrepancy, a wider interval
  that still contains the truth is correct hedging), and classification
  (only at `CLASS`/`TYPE` level — `PRESENCE`/`UNKNOWN` is never a
  discrepancy, by design). The stderr tripwire fires on two
  "physically impossible" checks only: believed range beyond
  `NAKED_EYE_RANGE_CAP_M`, and position error beyond
  `POSITION_ERROR_UNCERTAINTY_MULTIPLE` (5×) the contact's own stated
  uncertainty. Cardinality/classification discrepancies are recorded on
  every row but do not fire the tripwire (per user direction: catch the
  absurd, not tune a detector). Deliberately does **not** clear the shared
  collector — the poll loop owns that.
- `body-layer/src/detection_trace_writer.py` — `_observation_id_to_contact_id`
  → `observation_id_to_contact_id` (public), one call-site update, module
  docstring note on why.
- `body-layer/tools/eyesight_replay.py` (new) — offline replay from a
  recorded `--detection-trace` JSONL file, no live DCS session needed.
  Documents two honest limitations: no ownship heading is recorded in the
  trace (frames render relative to true north, not actual heading), and no
  live gaze is recorded (a stand-in full-forward cone labelled
  `"recorded (no live gaze)"` is drawn instead).
- `body-layer/tools/eyesight_sample.py` (new) — renders one hand-built
  illustrative frame from fixture data (no DCS, no trace file) — the dev
  aid `tests/test_eyesight_view.py`'s assertions cannot replace, mirroring
  `speak_samples.py`'s "for a human" posture.
- `plans/eyesight-view/implementation.md` (this file).

### Tests Added

- `body-layer/tests/test_eyesight_view.py` (24 tests) — `relative_bearing_deg`
  wrap behaviour; `contact_label`'s full AA/AR/TR/G/U mapping including the
  TYPE-level-resolves-via-parent-class and out-of-vocabulary-falls-back-to-U
  cases; `believed_markers_from_contacts`/`ground_truth_markers_from_trace`
  geometry; `believed_markers_from_trace_rows` dedup; `render_frame`'s
  draw-order precedence (believed wins over the gaze cone and over ground
  truth, pinned at an exact computed cell rather than a substring search,
  since the legend text itself contains every label substring); rear-cutoff
  clipping; off-edge legend (not silently dropped); the ownship-visibility
  regression (see Notable Discoveries); colour on/off; optic→cone-colour
  selection.
- `body-layer/tests/test_belief_truth_log.py` (15 tests) — position error/
  tripwire (zero-error case, range-cap tripwire, uncertainty-multiple
  tripwire); cardinality discrepancy (outside interval, wide-interval
  hedging is not a discrepancy, unknown ground truth is not a
  discrepancy); classification discrepancy (vaguer belief is never a
  discrepancy, class mismatch/match, TYPE-level resolves via parent
  class); `BeliefTruthLogWriter.write_poll` end to end (join succeeds,
  unadmitted/unresolved entries skipped, tripwire prints to stderr,
  ordinary rows print nothing to stderr, collector is not cleared by this
  writer).

### Checks

(body-layer/ — the only subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy src (run as `cd body-layer && PYTHONPATH=src:../world-model/src mypy src`, per this subproject's own CWD-only config-discovery note): pass, 0 issues across 51 source files
- pytest -q: pass — 1259 passed, 4 xfailed (baseline on `main` was 1220 passed / 4 xfailed; +39 new tests, 0 regressions)

### Notable Discoveries

- **Real bug found and fixed while rendering the sample frame, not by a
  test**: the ownship marker (`^`) was drawn with `set_if_blank`, but both
  the gaze centreline and the rear-cutoff boundary rays start their own
  trace at range 0 — i.e. ownship's own cell — so ownship was
  *permanently invisible* under whichever ray happened to draw first, on
  every frame, in every configuration. Fixed by drawing ownship
  unconditionally, positioned after the background layers (rings/cone)
  but before ground truth/believed markers, so a real contact exactly
  co-located (range ≈ 0) still wins the cell per the draw-order rule.
  Added `test_ownship_marker_is_always_visible` as a regression pin. This
  is exactly the class of defect the orchestrator's brief warned about
  ("mock-pass finding #3... losing a contact behind the cone drawing is
  exactly the case this instrument exists to make visible") — it happened
  to the ownship glyph instead of a contact glyph, same mechanism.
- **Legend text collides with canvas substring search.** An early test
  draft asserted `"AR" in frame`, which is trivially true regardless of
  rendering correctness because the legend line itself contains
  `"AR armour"`. Every draw-order/clipping test now either scopes to
  `frame.splitlines()[2:]` (canvas rows only) or asserts an exact computed
  cell position — worth flagging for any future eyesight-view test, since
  the failure mode is a false pass, not a false failure.
- **`PRESENCE_CLASS == DEFAULT_OP_CLASS == "OP_GROUPSOMETHING"`** means a
  presence-level contact's own classification *value* cannot distinguish
  "no claim at all" from "a cluster whose members disagreed down to the
  group root" by string alone. This is why `contact_label`'s `G` reads
  `Contact.cardinality.lo`, an independent field, rather than trying to
  read it off `classification.value` — a design note worth keeping in
  mind for any future feature that wants to render "group" from belief
  state.
