# Push-to-talk gate: can Export.lua read a held cockpit control?

**Date:** 2026-09-19
**DCS version:** 2.9.29.27278 (per `aircraft-layer/research/mi24p-command-surface.md`'s primary-
source dump; this session did not run a live probe against it — see Unresolved)
**Theatre:** n/a

### Question

For `srs-adapter` Slice 3 (inbound speech/STT), the plan needs a push-to-talk gate: a control the
player holds down while speaking to Petrovich, readable as a *held state* by
`aircraft-layer/dcs-export/Export.lua`. Everything this project currently reads from the player is
a discrete event (F10 radio menu). A held/momentary control had never been verified as readable.
Concretely: (1) can `Export.lua` read a momentary cockpit control's state while held, via
`GetDevice():get_argument_value()` and/or `LoGetAircraftDrawArgumentValue()`; (2) what tick
rate/latency would that give; (3) if the answer is no, what stdlib-only alternatives exist on the
Windows box.

### Findings

- **`GetDevice(0):get_argument_value(<arg>)` is already confirmed callable from this project's own
  `Export.lua`, live, on this airframe.** It is the same call this project already uses for the
  9K113 sight's azimuth readback (arg 874) — `aircraft-layer/research/2026-09-11-petrovich-detection-readout.md`,
  `mi24p-command-surface.md`, `Export.probe-commands.lua`/`Export.probe-wheel.lua`/
  `Export.probe-detection.lua` all confirm `GetDevice(0)` (the mainpanel device) is reachable and
  `get_argument_value` on it returns live, moving values from inside `LuaExportAfterNextFrame`.
  This settles the general mechanism question outright. — **evidence: reproduced-locally** —
  **source:** the files above.

- **`Export.lua` never calls `LoGetAircraftDrawArgumentValue()`** — this project's existing code
  and research use the device-object form (`GetDevice(id):get_argument_value(n)`) exclusively. No
  finding either way on whether the free-function form works too; not needed since the device form
  is already proven for this airframe.

- **The Mi-24P's own pilot PTT trigger is a real, specific, already-identified argument:
  `GetDevice(0):get_argument_value(738)`.** Source: `Scripts/DCS-SRS/Scripts/DCS-SRS-Modules/Mi24P.lua`,
  fetched live this session from `github.com/ciribob/DCS-SimpleRadioStandalone` (current `master`,
  via `gh api repos/.../contents/...`, not a forum paraphrase). The relevant lines:

  ```lua
  local _pilotPTT = SR.getButtonPosition(738)
  if _pilotPTT >= 0.1 then
      if _pilotPTT == 0.5 then
          -- intercom
          _data.selected = 0
      end
      _data.ptt = true
  end
  ```

  and elsewhere in the same repo's core script (`Scripts/DCS-SRS/Scripts/DCS-SimpleRadioStandalone.lua`):

  ```lua
  function SR.getButtonPosition(_args)
      local _value = GetDevice(0):get_argument_value(_args)
      return _value
  end
  ```

  So `SR.getButtonPosition(738)` **is** `GetDevice(0):get_argument_value(738)` — the exact call
  this project's own Export.lua already makes for other args, on the exact same device object
  (`GetDevice(0)`, mainpanel). — **evidence: documented** (primary source: the shipping SRS
  project's own current code) — **source:**
  `github.com/ciribob/DCS-SimpleRadioStandalone/blob/master/Scripts/DCS-SRS/Scripts/DCS-SRS-Modules/Mi24P.lua`
  and `.../DCS-SimpleRadioStandalone.lua`.

- **This is a graduated/continuous value, not an edge-triggered pulse — exactly the "held state"
  shape a PTT gate needs.** Arg 738 reads 0.0 released, ~0.5 at the trigger's first (intercom)
  stop, and (inferred from the `>= 0.1` / `== 0.5` branching, not directly stated) some higher
  value at the full/radio-transmit stop — a real two-stage spring-loaded trigger whose position is
  polled every export cycle, not a click event. SRS's own logic (`if _pilotPTT >= 0.1`) depends on
  reading it continuously while held, which is the same access pattern the PTT gate needs.
  — **evidence: documented** (same source) — **source:** as above.

- **Independent cross-validation that this project's own installed DCS version agrees with SRS's
  arg numbers, for two adjacent args (not 738 itself).** `Mi24P.lua` also reads the SPU-8 mode
  selector at arg 455 (`SR.getSelectorPosition(455, 0.2)`) and the hot-mic switch at arg 456
  (`SR.getButtonPosition(456) >= 1.0`). This project's own primary-source clickabledata dump
  (`aircraft-layer/research/mi24p-command-surface.md`, generated 2026-09-11 directly from
  `Mods/aircraft/Mi-24P/Cockpit/Scripts/{command_defs.lua,devices.lua,clickabledata.lua}` on DCS
  2.9.29.27278) independently lists exactly those two: `SPU8-MODE-PTR ... 455` and
  `SPU8-EXT-PTR ... 456`. Two independently-sourced files agreeing on two arg numbers for this
  exact airframe/version is meaningfully stronger evidence than the SRS source alone. — **evidence:
  reproduced-locally** (the 455/456 half) + **documented** (the SRS source) — **source:**
  `mi24p-command-surface.md` lines ~2330-2332, cross-checked against the SRS fetch above.

- **Arg 738 itself does not appear anywhere in this project's own clickabledata dump.** Checked —
  no line in `mi24p-command-surface.md` mentions `738`. The most likely explanation, consistent
  with the rest of that file's own documented caveats: the clickabledata/PTR table only enumerates
  *mouse-clickable* cockpit elements, and a physical trigger control is normally HOTAS/axis-bound
  (a joystick button), never a mouse-clickable 3D-model hotspot — so it would legitimately be
  absent from that enumeration while still being a real, readable device argument. This is
  **inferred, not confirmed** — the alternative explanation (738 is stale/wrong for this specific
  installed version) cannot be ruled out without a live read. — **evidence: inferred** — **source:**
  reasoning from `mi24p-command-surface.md`'s own documented scope (clickable-controls table only).

- **A dedicated probe script has been written and is ready to run** —
  `aircraft-layer/dcs-export/Export.probe-ptt.lua`. Self-contained (no collector needed), follows
  this project's existing probe-script pattern (`Export.probe-wheel.lua` etc.), logs arg 738
  (candidate PTT) alongside 455/456 (already-confirmed sanity check) on every value change, with a
  bounded sample count. Includes an explicit short-press (<200ms) test step to directly answer the
  "can a short momentary press be missed" question live, not just by argument.

- **Tick rate: `LuaExportAfterNextFrame` runs every DCS simulation frame, not throttled to the 5 Hz
  telemetry export rate.** This project's own `Export.lua` and its BL-6 command-injection feature
  already depend on and confirm this: the file's own comment (`Export.lua` lines ~445-447, ~519-521)
  states command handling "runs every frame, ahead of that function's own 5 Hz export throttle
  check, so a command is never delayed behind the telemetry export cadence" — the 5 Hz gate
  (`last_export_t`) only governs the *outbound telemetry push*, not the function's own call rate.
  Live diagnostic logging (referenced in the same file, `aircraft-layer/research/` stage-5 findings)
  measured **~8ms between consecutive `LuaExportAfterNextFrame` calls** in one prior live test —
  i.e. roughly 120 Hz, though this is one measurement on one machine/mission and not a guaranteed
  floor. — **evidence: reproduced-locally** (the BL-6 command-polling behavior and the ~8ms
  measurement are both from this project's own prior live tests) — **source:** `Export.lua` itself
  (comments + `poll_command_socket` structure), `aircraft-layer/CLAUDE.md` "Tech stack" note on the
  same point.

- **A held PTT gate at this poll rate would not plausibly miss a deliberate press.** At ~8-30ms per
  frame (conservatively even at DCS's typical 30-60 fps floor if that prior ~8ms figure doesn't
  hold on every machine), any press held for the hundreds of milliseconds a real "hold to talk"
  gesture takes spans many samples. Only a press shorter than a single frame (a few ms) could be
  missed entirely — well below what any player's press-and-speak gesture would produce. This is a
  reasoned inference from the measured/documented tick rate, not a separate live measurement of
  press-detection reliability itself (that's exactly what the new probe script's short-press step
  is for). — **evidence: inferred**.

- **Whether a *separate, spare* control is needed, or the existing intercom trigger can simply be
  reused, has a real answer worth flagging to Architect.** Arg 738's own semantics — half-press
  (~0.5) selects the **intercom** channel specifically, distinct from the full press which
  transmits on whatever radio the SPU-8 selector has chosen — mean the Mi-24P already has a
  real, in-fiction, physical control whose entire purpose is "talk to my own crew," independent of
  which mission-frequency radio is selected. This doesn't collide with the earlier, already-decided
  constraint that the player must stay on the mission frequency (`audio-adapter/research/2026-09-17-tts-audio-transport-recon.md`'s
  "frequency injection is NOT an acceptable fallback" note — that subproject was named
  `srs-adapter` when this note was written and the path was corrected 2026-09-21): the SPU-8 selector's radio choice is
  untouched by a half-press, since half-press routes to intercom regardless of `_data.selected`.
  Reusing this existing trigger — reading `GetDevice(0):get_argument_value(738)` for "player is
  half-pressing the real intercom trigger" — would need **no new joystick binding at all**, and it
  matches the real aircraft's own crew-communication control 1:1. This is a design option for
  Architect to weigh against a dedicated spare-button binding (which this session could not
  identify — no DCS install access to search `clickabledata.lua`/`command_defs.lua` for genuinely
  unbound args; see Unresolved). — **evidence: inferred** (mechanically sound reasoning from the
  documented SRS logic, not itself tested) — **source:** as above.

- **No DCS installation access from this session.** `DCS_INSTALL_PATH` is unset in this
  environment; `win-mac-sync/` (the Dropbox-symlinked cross-machine transfer folder described in
  `world-model/WORKFLOW.md`) does not exist in this worktree/session either. Everything above that
  is marked reproduced-locally comes from this project's own **already-committed** research files
  and probe/Export.lua source (prior sessions' live tests), not a fresh probe run this session. The
  new `Export.probe-ptt.lua` is written and ready, but running it requires the user to copy it to
  `Saved Games\DCS\Scripts\Export.lua` on the Windows box per the existing probe workflow
  (`aircraft-layer/WORKFLOW.md`) and fly the steps in the script's own header comment.

### Reproducible Test

`aircraft-layer/dcs-export/Export.probe-ptt.lua` — deploy as `Export.lua`, fly the six steps in its
header comment (settle 5s, half-press hold ~1s, full-press hold ~1s, one deliberate short press
(<200ms) of each stage, cycle the SPU-8 selector), bring back
`Saved Games\DCS\Logs\aircraft_layer_probe_ptt.log`. Confirms or refutes: arg 738 exists and moves
on this installed version; its half-press value (~0.5) and full-press value; whether every
deliberate press (including the short one) produced at least one logged sample.

`gh api repos/ciribob/DCS-SimpleRadioStandalone/contents/Scripts/DCS-SRS/Scripts/DCS-SRS-Modules/Mi24P.lua --jq .content | base64 -d`
— re-fetches the primary source this finding is built on, in case SRS updates it.

### Possible Approaches

- **Recommended: read arg 738 directly, and let Architect choose between "reuse the real intercom
  trigger" and "bind a spare control" once the live probe confirms 738's exact values.** The
  mechanism (`GetDevice(0):get_argument_value`) is already proven in this codebase; the only
  remaining open item is confirming 738's specific value on this exact install, which the new probe
  answers cheaply (one short flight, no collector/pipeline changes needed to test it).
- **If 738 turns out stale/wrong for this version**: the clickabledata dump's own documented
  Fragility note (`mi24p-command-surface.md` §9 — "command IDs are positional and will shift if ED
  inserts an entry into a table") applies to *commands*, not necessarily to draw-argument indices,
  but the same caution is worth carrying over. Re-derive by regenerating the clickabledata dump
  (already-existing tooling, `Export.probe-commands.lua`'s general approach) and cross-checking
  against a fresh pull of SRS's `Mi24P.lua` for the current arg number.
- **If, for some reason, no cockpit-argument PTT path holds up**, Q3's stdlib-only alternative
  (not needed on current evidence, but noted since the task asked): raw Windows joystick polling
  via `ctypes` against `winmm.dll`'s `joyGetPosEx`/`joyGetPos` (part of the Windows API, no `pip`
  package), reading the physical button state directly rather than through DCS's own argument
  table. This would run inside `aircraft-layer`'s existing Python collector process (already
  Windows-side, already stdlib-only) rather than in `Export.lua`, and would need no DCS
  cooperation at all — a real, non-package option, but strictly a fallback: it bypasses DCS's own
  modeling of which control state the player intends (e.g. it can't distinguish "half-press
  intercom" from "full-press radio" the way arg 738 does) and duplicates work DCS/SRS's own export
  already does for free.

### Unresolved

> **Addendum 2026-09-20 (Windows box, `clickabledata.lua` read directly).** Two of the four items
> below are closed, and a third is explained. `elements["STICK-PTT-PTR"]` declares
> `arg = {738, 738}`, `arg_value = {1.0, 0.5}`, `arg_lim = {{0.0, 1.0}, {0.0, 0.5}}`,
> `crew_member_access = {0}` — so **738 is the pilot stick trigger, full press (LMB, radio) = 1.0,
> right press (RMB, intercom) = 0.5, released 0.0**, first-party and no longer inferred from SRS.
> `elements["OP-STICK-PTT-PTR"]` is the operator's, **arg 856**, identical encoding. The reason 738
> was missing from `mi24p-command-surface.md` is a generator blind spot, not a stale arg: that dump
> captures the `default_*(…)` helper forms only, and 13 of `clickabledata.lua`'s 749 elements are
> raw table literals — including both PTTs and both collectives. Full detail:
> `2026-09-20-dcs-install-detection-deep-read.md` finding 11.

- ~~**Arg 738's exact live values on this project's installed DCS version are not yet confirmed**~~
  — **the declared values are now read first-party** (addendum above). What a live probe would still
  add is what `get_argument_value` actually *returns* mid-sortie, which is a different claim from
  what `clickabledata.lua` declares; `Export.probe-ptt.lua` remains the way to close that, and has
  not been run.
- **Whether the copilot-seat equivalent (arg 856 — now confirmed first-party as
  `OP-STICK-PTT-PTR`, `crew_member_access = {1}`) matters at all** — out of scope unless the player ever flies from the gunner seat, which this
  project's design (pilot seat, AI gunner) does not do; noted only so a future reader doesn't
  wonder why it wasn't checked.
- **Whether a genuinely spare/unbound control exists as an alternative to reusing arg 738** — not
  investigated this session (would need a full `clickabledata.lua`/`command_defs.lua` re-read
  hunting for something unused, which needs DCS install access this session didn't have). Given the
  intercom-trigger-reuse option above looks mechanically clean and requires no new binding, this is
  probably not worth pursuing unless Architect specifically wants a control independent of the real
  intercom function.
- ~~**Full-press (radio-transmit) numeric value of arg 738**~~ — **RESOLVED 2026-09-20: 1.0**,
  stated directly by `arg_value = {1.0, 0.5}` in `clickabledata.lua:1009-1025`. The guess of "~1.0"
  was right.

---

### Addendum 2026-09-23 — the stdlib-only fallback is confirmed working, first-party

The last bullet of "Possible Approaches" listed raw Windows joystick polling through `winmm.dll`'s
`joyGetPosEx` as a fallback "if, for some reason, no cockpit-argument PTT path holds up", and noted
it as a real but untested option. It has now been **run on the user's own Windows box**
(`audio-adapter/tools/probe_joystick.py`, which shares its binding with the production
`audio-adapter/src/ptt_source.py` rather than carrying its own copy):

- **Four devices answer, ids 0-3.** The specific doubt was that `joyGetPosEx` predates DirectInput
  and addresses devices by a small numeric id, so a multi-device pit (stick, throttle, pedals)
  might appear only partially. It does not — all four are enumerated and pollable.
- **A held press is read as a held state.** Device 2, button 0, **613 ms held**, down and up edges
  both captured. This was the second half of the doubt: an API that reported only edges would have
  been unusable as a talk gate.
- **Evidence: reproduced-locally** (the user ran it; output pasted into the session).

This does not change the recommendation for Stage 5 — arg 738's right press remains the in-fiction
control, needs no new binding, and its declared values are already first-party. What it changes is
that **Stage 4 no longer depends on Stage 5**: capture has a real, held, physical talk control on
Windows today, with DCS closed, so the whole speech chain can be exercised before any sim
dependency exists. That was the reason for preferring a joystick button over the plan's manual
`--capture-window-s` stub, and it now rests on a measurement rather than an expectation.

**Not probed, still:** `Export.probe-ptt.lua` remains unrun, so what `get_argument_value(738)`
actually *returns* mid-sortie is still a different claim from what `clickabledata.lua` declares.

---

### Addendum 2026-09-23 (second) — arg 738 read live, in flight, and it behaves

`Export.probe-ptt.lua` has now been run (user, Windows box). **This closes the last open item in
this note.** Three presses of the user's own bound PTT, logged as transitions:

```
#2 t_model=2.881 ptt(738)=0.5
#3 t_model=3.709 ptt(738)=0
#4 t_model=4.246 ptt(738)=0.5
#5 t_model=4.455 ptt(738)=0
#6 t_model=8.008 ptt(738)=0.5
#7 t_model=8.817 ptt(738)=0
```

- **738 is live on this install and returns exactly the declared value.** 0.5 pressed, 0.0
  released, matching `clickabledata.lua`'s `arg_value = {1.0, 0.5}` for `STICK-PTT-PTR`. The
  argument number is confirmed by *runtime behaviour*, not only by declaration.
  — **evidence: reproduced-locally.**
- **The player's existing HOTAS binding drives the cockpit argument.** This was the sharper of the
  two risks and it was never stated in the original note: a DCS binding can be a *game action* that
  never animates the cockpit control, in which case the argument would be right and still never
  move for a real press. It moves. No mouse-click control test was needed.
  — **evidence: reproduced-locally.**
- **It is a held state, not an edge pulse.** Each press logs one transition to 0.5 and the next
  transition ~0.8 s later, so the value *stayed* 0.5 across every intervening frame. The original
  note inferred this from SRS's `>= 0.1` branching; it is now observed.
- **A 209 ms press was captured.** The short-press step answered its own question: the momentary
  control is not missed at this poll rate, with two full orders of magnitude of margin against the
  frame time. The "could a brief press be missed" risk is closed.

**Not observed: the full-press value.** Every press in this run read 0.5, so 1.0 (radio) is still
declaration-only. That is not a gap for the PTT gate — see the design consequence below — but it
means any code that wants to *distinguish* radio from intercom is still working from the declared
value.

**Design consequence, and it is a real decision rather than a threshold choice.** SRS gates on
`>= 0.1`, which treats both stops as "transmitting". Petrovich should not: **the full press is the
player talking on the radio to someone else, and Petrovich has no business hearing it.** The right
gate is the intercom stop specifically — `abs(v - 0.5) < 0.1` — which is also what the real
aircraft does, since the half press routes to intercom regardless of what the SPU-8 selector has
chosen. Gating on `>= 0.1` would make every radio call to ATC an utterance aimed at the crew.

**One oddity worth recording, not chased.** Wall-clock and model time disagree across the run
(24 s of wall clock between samples #5 and #6 against 3.5 s of model time), so the mission was
paused or the session was not running at 1:1. It has no bearing on the readings — each press is
internally consistent in model time — but anyone timing something from this log should not use the
wall clock.
