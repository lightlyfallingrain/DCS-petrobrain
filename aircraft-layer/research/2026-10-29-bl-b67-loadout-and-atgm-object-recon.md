# BL-B67 — loadout-count readers and the launched-ATGM's world-object identity

**Date:** 2026-10-29
**DCS version:** not verified locally this session — no DCS install reachable from this (Mac)
dev machine; desk research only (installed-DCS file *listing* in-repo
`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`, prior aircraft-layer research notes, Hoggit
wiki, GitHub, web search). Last confirmed version in prior sessions' `autoupdate.cfg` read:
2.9.29.27278 — treat as stale, re-read `autoupdate.cfg` before trusting a version-specific claim.
**Theatre:** n/a (scripting-API / weapon-naming question, not terrain-specific)

### Question

`BL-B67` (the 9K113 ATGM attack run) needs, per `plans/bl-b67-atgm-run/explore-notes.md`
(2026-10-26/29 rounds): (1) a way to detect the player's missile count dropping by one, to
confirm launch jointly with the pilot's launch button; (2) a way to identify the launched
missile's own `LoGetWorldObjects` object, for impact detection ("that object leaving the list,
any cause"); (3) optionally, whether `S_EVENT_SHOT` is a usable cross-check; (4) whether any
source states which physical pylon each of `SHSCHO-KNOB-PTR`'s (arg 963) 8 non-zero steps
selects.

### Findings

**Q1 — loadout count**

1. **`LoGetPayloadInfo()` is real, documented-by-DCS's-own-shipped-template Export API, generic
   to ownship (not aircraft-family-specific)** — **evidence: documented (primary-source-adjacent
   — DCS's own default `Scripts/Export.lua` template comment block, reproduced verbatim in a
   public pastebin and corroborated independently by a 2026 GitHub issue)** — **source:**
   `pastebin.com/Hq6bvJqz` lines 552–567 (DCS's own commented reference block) and
   `github.com/Sitsko1/DCSMCPServer` issue #47. Shape:
   ```
   LoGetPayloadInfo() -> {
     CurrentStation,         -- number; 0 = no station selected
     Stations = {            -- array
       { container = bool, weapon = {level1, level2, level3, level4}, count = number }, ...
     },
     Cannon = { shells = number },
   }
   ```
   `weapon` is a four-level world-database classification, not a string — `LoGetNameByType(level1,
   level2, level3, level4)` (also in the same DCS-shipped template, "Always" category per the
   Hoggit `DCS_export` page) converts it to a display name, falling back to the raw four numbers
   when no name is registered. **Evidence for the shape: documented.** **Evidence for Mi-24P/
   helicopter applicability: inferred** — nothing read this session states it is fixed-wing-only
   or excludes helicopters, and it sits in the Hoggit wiki's "Ownship" category (general own-
   aircraft data, the same category `LoGetPayloadInfo` itself is listed under on the live
   `wiki.hoggitworld.com/view/DCS_export` page as of this fetch) alongside functions already
   confirmed aircraft-generic (`LoGetSelfData`). No Mi-24P-specific confirmation found.
2. **Export-permission restriction, documented**: on the live Hoggit `DCS_export` page, Ownship
   is one of three categories a multiplayer server host can disable, which would blank
   `LoGetPayloadInfo` along with every other ownship function on a server that disables it —
   **evidence: documented**. **Not applicable to this project's own single-player, own-DCS-
   instance deployment** (per `aircraft-layer research/2026-09-07-petrovich-perception-export.md`
   finding 10's parallel note about `LoGetWorldObjects` — this project controls its own DCS
   instance, so a hosted-server restriction is out of scope, same reasoning).
3. **It distinguishes launch from jettison on its own only by count, same ambiguity the user's
   button-AND-count design already accounts for** — a missile count dropping by one via
   `LoGetPayloadInfo` cannot itself tell a launch from a jettison (e.g. `CB-RIGHT-LAUNCHER-DETACH-
   PTR` arg 616, or `WEAP-JETTISON-LAUNCHER-PTR` arg 538/765, both present in
   `body-layer/config/sequences/mi-24p/switch-reference.md`) — **evidence: inferred from the
   documented shape itself** (the table has no launch/jettison-cause field). This is exactly why
   the explore-notes design pairs it with the pilot's launch-button arg (741) rather than reading
   count alone.
4. **Update latency: bounded by the export poll rate, not instantaneous** — `LoGetPayloadInfo`
   would be read inside the same `LuaExportAfterNextFrame` throttle `Export.lua` already runs at
   (currently 5 Hz for world-objects/telemetry per `aircraft-layer/CLAUDE.md`'s throttle note) —
   **evidence: inferred by direct analogy**, not itself measured; no probe of this specific call's
   cost has been run. A momentary launch-button tap (arg 741, `default_button`, 0/1 momentary,
   same row class as `SHSCHO-CHECK-PTR` arg 956) can in principle be missed between polls at a low
   poll rate — the same open design question `plans/bl-b67-atgm-run/explore-notes.md`'s sixth
   round already flags for the button half, carried over here since both signals (button edge and
   count drop) need to land in the *same* poll (or a short window of polls) to be read as one
   launch event.
5. **`Unit:getAmmo()` (mission-scripting state, not Export.lua) is a documented alternative for
   reading an *AI* unit's stores, not demonstrated for the player's own aircraft from this
   state** — **evidence: forum-claim/GitHub-issue-sourced, not primary-read** — **source:** the
   same `DCSMCPServer` issue #47, citing DCS's own JTAC menu code as a working call site. Returns
   each weapon type with `count` and a `desc` table (display name/type/category) — the issue
   itself flags `desc`'s exact fields as "unverified live." This is the mission-scripting-state
   analogue of `LoGetPayloadInfo`, reachable the same way the existing `S_EVENT_SHOOTING_START`
   bridge already is (`world.addEventHandler`/`net.dostring_in("scripting", ...)`,
   `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`), but
   **this project has no confirmed use of `Unit:getAmmo()` against the *player's own* unit** —
   every existing live-confirmed use of the mission-scripting bridge in this codebase (unit
   velocity, `getLife`/`getLife0`, shooting events) iterates `coalition.getGroups()` over AI
   groups, not the player. Whether the player's own aircraft is reachable the same way (it should
   be — it's an ordinary `Unit` by `getName()`/callsign, already the join key the mission-bridge
   LOS/velocity code uses) is **inferred, not probed**.
6. **Recommendation implied by the evidence, not a decision made here**: `LoGetPayloadInfo()`
   via `Export.lua` is the stronger candidate of the two — it is the Export-layer's own
   documented, ownship-scoped function (no AI-group iteration needed, no new mission-scripting
   bridge call to add), and this project's `Export.lua` already has a committed, unused probe
   pattern ready to extend (see Q3/below). `Unit:getAmmo()` would require confirming the player's
   own unit is reachable from the `"scripting"` dostring_in state the same way AI units are —
   an extra unverified step `LoGetPayloadInfo` does not need.
7. **No cockpit-arg lamp candidate found for a missile *count*.** The explore-notes' "SHSCHO
   Lamps Check" (arg 956, `SHSCHO-CHECK-PTR`) and the pylon knob (arg 963) are switches/knobs, not
   count readouts; `body-layer/config/sequences/mi-24p/switch-reference.md` (Device 7, I9K113,
   operator seat, rows 263–294) has no arg documented as a missile-remaining counter. This
   generated reference only lists *clickable* elements (device/cmd/arg/shape), so a read-only
   indicator with no `performClickableAction` entry (e.g. a lamp driven by a draw-argument) would
   not appear in it at all even if one exists — **absence here is not evidence of absence**, only
   evidence that the generator's source (`tools/generate_effector_registry.py`'s Windows dump) saw
   no clickable row for it.

**Q2 — ATGM as a world object**

8. **Rockets are confirmed, live, to appear in `LoGetWorldObjects()` as new named objects at the
   poll they launch** — **evidence: reproduced-locally (live sortie, this project's own
   probe)** — **source:**
   `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`, "PROBE
   RESULTS, 2026-09-25": the player's S-8KOM rockets appeared as new `C_8` objects in
   `aircraft_layer_probe_weapons.log` at the exact poll pairs were fired (`[33.14] count=15 → 17
   NEW: C_8`), and the count tracked rockets in flight and settled back down. Gun rounds never
   appeared (flat object count across 16 `start shooting` events). **This was measured for
   unguided rockets, not ATGMs.** A 9M114/9M120 appearing the same way (DCS models guided
   missiles, like rockets, as engine objects with their own flight/physics, unlike gun rounds) is
   the **expected** case by the same reasoning the user gave in the explore-notes sixth round, but
   has **not itself been observed** — no sortie has fired a Shturm/Ataka while this probe or its
   successor was running.
9. **The exact `Name`/type string an in-flight 9M114 Shturm or 9M120 Ataka would carry is
   unresolved by any source found this session** — **evidence: absence confirmed across multiple
   searches, not documented anywhere found.** Desk research covered: (a) the Hoggit `DCS_export`
   page's `LoGetWorldObjects` field list (confirms the *fields* — `Name`, `Country`, `Coalition`,
   `LatLongAlt`, `Heading` — but gives no example *values* for any specific weapon); (b)
   `Quaggles/dcs-lua-datamine` (a community weapons-table datamine repo) — found a Mi-24P entry
   (`_G/rockets/P_60.lua`, R-60M only, nothing for the Shturm/Ataka pylons) and a missile-naming
   convention from other aircraft (e.g. `_G["weapons_table"]["weapons"]["missiles"]["AIM_120C"]`,
   `name = "GBU_24"`) that shows weapon internal names are typically the weapon's own short
   designation string, not a generic family code — **inferred extrapolation, not a direct
   read**: by that pattern a Shturm/Ataka object's `Name` would plausibly be something like
   `"Ataka"`/`"9M120"`/`"9M114"`, but `C_8`'s own naming (a generic rocket-family code shared by
   several different S-8 warhead variants, not "S-8KOM" itself) is a **counter-example already in
   this project's own data** showing the convention is not simply "the weapon's designation
   string" — unguided rockets of the same caliber/family apparently share one `Name` regardless of
   warhead variant, so a guided-missile family's `Name` could equally be shared across the Shturm/
   Ataka pylon family rather than distinguishing the two; (c) general web search for the DCS CLSID/
   weapons-table entries for 9M114/9M120 (`db_weapons_data.lua` location confirmed by forum threads
   but the file's content was not read this session — no live DCS access — and multiple forum
   threads note ED removed much of `Scripts/Database/`'s Lua content as of DCS 2.7, making an
   offline file read less reliable going forward even with access).
10. **Fields `LoGetWorldObjects()` exposes per object, confirmed from the live Hoggit page this
    session** — **evidence: documented** — **source:** `wiki.hoggitworld.com/view/DCS_export`,
    Object category, worked example: `k` (the `pairs()` table key, i.e. `object_id`), `Name`,
    `Country`, `Coalition`, `LatLongAlt` (`.Lat`/`.Long`/`.Alt`), `Heading`. **No `Type` table
    (level1-4) on this function** — that four-level classification belongs to `LoGetPayloadInfo`'s
    `weapon` field and to the mission-scripting `Unit`/`Weapon` object API, not to
    `LoGetWorldObjects`'s return shape. The question's framing ("Type table level1-4" for
    `LoGetWorldObjects`) conflates the two APIs — worth flagging to Architect rather than silently
    assumed away: `LoGetWorldObjects` gives a plain string `Name`, and whatever that string is for
    a Shturm/Ataka is exactly the unresolved fact in Finding 9.
11. **No field links a weapon world-object to its launcher.** Neither `LoGetWorldObjects`'s
    documented field list (Finding 10) nor the aircraft-layer's own shipped schema
    (`src/schema/world_objects.py`, which only ever read `Name`/`Coalition`/`LatLongAlt`/`Heading`/
    `UnitName` — confirmed by reading that file this session) carries anything resembling a
    launcher/owner/parent id. **Evidence: documented absence (confirmed field list) +
    reproduced-locally (this project's own schema, which has never populated such a field
    because `Export.lua` never reads one).** This matches the explore-notes' own stated design,
    which does not rely on a launcher-link field: "we know the missile type we carry and can
    filter world object by that when launch button is pressed" — i.e. identify the new object by
    *type* and *timing* (new object appearing in the same poll the button+count-drop fired), not
    by a launcher-id join. The design is therefore already shaped around this gap rather than
    assuming a field that does not exist.

**Q3 — `S_EVENT_SHOT` as a cross-check**

12. **`S_EVENT_SHOT` is documented to fire "whenever any unit in a mission fires a weapon,"
    excluding only machine-gun/autocannon fire (routed to `S_EVENT_SHOOTING_START` instead), and
    carries the fired `weapon` as a `Weapon` object in its payload** — **evidence: documented,
    already established by this project's own prior research, re-cited not re-derived** —
    **source:** `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-
    bridge.md`, Finding 10 (`DCS_event_shot`). A guided missile (Shturm/Ataka) is exactly the
    weapon class `S_EVENT_SHOT` is defined for (the documented exclusion names only "machine gun or
    autocannon," and this project's own live probe already confirmed that exclusion is real for
    gun rounds — Finding 554–561 of the same file). **Evidence that it specifically fires for the
    player's own ATGM launch: inferred, not itself live-probed** — the live probe that ran this
    project's `petrobrain-damage-events-probe-hook.lua` (Findings 591–631 of the same file)
    confirmed `S_EVENT_SHOOTING_START`/`S_EVENT_HIT` delivery for a *ground* unit's gun fire and
    the *player's own* twin-cannon fire, but that sortie never fired an ATGM, so `S_EVENT_SHOT`
    itself — as opposed to `SHOOTING_START`/`END`/`HIT` — has never been observed arriving over
    this project's bridge for any weapon.
13. **As a cross-check for launch detection, `S_EVENT_SHOT` would add initiator + a `Weapon`
    object reference (whose own `getTypeName()`/`getDesc()` could in principle resolve the exact
    name Finding 9 is missing) via a *push* channel, instead of two *polled* signals
    (button + count) needing to coincide** — **evidence: inferred**, combining Finding 12
    (documented event) with this project's already-proven event-registration mechanism (Finding
    "Fact 2" of the same prior research note: `world.addEventHandler` reachable and persistent
    from the `"scripting"` dostring_in state, live-confirmed 2026-09-25). This is a genuinely
    cheaper candidate than the explore-notes' button+count design **if** `event.weapon` turns out
    to expose a resolvable type name live — unverified, and the explore-notes design does not
    currently plan to use it, so this is offered as an alternative for Architect's consideration,
    not a correction to the existing plan.

**Q4 — `SHSCHO-KNOB-PTR` (arg 963) pylon mapping**

14. **No source read this session — in-repo or web — states which physical Mi-24P pylon
    corresponds to which of the knob's 8 non-zero steps.** `body-layer/config/sequences/mi-24p/
    switch-reference.md` row 213 (`SHSCHO-KNOB-PTR`, "Select Station", operator,
    `multiposition_switch`, cmd `[3038]`, arg `[963]`, values "0 to 0.8 (9 steps)") confirms the
    knob's *identity* and *step count* only — this is the same row the explore-notes sixth round
    already cites, and this session found nothing beyond it. No Hoggit page, ED forum thread, or
    GitHub project surfaced a Mi-24P pylon-numbering convention for this specific control. **This
    remains exactly as unresolved as the explore-notes left it** ("probably... the knob's identity
    is believed, not yet seen moving in the sim; which step is which physical pylon is not
    stated") — not a new finding, a confirmed absence of one.

### Reproducible Test

No live probe was run this session (no DCS access from this machine). Two minimal probes follow
Export.probe-weapons.lua's existing pattern — a committed probe
(`aircraft-layer/dcs-export/Export.probe-weapons.lua`) already exists and already produced
Finding 8's `C_8` result; it is NOT modified here, both probes below are proposed as disposable
variants the user would run, same posture as that file's own header note ("Delete this file once
the question is settled").

**Probe 1 — extend the existing weapon-object probe to log full object detail on an ATGM
launch**, settling Findings 8/9/10/11 for guided missiles specifically. Minimal diff to
`Export.probe-weapons.lua`: where it currently logs only `obj.Name`, also log `obj.Coalition`,
`obj.LatLongAlt` and (if present) any other table keys via a one-shot `for k in pairs(obj) do ...
end` dump the *first* time a given `Name` is seen, so an unexpected field (anything beyond the
five already known) would show up without guessing the key in advance:

```lua
-- inside the existing `for _, obj in pairs(objects) do` loop, where `name` is first-seen:
if type(name) == "string" and seen_names[name] == nil then
    seen_names[name] = true
    local keys = {}
    for k in pairs(obj) do keys[#keys + 1] = tostring(k) end
    logline("NEW " .. name .. " keys=" .. table.concat(keys, ","))
end
```
Fly a mission, fire one Shturm and (if loaded) one Ataka at a target, read
`Logs\aircraft_layer_probe_weapons.log`. Settles: the exact `Name` string(s) for each missile
family, whether Shturm and Ataka share a `Name` the way S-8 variants share `C_8`, and whether any
field beyond the five already known exists on a missile object that doesn't exist on a rocket
object.

**Probe 2 — add `LoGetPayloadInfo()` to the same probe**, settling Finding 1/6/7 (count +
cadence, whether a button-press tap is caught):

```lua
-- once per poll, alongside the object-count log:
local okp, payload = pcall(LoGetPayloadInfo)
if okp and type(payload) == "table" then
    local parts = {}
    for i, st in pairs(payload.Stations or {}) do
        local okn, nm = pcall(LoGetNameByType, st.weapon[1], st.weapon[2], st.weapon[3], st.weapon[4])
        parts[#parts+1] = tostring(i) .. ":" .. tostring(okn and nm or "?") .. ":" .. tostring(st.count)
    end
    logline("payload " .. table.concat(parts, ";"))
end
```
Fire one missile from a multi-round pylon (if the Mi-24P's launcher carries more than one per
station — unconfirmed this session) or one rocket pod salvo, and check whether the count step
lands on the same poll as the launch-button press and the new world object, or lags by one or
more polls — this settles Finding 4's latency question directly rather than inferring it.

**Probe 3, optional — `S_EVENT_SHOT`**: extend the already-committed
`petrobrain-damage-events-probe-hook.lua` pattern (the mission-scripting event-registration hook
already proven live for `SHOOTING_START`/`END`/`HIT`/`DAMAGED`) to also log `event.id ==
world.event.S_EVENT_SHOT`, with `event.weapon:getTypeName()` (or `getDesc()`) if it does not
error. Settles Q3 (Findings 12/13) directly and would resolve Finding 9 as a side effect if
`getTypeName()` returns a clean string.

### Possible Approaches

- **Loadout count**: read `LoGetPayloadInfo()` from `Export.lua` at the same poll rate as the rest
  of the telemetry feed, paired with the existing explore-notes design (pilot's launch-button arg
  741, already read via `GET /watched_args/latest`/`polled.toml` per `body-layer/CLAUDE.md`'s
  effector-registry section). This needs no new mission-scripting bridge call and reuses the
  Export-layer mechanism this subproject already owns end-to-end. `Unit:getAmmo()` is a fallback
  only if `LoGetPayloadInfo` turns out not to be reachable or not to behave as documented for the
  Mi-24P specifically (Finding 1's one open "inferred" gap) — it would need its own
  player-unit-reachability probe first.
- **Launched-missile identity**: identify the new `LoGetWorldObjects` object by *type match +
  timing* (new object, same poll as button+count-drop), exactly as the explore-notes already
  design it — this does not require solving Finding 9 (the exact `Name` string) in advance of a
  live probe, since a diff-based "what's new this poll" filter works whether or not the `Name`
  string is predictable from documentation. Finding 9 (what the string actually *is*) still needs
  Probe 1 before any code hard-codes a specific `Name` to match against — do not guess the string.
- **If Probe 1 shows Shturm and Ataka share one `Name`** (the `C_8`-precedent risk, Finding 9):
  this still distinguishes "an ATGM launched" from "a rocket launched" (different `Name` than
  `C_8`/rocket names), which is all launch-detection needs; it would only block deriving *which
  missile family* from the object itself — but the explore-notes design already gets the family
  from the loadout read (`LoGetPayloadInfo`'s weapon-type/`LoGetNameByType`), not from the
  in-flight object, so this is not a blocking risk either way.
- **`S_EVENT_SHOT` (Q3)** is a candidate cross-check/alternative to the button+count design, not a
  replacement decided here — Architect's call whether the added event-channel complexity is worth
  it against the polled button+count approach the user already specified.
- **Pylon mapping (Q4)**: no source resolves this; the only paths forward are (a) the user watches
  the knob move in the sim while cycling `engage ... missiles` through each pylon and reports
  which physical station lights up per step, or (b) a probe reads `LoGetPayloadInfo()`'s
  `CurrentStation` field (Finding 1) against the knob's own `GET /watched_args/latest` value at
  the same poll — if `CurrentStation` tracks station index numerically, that *is* the mapping,
  without needing a human observation at all. **This second path is new to this session, not
  stated in the explore-notes, and is offered as a recommendation Architect may want ahead of
  asking the user to check in the sim again.**

### Unresolved

- **The exact `Name` string(s) for an in-flight 9M114 Shturm / 9M120 Ataka** (Finding 9) — no
  documentation, datamine, or forum source found it; needs Probe 1.
- **Whether Shturm and Ataka share one `Name`, or carry distinct ones** — same probe.
- **`LoGetPayloadInfo()`'s applicability/behavior specifically on the Mi-24P** — inferred generic,
  never confirmed on this module; needs Probe 2.
- **Whether a momentary launch-button tap (arg 741) and a `LoGetPayloadInfo` count-drop reliably
  land in the same poll, or need a short coincidence window** — needs Probe 2's timing read.
- **`Unit:getAmmo()` reachability against the player's own unit from the `"scripting"`
  dostring_in state** — never probed by this project; only AI-group iteration is proven.
- **`SHSCHO-KNOB-PTR` step-to-pylon mapping** — fully open; no source states it. The
  `CurrentStation`-correlation approach above is the cheapest resolution path found this session.
- **Whether `S_EVENT_SHOT` actually arrives over this project's existing event bridge for a
  guided-missile launch** (as opposed to the already-confirmed `SHOOTING_START`/`HIT`/`DEAD` for
  gun fire) — never observed; `event.weapon`'s own resolvability (`getTypeName()`/`getDesc()`) is
  likewise unobserved.
- **Whether a multi-round launcher rail (if the Mi-24P's Shturm/Ataka pylon ever carries more than
  one round per `Stations` entry) would make a single count-drop ambiguous** — not investigated
  this session; `switch-reference.md`'s knob having 8 non-zero steps for presumably 8 physical
  pylons suggests one-round-per-station is the likely shape, but this is inferred, not confirmed.
