---
name: eyesight-view-review-approved
description: feature/eyesight-view (ASCII view + belief-truth log) reviewed APPROVED clean, no required fixes — shared-collector ordering and read-only boundary both independently verified
metadata:
  type: project
---

`feature/eyesight-view` (63345a9) added two flag-gated body-layer debug instruments —
`--eyesight-view` (real-time ASCII top-down render) and `--belief-truth-log` (per-poll
ground-truth/belief consistency JSONL with a stderr tripwire) — sharing one
`DetectionTraceCollector` with `--detection-trace`. Reviewed proportionately, per explicit user
direction, as a default-off dev tool, not a shipped feature (skip cosmetic rendering opinions —
the user judges that by flying it).

**Shared-collector "fixed read-then-clear order" pattern, worth reusing as a template:** when N
consumers read one mutable collector inside a poll loop, exactly one of them owns the clear, and
it must run last. Here: `_render_eyesight_frame` takes `list(collector.records)` (a copy, so it
can't accidentally consume), `BeliefTruthLogWriter.write_poll` is documented and coded to never
call `.clear()`, and `DetectionTraceWriter.write_poll` (or an explicit `else: collector.records.
clear()` in the poll loop itself when that writer is absent) clears once, terminally. Verified by
reading `write_poll`'s body directly for the "does it call .clear()" question, not by trusting the
docstring's claim — the docstring said it right, but check the code.

**Gap found and filed as optional, not required:** no automated test drives
`_run_console_poll_loop`/`_run_crew_text_poll_loop` with multiple of the three collector-consuming
flags set together — module-level unit tests are solid, but the wiring itself (which is exactly
where a future reordering would silently break one consumer) has no regression test standing
guard, despite `test_logger.py` already having precedent for real-thread-driven tests of this loop
(`--detection-trace`'s own Stage 6 tests). Worth watching for on any future extension of this
shared-collector pattern — see [[feedback_verify_pipeline_wiring_not_just_module]].

**Cost claims should be measured, not reasoned, when cheap to do:** rendered
`eyesight_sample.build_sample_frame()` 500x in an isolated scratch tree — ~0.9ms/frame, negligible
against the 5 Hz poll budget. Reused the git-archive scratch-tree technique
([[feedback_worktree_main_based_pytest_pythonpath_trap]]) with `world-model/src` added to
`PYTHONPATH` for body-layer's in-process cross-subproject import.

Also found: a beyond-*radius* marker is explicitly rim-marked + listed in a trailing legend
(never silently dropped — tested), but a beyond-*rear-cutoff* marker (outside the cockpit
occlusion mask's own FOV) is silently absent from both canvas and legend. Read as intentional
(there is genuinely no gaze possible there, unlike a display-scale radius limit) rather than a bug
of the same shape as the ownship-marker `set_if_blank` fix this branch made — flagged as optional
docstring clarification only.
