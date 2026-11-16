# Review: fix/ai-wheel-pilot-seat-gate

Reviewed commit `53104a49` (one commit on `main` @ `11e40eb4`, fast-forwarded cleanly). No
`plans/` directory exists for this work — per the branch's own note, this is a "Fix now" bug fix
and `docs/acceptance/2026-11-16-ai-wheel-pilot-seat-feedback.md` is the spec. Reviewed against
that doc, the invariants, and `aircraft-layer/CLAUDE.md`.

### Review Summary

The fix gates the AI-pilot-wheel takeover sequence on a seat read from
`LoGetCameraPosition`/`LoGetSelfData`/`LoGetADIPitchBankYaw`, projected onto the airframe forward
axis. The seat ↔ eye-point mapping is independently verifiable against the installed DCS tree —
I read `/mnt/f/Games/DCS World/Mods/aircraft/Mi-24P/Views.lua` and `entry.lua` directly: the
`Cockpit` table's slot order (`player(3.15, 0.57)`, `player(4.65, -0.05)`, `gunner(...)`) matches
`entry.lua`'s `Mi-24P_pilot`/`Mi-24P_operator`/`Mi-24P_Gunner` input-profile order 1:1, so "pilot
= 3.15, operator = 4.65" is correct, not inferred. `limits_6DOF.x = {-0.1, 0.5}` on both seats
confirms the stated head-travel ranges (3.05–3.65 / 4.55–5.15) and the 4.1 m boundary's ≥0.45 m
margin — the arithmetic in the comment checks out. `LoGetCameraPosition()`'s `{p=…, x=…, y=…,
z=…}` shape (used as `cam.p`) is documented from DCS's own shipped `Scripts/Export.lua`
(`aircraft-layer/research/2026-09-11-petrovich-detection-readout.md:1341`), not guessed — `cam.p`
with no flat-shape fallback is correct, since `cam.x/.y/.z` are orientation basis vectors, not a
point, and treating them as one would be the real bug. `LoGetADIPitchBankYaw` (rather than
`LoGetSelfData().Pitch`) for pitch matches every other call site in this codebase
(`telemetry.lua`, `sight.lua`, every probe script) — established convention, not a deviation.
The projection math (unit forward vector from heading+pitch, bank correctly omitted since it
doesn't move that axis) is correct and the `TestSeatFromCamera` cases exercise it meaningfully
(heading, pitch, head-travel boundaries, external-camera exclusion, missing inputs).

The frame ordering in `Export.lua` (`run_ai_pilot_wheel` every frame, before the 5 Hz
`core.tick_due` gate; `update_ai_pilot_wheel_overlay` after it, same frame) means
`ai_pilot_parked_active` is always current for the overlay function and the keep-open/5 Hz path —
no staleness window there. I traced every `GetDevice(30):performClickableAction(cmd, 1)` call
site and confirmed each is reachable only through a code path gated on `in_operator_seat` being
true *this frame*; the only presses reachable while off-seat are **releases** (`value 0`) of a
press that was already open, which is correct (completing, not initiating, an action) and matches
what `test_switch_to_pilot_seat_mid_hold_releases_without_menu_tap` exercises. The
`on_stop`/seat-reset and the external-view hold-last-seat paths are both covered and both sound —
the external-view case matters especially because holding the last seat through the 9K113 sight
view is the *point* (operator using the sight while the AI flies is the feature's main use case),
and the sight view's own camera-position uncertainty (flagged in
`aircraft-layer/research/2026-11-14-9k113-mark-staleness-hand-hold.md`) is already handled safely
by the envelope/no-reading fallback, not special-cased.

`EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` are bumped together (`"2026-11-16c"`) with
matching comments on both sides. The wire/schema extension (`apw_seat`/`apw_cam_fwd_m`) is
additive and tested for an old-script line still parsing (`None`/`None`) and for a malformed
`apw_seat` being rejected. `ruff format --check`, `ruff check`, `mypy --strict` (run from inside
`aircraft-layer/`) and `luac5.1 -p` are all clean. The targeted tests (`test_ai_pilot_wheel_lua.py`,
`test_ai_pilot_wheel_api.py`, `test_export_lua_constants_parity.py`) pass (59/59), and the full
`pytest -m "not slow"` suite passes 806/807 — the one failure
(`test_close_during_a_blocked_accept_ends_the_loop_cleanly`) is in a file this diff never touches
and is the known pre-existing flake named in the task brief. `invariant-check` reports clean
(no omniscience/cross-import/sys.path/bare-except regressions; the two WARN categories are
pre-existing elsewhere in the tree, not in these files).

One real gap, below.

### Required Fixes

- **The one scenario the fix's own reasoning leans on hardest has no test: a transient false
  rising edge on the *pilot → operator* switch, absorbed only by the 0.5 s reference-toggle
  delay.** The code comment states the mechanism as settled ("the stow arg counts only while the
  player is in the operator seat"), and the acceptance doc's own framing of this review ("is that
  sound?") flags it as an open question — but nowhere in `TestSeatGate` or elsewhere is a case
  where: seat flips to `"operator"` this frame, `stick_park` still reads `>= 0.9` (un-stow
  animation lag, mirroring the already-measured *parking* animation's multi-frame ramp — never
  measured for a human retaking the stick), a rising edge is armed (`stage = "toggling_reference"`,
  `t` snapshotted), and then `stick_park` drops back below `AI_PILOT_PARK_THRESHOLD` before
  `t + 0.5s` — asserting the pending reference-toggle tap never fires and the takeover state is
  dropped cleanly. Every other scenario named in the task (seat-switch frame, `on_stop`, the 5 Hz
  overlay keep-open path, external-view hold-last-seat) has a passing test; this one does not.
  Reasoning through the code, the mechanism should hold (the 0.9 threshold sits early in the 1.0→0
  un-stow ramp, so the false edge should clear well inside 0.5 s even on a multi-second animation)
  — but that is inference, not a demonstrated case, on the one path explicitly flagged as
  uncertain. Add a `TestSeatGate` case: set `camera_fwd` to the operator eye point and
  `stick_park_value` to e.g. `0.95`, call `run_ai_pilot_wheel` once (arms `toggling_reference`),
  then drop `stick_park_value` below threshold and advance past `t + 0.5s`, and assert
  `#press_log == 0` and `ai_pilot_takeover.stage == nil`. Cheap (same harness as the existing
  `TestSeatGate` cases), and it is exactly what "do the new tests actually exercise the bug
  scenario" means for the one direction of the fix that isn't the originally-reported direction.

### Optional Refinements

- `ai_pilot_cam_fwd_m`/`apw_cam_fwd_m` is diagnostic-only and explicitly there "so one sortie
  settles" the unverified projection-origin assumption (per the code's own comment). Worth adding
  to the live-test instructions once this merges: watch `apw_seat`/`apw_cam_fwd_m` against the
  cockpit while switching seats and while in the 9K113 sight view, specifically to confirm the
  sight view reads as "no seat" (holds last) rather than a false "pilot" reading that would end
  AI flight mid-engagement. Not a blocker — the fallback behavior is already safe either way, this
  is about confirming *which* path is actually taken live.
- The `EyePoint` offset in `Views.lua` (`{0.05, 0.1, 0.0}` on both seats) is not folded into
  `SEAT_BOUNDARY_FWD_M`'s margin arithmetic in the comment. It's small relative to the ≥0.45 m
  margin and applies symmetrically to both seats, so it doesn't change the conclusion — just noting
  the comment's stated margin is very slightly optimistic, not wrong.

### Verdict
APPROVED WITH MINOR FIXES

The required fix is a test addition only — no production code is suspected wrong, and the
reasoning for why the existing code should already handle it is sound. Given the "Fix now"
directive and that the reported bug (pilot seat, AI wheel flapping forever) is fully fixed and
tested, I would not block the merge on this alone if the user wants it in now; I'd flag it as a
fast follow-up test before the next time this file is touched. Deferring to the orchestrator on
whether to loop back through Implementer for the one test or merge now and file it.

### Review Confidence
Full read — `ai_pilot_wheel.lua` in full, the complete diff, `Export.lua`'s call-site ordering,
`Views.lua`/`entry.lua` read directly from the installed DCS tree (not taken on the comment's
word), all touched tests read in full, full test suite run (806/807, one named pre-existing
flake unrelated to this diff), `ruff`/`mypy`/`luac5.1` run directly, `invariant-check` run.
