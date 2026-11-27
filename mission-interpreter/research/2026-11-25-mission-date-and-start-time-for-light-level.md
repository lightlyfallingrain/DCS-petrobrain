# Mission Date and Mission Start-Time Availability (for BL-B124 light-level)

**Date:** 2026-11-25
**DCS version:** not verified locally this session (no DCS install reachable from this worktree)
**Theatre:** n/a — pipeline/schema question, not a live-DCS question

### Question
BL-B124 needs the mission's real-world date and clock time of day to compute sun elevation.
Does `.miz`'s raw `mission.date` survive into `RuntimeMissionUnderstanding`
(`mission-interpreter/src/runtime/compact.py`) and from there into body-layer's
`MissionUnderstandingData`? Does the `.miz` mission table carry a wall-clock
`start_time`, and is it already modeled anywhere?

### Findings

- **`RawMission.date: Mapping[str, int]` is `{Year, Month, Day}` only — no time-of-day field.**
  — **evidence: reproduced-locally** — **source:** `mission-interpreter/tests/fixtures/
  synthetic_mission.py:53` (`["date"] = { ["Year"] = 2024, ["Month"] = 1, ["Day"] = 1 }`), and
  `mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md` line 24,
  which read this directly off a real third-party `.miz` sample and confirmed the same three
  keys, no others. `mission-interpreter/src/miz/tree.py:202`'s own docstring (lines 196-198)
  independently describes `date` as one of several fields "carried through" but not otherwise
  typed.

- **`reader.py` does populate `RawMission.date` from the parsed `.miz`** — **evidence:
  reproduced-locally** — **source:** `mission-interpreter/src/miz/reader.py:151`,
  `date=dict(mission.get("date", {}))`. So `{Year, Month, Day}` is present and typed at the
  `RawMission` layer. This part of the architect's read is correct.

- **`date` does NOT survive into `RuntimeMissionUnderstanding` (MI-6's compact artifact) — confirmed.**
  — **evidence: reproduced-locally** — **source:** `mission-interpreter/src/runtime/compact.py`
  (full file read). `RuntimeMissionUnderstanding`'s only fields are `schema_version`, `theatre`,
  `ownship`, `purpose`, `task`, `phases`, `route`, `key_locations`, `expected_threats` — no `date`,
  no weather, no any raw passthrough. This matches the architect's stated read exactly; it is not
  a dropped field by accident, it is simply never carried forward because MI-3's
  `MissionUnderstanding` (the richer upstream schema `compact.py` compiles from) also has no `date`
  field — `date` lives only on `RawMission`/`CrewAvailableMission`, one layer below the one MI-6
  compiles from. Confirmed also on the body-layer side: `body-layer/src/belief/mission_phase.py`'s
  `MissionUnderstandingData` (the dataclass `load_mission_understanding` builds) has no `date`
  field either — same absence, consistent all the way through.

- **A top-level `mission["start_time"]` key exists in a real `.miz` — but its value/meaning was
  never read, only flagged.** — **evidence: forum-claim-unverified / inferred (real file, unread
  field)** — **source:** `mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md`
  line 24, which lists `start_time` among several top-level `mission` keys "not anticipated by the
  prior note," explicitly marked `(all unread, editor/session bookkeeping)` — a guess at its
  category, not a confirmed read of its actual value or units. The real sample file
  (`mission-interpreter/research/samples/Mission 02-Bagram.miz`) is gitignored third-party content
  and was not present in this worktree this session, so this could not be re-verified now. A
  **separate, per-waypoint** `start_time` is confirmed to exist on `MovingGroup` route points
  (`mission-interpreter/research/2026-09-12-miz-file-structure.md:37`, a group's spawn-delay field)
  — do not conflate the two: that one is a vehicle's delayed-activation time, not the mission's
  wall-clock start.

- **No code anywhere in `mission-interpreter/src/` reads or types `start_time`.** — **evidence:
  reproduced-locally (absence)** — **source:** `grep -rn "start_time" mission-interpreter/` finds
  only the two research-note mentions above; `tree.py`/`reader.py` do not surface it as a typed
  field (it would currently live inside `RawMission.raw`, the full raw-dict passthrough, if parsed
  at all).

### Reproducible Test
```
grep -n "date" mission-interpreter/src/miz/tree.py mission-interpreter/src/miz/reader.py
grep -n "Year\|Month\|Day" mission-interpreter/tests/fixtures/synthetic_mission.py
grep -rn "start_time" mission-interpreter/
```
To settle the real `start_time` value/units, re-extract `mission-interpreter/research/samples/
Mission 02-Bagram.miz` (or any other real `.miz`) and read the raw `mission["start_time"]` value
directly: `unzip -p "<file>.miz" mission | grep -n '\["start_time"\]'`.

### Possible Approaches
1. **Add `date`/`start_time` to `RuntimeMissionUnderstanding` and `MissionUnderstandingData`.**
   Cheapest within the existing pipeline shape: `tree.py`/`reader.py` already parse `date`
   losslessly; `start_time` would need the same one-line treatment if its real-sample value turns
   out to be a wall-clock seconds-since-midnight offset (plausible, matching DCS's documented
   mission-editor "Start Time" field) — then plumb both through MI-3's `MissionUnderstanding`,
   MI-6's `compact.py`/`compile.py`, and `body-layer`'s `MissionUnderstandingData`/
   `load_mission_understanding`. This is the "through Mission Interpreter into the compact
   artifact" path the architect named, and is a schema-only change (no new DCS read) once
   `start_time`'s real meaning is confirmed.
2. **If `start_time` turns out not to be a reliable wall-clock offset** (e.g. it is an editor-only
   field DCS doesn't honor, or is always `0`), the fallback is `Export.lua`'s
   `LoGetMissionStartTime()` — see the sibling note
   `aircraft-layer/research/2026-11-25-mission-start-time-and-light-level-export-api.md` for that
   half of the question.

### Unresolved
- **The real value and units of top-level `mission["start_time"]`** — never read, only its
  presence flagged. Needs either a live `.miz` re-extraction (the gitignored sample, if available
  on another checkout) or a fresh mission exported from the DCS Mission Editor with a known,
  intentionally-set start time, then grep its raw `mission` table.
- Whether DCS missions commonly have multiple `.miz` revisions where `start_time` is stale/unset
  (community-authored missions vary in Editor discipline) is unknown — a day/night-vs-sun-elevation
  computation that trusts this field blindly could be wrong on a badly-authored mission; no
  fallback/sanity-check design is evaluated here (Architect's call).
