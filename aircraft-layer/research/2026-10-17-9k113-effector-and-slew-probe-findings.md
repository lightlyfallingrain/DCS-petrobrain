# 9K113 effector and slew probes — findings, 2026-10-17

Two live runs on the user's Windows box, both flown 2026-10-17:

| run | script | log |
|---|---|---|
| effectors | `aircraft-layer/dcs-export/Export.probe-9k113-effectors.lua` | `aircraft_layer_probe_9k113_effectors.log`, 22:12–22:20 |
| slew only | `aircraft-layer/dcs-export/Export.probe-9k113-slew.lua` | `aircraft_layer_probe_9k113_slew.log`, 22:27–22:30 |

Cards: `docs/acceptance/2026-10-17-9k113-effectors-probe.md`,
`docs/acceptance/2026-10-17-9k113-slew-probe.md`. Pilot's own observations between the two runs:
`docs/acceptance/2026-10-17-9k113-effectors-probe-results.md`.

---

## 1. The headline: Decision 1 inverts. The AI axis is dead; the player axis works.

**`plans/9k113-effectors/plan.md` §0 argues — at length, and on the strength of a five-point live
measurement from 2026-09-11 — that the AI axis (3060/3061) is a working position target and the
player axis (3025/3026) is the unverified one. Measured today, both halves of that are false.**

| channel | commanded | arg 874 (az) / 876 (elev) |
|---|---|---|
| **AI axis 3061** (azimuth) | −40°, −20°, 0°, +20°, +40°, then 12 staircase steps of 0.002 | **0.00000 throughout. Never moved once.** |
| **AI axis 3060** (elevation) | −0.50, −0.25, 0, +0.25, +0.50, then 12 staircase steps | **0.00000 throughout. Never moved once.** |
| **player axis 3026** (azimuth) | +0.5 held ~3 s, then −0.5 | **0 → 0.165 → 0.330, then back to −0.00000** |
| **player axis 3025** (elevation) | +0.5 held ~3 s, then −0.5 | **0 → −0.28125 → −0.56250, then back to 0** |

Every `SetCommand` returned `ok=true` in both cases, so **the return value says nothing** — the AI
axis accepts the call and does nothing with it. Only the argument readback distinguishes them.

This held in **both** runs, under different setups:

- Run 1 wrote the warm-up switches itself (wrongly ordered, by the pilot's own reading) and tested
  the AI axis at t=67–98 s with 885/886 both reading 1.0. Nothing moved.
- Run 2 had the aircraft set up by hand, correctly, with `OBSERV` confirmed on at t=60 s
  (`886 = 1.00000`), and tested the same commands at t=63–139 s. Nothing moved — **and then the
  player axis moved the head immediately afterwards in the same run, same device, same
  `SetCommand` method.** That is the controlled comparison: the call path works, the AI commands
  are the part that is inert.

**Consequences, which are large:**

- **The rate loop is back.** §0's whole argument — no controller, no empirical deflection law, no
  deadband, no limit-cycle risk, no `BL-B63` dependency — rested on the AI axis being available.
  It is not.
- **`BL-B63` (the fast lane) returns as a hard dependency**, exactly as `BL-B66`'s own entry said
  under direction §12 before the plan argued it away. A rate-commanded loop cannot close at 1 Hz.
- **Direction §12 was right about the mechanism and right about the channel.** The user wrote
  *"The axis input is the slew speed… we need a constant inspect and adapt loop"*. The plan
  re-read that as a statement about the crewman rather than about our command channel. It was
  both.
- **The plan's own scope caution now applies**: with the rate loop mandatory rather than optional,
  the honest read is to narrow `BL-B66` to the switch work plus `OBSERV`, and file the slew loop
  as its own entry gated on `BL-B63`.

### What is *not* established

**Why the 2026-09-11 measurement disagrees.** That pass recorded the AI axis settling in 0.25 s
with `arg_874 = value × 0.44` at five points, and it is a reproduced-locally finding, not folklore.
Something differs between then and now — a DCS update renumbering a positional command, a
different call path, or an AI-ownership precondition (the AI axis may only answer while the sight
is under Petrovich's control rather than idle). **This probe cannot tell which**, and the open
question is worth naming rather than quietly overwriting the older finding: `mi24p-command-surface.md`
§4.1.2 keeps its CORRECTION note, with this result recorded beside it.

Note also that the log's version line reads `DCS table: 000002273D839D20` — `LoGetVersionInfo()`
returned a table whose fields print as an address, so **the build number was not captured**. Every
argument and command number here is positional. Fixing that line is a one-line change to both
probes and should happen before the next run.

---

## 2. The player axis is a rate command, and it is fast

Azimuth converts cleanly using the existing calibration (`arg_874 = (deg/60) × 0.44`, i.e.
`0.0073333` per degree):

| sample | arg 874 | degrees |
|---|---|---|
| before | 0.00000 | 0.0° |
| +0.2 s | 0.16500 | **22.5°** |
| +1.5 s, +2.8 s | 0.16500 | 22.5° |
| +3.5 s (after release) | 0.33000 | **45.0°** |

Then −0.5 walked it back symmetrically: 0.33 → 0.165 → −0.00000. Elevation did the same shape at
−0.28125 → −0.56250 and back, **sign-inverted** against the command (+0.5 drove the argument
negative) — which matches the repo's existing note that player elevation 3025 is inverted relative
to the argument while AI elevation 3060 is not.

**~45° of azimuth in one ~3-second hold at half deflection** is 13–16°/s depending on whether
motion stopped at the release write (t+2.8 s) or ran to the sample (t+3.5 s). The device spec's
`h_axis_velocity = rad(20)/s` makes 10°/s the expectation at 0.5 deflection, so the real figure is
roughly 1.3–1.6× that. Either the deflection-to-rate map is not linear, or 0.5 already saturates.

**Unresolved, and it is a probe-design gap rather than a DCS unknown:** the four samples per hold
show two discrete plateaus (22.5°, then 45°) rather than a ramp. A rate command should produce a
ramp. Two readings fit — the argument readback is quantised or lagged, or the motion really is
stepped — and **this probe cannot separate them because it only sampled four times per hold.** The
heartbeat logs the slew arguments only every 5 s or on a *switch* change, so the trace between
samples was never recorded. **The fix is one line: log every change of 874/876 per frame.** Until
that run happens, no deflection law should be fitted to these numbers.

---

## 3. Switch writes: all five, confirmed, with an animation ramp

Run 1, every one of the five took, from the pilot's seat, against the operator's panels:

| arg | switch | device · cmd | before → target | final |
|---|---|---|---|---|
| 673 | SAFETY SWITCHES ARMAMENT CIRCUITS | `WEAP_SYS` · 3020 | 0 → 1 | **1.0** |
| 955 | ЩО `PWR` | `WEAP_SYS` · 3030 | 0 → 1 | **1.0** |
| 885 | `GUID.UNIT POWER` | `I9K113` · 3001 | 0 → 1 | **1.0** |
| 886 | `OBSERV.` (НАБЛ) | `I9K113` · 3002 | 0 → 1 | **1.0** |
| 963 | launch-station selector | `WEAP_SYS` · 3038 | 0 → 0.1 | **0.1** |

All five restored cleanly at the end of the run. The pilot's reading — *"several swithces moved ->
assume we can move all"* — is if anything conservative: all five moved, across both devices.

**Devices 6 (`WEAP_SYS`) and 7 (`I9K113`) had never been written to before this run**; everything
proven previously was devices 30 and 55. That generalisation is now made.

**One mechanical detail worth building around:** a switch write **animates over ~3 frames** rather
than snapping. Every toggle logged `0.32 → 0.64 → 1.00` within ~0.1 s, and the restore pass showed
the same ramp in reverse (`0.68 → 0.36 → 0.00`). So **a readback taken immediately after the write
will catch an intermediate value**, and any sequencer that verifies a switch before moving to the
next one must either wait a few frames or accept a tolerance. The project's own 1 s inter-switch
delay (a modelling choice, not a manual requirement) already covers this comfortably.

---

## 4. The `READY` lamp is not readable — `list_indication` confirmed negative

- **`list_indication(8)` (`ccGunnersCPanel`) returned 0 bytes**, unpowered and powered alike. The
  index was never tried before; it is now tried and empty.
- **`list_indication(0)` (the sight's own channel) returned 3,582 bytes both times — byte-identical
  before and after power.** It is the 9K113 viewport's *element tree and key-binding help text*
  (`ENLARGMENT FACTOR [LCTRL+X]`, `LASER PROTECT [RALT+G]`, `KNOBS IN NEUTRAL [RCTRL+I]`,
  `LAUNCH MISSILE [RCTRL+SPACE]`), not instrument state.

**There is a node named `Ready_9k113`** in the `SCENE` child list, alongside `Grid_9k113`,
`SteeringLine` and `BG_9k113_Orange` — but it carries **no value**, and the dump does not change
when the guidance unit is powered. So the element exists in the tree and its *state* does not reach
Lua, which is the same shape as the already-confirmed native-only getters (`isGyroReady`,
`isLaunchPermission`). **Finding 2's `list_indication` workaround is closed as unavailable.**

One incidental readable: `txt_NABLTips` carries `OPEN SIGHT DOORS` as live prompt text. Not a
readiness signal, but it is real text from the sight's own panel and it is the only element in the
dump that is not a static label — worth a second look if a state-ish string is ever needed.

**Low cost to have asked**: this was the "keep it only if the sortie has room" question, and it
closed a workaround that two findings were leaning on.

---

## 5. What this changes, as a list

1. **`plans/9k113-effectors/plan.md` Decision 1: answer is the player axis, by elimination.** §0's
   recommendation is withdrawn by measurement, not by argument.
2. **`BL-B63` is a hard dependency of the slew half of `BL-B66`** — restored, not newly discovered;
   the entry said so before the plan argued it away.
3. **`BL-B66` splits sensibly**: the switch sequence and `OBSERV` are unblocked and buildable now;
   the slew loop is blocked on `BL-B63` and on one more probe run (per-frame slew logging) before
   any deflection law is fitted.
4. **`mi24p-command-surface.md` §4.1.2 needs this result recorded beside its CORRECTION**, not
   instead of it — two live measurements disagree and the reason is unknown.
5. **Both probe scripts need the version line fixed** (`LoGetVersionInfo()` returns a table; print
   its fields) before any further run, because every number here is positional.
