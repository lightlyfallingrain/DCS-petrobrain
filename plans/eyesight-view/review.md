### Review Summary

Branch `feature/eyesight-view`, single commit `63345a9`, branched from `main` at `0918477`.
Reviewed as what it is: a default-off developer instrument (`--eyesight-view`,
`--belief-truth-log`), not a shipped product feature. Not reviewed for cosmetic rendering
opinions (the user is deciding that by flying it).

**Poll-loop integration (the area asked to receive the most scrutiny):**

- No-flag path is byte-identical. With `eyesight_view=False` and `belief_truth_log_path=None`
  the new branches (`if eyesight_view:`, `if belief_truth_writer is not None:`) are dead and
  the surviving code is exactly `--detection-trace`'s pre-existing shape
  (`trace_writer.write_poll(...)`), confirmed by reading both `_run_console_poll_loop` and
  `_run_crew_text_poll_loop` in full.
- Both new call sites (`_render_eyesight_frame`/`_print_eyesight_frame`, and
  `belief_truth_writer.write_poll`) sit inside the same `try/except Exception:
  logger.exception(...); continuing` guard that already wraps `runner.run_once()` in both loops
  — the guard this morning's security pass added specifically because a daemon thread dying
  there is silent. A rendering exception or a log-file write error cannot kill the poll thread.
- Shared-collector ordering verified by direct code read, not just docstring: per poll, the
  sequence is (1) `_render_eyesight_frame` — takes `list(trace_collector.records)`, a copy, so
  it cannot itself mutate the collector; (2) `belief_truth_writer.write_poll` — its own
  docstring and code (`belief_truth_log.py:275`, `write_poll` never calls `.clear()`)
  confirm it deliberately does not clear; (3) `trace_writer.write_poll` (clears, per
  `detection_trace_writer.py:83`) if `--detection-trace` is set, **else** the poll loop's own
  `trace_collector.records.clear()`. Exactly one clear, always last, regardless of which subset
  of the three flags is active — checked all four combinations (`--eyesight-view` alone,
  `--belief-truth-log` alone, both, neither) by tracing the branch logic, not just reading the
  one combination the fixture happens to exercise.
- Cost measured, not reasoned: `eyesight_sample.build_sample_frame()` (full `render_frame` call,
  same code path the poll loop drives) averaged **~0.9 ms/frame** over 500 iterations on this
  machine — negligible against a 5 Hz (200 ms) poll budget.
- `observation_id_to_contact_id`'s widening to public: diffed against the pre-existing
  `_observation_id_to_contact_id` — a pure rename, one call-site update in
  `DetectionTraceWriter.write_poll`, no behavior change. `belief_truth_log.py` imports and calls
  the same function, so the join is genuinely the one join, not a second implementation that
  happens to agree today.

**Read-only/one-directional boundary:**

- Both `eyesight_view.py` and `belief_truth_log.py` carry an explicit module-docstring statement
  of the invariant (read-only, exactly `detection_trace_writer.py`'s precedent), not left
  implicit.
- Grepped both new modules for any call into `ContactStore` beyond read access
  (`store.contacts`, `contact.last_position`, `.cardinality`, `.classification`) — no `ingest`,
  no `Percept`/`Contact` construction fed from a ground-truth field, no import of `belief/` by
  either module. Holds.

**Correctness spot-checks:**

- `contact_label`'s `G`-from-cardinality claim: confirmed in `belief/classification.py` and
  `perception/object_model.py` that `PRESENCE_CLASS` and `DEFAULT_OP_CLASS` are the same string
  constant, so `Contact.classification.value` genuinely cannot distinguish a real "no claim"
  contact from a degraded-group one — `cardinality.lo > 1` is the only independently-populated
  signal available. Test `test_label_singular_cardinality_does_not_force_group` covers the
  boundary.
- Beyond-radius handling: both `render_frame`'s `beyond` list (believed markers) and the
  ground-truth loop append any marker with `range_m > radius_m` to the trailing legend rather
  than dropping it; `test_contact_beyond_radius_appears_in_legend_not_silently_dropped` and the
  fixture's own 8.89 km entry exercise this. One related but distinct behavior, not in scope of
  the brief's beyond-radius question but worth noting for the user (see Optional Refinements):
  a marker beyond `rear_cutoff_deg` (behind the co-pilot's own occlusion mask) is not drawn *and*
  not listed anywhere — `to_cell` returns `None` for it and nothing downstream records it. This
  is architecturally different from beyond-radius (there is genuinely no gaze possible there, not
  a display-scale limitation), so it reads as intentional rather than a bug, but it means "beyond
  radius" and "outside rear cutoff" are not symmetric even though radius overflow got explicit
  legend treatment.
- Belief-truth log's vagueness-vs-error distinction: `_classification_discrepancy` returns
  `False` whenever `classification.level < SpecificityLevel.CLASS`, before ever comparing values
  — a `PRESENCE`/`UNKNOWN` belief cannot fire regardless of ground truth.
  `test_classification_no_discrepancy_when_belief_is_vaguer_than_truth` covers this directly.
- Tripwire thresholds: `range_cap_tripwire = believed_range_m > NAKED_EYE_RANGE_CAP_M`. Applied
  to the 2026-09-24 defect shape (87.5 km believed against a 10 km cap), this fires — 87,500 m is
  well past any plausible `NAKED_EYE_RANGE_CAP_M` value, and the test suite's own
  `test_range_cap_tripwire_fires_beyond_naked_eye_cap`/`..._does_not_fire_within_cap` pair
  exercises the boundary. `position_uncertainty_tripwire` is 5x the contact's own stated
  uncertainty — loose by design (module docstring quotes the user direction directly) and tested
  both sides.

**Independent verification run** (isolated `git archive` scratch tree at `/tmp/eyesight-scratch`,
`world-model/src` from `main` added to `PYTHONPATH` for the in-process import, per the known
pytest-pythonpath trap):
- `ruff format --check` / `ruff check` on all 8 touched/new files: clean.
- `mypy --strict` on `eyesight_view.py`, `belief_truth_log.py`, `logger.py`,
  `detection_trace_writer.py`, both `tools/` scripts: clean.
- `pytest tests/test_eyesight_view.py tests/test_belief_truth_log.py -q`: 39 passed, matching the
  claimed count.
- Rendered `eyesight_sample.build_sample_frame()` directly; timed it (see cost note above).

### Required Fixes

None.

### Optional Refinements

- **No automated test exercises the three-flag collector-sharing wiring inside `logger.py`
  itself** (`_run_console_poll_loop`/`_run_crew_text_poll_loop` with `--eyesight-view` and
  `--belief-truth-log` both set, alongside `--detection-trace`). The per-module unit tests are
  solid, and I verified the ordering by direct code read across all four flag combinations, but
  the sharp edge the orchestrator brief flagged — one consumer silently getting nothing if a
  future edit reorders the reads/clear — has no regression test standing guard against a
  reordering, unlike the module-level logic which is well covered. Given `test_logger.py`
  already has precedent for driving `_run_console_poll_loop` on a real background thread
  (`--detection-trace`'s own Stage 6 tests), a similar thread-driven test asserting all three
  outputs are non-empty from one shared poll would close this gap cheaply. Optional because the
  ordering is currently correct and simple (three sequential branches, one terminal clear), and
  this is a debug tool — but it is exactly the kind of quiet regression this instrument exists to
  catch elsewhere.
- `todo/todo.md`'s "Added 2026-09-25 (user)" entries for the ASCII view and (implicitly, via its
  2026-09-26 follow-up referenced in the code) the belief-truth log are still unchecked (`[ ]`)
  even though both are now implemented on this branch. Cheap to fix, consistent with this
  project's established pattern of flagging stale backlog/roadmap entries at review.
- The beyond-rear-cutoff asymmetry noted above (silently absent rather than rim-marked/listed,
  unlike beyond-radius) is worth a one-line mention in `eyesight_view.py`'s module docstring if
  it is deliberate, since a future reader could otherwise mistake it for the same bug class the
  ownship-marker fix just addressed.
- `run-scripts/run-audio-adapter.sh`, `run-scripts/run-console.sh`, `run-scripts/run-crew-text.sh`
  show as modified in the main checkout's git status but are not part of this commit (`git show
  --stat 63345a9` does not touch `run-scripts/`) — unrelated, pre-existing working-tree state, out
  of scope for this review.

### Verdict

APPROVED

### Review Confidence

Full read — both new modules (`eyesight_view.py`, `belief_truth_log.py`) read in full, the full
`logger.py` diff read and the poll-loop wiring traced by hand across all flag combinations, both
`tools/` scripts read, test files enumerated and cross-checked against the behavior they claim to
cover. Format/lint/type-check/test suite for the touched files independently reproduced in an
isolated scratch tree rather than trusted from the commit message.
