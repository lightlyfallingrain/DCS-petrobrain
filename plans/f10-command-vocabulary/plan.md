# Plan: F10 command vocabulary and ownship-relative sectors

Status: approved (user decisions 2026-09-16). Branch `feature/f10-command-vocabulary`.

Source spec: `docs/concept/state-transitions.jpg` (user-authored draft, committed `0e4c165`).

## Why

The user cannot get useful feedback from flying because the command surface is too thin to
exercise anything. `petrobrain-f10-commands-hook.lua:131-134` registers three flat,
parameterless items, and two of the three are hollow by construction:

- `scan_forward` is, in `crew_console.py`'s own words, *"the bare AI-Wheel trigger, not
  `belief.tools.scan_area`"* — it fires DCS Petrovich's scan and registers nothing in the belief
  layer: no task, no area, no attention.
- `cancel_task` *"currently always reports 'no pending task' in practice"*, because nothing in
  the F10 path ever creates one.

Only `watch_nearest` genuinely exercises the belief layer. This milestone widens the command
vocabulary toward the spec and makes each command produce real belief-state, so a sortie
actually tests something.

This also clears the standing backlog item "F10 command refinement and specification"
(`body-layer/ROADMAP.md`), deferred 2026-09-13 with "we first need the full pipeline to work,
then refine everything". The pipeline now works end to end.

## Scope

**In:** the command half of the spec — the F10 menu vocabulary, ownship-relative sectors, and
wiring each command to real belief-state.

**Out (deliberate, user decision 2026-09-16):** the spec's autonomous-behaviour half — weapon
filtering by player bubble/aim, classification-resolution upgrade reports, behaviour-change
reporting, engagement-envelope danger/safe calls, auto-watch on being engaged,
group-as-single-threat, mission-lifecycle reset and debriefing. That half is BL-4/BL-7 territory,
partly built, and should be designed against real sortie feedback rather than guessed at — the
same reasoning that gates BL-8 on real flights.

**Out (blocked, not deferred by choice):** the spec's `Observ`/`Track` verbs need the 9K113
OBSERV OFF control, which `body-layer/ROADMAP.md` records as *not yet identified* (BL-6 found
only 3001/3015). The only effector that exists today is
`aircraft_client.trigger_petrovich_search("forward"|"boresight")`. These need an Investigator
pass before they are plannable; not attempted here.

## Decisions

**D1 — Ownship-relative sectors are a real frame alongside the absolute one, not a conversion
at command time (user decision 2026-09-16).** The spec's sectors are ownship-relative
(`ahead` = 11–1 o'clock, `left` = 9–11, `right` = 1–3, `full` = 9–3); `belief/attention.py:62`'s
`Sector` is compass-absolute (`N`/`NE`/…). A standing "watch left" must keep following the nose
through a turn rather than freezing to the heading held when the player pressed the button.

**D2 — Implemented by re-projection on the telemetry tick, not by threading ownship pose
through the attention API.** `area_contains` measures its wedge *from `area.center`*, and
`effective_attention`/`area_contains` have ~8 call sites in `src/` and 50 references including
tests. Giving them an ownship-pose parameter would churn all of it and make a pure, absolute
geometric predicate depend on live state. Instead: an ownship-anchored area stores its relative
spec, and `logger.py`'s tick re-projects it to an absolute centre and wedge each time telemetry
arrives (`Runner.run_once`, right after `self.last_ownship_state = ownship` and before
`store.ingest`/`store.tick`, so the same tick's contacts are judged against the fresh
projection). `area_contains` stays pure and unchanged.

**D3 — Wedge geometry is generalized additively.** The absolute `Sector` is eight fixed 90°
wedges; the relative sectors are 60°/60°/60°/180° wedges at an arbitrary heading, which no
`Sector` literal can express. `AttentionArea` therefore gains an optional explicit
`wedge_deg: tuple[float, float] | None` (centre bearing, half-width). `area_contains`
precedence: explicit `wedge_deg` if set, else the `sector` literal's derived wedge, else no
angular filter. `sector` keeps its exact current meaning, so no existing caller or test changes.

**D4 — Static F10 menu tree, fixed vocabulary (user decision 2026-09-16).** DCS radio menus are
fixed trees with no free-text input. Every item is known at load time; no collector→Hook menu
pushes, no `removeItemForGroup` traffic mid-flight. A dynamically-rebuilt contact list (the
spec's `watch <unit> <where>`) is a materially bigger build with a new in-flight failure
surface.

**D4a — the richer command forms are SRS's, not F10's (user direction 2026-09-16).** The
dynamic contact list above, waypoint/landmark-anchored scans, and the spec's
`o'clock-and-distance` location form are *not* deferred pending sortie evidence — they are
**rejected for F10 outright** and belong to BL-10/SRS, where free speech makes them natural and
a fixed radio menu never could. "A somewhat simple set via F10 comms menu will suffice."

This matters beyond this milestone in two ways. First, the 15-token vocabulary below is the
*target* set, not a stepping stone toward a richer menu — nobody should later expand the F10
tree on the "we deferred this until after the sorties" rationale, because that rationale is now
void. Second, it sharpens BL-10's brief: SRS is not merely swapping BL-5a's typed stand-ins for
a real adapter, it inherits the whole command half of
`docs/concept/state-transitions.jpg` as its requirements input.

**D5 — `scan_*` registers a real `PendingIntent` *and* fires the effector.** The current
handler does only the latter. `belief.tools.scan_area` is pure and DCS-I/O free by design (its
docstring: the handler "is also responsible for the live effector call, wrapped in its own
failure handling, so a failed live trigger never prevents the belief-state task from being
registered"). The handler will follow that contract: register first, then trigger, and report a
degraded result if the trigger fails. This is also what makes `cancel_task` non-hollow.

## Menu tree (D4)

    Petrovich
    ├── Scan
    │   ├── Ahead          -> scan_ahead
    │   ├── Left           -> scan_left
    │   ├── Right          -> scan_right
    │   ├── Full           -> scan_full
    │   └── Bearing
    │       ├── North      -> scan_bearing_n
    │       ├── Northeast  -> scan_bearing_ne
    │       ├── East       -> scan_bearing_e
    │       ├── Southeast  -> scan_bearing_se
    │       ├── South      -> scan_bearing_s
    │       ├── Southwest  -> scan_bearing_sw
    │       ├── West       -> scan_bearing_w
    │       └── Northwest  -> scan_bearing_nw
    ├── Watch
    │   ├── Nearest              -> watch_nearest
    │   └── Nearest Air Defence  -> watch_nearest_air_defence
    └── Cancel Task              -> cancel_task

15 leaves total: 4 relative scans + 8 compass-absolute `Bearing` scans (the existing absolute
`Sector` literal, unchanged) + `Watch: Nearest`/`Watch: Nearest Air Defence` + `Cancel Task` --
matching D4a's "15-token vocabulary below."

**D6 — `Watch: Nearest Air Defence` filters on *believed* classification, never ground truth**
(user request 2026-09-16; the spec's `watch <unit type> <where>` form, narrowed to the one unit
type worth a dedicated button). A contact qualifies only if its folded classification claim has
resolved to `class` or `type` level *and* `belief.classification.parent_class_of` puts it in
`_AIR_DEFENCE_OP_CLASSES` -- the four air-defence buckets in `perception.object_model`'s profile
table (`OP_SPAAG`, `OP_ZU23`, `OP_SRSAM`, `OP_MRSAM`).

A `presence`-level contact ("something is there", the naked-eye channel's `lowres` tier) is
therefore never matched, **even when the object really is a SAM**. That is the correct
behaviour, not a gap: the crew has no basis to call an unidentified blob air defence, and
answering the question anyway would be precisely the fabricated-knowledge failure the
no-omniscience invariant exists to prevent. The honest consequence, which a sortie will feel: 
this command can report "no air defence contact to watch" while an unidentified SAM sits in
plain sight. The empty result is also worded distinctly from the plain `Watch: Nearest` item's,
since "no air defence contact" and "no contact" are materially different statements.

`scan_forward` is replaced by `scan_ahead`, not aliased: the token vocabulary is a fixed
allow-list checked at the receiver (`collector.f10_command_receiver.ALLOWED_COMMANDS`), nothing
persists old tokens across a restart, and keeping a dead synonym in a hand-maintained allow-list
is how vocabularies rot.

## Sector bounds (spec, in relative bearing degrees, 12 o'clock = 0)

| Relative sector | O'clock | Centre | Half-width |
|---|---|---|---|
| `ahead` | 11 → 1 | 0° | 30° |
| `left`  | 9 → 11 | −60° | 30° |
| `right` | 1 → 3  | +60° | 30° |
| `full`  | 9 → 3  | 0° | 90° |

Only the four new ownship-relative sectors get a bounds table -- the eight `Bearing` submenu
items reuse the pre-existing compass-absolute `Sector` literal (`belief/attention.py`'s
`_SECTOR_CENTER_DEG`/`_SECTOR_HALF_WIDTH_DEG`) unchanged, so they need no new bounds definition
here.

The spec's "there is no visibility to rear hemisphere" is consistent with `full` spanning only
the forward hemisphere. Rear sectors are deliberately not offered.

## Stages

0. Branch, plan (this file).
1. `belief/attention.py`: `RelativeSector` literal, bounds table, `wedge_deg` field on
   `AttentionArea`, `area_contains` precedence (D3), `project_relative_area`.
2. `belief/contacts.py`: `ContactStore.add_area` accepts a relative spec; new
   `reproject_relative_areas(ownship)` applying D2.
3. `logger.py`: call the re-projection on the tick.
4. `belief/tools.py`: `scan_area`/`watch_area` accept `relative_sector`.
5. Hook Lua + `ALLOWED_COMMANDS`: the D4 tree and token set.
6. `belief/crew_console.py`: dispatch the new tokens; D5's register-then-trigger.
7. Docs: `aircraft-layer/WORKFLOW.md` deploy note, `body-layer/CLAUDE.md`, roadmaps, close the
   deferred backlog item.

## Risks

- **Re-projection cadence is telemetry-rate, not continuous.** A relative area is stale between
  ticks. At the current poll rate this is sub-second and far below the angular precision the
  60°-wide sectors imply, but it is a real approximation and should be stated where the field
  is defined, not discovered later.
- **An ownship-anchored area whose centre tracks ownship changes what "area" means.** The
  existing areas are patches of ground; these are patches of *view*. `tasks.py` completes a task
  when a contact falls inside `task.area` — for a moving anchor, that is "was seen in the sector
  at some tick", which is the spec's intent for a scan, but it is a different predicate from the
  fixed-area case and needs saying in `tasks.py`'s docstring.
- **No live acceptance in this milestone's DoD.** The whole point is to enable the user's
  sorties; acceptance is the sortie itself, which happens after merge. This milestone's gate is
  fixture/console testing, and the live run then feeds the autonomous half.
