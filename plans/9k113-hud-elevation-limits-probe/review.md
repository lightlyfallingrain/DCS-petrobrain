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

---

## Re-review (2026-10-27) — simplified rewrite, `b181d3d0`

Branch `probe/9k113-hud-elevation-limits`, tip `b181d3d0` (matched `HEAD` exactly in the dedicated
worktree, no merge needed, tree clean). Diff `2c9a7f5c..b181d3d0`: the required fix above and its
`MARGIN_S`/`CYCLES`/travel-plausibility machinery are **superseded**, not patched — the whole probe
was rewritten per the pilot's own, simpler spec (`implementation.md`, "Simplified per user,
2026-10-27", direction quoted verbatim). Re-reviewed the new
`Export.probe-9k113-hud-elevation-limits.lua` (348 lines, full read), the rewritten acceptance card,
`run_sight_servo`'s dither branch in production `Export.lua` (lines ~1192–1797, full read), and
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` runs 9–11 (the dither-closes-the-gate
evidence this redesign leans on), which this review's first pass had not needed to read.

### Why the prior required fix no longer applies

The withdrawn design's problem was a stall-vs-clip ambiguity sized against the *undithered* gate
windows in runs 6–8 (4–18 s, once ~100+ s). Runs 9–11 (read for this pass) show that production's
own always-on dither closes almost all of that: run 9's dithered block had **zero** stalls across
7/7 targets against the undithered block's 6 stalls/1-of-5; run 10's dithered holds had three
stalls of **0.24–0.30 s**, each self-recovering; run 11 confirms any per-frame value change
(dither or flicker) keeps the axis obeyed on 6/6 pulses, every amplitude tried. The new design's
`REVERSE_CHECK_S = 1.0 s` sits 3–4× above the measured dithered-stall length, and — this is the
part that matters more than the margin — it does not need to be sized against the gate's *maximum*
duration at all: a reversal that sees no movement within the window is logged `stall, not an edge`
and the probe simply resumes pushing and re-plateaus, so an arbitrarily long gate (run 8's case)
costs wall-clock time, not a wrong answer. That is a structurally different, and strictly stronger,
guarantee than the margin-based design had — the probe can no longer report a gate's frozen value
as `EDGE UP`/`EDGE DOWN` regardless of how long the gate lasts, which is exactly what the prior
required fix was trying to buy with an upper-bound guess.

### Checked

- **Plateau → reverse → accept/resume, traced against the code, not summarized.** `check_ref` is
  set from `plateau_value` (the flat window's own midpoint) at the moment the reversal begins;
  `edge_pos_555`/`edge_neg_555` are assigned from `check_ref`, never from the reversed-phase read
  `m` — the probe records the plateau, not the push-back. A stall (no movement past `PLATEAU_EPS`
  within `REVERSE_CHECK_S`) re-enters `SEEK_POS`/`SEEK_NEG` via `start_seek`, which resets `hist`,
  so a stale flat-window from before the reversal cannot immediately re-trigger a false plateau. No
  unbounded-loop risk beyond "a manually-flown probe that keeps running until the pilot sees
  `PROBE DONE` or stops the mission" — acceptable for a one-flight recon script, and the explicit
  design goal (no `MAX_PHASE_S` timeout) per the user's own simplification request.
- **Stops writing at the end.** The `phase == "DONE"` branch is a bare comment with no
  `write_axes` call; no other branch runs once `phase` reaches `"DONE"`. Confirmed by full read, not
  grep.
- **Device/command/arg numbers**, re-checked against current production `Export.lua`: `DEV_I9K113
  = 7`, `CMD_AI_AZ = 3061`, `CMD_AI_ELEV = 3060`, `ARG_OBSERVE = 886` all match exactly
  (`grep -n` on both files). Mark pair convention (565/566 az, 555/556 el) matches the cited
  2026-10-22 doc.
- **Azimuth dither conversion is an exact match to production**: `wobble_az_deg / 60.0`, same
  literal divisor as `run_sight_servo`'s `write_az_cmd = write_az_deg / 60.0` (production has no
  sign branch on this axis either — the field is symmetric).
- **Elevation dither conversion is *not* a byte-for-byte copy, despite the implementer's "copied
  unmodified" wording** — worth recording, not blocking (see Optional Refinements).
- **`EL_RATE_CMD = 0.05` → 0.5°/s**, checked against `Devices_specs/9K113.lua`'s
  `v_axis_velocity = rad(10)/s` (confirmed in `aircraft-layer/research/mi24p-command-surface.md`
  line 312: the `10` is degrees, converted by `rad()`) — `0.05 * 10 = 0.5`, matches the comment.
  Comfortably above the `Slew_dead_zone = 0.003` deadzone (same source line), and the comment's
  cross-reference to "`Export.lua`'s own `FLICKER_EPS` comment" is accurate: that comment block
  (lines ~1194/1205) documents the same 0.003 figure, even though `FLICKER_EPS` itself is a
  different, smaller constant (1e-4) used only in the flicker branch.
- **`MARK_DEG_PER_UNIT_EL` placeholder citation** (`plans/9k113-sight-pointing/plan.md` line 588)
  checked against the source line — accurate: elevation's scale is explicitly a borrowed placeholder
  from azimuth's measured value, not an independently confirmed figure, and both the probe's comment
  and the card say so.
- **Card vs. script**, line by line: `EDGE UP`/`EDGE DOWN`/`PROBE DONE` log strings match the card's
  description exactly; the `WAIT_OBSERV → DELAY(15s) → SEEK/CHECK → DONE` phase sequence matches the
  timeline table; the up/down-is-unconfirmed caveat is carried in both places. No gimbal clamp is
  applied (`write_az_cmd`/`write_el_cmd` are not clamped), matching the user's explicit "gimbal
  limits: nowhere near the HUD limits, safe to ignore" and the card's framing.
- **No leftover superseded machinery.** `MARGIN_S`, `RETURN_NUDGE_S`, `MAX_PHASE_S`,
  `MIN_TRAVEL_FRACTION`, `MIN_TRAVEL_EL`, `CYCLES`, `CONSISTENCY_EPS`, `FLICKER_EPS` from the
  withdrawn design do not appear anywhere in the new file (full read + grep).
- **Checks re-run independently** (not taken from `implementation.md`'s report), from
  `/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv` with `cwd` inside this worktree's
  `aircraft-layer/`: `luac5.1 -p` on the new file — pass. `luac5.1 -l -p | grep GETGLOBAL` — only
  `GetDevice`, `io`, `ipairs`, `lfs`, `LoGetModelTime`, `LoGetVersionInfo`, `math`, `os`, `pcall`,
  `string`, `table`, `tostring`, `type` (all genuine DCS/Lua globals, no own local leaked).
  `ruff format --check src tests` — 72 files already formatted. `ruff check src tests` — all
  checks passed. `mypy --strict` (run from inside `aircraft-layer/`) — no issues, 25 source files.
  `pytest -q` — 610 passed. No Python was touched by this diff, so these are regression checks, not
  new coverage.

### Required Fixes

None.

### Optional Refinements

- **The elevation dither's unit conversion is not actually "copied unmodified" from production,
  though the magnitude makes it harmless.** Production's `write_el_cmd` divides by
  `GIMBAL_EL_UP_DEG` (20.0) only when the *combined* `write_el_deg` (correction + wobble) is ≥ 0,
  and by `-GIMBAL_EL_DOWN_DEG` (15.0) when it is negative (`Export.lua` lines 1783–1787) — an
  asymmetric scale reflecting the sight's own asymmetric elevation gimbal (+20°/−15°). The probe's
  `wobble()` always divides `wobble_el_deg` by `GIMBAL_EL_UP_DEG`, regardless of sign, because it
  has no correction term to sum against first — `write_axes` adds the raw-unit `w_el` straight onto
  the already-raw-unit `el_cmd`. Worst case at `DITHER_EL_DEG ≈ 0.012°`: `0.012/15 − 0.012/20 ≈
  0.0002` raw-555 units of error on the negative half-cycle — two orders of magnitude below
  `PLATEAU_EPS = 0.003`, so it cannot affect plateau/edge detection and the dither still does its
  one required job (a per-frame value change). Not a required fix; worth a one-line comment update
  so "copied unmodified" doesn't overstate it, since a future reader diffing against production
  would otherwise go looking for a discrepancy that isn't there in effect, only in the conversion
  path.
- The card's "~1 minute" runtime estimate assumes no gate-stalls; if the dithered stall rate seen in
  runs 9–11 (sub-second, self-recovering) does not hold for this specific axis/direction, actual
  runtime could run longer. The card already tells the pilot to just note it rather than worry about
  it, which is the right amount of caveat for a one-flight recon probe — no change needed.

### Verdict

APPROVED

### Review Confidence

Full read — the rewritten probe script (348 lines), the rewritten acceptance card, production
`Export.lua`'s `run_sight_servo` dither branch, and runs 9–11 of
`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` were all read in full, not summarized. All
mechanical checks (Lua syntax/global-leak, `ruff format`/`ruff check`/`mypy --strict`/`pytest`) were
re-run directly in this pass, not taken from the implementer's report.
