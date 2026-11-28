# Mi-24P right-pedal cap: adjustable stops, channel B, and the knob

**Date:** 2026-11-28
**DCS version:** 2.9.30.28738 (from `body-layer/config/effectors-raw/mi-24p.toml`'s own
generator header — not independently re-verified live this session; no DCS install was reachable
from this Mac session, so this is the version the registry was last generated against, not a
fresh check).
**Theatre:** not applicable (cockpit-system question, not terrain).

Context: DCS World video game add-on (Mi-24P / Petrobrain). "SAU", "pedal stops", "channel B" and
the cockpit controls below are simulated Mi-24P systems in a flight-sim mod; nothing here controls
real hardware.

### Question

What limits the Mi-24P's effective right pedal in flight in DCS (arg 1103), and what can
Petrovich do about it — channel B "adjustable stops", its knob, or something else?

### Findings

**What limits the pedal, functionally — settled, reproduced earlier, restated here for context:**

- Arg 1103 is the *effective* pedal (what the DCS controls overlay shows), not the cockpit pedal
  animation at full physical travel. **Evidence: reproduced-locally** —
  `docs/acceptance/2026-11-28-sortie-feedback.md`, "Third sortie".
- With the real stops panel in its stock/"ON" state, full right pedal (hand-flown, and separately
  Petrovich's own full-right write) pins arg 1103 at **−0.569**; with the stops panel in its "OFF"
  state, full right pedal reaches **−0.676** — about 19% more right-pedal authority with the stops
  off. Left side tops out at +0.247 with the stops on. **Evidence: reproduced-locally** (same
  source, both the player's hardware pedal and Petrovich's write hit the same −0.569 cap) — this
  is the strongest evidence in this note, because two independent inputs (a human foot and a
  scripted write) hit the identical number.
- All of these cap readings were taken at hover or below ~50 km/h. **Whether the cap changes with
  airspeed or altitude/air-density is unresolved** — see "Unresolved" below; this matters because
  the real system (next finding) is explicitly density-compensated, not simply on/off.

**The real aircraft's adjustable-stops system, identified from the manual — new this session:**

- `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` (167 pages, Russian; swept with
  `pdftotext -layout` + `grep`, per `.claude/agent-memory/investigator/
  reference_pdftotext_sweep_quickstart_pdf.md`), p.11 (§1.4 "Левый передний пульт летчика", the
  pilot's left front console, figure 1.5): item 6 is **"Блок управления 'ПОДВИЖНЫЕ УПОРЫ' (БУ-32)
  из комплекта СПУУ-52"** — "Control unit 'MOVABLE STOPS' (БУ-32), part of the СПУУ-52 kit" — a
  **separate panel from item 5, "Пульты управления САУ-В24-1"** (the SAU/AFCS panel), sitting next
  to it on the same console. **Evidence: documented** (the real-aircraft systems manual, not a
  DCS-specific source, but the canonical reference this project already relies on for Mi-24P
  systems — see the reference memory above).
- Item 7 on the same console, the **ДИСС+СПУУ-52 technical-check/test panel, is explicitly marked
  "(в игре не используется)"** — "not used in the game" — in the manual's own caption. **Evidence:
  documented.** This is DCS's own simplification being called out by the manual itself.
- p.37 (pre-flight/startup checklist, step 4): **"Установить выключатель 'ПОДВИЖ. УПОРЫ' в
  положение 'ВКЛ.' и убедиться в работоспособности системы СПУУ-52-3 по погасанию кнопки-табло
  'ПОДВИЖНЫЕ УПОРЫ' с красным светофильтром на пульте и по установке подвижного индекса нулевого
  индикатора в положение, соответствующее плотности воздуха."** — "Set the 'MOVABLE STOPS' switch
  to 'ON' and confirm the СПУУ-52-3 system works by the red-filtered 'MOVABLE STOPS' annunciator
  pushbutton extinguishing on the panel, and by the zero-indicator's movable index settling to a
  position corresponding to air density." A footnote adds that near sea level, at average/low
  outside air temperature (high density), the zero-indicator needle sits toward the right; at low
  density it may stay at its leftmost position. **Evidence: documented.** This matches the user's
  screenshot description closely: a small round gauge (the "zero indicator," reading air density)
  and a red push-button-with-annunciator ("MOVABLE STOPS" ON/self-test). **The real system is an
  automatic, air-density-compensated pedal-travel limiter** (more tail-rotor authority/pedal travel
  allowed at low density — altitude/heat — less at high density), not a simple airspeed schedule as
  this note's earlier draft guessed. Why DCS's own measured ON/OFF cap difference exists at all —
  "ON" applies the density-appropriate (tighter, at the sea-level-ish density the test flights were
  presumably near) limit, "OFF" bypasses the limiter for full mechanical travel — is consistent
  with this reading, though not independently confirmed inside DCS.
- Neither this manual, the pilot-interview transcript (`Mi-24 pilot interview RU transcript.txt`)
  nor `Goncharov-English-Summary.md` describes the black rotary knob or the "P↔T" toggle switch the
  user saw on the stops panel in their screenshot — a targeted grep for "упор"/"СПУУ"/"педал"/
  "плотност" across all three found only the two manual passages above. **Evidence: absence
  confirmed by a full-text sweep, not a page-range guess** — this is a genuine unresolved gap, not
  an unindexed one.

**Correction: SAU channel B is NOT the adjustable stops — user direction, 2026-11-28, superseding
this note's own first draft and two project documents:**

- The user confirmed live: **channel B is the ALTITUDE channel.** This matches the Cyrillic
  "В" = "высота" (height/altitude) reading, and the manual's own panel layout: SAU/АФЦС channels
  are listed as "YAW / ROLL / PITCH / ALT" (H/K/T/B) in the user's screenshot description, and the
  "STABILIZE SPEED"/"OFF" lamps and "BRIGHT/D" toggle the user also described match
  `SAU-SPEED-ON/OFF-PTR` (args 268/269) and `SAU-BRIGHT-DIM-PTR` (arg 267) by literal label text.
  **Evidence: documented** (user's own domain knowledge, which this project treats as its
  strongest available source for real Mi-24P systems the manual doesn't cover in full — see
  `plans/flight-lift-vector/explore-notes.md`, "SAU in mode 1").
- **This corrects two existing project documents that call channel B "adjustable stops":**
  `body-layer/ROADMAP/BL-16.md` ("...switches SAU H (heading), K (bank), T (pitch) and B
  (adjustable stops) ON...") and `plans/flight-lift-vector/explore-notes.md`'s transcription of the
  user's own earlier words ("'B' - adjustable stops cahnnel... Affects pedals to tail rotor force
  stabilization."). Both predate today's correction and should be updated by whoever next touches
  them — not done here, since this role does not write pipeline code or edit other modules' plan
  docs; flagging it is the deliverable. **The functional behaviour already built (switching B ON at
  every handover) is unaffected** — it is still correct to leave the altitude channel ON, just for
  the right reason now.
- `SAU-B-ON-PTR`/`SAU-B-OFF-PTR` (device 10, cmds 3013/3015, args 255/254) are channel B's (the
  altitude channel's) own ON/OFF buttons — already partly curated in
  `body-layer/config/sequences/mi-24p/effectors.toml` as `p_sau_b_channel_on` (OFF is not yet
  curated). `SAU-B-SWITCH-PTR` (device 10, cmds 3019 `ControlDown`/3017 `ControlUp`, arg 253,
  shape `springloaded_3_pos_tumb`, generic label "Autopilot Altitude Control") sits in the same
  positional pattern as `SAU-H/K/T-KNOB-PTR`'s own "channel delta correction" controls (each
  channel's own correction control's arg sits immediately before that channel's OFF/ON pair: 234 <
  236/237 for H; 240 < 242/243 for K; 246 < 248/249 for T; 253 < 254/255 for B). **Evidence:
  inferred, now the best-supported reading of this element**: it is channel B's own altitude
  delta-correction rocker (a spring-loaded nudge, where H/K/T instead got a continuous axis) — its
  generic "Altitude Control" label is in fact accurate, not stale, once B is known to mean
  altitude. **This supersedes this note's own earlier hypothesis** that `SAU-B-SWITCH-PTR` might be
  the adjustable-stops knob; it is not — it has nothing to do with pedal stops.

**The real stops control is in the registry after all — found on a second pass, under device 19
(`SPUU_52`), not under "SAU" or "stop"-shaped label text:**

- This note's first-pass grep searched for "stop"/"упор"/"limit"/"restrict"/"adjust" and missed
  **"SPUU"** — the device name literally transliterating СПУУ (the manual's own "СПУУ-52"), because
  the search was pattern-matched against "SAU"/"stop", not "SPUU". The element
  `SPUU-CONTROL-PTR` (springloaded 3-position, "P/NONE/T") was in fact visible in this note's own
  first `springloaded_3_pos_tumb` sweep, at the very end of the results — and was misread as
  unrelated. **Lesson for next time: grep the device list (`device_name`) directly, not just
  labels, whenever a system is named by its Russian initialism.**
- `body-layer/config/effectors-raw/mi-24p.toml` lines ~5276-5330, device 19, `device_name =
  "SPUU_52"`, four elements:
  - **`SPUU-ON-OFF-PTR`** — cmd 3010, arg **270**, "SPUU Power ON/OFF", `default_2_position_tumb`
    (a persistent switch, not momentary). **This is the best candidate for the control behind the
    measured −0.569 (on) vs. −0.676 (off) cap**: powering the whole СПУУ-52 unit off plausibly
    disengages the mechanical limiter entirely, giving full travel, matching the real system's
    description (the limiter's job is to *restrict* travel; removing power from it removes the
    restriction). **Evidence: inferred** — the device/arg identity is documented (the registry
    entry itself), but the causal link to the measured cap has not yet been flown against this
    specific arg.
  - **`SPUU-OFF-PTR`** — cmd 3001, arg **275**, "SPUU OFF (that's a button but acts like a
    switch)", `default_position_tumb`. The raw-dump curator's own parenthetical flags this as
    behaviourally ambiguous. Likely candidate for the manual's red-lit "ПОДВИЖНЫЕ УПОРЫ"
    annunciator-pushbutton (p.37: lit when the system is off/faulted, extinguishes when on and
    healthy) rather than an independent disable — **but this is not distinguished from an
    independent manual override without a live test**. **Evidence: inferred**, lower confidence
    than the power switch above.
  - **`SPUU-KNOB-PTR`** — cmd 3003, arg **276**, "SPUU Adjustment Knob", continuous 0..1, gain
    0.1667, `default_axis`. This is almost certainly the **black rotary knob** the user saw below
    the round gauge.
  - **`SPUU-CONTROL-PTR`** — cmds 3007 (`switchDown`)/3006 (`switchUp`), arg **277**, "SPUU
    Control Switch P/NONE/T", `springloaded_3_pos_tumb`. This is the **"P↔T" toggle** the user saw.
    Reading it against the manual's own startup-check description (p.37: the system derives a
    pedal-stop setting from **air density**, shown on a "zero indicator" gauge) and the standard
    aviation pairing of "P" and "T": **inferred, moderate confidence** — P/T most likely select
    which of **pressure** (давление) and **temperature** (температура) the knob manually drives.
    **Corroborated independently, raising confidence**: the user, unprompted by this hypothesis,
    described the real system's behaviour in these terms (2026-11-28, verbatim): *"For hover,
    ambient air temperature and altitude play a big role. At colder air and lower altitude, there
    is more control and right pedal is more effective. Higher up and/or hot air, the opposite."*
    This is exactly a density-scheduled pedal-authority system (lower density — high/hot — needs
    more pedal travel to produce the same tail-rotor thrust, so a fixed stop bites harder), matching
    both the manual's own "zero indicator... position corresponding to air density" description and
    the P/T reading above. **Two readings remain open and are NOT distinguished by anything
    available this session**: (i) P/NONE/T selects a ground-test input and the real scheduling is
    automatic/sensor-driven in normal operation ("NONE" = automatic), or (ii) P/NONE/T plus the
    knob is how the pilot *manually* sets the stop for the day's density — relevant precisely
    because the manual flags the sibling ДИСС+СПУУ-52 **technical-check panel** (not the stops
    unit itself) as "not used in the game": if DCS likewise does not model automatic density
    sensing for this unit, (ii) would mean **the knob is not a test control at all, but the only
    way the stop gets set correctly for the mission's actual altitude/temperature** — a real,
    actionable capability for Petrovich (dial it from the mission's known field elevation/OAT at
    start), not a side experiment. This is exactly the kind of claim that needs a live test before
    it is trusted; it is a plausible, now better-corroborated reading of the panel, not a confirmed
    one.
- **Why the earlier label-based search missed this for so long**: the registry's `label` field is
  generator-derived from ED's own source comments, and ED's comment for this device literally
  wrote the system's Russian initialism in Latin transliteration ("SPUU") rather than translating
  it to an English word like "stop" or "limiter" — so no English-synonym grep found it, and the
  fix was to grep `device_name` values directly instead of `label` text.
- **`p_spuu_power` (arg 270, `SPUU-ON-OFF-PTR`) is already curated and is now pressed ON by
  `config/sequences/mi-24p/seat-pilot.md`** (commit `ffa419f9`). **Evidence: documented** (the
  sequence file and its commit). This means Petrovich already turns the real stops system's power
  on when the player takes the pilot seat — consistent with "stops on" being the normal/expected
  state, and separate from this note's earlier, now-corrected SAU-channel-B framing. The other
  three SPUU elements (275/276/277) are not yet curated anywhere.

**The 0.32 write offset is a different, unrelated mechanism — already measured elsewhere, cited
for completeness:**

- `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, "Added 2026-11-24",
  measured `arg 1103 = 0.32 − command` in flight, at every command magnitude tested (not just near
  full deflection). The stops cap, by contrast, only engages near full deflection, and its own
  ON/OFF difference is ≈0.107 (0.676 − 0.569), not 0.32. **Evidence: inferred** (from two already-
  documented, independently measured numbers): these are not the same phenomenon. The main loop's
  earlier reading that conflated them (`docs/acceptance/2026-11-28-sortie-feedback.md`, "the main
  loop's earlier reading... was wrong; corrected here") already supersedes the merge, and this note
  agrees with that correction on independent grounds (the numbers don't match).

### Reproducible Test

The grep sweeps above are exactly reproducible:

```sh
grep -c "^\[elements\." body-layer/config/effectors-raw/mi-24p.toml   # 514
grep -n -i "SPUU" body-layer/config/effectors-raw/mi-24p.toml        # the four stops elements
pdftotext -layout "docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf" /tmp/quickstart.txt
grep -n -iE "упор|СПУУ|нулевой индикатор|плотност" /tmp/quickstart.txt
```

### Possible Approaches

- **Do not build "toggle channel B to relax the pedal cap"** — that idea rested on this note's own
  first-draft, now-corrected B = stops reading. Channel B toggling is still worth having for the
  altitude channel's own sake, but it will not touch the pedal cap.
- **The SPUU-52 device (19) is a real, already-reachable cockpit system** — `SPUU-ON-OFF-PTR`
  (power, arg 270) is already curated and wired into `seat-pilot.md`. Petrovich can toggle it
  (and, once curated, `SPUU-OFF-PTR`/`SPUU-KNOB-PTR`/`SPUU-CONTROL-PTR`) through the existing
  `cockpit_switch`/effector-sequence mechanism — no new project mechanism is needed, only new
  curated entries in `body-layer/config/sequences/mi-24p/effectors.toml` once the probe below
  confirms what each one actually does. **This replaces the earlier, now-withdrawn reading that
  the real stops control might be a non-cockpit DCS "Special Option" outside Petrovich's reach.**
- **Fly the probe before building anything that changes the pedal cap automatically.** The one
  settled fact (next bullet) is actionable without it; the SPUU-specific causal claims above are
  all labelled inferred and should not be built against until flown.
- **The already-settled, reproduced finding is actionable now, independent of which SPUU control
  turns out to cause it**: the right-pedal cap measurably sits at ≈ −0.57 "stops on" vs. ≈ −0.68
  "stops off" at hover/low speed, **at this mission's ~925 m ASL field, unknown temperature**. The
  user's own mitigation (2026-11-28) — ease collective and accept a slight descent, or gain speed
  if there is altitude to spare; act before the left-yaw runaway starts, since there is no pedal
  left once it does — can be built into Petrovich's near-pedal-limit guidance. **But do not hard-
  code −0.569 (or any other single number) as `pedal_limit_positive`** — the user's own account
  (temperature/altitude change the real margin materially) and the hand-flown note's own reading
  ("Petrovich's limits must therefore come from what he measures in flight... not from these fixed
  values") both say the cap is condition-dependent. The guard should detect the live cap (the
  pedal commanded at/near full travel while the arg settles short of it) rather than assume a
  figure measured on one mission. `pedal_limit_positive` is currently 1.0 (per `.claude/agent-
  memory/reviewer/project_bl16_pedal_near_limit_guard_regression.md`'s own context, BL-16
  lift-vector law), so the near-limit collective guard does not yet see any real cap at all —
  fixing that is a design decision for Architect, not this note, but the "measure, don't hardcode"
  constraint should carry into that design.
- **If the probe shows DCS does not auto-sense density (reading (ii) above)**, a further,
  separate design question for Architect: whether Petrovich should set the SPUU knob from the
  mission's known field elevation/OAT at startup, as a new effector-sequence action alongside the
  existing `seat-pilot.md` SPUU-power-on step. Not designed here — flagging the possibility is the
  deliverable of this investigation.
- **`aircraft-layer/dcs-export/Export.probe-pedal-stops.lua`** (this session) drives device 19
  (`SPUU_52`) directly: hold full right pedal at hover/low speed while the probe cycles
  `SPUU-ON-OFF-PTR` (270, off then on), `SPUU-OFF-PTR` (275, on then off), `SPUU-KNOB-PTR` (276,
  0.0/0.5/1.0/back to 0.0) and `SPUU-CONTROL-PTR` (277, pulsed P → NONE → T → NONE), logging arg
  1103 and all four SPUU args before/after each step and continuously while it runs. Lua syntax
  checked (`luac5.1 -p`); not yet flown. See the card below for the exact run.

**Corroboration from the 2026-11-28 hand-flown sortie (hover/transitions):**

- `aircraft-layer/research/2026-11-28-mi24p-hand-flown-trim-and-transitions.md` (committed on
  this branch's later tip, `e6f7ba28`/`bd15551c` — read via `git show`, not yet present at this
  investigation's own starting commit) measured the hover trim directly: with the stops on, right
  pedal sits at **−0.53…−0.56** at hover (collective +0.50) — i.e. **the pilot hovers with almost
  no right-pedal margin left** (0.01–0.04 from the −0.569 ceiling), and the pedal pins at the stop
  in 12 runs during the same sortie. That note's own "Limits" section independently reaches the
  same P/T hypothesis this note does, and records the flight's own conditions: **field elevation
  ≈ 925 m ASL** (from `LoGetSelfData` at mission start), **temperature not logged**. Its own
  closing line: *"the adjustable stops may be set for ambient air density, which would make the
  ceiling itself condition-dependent. Unverified; being researched."* — this note is that research
  landing. **Evidence: reproduced-locally** for the measured trim/cap numbers; **inferred** for the
  density link, same confidence level as above.
- That note also draws the operational consequence this note's "Possible Approaches" should carry
  forward: *"Petrovich's limits must therefore come from what he measures in flight (where the
  pedal is against the stop), not from these fixed values."* — whatever the SPUU knob turns out to
  do, a single hard-coded cap number (e.g. hard-coding −0.569 into `pedal_limit_positive`) would be
  wrong on a different mission's altitude/temperature; the guard should detect the live cap (pedal
  commanded at/near ±1 but the arg stuck short of it) rather than assume a fixed figure.

### Unresolved

- **What `SPUU-KNOB-PTR` (276) and `SPUU-CONTROL-PTR` (277, P/NONE/T) actually do to the pedal
  cap, in flight** — the P/T-selects-density-input reading is a plausible inference from the
  panel's grammar, the manual's density-indicator description, and the user's own independent
  account of the real system's altitude/temperature sensitivity, but it is not a confirmed one. The
  probe above is designed to settle this directly.
- **Whether DCS models automatic density sensing for this unit at all, or only the manual
  knob/switch** — i.e. reading (i) vs. (ii) above. This decides whether the knob is a side
  experiment or Petrovich's only way to set the stop correctly per mission (dialled from field
  elevation/OAT at start) — a materially different build either way, so this should be settled
  before any such mechanism is designed, not assumed.
- **Whether `SPUU-ON-OFF-PTR` (270) alone reproduces the measured −0.569 → −0.676 jump**, or
  whether `SPUU-OFF-PTR` (275) is also/instead needed — both are inferred from label text and the
  manual, neither flown against the specific arg yet.
- **Whether the pedal cap is scheduled by airspeed, air density, or both inside DCS** — every DCS
  measurement to date is from missions at a similar, unlogged temperature; the 2026-11-28 sortie's
  field elevation (≈925 m ASL) is known but its temperature is not, so even the one data point
  available does not pin down the relationship.
- **Whether the 2026-11-18 sortie's "stops OFF" phase was produced by 270, 275, or some
  combination** — not re-derived here; the probe above answers this once flown.

## Probe flown (2026-11-28, ~20:01)

**Source:** `docs/acceptance/logs-2026-11-28/pedal-stops-probe.log` (gitignored, local). Same
mission as the hand-flown hover sortie. User: *"OAT ~13 C, same mission as earlier hover logs, to
same OAT"*. Field ≈ 925 m ASL; flown at 140–250 m AGL, so ≈ 1 070–1 175 m pressure altitude.
Steps flown: BASELINE, POWER-OFF, then a full press to DONE (power back on). Steps 3–12 (OFF
button, knob sweep, P/t switch) were **not** flown.

| step | SPUU power (arg 270) | knob (276) | IAS while pinned | full-right effective pedal (arg 1103) |
|---|---|---|---|---|
| BASELINE | 1 (mission default) | 0.5 (mission default) | 32–35 km/h | **−0.565** |
| POWER-OFF (Petrovich's own write, cmd 3010 → 0) | 0 | 0.5 | 25–78 km/h | **−0.678** |
| DONE (cmd 3010 → 1) | 1 | 0.5 | 81 km/h | back to −0.571 within ~4 s |

**Verified:**
- **SPUU-52 power (arg 270, `p_spuu_power`) alone causes the right-pedal cap**: off → −0.678, on →
  −0.57. The write works from Export (`performClickableAction(19, 3010, v)`, `ok=true`), so
  Petrovich can switch the stops himself. This settles the 2026-11-18 / hand-flown "stops off"
  phase as this switch.
- **No airspeed schedule between 25 and 78 km/h**: with the stops off the cap sat at −0.678 flat
  across that whole range; with them on, −0.565 at 32–35 km/h (and −0.567…−0.569 at hover in the
  hand-flown sortie). Above 80 km/h untested.
- The mission starts the knob at **0.5** and the P/t switch centred.

## Probe flown, second run — every step (2026-11-28)

**Source:** `docs/acceptance/logs-2026-11-28/pedal-stops-probe-2.log` (the file also holds the first
run). Same mission and OAT. All steps flown, full right pedal held throughout, IAS 35 → 140 km/h.

| step | write | full-right effective pedal (arg 1103) |
|---|---|---|
| BASELINE (power on, knob 0.5) | — | −0.567, pinned 37–118 km/h |
| POWER-OFF | 270 → 0 | **−0.678** |
| POWER-ON | 270 → 1 | **−0.566** |
| OFF-BUTTON on / off | 275 → 1 / 0 | −0.566 / −0.566 (no effect) |
| KNOB 0.0 / 0.5 / 1.0 / 0.0 | 276 | −0.566 throughout (no effect) |
| SWITCH P / NONE / T / NONE | 277 pulses | −0.565…−0.566 (no effect) |

**Verified:**
- **The power switch (270) is the only control that moves the right-pedal cap**, reproducibly:
  off −0.678, on −0.566, switched both ways by Petrovich's own write.
- **The OFF button (275), the knob (276) and the P/t switch (277) change nothing measurable** in the
  cap in DCS (each write `ok=true`, the args moved). Whatever they model in the real SPUU-52, DCS does
  not expose it through the pedal ceiling here.
- **No airspeed schedule from 14 to 140 km/h**: with power on the cap is −0.565…−0.567 flat across
  the whole range flown (both runs); with power off −0.678 flat across 21–78 km/h.
- Side effect: the run left the knob at 0.0 (mission default 0.5) — immaterial, since it does nothing.

**Still open:** whether the caps move with OAT or altitude (one data point: 13 °C, ≈ 1.1 km); whether
−0.678 is a further limit or full travel at this density (the ground measurement read −1).
