### Review Summary

Stage 3 (`a448c67..HEAD`, commits `6fd853d`..`e9eede5`) delivers the elevation/surface_type
probe: parser extension, `ingest_probe`, pipeline wiring, three Lua probe rungs, and the live
DCS round-trip. Verified independently: `ruff format --check`, `ruff check`, `mypy --strict`
(src+tests), and `pytest` all pass (137 tests). Grid coverage was queried directly against the
real `data/world-model/latakia-20km.sqlite` — confirmed 1,681/1,681 populated cells for both
`elevation` and `surface_type`, and `elevation.stats["srtm"]` is genuinely `null` (not a
placeholder or fabricated value). Scope is correctly held to elevation+surface_type wiring —
no Stage 4 control-point/tolerance-band tests or formal spot-check tables were added; the
reported spot-checks are ad-hoc CLI runs in the research note, which is appropriate. The
incremental ladder (121 → 441 → 1,681) was genuinely followed, evidenced by three separate
commits and a research note that grew rung-by-rung with real numbers at each step, not
retrofitted. SRTM delta handling matches the plan exactly: metadata-only in `stats_json`, no
grid/grid_sample rows, and a real synthetic-tile test (`test_ingest_probe.py`) exercises the
code path — the honest gap is reported, not silently glossed over. `getSurfaceType`'s output was
sanity-checked (enum range, spatial plausibility, cross-subsystem RUNWAY/ROAD placement vs. the
Stage 1 airfield point) before being trusted at scale, as required. `describe_position` needed no
logic changes — confirmed correct, since Stage 1 already wired grid reads through
`store.reader.sample_grid`.

One required fix: the probe scripts do not follow the checklist's mandated
`timer.scheduleFunction` chunking / append-mode pattern, and the implementation log's Stage 3
section claims "append-mode `io.write`" for a script that in fact opens the file in `"w"`
mode once and writes the whole grid in a single blocking loop.

### Required Fixes

- **Probe scripts use a single blocking loop, not `timer.scheduleFunction` chunking, contradicting
  an explicit checklist instruction — and the implementation log misdescribes this as "append-mode
  `io.write`".** `checklist.md` Stage 3 (line 77) and `plan.md`'s Finding E are unambiguous:
  "`timer.scheduleFunction` chunking, append-mode `io.write`... never one giant loop holding
  results in memory." All three scripts (`terrain_probe_smoke.lua`, `terrain_probe_500.lua`,
  `terrain_probe_full.lua`) instead open the output file once with `io.open(..., "w")`, run a
  single `for _, p in ipairs(points) do ... end` loop over the entire rung (up to 1,681 points ×
  2 blocking `land.*` calls each), and close the file only after the whole loop finishes — this is
  exactly the "one giant loop" pattern Finding E says to avoid, and it is not append mode (it
  truncates and writes fresh each run, never resuming a partial write). `implementation.md`
  (line 529) asserts "`pcall`-wrapped calls, append-mode `io.write`, one JSON object per line" for
  this script, which does not match what the code does — the file is opened in `"w"` mode, and
  writes only "append" to that one open handle, not across scheduled ticks. The scripts do mirror
  M4's `elevation_probe.lua` structure, which is true and stated, but M4 ran only 100 points; the
  checklist raised the bar to explicit chunking specifically for Stage 3's larger workload
  (1,681 points × 2 calls), and that instruction was not followed and not flagged as a deliberate
  deviation anywhere in the decision log. In practice DCS did not hang on any of the three live
  runs (per the research note), so this did not cause a failure this time — but the risk the
  checklist was written to close (busy-wait-hangs-DCS on a long unscheduled loop) was not actually
  mitigated, and the report's description of the mitigation being in place is inaccurate. Fix:
  either rewrite the three scripts to use `timer.scheduleFunction` self-rescheduling chunking with
  true append-mode writes (`io.open(..., "a")`, opened/closed per chunk or kept open across scheduled
  calls), or explicitly document in `implementation.md` why the single-loop approach was judged
  safe for this workload and correct the "append-mode" claim to describe what the code actually
  does.

### Optional Refinements

- **The "three independent live runs returned bit-identical results" determinism claim is
  narrated only, not asserted by any test.** It's a genuine and useful finding recorded in the
  research note and agent memory, but nothing in `tests/` pins it — a small test that loads the
  smoke and full fixture subsets (or a literal shared point) and asserts equal `height_m`/
  `surface_type` would let this claim survive a future refactor rather than resting on a
  point-in-time manual comparison. Not a checklist requirement, so optional. (optional)
- **No wall-clock/cost numbers were recorded for any of the three Lua probe rungs**, unlike
  Stage 2's `.routes` walk which got an explicit timing measurement. The checklist's "stop and
  reassess if any rung shows non-linear cost" instruction has no data behind it in the research
  note beyond "it worked, no hang was observed" — worth a rough in-mission timestamp or DCS log
  timing next time a probe scales up, so the non-linear-cost check has something to compare
  against. (optional)

### Verdict

APPROVED WITH MINOR FIXES
