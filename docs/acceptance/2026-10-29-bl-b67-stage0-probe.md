# BL-B67 Stage 0 — the ATGM-run probe sortie

<!-- doc-provenance:start -->
**Topics:** #9k113 #atgm-run #cockpit-manipulation #firing-events
**Flight for:** [[BL-B67]]
<!-- doc-provenance:end -->

**Branch: `main`** (batch A of `feature/bl-b67-atgm-run` — Stages 1-4 plus this Stage 0 probe —
merged to `main` 2026-10-29; the card originally named the feature branch before that merge).

```sh
git fetch origin && git checkout main && git pull
```

Two files, both already disposable extensions of existing committed probes (not new files):

- `aircraft-layer/dcs-export/Export.probe-weapons.lua` — replaces production `Export.lua` for the
  duration.
- `aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua` — a Hook script, runs
  alongside anything else.

**No pipeline code in this stage.** This sortie only answers questions `plans/bl-b67-atgm-run/
plan.md`'s Stage 1–7 batches need before they can be built or merged. Nothing here is production
code and nothing here is kept after the questions are answered.

---

## What this answers

| Q | Question | Where the answer comes from |
|---|---|---|
| Q1 | Does `LoGetPayloadInfo()` work on the Mi-24P? Station names/counts? When does the count drop relative to the shot? | `Export.probe-weapons.lua`'s `payload …` lines, correlated against the `COUNT DROP …` line and the Hook's `OWN_SHOT …` line for the same missile |
| Q2 | The launched ATGM's `LoGetWorldObjects` `Name`(s) — for exclusion only, never for identification | `Export.probe-weapons.lua`'s `NEW … keys=…` line, the first time a Shturm/Ataka object appears |
| Q3 | Knob step → station index. Does a 3038 write set an absolute position? | `Export.probe-weapons.lua`'s `SWEEP write step=N` / `arg963(knob)=…` / `payload … current=…` lines together — if the logged `current` after writing step N is N, the write is an absolute set and the mapping is 1:1 |
| Q5 | Does 3029 (1 then 0) press and release Radiation Reset (does arg 882 move)? | `Export.probe-weapons.lua`'s `RADIATION RESET pressed/released` and the paired `arg882(rad_reset)=…` readback |
| Q6 | Does `S_EVENT_SHOT` arrive for **our** ATGM with `event.weapon` populated? Its `typeName`/`category`/`guidance`/`displayName`? Does `isExist()` hold for the flight and go false at impact — how long after the visible impact — and does `S_EVENT_HIT` fire on the same object? | `petrobrain-damage-events-probe-hook.lua`'s `OWN_SHOT …`, `WEAPON_GONE t=…` and `HIT_ON_KEPT_WEAPON` lines in `dcs.log` |

(Q4, the HOTAS fire-button-arg question, is retired per the plan revision — no longer needed since
launch/impact now come from `S_EVENT_SHOT`.)

---

## Setup (Windows)

1. **Back up** `Saved Games\DCS\Scripts\Export.lua` somewhere safe, then copy
   `Export.probe-weapons.lua` over it. The normal body-layer pipeline (collector, overlay,
   Petrovich's belief loop) is dead for this sortie — that is expected.
2. Copy `petrobrain-damage-events-probe-hook.lua` to `Saved Games\DCS\Scripts\Hooks\` (or confirm
   it is already there from an earlier session — it is idempotent and safe to leave alongside
   the production Hooks).
3. Confirm `Saved Games\DCS\Config\autoexec.cfg` has:
   ```
   net.allow_dostring_in = { "scripting" }
   ```
   Without it, the Hook's event registration silently fails every poll (`aircraft-layer/
   WORKFLOW.md` has the full note) — watch `dcs.log` for `PetrobrainDamageProbe` lines; `register:
   ok=true` confirms the opt-in is in place.
4. Delete any stale `aircraft_layer_probe_weapons.log` so this run's log is clean.
5. Mission: Mi-24P **air start** (warm guidance unit, this project's standard for every 9K113
   probe — never a cold start), **straight and level**, two BTRs roughly 3.5 km ahead. Loadout:
   **Shturm on at least one station**; an Ataka station and an S-8 rocket pod too if your loadout
   allows it — not required, but free extra data if present.

---

## Flying it (~10 minutes)

1. **Start the mission and do nothing with the SHSCHO knob for the first ~20 seconds.** The probe
   itself sweeps the knob through all 9 positions (2 s apart), parks on the first loaded station,
   and presses Radiation Reset once — all scripted, all logged. Touching the knob yourself during
   this window would contaminate the Q3 readback.
2. Once the probe has parked (log line `PARKED step=N`, ~20 s in — you don't need to watch for
   this live, it's in the log either way), fly toward the first BTR.
3. **Fire one Shturm at the first BTR.** Wait for the visible impact. **Note the clock (your DCS
   mission time, not model time) at the moment you see it hit.** **Then wait — the knob does not
   move at launch.** It auto-advances to the next loaded station **~25 seconds after the count
   drop**, not on the shot itself (the probe used to switch immediately, which the Stage 0 review
   flagged as very plausibly happening while the missile was still in flight — this was fixed
   before you flew it). Watch for `ADVANCE scheduled … for t=…` right after the count drop and
   `ADVANCED to step=N at t=…` roughly 25 s later in the log (or just wait ~25 s past the impact
   before expecting the knob to have moved — you don't need to watch the log live). If you fire a
   second missile off the same station before that 25 s is up, the wait restarts from the second
   shot — expected, not a bug.
4. **Fire a second Shturm at the second BTR — only once you're ready to, the knob's own timing
   does not gate you, just don't expect it to have switched stations until ~25 s after shot 1's
   count drop.** Wait for the visible impact. Note the clock again.
5. If an Ataka station is loaded, repeat once against whatever target is left (or a decoy) —
   optional, only if time and loadout allow. Same ~25 s note applies between shots on the same
   station.
6. If an S-8 pod is loaded, **fire one pair of rockets** at anything convenient. This is the known
   case (`C_8` objects, already confirmed in an earlier probe) and exists here only as an in-sortie
   cross-check that the extended probe is still logging the object feed correctly.
7. End the mission (or just let it idle a few seconds after the last shot) and exit to the main
   menu so the log file is flushed.

That's the whole sortie — no particular flight path matters, only that the two BTRs are visible
and in range for a Shturm shot (the probe does not care about range gates; it is not the production
run).

---

## Bring back

Copy these into `win-mac-sync/from-windows/`:

- `Saved Games\DCS\Logs\aircraft_layer_probe_weapons.log`
- `Saved Games\DCS\Logs\dcs.log` (or just the `PetrobrainDamageProbe` lines from it, but the whole
  file is safer — grep misses nothing that way)

Plus, in your own words: **the clock at each visible impact** (step 3/4 above) — that is the one
fact only you can give, since the log's own `WEAPON_GONE` time is `isExist()` turning false, which
may lag or lead the visible explosion by an unknown amount. That gap *is* part of what Q6 is
asking.

## Restore afterward

- Copy the backed-up `Export.lua` back over `Saved Games\DCS\Scripts\Export.lua`.
- `petrobrain-damage-events-probe-hook.lua` is safe to leave in `Hooks\` (it shares no state with
  the production Hooks and is idempotent on mission restart) — but delete it too if you'd rather
  not carry a probe script around.

---

## Results

*(to be filled in after the flight — the research note this feeds is
`aircraft-layer/research/2026-10-xx-bl-b67-stage0-probe-results.md`, per the plan's Affected Modules
list)*
