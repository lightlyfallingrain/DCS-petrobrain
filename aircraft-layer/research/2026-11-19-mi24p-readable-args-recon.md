# Mi-24P readable cockpit values — gauges, lamps, and rotor RPM specifically

**Date:** 2026-11-19
**For:** `[[BL-B132]]`
**DCS version:** not verified locally this session — no DCS install reachable from this worktree
(Mac, DCS runs on the Windows box). Numbers below carrying "cross-checked" status were
independently corroborated in a prior session against the installed Mi-24P at **DCS 2.9.29.27278**
(`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`); the rotor-RPM args found
*this* session come from a third-party source clone, not a local DCS read, and carry no such
cross-check.
**Theatre:** n/a (cockpit-only question)

### Question

Which Mi-24P cockpit values can Petrobrain *read* — gauges, needles, lamps, warning lights — and
what are their arg numbers/names, with **rotor RPM (main-rotor tachometer, not engine/
turbocompressor RPM)** as the specific target for `[[BL-B132]]`.

### What was already known (graph + memory search first)

`.claude/scripts/gq.sh` and `memory-search.py` turned up no prior investigation of rotor RPM
specifically. The existing readable-state corpus
(`aircraft-layer/research/mi24p-command-surface.md` §3/§4/§6/§7, `2026-11-16-mi24p-operator-
altimeter-recon.md`, `2026-10-21-dcs-bios-mi24p-9k113-controls.md`, `2026-10-17-9k113-effector-
and-slew-probe-findings.md`, `2026-10-22-9k113-ai-latency-probe.md`) is **all 9K113/ASP-17/
sight-and-weapon focused**. None of it touches engine or rotor instruments. The one existing
engine-adjacent fact is `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`
Finding 3: `list_cockpit_params()` returns ~112-116 `BASE_SENSOR_*` values including
`BASE_SENSOR_LEFT_ENGINE_RPM`, with **no rotor RPM entry anywhere in that sweep** (the sweep is a
small, fixed flight-model/FFB parameter set, not a general cockpit-state dump). No existing
research file names a rotor RPM arg number. **This question was genuinely unanswered**, not
re-investigated.

### Findings

1. **Rotor RPM arg numbers (pilot and operator) — evidence: documented (third-party source),
   independent of a local DCS read.** Cloned `github.com/DCS-Skunkworks/dcs-bios` (shallow,
   `--depth 1`, fetched 2026-11-19) and read
   `Scripts/DCS-BIOS/lib/modules/aircraft_modules/Mi-24P.lua` directly (lines 18-24):

   | identifier | arg | seat | gauge range |
   |---|---|---|---|
   | `PLT_ROTOR_RPM` | **42** | pilot | `{0, 1}` |
   | `OP_ROTOR_RPM` | **845** | operator | `{0, 1}` |
   | `PLT_ROTOR_PITCH` | 36 | pilot | `{0, 1}` (collective/blade-pitch indicator, adjacent gauge) |
   | `PLT_ENG_L_RPM` | 40 | pilot | `{0, 1}` |
   | `PLT_ENG_R_RPM` | 41 | pilot | `{0, 1}` |
   | `OP_ENG_L_RPM` | 838 | operator | `{0, 1}` |
   | `OP_ENG_R_RPM` | 839 | operator | `{0, 1}` |

   `defineFloat(identifier, arg_number, {min, max}, category, description)` is DCS-BIOS's generic
   float-gauge wrapper, and `Module.lua` shows it does exactly one thing: `dev0:get_argument_value
   (arg_number)` on every export tick — the identical call shape this project already uses for
   874/876 (9K113 sight angle) and confirmed identical in `2026-10-21-dcs-bios-mi24p-9k113-
   controls.md` Q1. So **the read call for rotor RPM, if this holds, is simply
   `GetDevice(0):get_argument_value(42)`** (pilot) / `get_argument_value(845)` (operator) — no
   device object needed, same pattern as every other draw-argument read in this module.

2. **The `{0, 1}` range is the raw draw-argument range, not a percent-RPM calibration — evidence:
   inferred.** DCS-BIOS's `defineFloat` third argument is the *gauge's own* input range as the
   aircraft module declares it (compare 9K113's non-`{0,1}` azimuth/elevation ranges, which *are*
   physically meaningful because the module's own gauge declares them that way). For the rotor
   tachometer, `{0, 1}` most likely means "normalised needle position, 0 = needle at its mechanical
   zero stop, 1 = needle at full deflection" — the same shape as every switch-position arg in
   `mi24p-command-surface.md` §7. **What physical %RPM (e.g. 0-120% Nr) that 0..1 spans is not
   established by this source** — that mapping lives in `Devices_specs/*.lua` or the gauge's
   `CreateGauge(...)` call in `mainpanel_init.lua`, exactly the pattern
   `2026-11-16-mi24p-operator-altimeter-recon.md` used for the altimeter (`input {0..10000} ->
   output {0..1}`) and `mi24p-command-surface.md` §4.1 used for the 9K113 sight angle. **Neither
   file is reachable this session** (no DCS install). A real-world Mi-24 rotor tachometer (УИ-21/
   similar) typically reads 0-120% Nr with a redline ~95-107%, but that is general-helicopter
   background knowledge, not something read from this module's files — **do not treat it as the
   calibration without reading `mainpanel_init.lua`'s `CreateGauge` call for arg 42/845.**

   **Working assumption, user 2026-11-19:** *"very likely that is value * 100 = rotor rpm per
   cent. Unless the dial goes to over 100%, that has to be checked in cokpit."* So until checked:
   %Nr = arg value × 100. The check is the dial's top mark in the cockpit (or the `CreateGauge`
   output range): if the scale runs past 100% (e.g. to 110% or 120%), the mapping is value × that
   maximum instead.

3. **Does `BASE_SENSOR_LEFT_ENGINE_RPM` include rotor RPM? No — it is a separate, engine-only
   quantity, and DCS-BIOS's own data confirms the module treats them as entirely separate args.**
   `PLT_ROTOR_RPM` (42) and `PLT_ENG_L_RPM`/`PLT_ENG_R_RPM` (40/41) are three different draw
   arguments on three different gauges in the same "Engine Gauges" DCS-BIOS category — the module
   itself distinguishes rotor speed from each engine's own turbine speed. `BASE_SENSOR_LEFT_ENGINE_
   RPM` (from `list_cockpit_params()`) is almost certainly the flight-model source feeding the
   gauge at arg 40/41 (or a close cousin of it), not arg 42/845 — **evidence: inferred**, from the
   naming match and the "flight model quantity" framing in Finding 3 of the 2026-09-09 probe; not
   cross-checked against arg 40/41 directly this session.

4. **Does the engine RPM proxy fall when rotor RPM droops, or rise with collective? — evidence:
   inferred / forum-claim-unverified; genuinely unresolved, not something this session's sources
   settle.** A WebSearch for Hoggit's `LoGetEngineInfo` documentation returned no Hoggit page
   (404s) and only DCS-forum threads reporting inconsistent, module-dependent behaviour — one
   2012-era thread describes a `{RPM, Temperature, FuelConsumption}`-shaped table existing for
   some aircraft, a 2019 thread reports it broken for the F-18C, and posters generally fall back to
   `get_argument_value()` instead — **evidence: forum-claim-unverified**, and this project's own
   memory on forum reliability (`feedback_forum_403_fallback`) already treats such threads as weak.
   On the mechanics itself: in a real turboshaft helicopter, the free turbine (Nf/engine RPM) and
   main rotor (Nr) are coupled through a reduction gearbox with a free-wheeling (sprag) unit that
   only transmits torque one way — during normal powered flight a governor holds both near a
   target RPM, so raising collective increases torque demand and the governor compensates by
   increasing fuel flow to **hold** Nf (and therefore Nr) roughly constant, with only a brief
   transient droop if the governor can't react instantly; under engine failure or during
   autorotation the free-wheeling unit lets Nr diverge from a falling Nf. **Whether DCS's Mi-24P
   flight model actually implements this governor/free-wheel coupling, and whether
   `BASE_SENSOR_LEFT_ENGINE_RPM` moves with it in a way a probe could see, is not established by
   anything read this session** — it is general turboshaft-helicopter background, not a DCS-file
   or forum finding, and is exactly what Unresolved item 1 below would settle.

5. **Full readable inventory from the Mi-24P module — proposed shape and current best source.**
   No local `mainpanel_init.lua`/`clickabledata.lua` read was possible this session (no DCS
   install reachable). The best available substitute is the same DCS-BIOS source file used for
   Finding 1, which is comprehensive for this module:

   | DCS-BIOS call | count | roughly maps to |
   |---|---|---|
   | `defineFloat` | 177 | continuous gauges/needles (incl. rotor/engine RPM, altimeter, temps, pressures) |
   | `defineIndicatorLight` | 229 | lamps/warning lights, gated read of a draw argument |
   | `defineToggleSwitch` | 267 | switch *positions* (write-and-readback pairs; overlaps `mi24p-command-surface.md` §7/§10) |
   | `definePushButton`, `defineMultipositionSwitch`, `defineRotary`, `definePotentiometer`, `defineTumb`, others | ~120 combined | other control shapes |

   — **evidence: documented (third-party GPL-3.0 source), not reproduced-locally against this
   project's own installed tree.** The licensing posture is unchanged from
   `2026-10-21-dcs-bios-mi24p-9k113-controls.md`'s "Licence" section: arg-number *facts* (DCS's own
   cockpit, not DCS-BIOS's creative expression) are lower-risk to cite than reproducing DCS-BIOS's
   source tables verbatim as a shipped file — that line is Architect/the user's to draw if this
   project ships a derived table built from this source, exactly as flagged there.

   **Proposed generator-consumable shape**, mirroring the existing write-side convention
   (`body-layer/config/effectors-raw/mi-24p.toml`, rendered by `switch-reference.md`'s generator):
   a parallel `readable-args-raw/mi-24p.toml`, keyed by identifier, one table per arg:

   ```toml
   [args.PLT_ROTOR_RPM]
   arg = 42
   kind = "float"              # float | lamp | string
   category = "Engine Gauges"
   seat = "pilot"
   gauge_range = [0.0, 1.0]
   physical_mapping = "unknown"  # filled in once CreateGauge/Devices_specs is read
   label = "PILOT Rotor RPM"
   source = "cross-ref:dcs-bios Mi-24P.lua:18"   # vs "mainpanel_init.lua:<line>" once read locally
   confidence = "documented-thirdparty"           # vs "reproduced-locally" once confirmed
   ```

   This keeps the "which source, what confidence" distinction a generator would need to merge a
   DCS-BIOS cross-reference pass with a later direct `mainpanel_init.lua` read without losing
   provenance — the same reason `effectors-raw/mi-24p.toml`'s header records input file hashes and
   DCS build. **A generator for this does not exist yet** — this is a proposal for Architect, not
   a built tool; writing it is pipeline code, out of this role's scope.

6. **Rotor-adjacent lamps, by name only, not yet arg-confirmed against this project's own tree.**
   The same DCS-BIOS file (not reproduced verbatim here beyond identifiers/args, per the licensing
   note above) names a `PLT_ROTOR_BRAKE` toggle switch (device 3, cmd 3011, arg **745** — this one
   *is* cross-checked: `mi24p-command-surface.md` line 1961 independently lists
   `ROTOR-BRAKE-PTR` at the same arg 745, device/command matching `LEVER_Rotor_Lock`/`ENGINE_
   INTERFACE`/745 exactly) and a `PLT_CB_R_ROTOR_RPM` circuit breaker (device 1, cmd 3078, arg
   **606** — also independently cross-checked, `mi24p-command-surface.md` line 2076:
   `CB-RIGHT-ROTOR-RPM-ADJUST-PTR` at the same device/cmd/arg). Neither is a rotor RPM *readout*;
   both are switches whose *position* is readable the same way as any §7 switch.

### Reproducible Test

Not run live this session (no DCS access). For whoever next has the Windows box:

1. **Confirm arg 42/845 are real and calibrated.** In the pilot and operator seats, with the
   rotor spun up (ground idle through to flight RPM), log `GetDevice(0):get_argument_value(42)`
   and `(845)` once per second across a full engine start, and separately
   `GetDevice(0):get_argument_value(40)`/`(41)`/`(838)`/`(839)` for the engine gauges. Compare the
   rotor arg's trajectory against the cockpit's own tachometer needle on screen (screenshot
   timestamps, same technique as `2026-09-09-pb15-ambient-callout-live-probe.md`) to confirm it
   moves with the rotor and not the engine.
2. **Find the physical calibration.** Grep `mainpanel_init.lua` for `arg_number = 42` / `845` (or
   whatever the gauge variable is named near them) and read its `CreateGauge`/output-range call —
   the exact technique already used for 874/876 (§4.1) and the altimeter (`2026-11-16-...-recon.md`
   §A). This resolves Finding 2's "what does 0..1 mean in %Nr" gap.
3. **Settle Finding 4** (engine-vs-rotor coupling): log arg 42/845 (rotor) alongside
   `BASE_SENSOR_LEFT_ENGINE_RPM`/`BASE_SENSOR_RIGHT_ENGINE_RPM` and args 40/41/838/839 (engine
   gauges) through a deliberate collective pull and, if safe to test, a simulated engine-out —
   the only way to see whether the governor holds them together or whether the free-wheeling unit
   lets them diverge in this flight model specifically.
4. **If a fuller inventory is wanted**, read `mainpanel_init.lua`/`clickabledata.lua` directly
   (the same two files `effectors-raw/mi-24p.toml`'s generator already parses for the write side)
   rather than leaning further on the DCS-BIOS cross-reference — `dcs-file-investigation` skill has
   the path map.

### Possible Approaches

- **Short term, for `[[BL-B132]]`:** treat arg 42 (pilot)/845 (operator) as the rotor-RPM read
  candidates, gated as "documented (third-party), not yet cross-checked against this project's own
  tree" until Reproducible Test step 1 runs. This is the same confidence tier `2026-10-21-dcs-bios-
  mi24p-9k113-controls.md` used for 874/876 before its own cross-check landed — a known, workable
  interim state, not a blocker.
- **For the physical-units gap (Finding 2):** until `mainpanel_init.lua` is read, treat the rotor
  RPM value as a **relative/normalised indicator** (0 = low, 1 = high) rather than a calibrated
  percentage in any body-layer consumer — e.g. a threshold-based "rotor RPM looks low" callout
  could use a provisional cutoff against the raw 0..1 value, flagged explicitly as uncalibrated,
  rather than block on the exact %Nr mapping.
- **For the full-inventory ask (Finding 5):** the DCS-BIOS source is a legitimate reference-only
  cross-check (per the existing recommendation in `2026-10-21-dcs-bios-mi24p-9k113-controls.md`),
  not a dependency — reading it answers "what probably exists and at what arg" cheaply, but a
  shipped generator/table should still be built from this project's own `mainpanel_init.lua`/
  `clickabledata.lua` read, both for licensing cleanliness and because DCS-BIOS itself warns (via
  its absence of a sight-readiness lamp) that third-party surveys have gaps.

### Unresolved

- Whether arg 42 (pilot)/845 (operator) actually track the rotor and not something else — no live
  probe this session.
- The 0..1 → physical %Nr calibration for both rotor and engine RPM gauges (needs
  `mainpanel_init.lua`'s `CreateGauge` call, not reachable this session).
- Whether `BASE_SENSOR_LEFT_ENGINE_RPM`/`_RIGHT_ENGINE_RPM` correspond to arg 40/41 specifically,
  versus some other internal flight-model channel.
- Whether rotor RPM droop under collective/engine-failure is observable in this flight model at
  all, and through which of the above channels — Finding 4 is background knowledge plus unverified
  forum chatter, not a DCS-specific answer.
- A full, locally-sourced (not DCS-BIOS-cross-referenced) inventory of the module's ~177
  `defineFloat`-shaped gauges and ~229 lamps, keyed to this project's own confirmed arg numbers —
  Finding 5 proposes the shape; building it needs a live `mainpanel_init.lua`/`clickabledata.lua`
  read.
