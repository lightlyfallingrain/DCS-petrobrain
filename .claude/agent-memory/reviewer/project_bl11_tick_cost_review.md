---
name: bl11-tick-cost-review
description: BL-11 Stages 1/2/3b/5 review — APPROVED WITH REQUIRED FIXES; the disk-full premise in the task was backwards and checking it changed the verdict.
metadata:
  type: project
---

`feature/bl11-tick-cost` at `ab9188e`, reviewed 2026-10-06. Verdict APPROVED
WITH REQUIRED FIXES. 1506 passed / 4 xfailed, matching the implementer's
figure; ruff + `mypy --strict` clean.

**The orchestrator's framing of one finding was factually backwards, and
checking it flipped the severity.** The task asked for a ruling on Stage 5
depositing stamped log files loose in `~`, framed as: "Before this change that
was cosmetic — three files overwritten in place. Now every run deposits three
new stamped files ... a few sorties leave gigabytes." But all three writers
open with `"a"` (`detection_trace_writer.py:66`, `belief_truth_log.py:262`,
`speech_log.py:71`) and never rolled — which is *why* the 2026-10-05 analysis
had to seek to byte offset 2,448,471,603. Pre-branch disk growth was already
unbounded. Stage 5 writes the same bytes into dated, deletable files, so the
disk picture is neutral-to-better, not a regression. The required fix survived
on different grounds (the branch added three `logs/` doc references describing a
directory nothing creates), at a much lower severity than requested.

**Why: a one-line check of the `open()` mode decided it.** The task's own
grep-the-run-scripts sweep had been done and reported; the premise underneath it
had not.

**How to apply:** when a task hands you a severity along with a finding, verify
the *premise* of the severity, not just the finding. Here it was `grep 'open("'`
across three files.

**Option (b) in that ruling had a hidden dependency worth naming:** "point the
run scripts at `logs/`, two lines each" is not two lines — nothing `mkdir`s it,
`per_run_log_path` does not, and the writers' `__init__` calls `path.open("a")`
unguarded, so a missing `logs/` is a `FileNotFoundError` at startup *before* any
of Stage 5's new `_fail` reporting can fire. `body-layer/.gitignore:8` already
ignores `logs/`, so the directory is intended and uncreated.

**Stage 3b ruling, for whoever revisits the grain:** quantising
`WorldEnrichmentCache`'s key onto 50 m is acceptable. The constant's docstring
justifies it only via `describe_position`'s feature names and coarse bands, but
the cached `world_position` also feeds `relative_geometry` (range rendered at
0.1 km by `tools._format_range_km`) and `terrain_divide_qualifier` (a binary
"beyond the ridge" phrase). Worst case is the **cell diagonal** — ~70.7 m
horizontal, ~86.6 m in 3D — not 50 m, and floor-based cells mean "within 50 m"
never implied a shared result anyway. Still well inside the believed position's
own uncertainty, so docs-only.

See also [[feedback_equivalence_test_must_not_import_the_code_it_pins]] for the
Stage 2 finding, which was the substantive one.
