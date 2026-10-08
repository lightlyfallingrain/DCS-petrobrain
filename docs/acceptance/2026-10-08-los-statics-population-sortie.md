# LOS statics — population & downstream-join sortie

**Cockpit card (published):** https://claude.ai/artifact/CeF8PB3kbbL2cKFZTRS6JZ — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `fix/los-hook-statics`** — DoD PASSED on mechanical checks (ruff/mypy/pytest/luac, 256
tests). The statics enumeration itself is already confirmed working from your earlier flight today
(open terrain: 42 of 49 candidates were statics, zero enumeration failures on either counter).
This card covers only what's still open from that flight.

```sh
git checkout fix/los-hook-statics && git pull
```

## Why this flight is separate from "does the enumeration work"

Your first flight already answered that. What's left are two things only a second, targeted
observation can settle: **what population is binding the sightline cap over a dense city**, and
**whether a static's verdict ever actually reaches a tracked contact downstream**. Neither needs a
code change first — BL-B42 (the cap-population question) is explicitly parked pending this data,
per root `CLAUDE.md`'s "flight feedback is captured, then explored, then planned."

## Setup

Nothing new to deploy — same Hook script, same collector, same `--detection-trace` flag as your
last flight. If you're running fresh:

```sh
cd run-scripts
./run-crew-text.sh --detection-trace ~/dcs-detection-trace.jsonl
```

## Do / expect / record

**1 — Prize measurement: the full scan line over Damascus (or any dense built-up area).**
- *Do:* tail/grep `dcs.log` for `"PetrobrainLineOfSight scan"` while flying over or near a dense
  city, the same kind of area that produced `cap_hit=1` on your last flight. Capture the **whole**
  line this time — your last paste over Damascus didn't include `statics_in_wedge`, which is the
  one field that settles the open question.
- *Expect:* a line of the shape
  `objects_in_bubble=N statics_in_bubble=N objects_in_wedge=N statics_in_wedge=N candidates=N
  sightlines_computed=N max_sightlines=128 cap_hit=0|1 static_enum_failures=N
  unit_enum_failures=N name_rejects=N ownship_unidentified=0|1`.
- *Record:* the exact numbers. In particular: is `statics_in_wedge` close to `objects_in_wedge`
  (meaning the ~200+ really are statics, and the next question is which *types*), or is it small
  while `objects_in_wedge` stays large (meaning they're AI units and the statics change isn't the
  cause at all)? Also note `static_enum_failures`/`unit_enum_failures` — nonzero would mean the
  reading is unreliable for a different reason entirely.

**2 — Does a static's verdict ever reach a tracked contact?**
- *Do:* fly toward a mission-placed static vehicle you can identify on the map or by briefing (a
  T-55/T-72/Shilka emplacement, not a moving AI unit) until Petrovich would plausibly pick it up,
  then check `~/dcs-detection-trace.jsonl` (or ask for its summary afterward,
  `body-layer/tools/summarize_detection_trace.py`) for that object's entries.
- *Expect:* an entry showing `building_clear`/`terrain_clear` populated for that object, the same
  shape as a unit's entry — nothing in the trace format distinguishes a static from a unit, so if
  it shows up at all, it looks ordinary.
- *Record:* did a static's LOS verdict show up in the trace at all? If it did, did it ever get
  folded into a `Contact` (same object, same name, appearing in a `show <id>` / contact listing if
  you're running `--console`)? This has never been directly observed in flight — your last flight
  confirmed the enumeration produces statics, not that one of them was ever consumed downstream.

**3 — Pause-state check.** Same standing caveat as every Hook-script family in this project
(`aircraft-layer/CLAUDE.md`'s own testing note — export-rate bugs have twice been invisible to
in-flight-only testing).
- *Do:* pause mid-flight for a few seconds, unpause.
- *Expect:* `PetrobrainLineOfSight scan` lines keep appearing (or cleanly stop and resume) rather
  than silently going stale.
- *Record:* what you saw in `dcs.log` across the pause.

## What this flight is not testing

- **The ~5 s stutter** from your last flight. Leading hypothesis is `Export.lua`'s collector
  reconnect path (blocking 200 ms connect every 5 s while disconnected), not this Hook script
  (which polls at 1 Hz, so would stutter at 1 s if it were the cause). If the collector stays
  connected the whole flight, that's evidence against the LOS Hook being involved — worth noting if
  you see it, but it's a separate investigation, not this card's.
- **Whether the cap *should* be raised, or the population filtered.** That decision waits on this
  flight's data (item 1) and an `/explore` conversation — not something to decide mid-flight.

## Bring back

- The full `PetrobrainLineOfSight scan` line over a dense city, `statics_in_wedge` included.
- Whether a static's verdict was ever seen folded into a tracked `Contact`.
- Anything across the pause-state check.
- Anything that surprised you — that's worth more than anything on this list.
