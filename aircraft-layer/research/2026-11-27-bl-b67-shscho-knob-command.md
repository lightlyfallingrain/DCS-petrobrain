# BL-B67 — the SHSCHO (launch-station selector) knob: correct device/command for Export.lua

**Date:** 2026-11-27
**DCS version:** not verified locally this session — no DCS install reachable from this (Mac) dev
machine. The two primary-source readings this finding rests on were taken on the Windows DCS
machine in prior sessions: `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`
states DCS build unknown (`LoGetVersionInfo()` printed as a table address, "build number was not
captured" — a known gap in that probe, not resolved here); `aircraft-layer/research/mi24p-command-surface.md`
states DCS **2.9.29.27278** (build 20260826-084519), generated from the installed
`clickabledata.lua`/`command_defs.lua`/`devices.lua`. The 2026-11-27 Stage 0 sortie that exposed
the bug this note explains did not record its own DCS build either.
**Theatre:** n/a — cockpit-scripting question, not terrain-specific.

### Question

The 2026-11-27 Stage 0 probe sortie (`docs/acceptance/2026-11-27-bl-b67-stage0-probe-feedback.md`,
Q3) found that `GetDevice(7):performClickableAction(3038, n * 0.1)` does **not** move the SHSCHO
(ЩО, launch-station selector) knob — cockpit arg 963 stayed `0.000` for every scripted write,
n = 1..8, while the user turning the knob by hand moved arg963 in steps of 0.1, and the same
device 7 with command 3029 (Radiation Reset, arg 882) did work. What is the correct device id,
command id, and value convention for writing this knob from `Export.lua`?

### Findings

- **The probe used the wrong device id. The knob is not on device 7 (`I9K113`) at all — it is on
  device 6 (`WEAP_SYS`).** — **evidence: documented, primary-source read of the installed Lua
  twice over, from two independent prior sessions, and reproduced-locally once** —
  **source:**
  - `aircraft-layer/research/mi24p-command-surface.md:2245`, the generated `clickabledata.lua`
    dump: `SHSCHO-KNOB-PTR  WEAP_SYS  weapon_commands.Operator_SWITCHER_LAUNCH_STATION  963` —
    explicitly `WEAP_SYS`, not `I9K113`.
  - The same file's device-id table (§2): `6 | WEAP_SYS`, `7 | I9K113` — two different device
    numbers.
  - `body-layer/config/sequences/mi-24p/switch-reference.md:213`: `SHSCHO-KNOB-PTR … multiposition_switch | [3038] | [963] | 0 to 0.8 (9 steps)` — same control, same command id, device not
    printed in that table but consistent with the other two sources.
  - **Reproduced-locally, live, 2026-10-17**: `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md` §3's results table has a row the Stage-0 probe's own author did not
    cross-check against: `963 | launch-station selector | WEAP_SYS · 3038 | 0 → 0.1 | **0.1**` —
    writing cmd 3038 on device `WEAP_SYS` (device 6) with target value `0.1` moved arg 963 from
    `0` to `0.1`, live, in that same probe run. That is the knob actually moving, under the
    correct device.
  - The confusion is understandable: `command_defs.lua`'s `start_command = 3000` restart means
    **every** device-local command table reuses small IDs (`mi24p-command-surface.md` §1,
    "Critical consequence") — `3038` is `weapon_commands.Operator_SWITCHER_LAUNCH_STATION` on
    `WEAP_SYS`, and a *different* `3038` exists in at least four other tables in the same file
    (`BatteryRightEXT`, `FuelMeterEXT`, `Command_CPT_MECH_Elements_Hide_EXT`, `RouteOn`, and
    `STARTUP_APU_Launch_Method_ITER`, per the same file's full dump) — the command number alone is
    meaningless without the device id, exactly the trap §1 names. The Stage-0 probe's own comment
    justified device 7 by analogy ("the same device id the production Export.lua already uses for
    this unit"), but that analogy only holds for the *other* commands it sends on device 7
    (`Command_POWER_PN` 885/`Command_NABL` 886, both genuinely on `I9K113`) — not for this one,
    which sits on the weapons panel (`WEAP_SYS`) despite being colloquially "part of the 9K113
    system."
  - Why `3029` (Radiation Reset, arg 882) *did* work on device 7: unresolved by this session
    whether that command is itself on `I9K113` or coincidentally tolerant — not re-derived here,
    out of scope for this question, and not contradicting the finding above (a working control on
    the same device number does not establish that *every* command number on that device is
    correctly addressed there).

- **Value convention: absolute set, not increment/step index.** — **evidence: reproduced-locally**
  — **source:** same 2026-10-17 row — the write specified target value `0.1` and the readback
  settled at `0.1`, not at a step-index encoding (e.g. `1`) or a relative delta. This also matches
  the clickable-helper analysis independently done from the installed `clickable_defs.lua`/
  `clickabledata.lua` (`aircraft-layer/research/2026-10-23-mi24p-clickable-value-ranges.md`):
  `SHSCHO-KNOB-PTR` is built with `multiposition_switch(hint, dev, cmd, arg, count_, delta_, inversed_, min_, anim, cycled_, crew)` called as `963, 9, 0.1, …` — `count_=9`, `delta_=0.1`,
  `min_` defaulting to `0` — and that helper's documented settable-value set (same note's helper
  table) is `min_ + k*delta_` for `k = 0..count_-1`, i.e. exactly `{0, 0.1, 0.2, …, 0.8}`, the
  **absolute cockpit-arg position**, matching both the hand-turned steps the user observed
  (`arg963` moving in 0.1 steps) and the one live scripted write that worked. There is no evidence
  anywhere read this session of a relative/step-index convention for this control.

- **Why this reads as "the knob can't be moved from Export.lua" when it can**: the 2026-11-27
  probe's own `maybe_advance_station`/sweep logic (`Export.probe-weapons.lua`) wrote
  `GetDevice(7):performClickableAction(3038, n * 0.1)` — correct command id and correct value
  convention, wrong device. A device mismatch in `performClickableAction` is not documented
  anywhere read this session to raise an error or return `false`; the 2026-10-17 note itself
  observed "every `SetCommand` returned `ok=true`" even for a command later shown to be inert for
  an unrelated reason (the AI sight axis), so a silent no-op on a device/command mismatch is
  consistent with everything already known about this API's error behaviour — **evidence:
  inferred**, not a documented error-handling guarantee; no source read this session states what
  `performClickableAction` does when the device has no matching command id, only that it does not
  visibly fail.

- **`LoGetPayloadInfo().CurrentStation` and the knob — still not shown to be the same thing.**
  The 2026-11-27 Stage 0 result (`…probe-feedback.md` Q1) recorded the knob moving (by the
  user's hand) at probe-t 63, 191, 284–291, 346 while `CurrentStation` stayed `0` until t≈356,
  then became `3` — i.e. `CurrentStation` did **not** track the knob's position at all during
  this sortie. **Evidence: reproduced-locally (a real negative observation), but inconclusive
  on the underlying relationship** — this session's reading of the knob was itself via the wrong
  device/no-op script, so nothing here rules out `CurrentStation` tracking the knob correctly
  once writes are fixed; it only shows that **in this sortie, with the knob changed exclusively by
  hand**, the two did not move together on any poll recorded. Finding 14 of
  `aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md` already flagged this
  mapping as fully open before this probe flew, and that remains true — this sortie neither
  confirms nor refutes it, since the knob-write half of the probe never actually moved the knob to
  correlate against.

### Reproducible Test

A minimal re-probe, one line different from the 2026-11-27 script's existing sweep
(`Export.probe-weapons.lua`'s `DEV_I9K113`/`CMD_KNOB` constants):

```lua
local DEV_WEAP_SYS = 6   -- was DEV_I9K113 = 7; SHSCHO-KNOB-PTR is on WEAP_SYS, not I9K113
local CMD_KNOB = 3038    -- unchanged, already correct for this device
...
GetDevice(DEV_WEAP_SYS):performClickableAction(CMD_KNOB, n * 0.1)
```

Fly with the same sweep (steps 1..8, two seconds apart), watch arg 963 in the readback log.
Expected per the 2026-10-17 result: arg963 settles at `n * 0.1` on each step, with the same
~3-frame animation ramp already documented for other `WEAP_SYS`/`I9K113` switches (same note, §3,
"a switch write animates over ~3 frames"). While this is running, also log
`LoGetPayloadInfo().CurrentStation` every poll to finally test the Q4 mapping question against a
knob that is actually moving this time.

### Possible Approaches

- **Immediate fix for BL-B67 Stage 0**: change the probe's knob-write device constant from 7 to 6
  and re-run. No other part of the sweep/auto-advance logic needs to change — command id, value
  convention, and timing assumptions are all already correct per the findings above.
- **Guard against the same class of mistake elsewhere**: any future `performClickableAction` call
  built "by device-family analogy" (assuming a command belongs to the same device as a visually
  or conceptually related control) should be checked against `mi24p-command-surface.md`'s own
  per-element device column, not inferred — the restart-at-3000 numbering makes device id the only
  thing that disambiguates a command, and this is exactly the trap §1 of that file already
  documents in the abstract; this is a concrete instance of it.
- **`CurrentStation`-to-knob mapping (Q4, still open)**: once the knob write is fixed, the cheapest
  next step is exactly what `2026-10-29-bl-b67-loadout-and-atgm-object-recon.md` Finding/Approach
  already proposed — poll `LoGetPayloadInfo().CurrentStation` alongside the (now-working) knob
  write and see whether it tracks numerically. This note does not resolve that question, only
  removes the reason the previous attempt could not test it.

### Unresolved

- **Why command 3029 (Radiation Reset) worked on device 7** while 3038 did not — not
  investigated this session (out of scope for the knob question), and not needed to fix the knob
  write, but worth a line of curiosity before trusting device 7 for any *other* new command by
  analogy: it may be coincidentally correct for 3029 specifically (if Radiation Reset really is an
  `I9K113` command) rather than evidence that device-7 writes are generally tolerant of wrong
  commands.
- **Whether `performClickableAction` ever raises or returns a detectable failure signal for a
  device/command mismatch**, as opposed to the silent no-op observed twice now (2026-11-27's knob,
  and 2026-10-17's inert AI-axis commands for an unrelated reason) — no source read states this;
  worth a dedicated probe only if silent failures elsewhere start costing debugging time.
  **DCS version this would need to be checked on**: whichever build the user is currently running —
  neither of the two readings this note relies on captured a build number for the write path
  itself (see "DCS version" above).
- **`CurrentStation` vs. the knob's step value** — unresolved by this sortie (see Findings above);
  needs the re-probe.
