# The 9K113 warm-up sequence and ATGM employment procedure — from the DCS Mi-24P QuickStart

**Date:** 2026-10-14
**DCS version:** not verified locally this session — no DCS install reachable from this (Mac)
worktree. The one DCS-install-derived source cited below (`mi24p-command-surface.md`) was itself
generated 2026-09-11 against the installed tree, DCS **2.9.29.27278** (build 20260826-084519); its
device/argument/command numbers are current as of that date and are **positional** — they will
shift if ED inserts an entry into a `clickabledata.lua`/`command_defs.lua` table on a later patch.
**Theatre:** not applicable (cockpit systems, not terrain).

This is the Investigator pass `BL-B64` calls for. It fills the `TBD`s in `docs/concept/9K113.md`
(the user's own specification, not edited by this note) by reading the sections that document
names in `docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf`, and cross-references the
already-DCS-install-derived `aircraft-layer/research/mi24p-command-surface.md` for device/command/
argument numbers. Does not write pipeline code and does not edit `docs/concept/9K113.md`.

### Question

Resolve `docs/concept/9K113.md`'s `TBD`s: the warm-up switch table, the "sight ready" indication
and its DCS readability, the OBSERV gyro-alignment wait time, which ATGM type(s) DCS supports and
their speed/range, whether the wide/narrow FOV figures are already in this repo, the weapons safety
circuit switch's device argument, the guidance-unit transmitter reset button, and whether 9K113
state (slew, OBSERV, gimbal limits) is exportable to ownship telemetry.

### Findings

#### 1. The warm-up switch sequence — now a real table

**Source: §4.6.7 (pp. 66–70) and §5.3.8 steps 1–11 (pp. 105–111) of the Russian QuickStart PDF.**
§5.3.8 is the full, numbered ATGM employment checklist and is by far the stronger source — it is
procedural, in DCS's own English cockpit-label terms (screenshots carry English UI text even though
the body text is Russian), and it is what the game actually expects the crew to do. §4.6.7 is the
reference/parts-catalogue chapter the spec also named; it describes the same panels but not as a
sequence.

**Evidence: verified from primary source**, for the steps and labels below — the reset-sequence
timings (210 s, 3–4 min, 10–15 s) are the PDF's own numbers, not inferred. Device/command/argument
columns are **verified from primary source (reproduced-locally)** where they trace to
`mi24p-command-surface.md`'s confirmed-live entries, and **unresolved** where no matching entry was
found there — see the notes under the table.

| # | Seat / panel | Switch (DCS cockpit label) | To position | Device · command · arg | Notes |
|---|---|---|---|---|---|
| 1 | Commander, front-right panel | `AUX STORES LIGHTS` | ON | **unresolved** (not in `mi24p-command-surface.md`'s captured set) | Enables stores-present lamps + red PUVL backlight. Minor; not gating. |
| 2.1 | Commander, PUVL | `SIGHT / CAM` | ON | unresolved | PDF: *"for ATGM launch this is not 'electrically' necessary."* Optional. |
| 2.2 | Commander, PUVL | weapon-type selector knob | `OFF (MSL)` | `WEAP_SYS` · `Pilot_SWITCHER_OFF_GM_URS_NPU` · arg **523** | Needed for intercom and for the ASP-17 to display the 9K113 line-of-sight mark. |
| 3 | Commander, ASP-17 panel (VG-17) | `AUTO / MAN` | AUTO | `ASP_17V` · `Manual_Auto` (cmd 3001) · arg **553** | So the pilot's HUD mark follows the operator's guidance-unit line of sight (computed by 9K476). |
| 4 | Operator, left panel | `SAFETY SWITCHES ARMAMENT CIRCUITS` | ON | `WEAP_SYS` · `Operator_SWITCHER_SAFE_WEAP` (cmd 3020) · arg **673** | **This is the weapons safety circuit switch `BL-B65` asked about** — see Finding 6. |
| 5 | Control Panel (ПК) | `OPER / CHECK` | confirm OPER | unresolved | A verification step, not an action — PDF says only to confirm position. |
| 6 | Operator, right instrument panel | `MISSILE POWER` (УРСы — ПИТАНИЕ УРС) | ON | `WEAP_SYS` · `Operator_URS_POWER` · arg **773** | |
| 7 | Operator panel (ЩО, labelled `9С475`) | `PWR` (B1) | ON | `WEAP_SYS` · `Operator_POWER_SHO_SWITCHER` · arg **955** | **Starts the ~3-minute warm-up.** Powers 9С475/9С476/9С477; lamps `COMP ON` and `LNCHR OFF` light; a program timer starts counting **210 seconds**, which the PDF's own annotation (not the manual's official prose — see confidence note below) attributes to warming the command radio-link equipment. |
| 8 | Control Panel (ПК) | `GUID.UNIT POWER` (B1) | ON | `I9K113` · `Command_POWER_PN` · arg **885** | Lamp `GUID UNIT POWER` lights at full brightness; `HEATING Г`/`В` lamps also light. |
| — | *(wait)* | — | — | — | **After 3–4 minutes from steps 7–8**, see Finding 2. |
| 9.1 | — | ШТВ-91 panel | shows `READNS.` placard | — | Readiness indication, airframe side. |
| 9.2 | Operator panel (ЩО) | green `READY` lamp | lights | — | **This is the "sight ready" light** — see Finding 2. |
| 10 | Control Panel (ПК) | `OBSERV.` (B2, `НАБЛ`) | ON | `I9K113` · `Command_NABL` · arg **886** | Opens the guidance unit's outer doors; see Finding 3 for the gyro-alignment timing this triggers. |
| 10.3 | Control Panel / operator right panel | inner doors / glass defrost / eyepiece heating | optional | `I9K113` · `Command_STVORKI` (arg 775, inner doors "doors open" switch, per the right-panel §4.6.6 table item 17) | PDF: *"if needed (but not mandatory)."* Eyepiece heating is noted as **"not modelled in DCS."** |
| 11 | Operator panel (ЩО) | 9-position selector (B2, `LNCHR OFF`–1…8) | position with a loaded TPK | `WEAP_SYS` · `Operator_SWITCHER_LAUNCH_STATION` · arg **963** | Green `MSL ON LNCHR` lamp lights when the selected station carries a round. |

A twelfth switch, `Operator_CHECK_LAMPS_9C475` (arg 956, the `TEST LAMP` button on the ЩО, B3) is
documented but not part of the warm-up gate itself — it is a self-test, pressed on demand.

**The spec's "1 s delay between switch actions, simulating Petrovich moving his hand" is this
project's own modelling choice, not in the manual** — the PDF gives no inter-switch timing at all,
it is a checklist of actions with no stated pacing. Nothing in the source contradicts the project
building that delay in; nothing in the source requires it either.

#### 2. The "sight ready" indication — IS the ЩО's green `READY` lamp, and the warm-up is 3–4 minutes, matching the spec's "about 3 minutes" closely

**Evidence: verified from primary source**, p.110 step 9 of the PDF.

*"Через 3-4мин: на ШТВ-91 загорается табло-транспарант ГОТОВНОСТЬ; на ЩО загорается лампа зеленого
цвета ГОТОВ"* — "After 3–4 minutes: the ШТВ-91 panel lights the `READINESS` placard; on the ЩО the
green `READY` lamp lights."

So: the light the spec refers to is on the **operator's own control panel (ЩО, labelled `9С475`)**,
the fourth of six lamps left-to-right (`COMP ON`, `LNCHR OFF`, `CHECK`, **`READY`**, `MSL ON LNCHR`,
`LAUNCH APPRVL`) — not a light on the Control Panel (ПК) or the guidance unit itself. The spec's
callout phrasing ("Guidance unit ready") is this project's own wording, not the manual's — the
manual's placard text is `ГОТОВНОСТЬ`/`READINESS`, and the lamp is simply `ГОТОВ`/`READY`.

**Readability from DCS: no read path found.** This lamp is an *indicator*, driven by a
`ceStringPoly`/lamp controller rather than a clickable switch, so it never appears in
`clickabledata.lua`'s helper-call form that `mi24p-command-surface.md`'s generator parses — lamps
are outputs, and that generator only captures *inputs*. `mi24p-command-surface.md` §4.4 separately
confirms `isGyroReady`/`isLaunchPermission`/`get9K113State`/`getHelperIsOn` are **native-only, not
reachable from Lua at all** — and those are exactly the booleans this lamp represents. **Evidence
for the lamp's own unreadability: inferred**, not directly probed — no one has tried
`list_indication` against the ЩО panel specifically. §6 of that same research file notes index 8,
`ccGunnersCPanel`, is "owned by `WEAP_SYS`" (the same device the ЩО's own switches belong to, per
Finding 1's table) and has never been read — that is the cheapest next probe if Petrobrain needs
this signal live rather than timed.

**Practical consequence for the Architect pass**: lacking a confirmed read path, the "ready"
callout is most likely implementable only as **a timer Petrobrain runs itself** (fire the
`PWR`/`GUID.UNIT POWER` writes, then wait a fixed 3–4 minutes and assume readiness) rather than
polling for the lamp — unless the `ccGunnersCPanel` probe above comes back positive.

#### 3. The OBSERV gyro-alignment wait — 10–15 seconds, not a round number from elsewhere in the manual

**Evidence: verified from primary source**, p.111 step 10.2.

After `OBSERV.` (НАБЛ) goes ON: the `GUID.UNIT POWER` lamp switches from dim to half-brightness
("вполнакала" — in DCS this **blinks** rather than showing analogue half-brightness, the PDF notes
that distinction explicitly), and **"через 10-15 c"** (after 10–15 seconds) the `OBSERV` lamp and a
second lamp labelled `Д.КР.РАССТОП` (roll-rate sensor un-caged) light on the Control Panel.

So: **X = 10–15 seconds**, not the figure the spec's placeholder was guessing at. This is the gyro
*un-caging* confirmation specifically — a separate, shorter wait from the 3–4 minute power-up warm-up
in Finding 2; the two should not be collapsed into one timer.

The PDF's own "Примечания" (notes) at the end of §5.3.8 add two more timing facts worth carrying
forward even though they're outside the spec's immediate ask: **electrically caging the gyros
(turning OBSERV off deliberately before a high-rate manoeuvre) takes 2–8 seconds**, and if the
platform ever "falls over" from an excessive-rate manoeuvre while OBSERV was on, recovery requires
cycling `GUID.UNIT POWER` off and waiting **3–4 minutes** for the gyros to spin down before
restarting the whole warm-up — a failure mode the spec doesn't currently model at all.

#### 4. ATGM types — only 9M114 "Shturm" is implemented in DCS; 9M120 "Ataka" is explicitly WIP

**Evidence: verified from primary source**, §4.1 p.42 and Fig. 4.1's own caption (p.40):

> *"управляемое ракетное вооружение включает в себя управляемые ракеты (УР) с радиокомандной
> системой наведения: **9М114 "Штурм" и семейство УР 9М120 "Атака" (в разработке)**; УР с ИК ГСН
> типа Р-60М (в разработке)"*

— "guided rocket armament comprises command-guided missiles: **9M114 'Shturm', and the 9M120
'Ataka' family (in development)**; IR-seeker missiles of the R-60M type (in development)."

Fig 4.1's caption lists the launch rail as carrying "ПТУР 9М114 или 9М120", and §3411 (chapter 4,
loadout diagrams) separately marks "9М120 (WIP)" — consistent, not contradictory: the rail can
*mount* either designation in the 3D model, but only 9M114 Shturm is a functioning weapon as of
this manual.

**This directly corrects the spec's own example.** `docs/concept/9K113.md` guesses the launch
callout word *"Ataka"* (*"e.g. 'Ataka, 7 seconds'"*). Per this source, **the correct word is
"Shturm" — "Ataka" is the *other*, not-yet-implemented missile family.** This should be flagged to
the user/Architect rather than silently corrected, since the spec is the user's own document.

**Missile speed and maximum range: not found anywhere in this document.** I searched the full PDF
text (via `pdftotext`, all ~5375 lines) for every speed/range keyword near 9M114/Shturm/9K113 and
found none — the only "м/с" (m/s) figures in the whole manual are the GSh-2-30 cannon's muzzle
velocity (870→940 m/s with the extended barrel) and generic airspeed-indicator descriptions,
neither of which is the missile. The stadiametric sight calibration (5000 m mark for a 2.5 m target,
already documented in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`) bounds the
sight's *useful range aid*, not the missile's own flight envelope. **Unresolved** — this needs
either the English-edition manual (which supplied the sight's own angular limits per that same
research note) or a real DCS flight measurement (time-to-impact at a known range).

#### 5. Wide/narrow FOV — already in this repo; re-read, no new figures, nothing contradicted

**Evidence: already documented**, `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`.
I re-read pp. 66–70 of the same PDF directly for this pass (§4.6.7's `ПН`/`ПУ ПН` subsections) and
confirm the existing note's reading exactly: the guidance unit has two magnifications, **×3.3 and
×10** (p.68, Рис. 4.17 item 1), selected by a handle (positions A/B). **The field of view in degrees
is not stated anywhere in this document** — only the two magnification ratios and the reticle's mil
markings (Рис. 4.19: 0.5/2/2.5/5/10/13 mil). I searched the full PDF text for every occurrence of
"поле зрения" (field of view); the only sentence naming a numeric FOV is the existing note's own
discussion, sourced from the English edition outside this repo and marked unverified there. **No
correction needed to that note** — it already carries the right confidence label.

#### 6. The weapons safety circuit switch (`BL-B65`) — identified, with device/command/argument

**Evidence: verified from primary source**, cross-referencing §5.3.8 step 4 (p.107) against
`aircraft-layer/research/mi24p-command-surface.md`'s confirmed-live device table.

The switch is the operator's left-panel **`SAFETY SWITCHES ARMAMENT CIRCUITS`** bar switch (the
same one shown in §4.6.1, p.60, Fig. 4.12 — the chapter the spec's own reading list names). It is
one physical bar covering several gang-switched positions (the PDF: *"соединены общей планкой"* —
"joined by a common bar"); ON arms the circuit, OFF safes it.

- **Device:** `WEAP_SYS` (device ID 6)
- **Command:** `Operator_SWITCHER_SAFE_WEAP` (command ID 3020)
- **Clickable draw argument:** **673**

Source line: `mi24p-command-surface.md:2204` (`ARMAMENT-POWER-OP-PTR | WEAP_SYS |
weapon_commands.Operator_SWITCHER_SAFE_WEAP | 673`), itself generated from the installed
`clickabledata.lua`/`command_defs.lua` on 2026-09-11 (DCS 2.9.29.27278) and in that file's own
"confirmed callable" status.

Lamp behaviour (p.60, §4.6.1, and confirmed again at p.107 step 4): the switch gates two placards —
green **"ЦЕПИ ВООРУЖЕНИЯ ОТКЛЮЧЕНЫ"** ("armament circuits disconnected") when OFF, red **"ОСТОРОЖНО!
ЦЕПИ ВООРУЖЕНИЯ ПОД ТОКОМ"** ("caution, armament circuits live") when ON — but the red placard
**only lights with the landing gear extended**; the green one lights with gear either up or down
whenever the switch is OFF. Not confirmed whether either placard is readable via `get_argument_value`
— unresolved, same shape of gap as Finding 2's `READY` lamp.

#### 7. The guidance-unit transmitter reset button — identified, with device/command/argument

**Evidence: verified from primary source**, §5.3.8 step 19 (p.115):

> *"После попадания в цель, или промаха, или ухода ракеты на самоликвидацию нажать кнопку на ПУ
> СБРОС ИЗЛУЧ. [LAlt+R]"* — "After hitting the target, missing, or the missile self-destructing,
> press the button on the PU (missile control console) labelled `СБРОС ИЗЛУЧ.` (reset
> transmission/radiation)."

This is a physical button on the **ПУ ПН** (missile control console, the hand controller the
operator slews with — `Пульт Управления прибора наведения`), bound in DCS to `LAlt+R`.

- **Device:** `I9K113` (device ID 7)
- **Command:** `Command_RadiationReset` (command ID 3029)
- **Clickable draw argument:** **882**

Source line: `mi24p-command-surface.md:2266` (`OP-AIM-RESET-RAD-PTR | I9K113 |
i9K113_commands.Command_RadiationReset | 882`). A second variant, `Command_RadiationReset_Ext`
(command 3056), also exists — likely the discrete press-and-release ("EXT") form rather than a held
axis; not distinguished further here.

**This confirms the spec's "1 s after impact" framing is this project's own pacing choice, not the
manual's** — the PDF gives no delay before pressing this button, only the triggering condition
(hit, miss, or self-destruct).

#### 8. Is 9K113 state exportable? — partial yes: slew position and OBSERV switch state are; readiness/launch-permission booleans are not

**Evidence: verified from primary source (reproduced-locally)**, `mi24p-command-surface.md` §4.1,
§4.1.2, §4.3, §4.4 — all from the 2026-09-11 live probe runs against the installed DCS tree, not
inferred from Lua source alone.

**Exportable, confirmed live:**
- **Slew position** — `GetDevice(0):get_argument_value(874)` (azimuth) and `(876)` (elevation) give
  the sight's current pointing angle relative to the airframe, confirmed live across five probe
  points with an exactly linear calibration (`arg_874 = value × 0.44`, `azimuth_deg = value × 60`).
  Elevation's piecewise gauge (`-1→-0.75`, `0→0`, `1→1.0`) means its degree conversion is still
  unmeasured even though the raw argument read is confirmed.
- **OBSERV on/off** — `get_argument_value(886)` reads the `НАБЛ`/`OBSERV` switch position (Finding
  1's row 10), part of the same confirmed-readable "24 panel switches" set §4.3 documents.
- **The sight-pointing *write* channel** (for driving the sight to a commanded bearing, not reading
  it) is `GetDevice(7):SetCommand(3061, azimuth_deg/60.0)` (and 3060 for elevation) — the AI axis,
  confirmed to be a single position write with no closed loop, settling inside 0.25 s.

**Fixed, known, but not runtime-read:**
- **Gimbal limits** — ±60° azimuth, +20°/−15° elevation — are a constant sourced from the
  **English**-edition manual (outside this repo), not read live from any DCS API; the native
  `av9K113::initLimits` that holds the true limits is confirmed **not** exposed to Lua at all.

**Not exportable — native-only, confirmed negative:**
- `isGyroReady`, `isLaunchPermission`, `get9K113State`, `isCaged`, `getHelperIsOn`,
  `get_slew_velocity`, `get_LandPoint`, `get_CameraPoint`, `getCurrentFOV`/`getCurrentHFOV` all
  appear in `CockpitMi24.dll` as native methods on `av9K113` but **none appear as a plain
  registration string reachable from the Lua state** (`mi24p-command-surface.md` §4.3/§4.4). This
  is the project's existing finding, re-confirmed rather than re-derived this pass. It covers
  exactly the booleans the "guidance unit ready" and "launch permission" (`РАЗРЕШ.ПУСК`) callouts
  would ideally be driven from.

**So the likely-hard-no from the task brief turns out to be a real but partial no**: position and
simple switch state are genuinely exportable; only the *derived readiness/permission* signals are
closed off, and those have the two workarounds already named in Findings 2 and 7's launch-permission
analogue — a self-run timer, or (unverified) a `list_indication` probe against `ccGunnersCPanel`
(§6, index 8) or the 9K113's own `list_indication(0)` text channel (§4.3, confirmed to carry real
`ceStringPoly` text — `Zoom_Val`, `Laser_Filter`, `Orange_Filter`, `BackLight`, `ArrowHelper_Val`,
`txt_Tips`, `txt_NABLTips`, `HintsOn` — none of which is `READY` itself, but an unexamined sibling
panel might carry it).

**One more datum worth carrying to the Architect pass, found in step 12 (p.112) rather than asked
for directly**: the missile's **launch-entry condition** (line of sight within 0.86° of the
airframe axis, the "`РАЗРЕШ.ПУСК`" red-sector-and-buzzer cue) is visually and audibly signalled
*inside the sight itself*, matching exactly what
`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md` already recorded from the English
edition — this pass found the same 0.86° figure independently in the Russian edition's procedural
chapter, which strengthens that figure from single-source to corroborated across both editions.

### Contradiction check against existing project beliefs

**The one contradiction the task brief named — `BL-14`'s vertical-axis discrimination guidance vs.
the spec's "9K113 gives poor vertical understanding" — is already resolved in `BL-14`'s own roadmap
entry** (`body-layer/ROADMAP/BL-14.md`, "2026-10-14 update (third)"): BL-14's tier-1/tier-2
alignment guidance is naked-eye/binocular only, with **no 9K113 channel at all** — ATGM guidance
through the 9K113 is explicitly out of BL-14's scope per the same entry's cross-reference. So the
two claims are about different instruments, as BL-14 itself already states, and this investigation
found nothing in the PDF that bears on the 9K113's *own* vertical resolution one way or the
other — no FOV-in-degrees exists for either axis (Finding 5), so there is no numeric basis here to
confirm or deny "poor vertical understanding" as a modelling claim. Flagging this as **unresolved
by this source**, not as settled.

No other contradiction between this document and already-recorded project beliefs was found.

### Reproducible Test

The switch table (Finding 1) and procedure (Findings 2, 3, 7) were read directly from
`docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` pages 40–45, 60–70, and 105–116, via the
`Read` tool's `pages` parameter (max 20 pages/call). The missile-type/speed search (Finding 4) and
the FOV search (Finding 5) were done with:

```sh
pdftotext -layout "docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf" /tmp/quickstart.txt
grep -n -iE "м/с|скорост|дальност|9М114|Штурм|9М120|Атака" /tmp/quickstart.txt
grep -n -iE "поле зрения" /tmp/quickstart.txt
```

The device/command/argument cross-references (Findings 1, 6, 7, 8) were `grep`s against the
already-committed `aircraft-layer/research/mi24p-command-surface.md`, not a fresh DCS probe — no
DCS install was reachable from this (Mac) worktree this session (`find / -iname "*DCS World*"`
and `find / -iname "mainpanel_init.lua"` both returned nothing).

### Possible Approaches

- **"Guidance unit ready" and "in range"/launch-permission callouts**: without a confirmed read
  path for the `READY`/`РАЗРЕШ.ПУСК` lamps, implement the warm-up gate as **a timer Petrobrain owns
  itself** — issue the power-on writes (Finding 1, steps 7–8), then treat the sight as ready after a
  fixed delay (3–4 min warm-up, separately 10–15 s after OBSERV for gyro alignment) rather than
  polling. This matches how the manual itself presents the timing (as elapsed-time gates, not
  event-driven ones) and sidesteps the native-only read gap in Finding 8.
- **Before committing to the timer approach**, the cheap unresolved probes worth running on the
  Windows box are: `list_indication` against index 8 (`ccGunnersCPanel`, owned by `WEAP_SYS`, never
  tried) and against the 9K113's own `list_indication(0)` (confirmed to carry real text, but not
  checked for a readiness string specifically). Either coming back positive would let Petrobrain
  observe real state instead of guessing a delay.
- **Missile speed/range (Finding 4)**: not in this document. Either locate the English-edition
  manual (which already supplied the sight's own angular limits, per the existing research note)
  and check its weapons-characteristics section, or measure live — fire an ATGM at a known range in
  a test mission and time to impact. A rough placeholder (DCS community consensus puts 9M114 Shturm
  around 400–450 m/s, but **this number does not come from this document and must not be recorded
  as verified** until sourced or measured) would let the Architect pass proceed with the callout
  formula shape while flagging the constant itself as provisional.
- **The launch-callout word should say "Shturm," not "Ataka"** (Finding 4) — a one-line correction
  to carry into the Architect pass; the spec document itself is the user's and is not edited here.

### Unresolved

- **Missile speed and maximum range** — not found anywhere in this PDF (Finding 4). Needed for the
  "`<missile>`, `<flight time>`" callout and the in-range/out-of-range gate.
- **Whether the `READY`/`РАЗРЕШ.ПУСК`/safety-circuit placard lamps are readable from DCS at all** —
  inferred unreadable from the absence of any clickable-element entry and the confirmed-native-only
  getters (Findings 2, 6, 8), but never directly probed with `list_indication` against the specific
  panels named above. A cheap live test would settle it either way.
- **`AUX STORES LIGHTS` and the `OPER/CHECK` verification switch's device/argument** (Finding 1,
  rows 1 and 5) — not found in `mi24p-command-surface.md`'s captured set; low priority, neither
  gates warm-up completion.
- **Elevation's degree conversion for args 876/3060** — the raw argument read and AI-axis write are
  confirmed live, but the piecewise elevation gauge's angle-per-unit is still unmeasured (carried
  over from the existing `mi24p-command-surface.md` finding, not new to this pass).
- **Whether the "poor vertical understanding" claim has any numeric basis** — neither this document
  nor the existing optics research note states an FOV in degrees for either axis, so there is no
  source to confirm or refute that specific modelling claim against. Flagged for the user's own
  `/explore` pass, per the spec's own instruction ("where this document contradicts something
  written earlier, explore with user").
- **Live DCS confirmation of every device/command/argument in Finding 1's table and Findings 6–7** —
  all are cross-referenced from a different research pass's live probe (2026-09-11), not re-probed
  this session. They should hold (device/command tables are positional but stable across a single
  DCS version), but a DCS update between 2026-09-11 and whenever this is built could have shifted
  them — regenerate against the installed tree before relying on exact argument numbers in code.
