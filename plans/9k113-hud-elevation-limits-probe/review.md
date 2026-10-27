### Review Summary

Reviewed `aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua`,
`docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md`, and
`plans/9k113-hud-elevation-limits-probe/implementation.md` against the user's literal request
("slew up until limit, then down until limit and log the values"), `plans/9k113-sight-pointing/plan.md`
v3's "Elevation - measure in flight" decision, and the measured facts in
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` (runs 1–8).

Scope matches the ask exactly — a single-purpose, throwaway recon probe, correctly routed straight
to Implementer (no Architect pass needed, per `AGENTS.md`'s "small feature, one role"). Device/command/
arg numbers (`DEV_I9K113=7`, `CMD_AI_AZ=3061`, `CMD_AI_ELEV=3060`, `ARG_OBSERVE=886`, mark pairs
565/566 and 555/556, lamps 898/960/962) all match production `Export.lua` exactly (grepped both).
Per-frame dither-flicker on both AI axes is correctly reused from the calibration-probe pattern and
is necessary per the cited doc (runs 6–8: DCS intermittently drops a held, unchanging command value).
The script ends by nudging back off the edge and stopping all writes (`centre_all()` then `phase =
"FINISHED"`, after which no `if phase == ...` branch matches and nothing further is written) — note
below on what "centred" actually means here. Lua syntax is clean (`luac5.1 -p`), and the
local-before-declaration bug class this project has hit twice is absent (`luac5.1 -l -p | grep
GETGLOBAL` lists only genuine DCS/Lua globals). `ruff format --check`, `ruff check`, `mypy --strict`,
and `pytest aircraft-layer/tests -q` (610 passed) all pass unchanged — no Python touched, and the
glob-based `test_dcs_export_lua_syntax.py`/`test_dcs_export_lua_local_order.py` automatically cover
the new file.

The one substantive concern is the stall-vs-clip discrimination the task specifically asked to be
checked, detailed below.

### Required Fixes

- **`MARGIN_S = 3.0` is not long enough to rule out the AI-axis "gate" the same cited acceptance doc
  documents, and the failure mode it enables has already been observed once at full severity.**
  `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` runs 6–8 found an intermittent AI-axis gate
  (cause still unknown — "Unknown: what closes the windows") that drops commands for **4–18 seconds
  at a stretch** (run 7/7b), and in run 8 **for essentially the entire flight** (~100+ s, 42 stick-park
  toggles did not restore motion). The new probe's plateau detector (`PLATEAU_WINDOW_S = 0.6`,
  `PLATEAU_EPS = 0.0015`) cannot distinguish "the sight physically stopped at the field edge" from
  "the gate just swallowed the command from the very start of this SEEK phase, so the mark never left
  boresight." Both present identically: 555 flat while still commanding. The only defence against
  this is `MARGIN_S`'s 3-second extra push — but 3 s is shorter than nearly every documented gate
  window, so a gate onset at the *start* of a SEEK phase reads as a confirmed plateau at
  **≈boresight**, not the true edge, within about 3.6 s total. `CYCLES = 3` is the only remaining
  safeguard, and it is not reliable against this specific failure: run 8 shows the gate can be
  essentially flight-duration, in which case all three cycles would plateau at the same near-zero
  value and the cross-cycle consistency check (`CONSISTENCY_EPS`) would report `CONSISTENT (real
  clip)` — a wrong but confident-looking result, for a value a human skimming the summary line has no
  reason to doubt.
  **Fix (either is sufficient, cheapest first):** add a loud flag when a plateau's travel from the
  SEEK phase's starting value is implausibly small (e.g., well under what `EL_RATE_CMD`'s rate times
  elapsed time would predict) — log it as `SUSPECT — near-zero travel, matches the known AI-axis gate
  (ai-latency-probe runs 6–8), not necessarily a true edge` rather than with the same "plateau
  confirmed" wording a true clip gets. Optionally also raise `MARGIN_S` well past the documented 4–18 s
  window. Either way, add one line to the test card telling the pilot what a gate-stall looks like by
  eye (the crosshair stopping almost at centre, not visibly approaching an edge) and to flag/re-fly
  that specific leg rather than trust the log's own verdict.

### Optional Refinements

- The card could note, for the pilot's own sanity check, that a returned elevation half-angle far
  from the already-measured azimuth figure (≈4.3°) is worth a second look before being trusted (not
  required — the raw log is still the ground truth the follow-on plan work will read from directly).
- `centre_all()` at the end does not actually recentre the sight — per the cited doc (runs 3–5), the
  AI axis is a **rate** command, and writing 0 only stops further motion, it does not return the mark
  to boresight. The preceding `RETURN` phase's 3 s nudge (at `EL_RATE_CMD`'s rate, reusing `MARGIN_S`
  for an unrelated purpose) only partially closes the gap, by design ("not a precise re-centre, just
  so the real sight is not left parked at a field edge" — a reasonable, honestly-scoped goal). Worth
  one sentence in the card telling the pilot the sight will settle a few degrees off true centre
  afterward, which is expected and not a sign the probe failed.
- Gating the 20 s start delay on the Л5 alignment lamp (arg 898, confirmed lighting at exactly T+10.0
  in every run 6/7/7b/8 flight) rather than a flat timer would be slightly more robust, though the 2×
  margin above the measured ~10 s alignment makes this low-risk as is.
- Reusing `MARGIN_S` for both the stall-discrimination window and the final return-nudge duration is a
  minor conflation of two different concerns sharing one constant by coincidence, not a bug.

### Verdict

APPROVED WITH MINOR FIXES

The probe is correctly scoped, uses the right device/command/arg numbers, reuses the established
dither-flicker pattern correctly, and passes every mechanical check. The one required fix is cheap
(a log-wording/flag change plus one card sentence) and does not require restructuring the probe — it
exists because this project has already measured, in the very doc this probe cites, a failure mode
(the AI-axis gate, up to flight-duration in run 8) that the current stall/clip discrimination cannot
tell apart from a true field edge in the worst case. Given this is a one-flight recon probe whose
output feeds directly into setting `ASP17_FIELD_EL_HALF_DEG`, a confidently-wrong number is the
worse failure to ship silently, and the fix is cheap enough that it should land before the flight
rather than be risked.

### Review Confidence

Full read — all three task files read in full; the relevant sections of
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` (runs 1–8, the full stall/gate history) and
`plans/9k113-sight-pointing/plan.md` v3's elevation decision were read directly rather than taken on
summary. Device/command/arg numbers, Lua syntax/global-leak checks, and the full aircraft-layer
format/lint/type/test suite were run directly, not assumed from the implementer's report.
