# Why an M163 Vulcan's firing event read `targets_ownship=false` while a Leopard-2A5's read `true`

**RESOLVED.** `targets_ownship: false` was the **correct** reading: this sortie's own `debrief.log`
(written once the mission ended, confirmed below) shows the specific `SHOOTING_START` the collector
read at t=335.461 genuinely targeted the player's wingman, not the player. Hypothesis (a) —
first raised as speculation from the pilot's own recollection, then confirmed from the sortie's own
post-mission record — is the answer. No code defect, in this Hook or in `EmitterTracker`.

**Date:** 2026-10-20 (corrected twice same day — see "Correction" and "Final confirmation" below;
the original version's Findings 1–4 contained two errors the first correction fixed, left in git
history rather than silently edited away)
**DCS version:** 2.9.30.28738 (`autoupdate.cfg`, `$DCS_INSTALL_PATH`, read directly this session)
**Theatre:** Kola (`dcs.log`: `Dispatcher (Main): Terrain theatre Kola`)

### Question

`docs/acceptance/2026-10-20-sortie-feedback.md` F6's "live check while paused" / "Correction"
entries recorded: at sim t=335.7s, a unit named `Vulcan-2` was visually firing tracers at the
player (confirmed by the user, bearing corrected 0→9 o'clock) while the collector's
`/firing/latest` reported it with `targets_ownship: false`; earlier in the same sortie, a
`Ground-1-3` (Leopard-2A5) firing event correctly read `targets_ownship: true`. The note's own
working hypothesis — *"the likely reading is that an AAA gun's `S_EVENT_SHOOTING_START` carries no
`target` (nil, so false), but that is unverified"* — is exactly what this investigation was
dispatched to check, and it was wrong: see below for what the code and the sortie's own record
actually show.

### What the Hook code actually does (so "false" is traced to a cause, not just observed)

`aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` lines 175–183 (`targetsOwnship`):

```lua
local function targetsOwnship(target)
    if target == nil then return false end
    local okP, player = pcall(world.getPlayer)
    if not okP or player == nil then return false end
    local playerName = safeName(player)
    local targetName = safeName(target)
    if playerName == nil or targetName == nil then return false end
    return playerName == targetName
end
```

— **evidence: documented (direct code read)**. `false` is returned by exactly four distinct paths:

| branch | condition | what it means if this is what happened |
|---|---|---|
| 1 | `event.target == nil` | the AI had no locked target object at all at that instant |
| 2 | `world.getPlayer()` fails or returns `nil` | the Hook couldn't resolve *its own side* of the comparison |
| 3 | `safeName(player)` or `safeName(target)` fails (`pcall` raises) | a `getName()` call on either object raised |
| 4 | both names resolved, and differ | the AI genuinely has a target, and it is not the player |

The sortie note's hypothesis only considered branch 1. `targets_ownship` is computed **once**,
Hook-side, at `S_EVENT_SHOOTING_START` time only (`ownship01` is set inside that branch and
nowhere else), and `collector/firing_receiver.py`'s `EmitterTracker._apply` **replaces the whole
`ActiveEmitter` entry, `targets_ownship` included, every time a new `S_EVENT_SHOOTING_START`
arrives for that unit's name** (`self._active[event.initiator] = ActiveEmitter(...)` — a full
replace, not a merge or an update of one field). This second fact is the one the original version
of this note got wrong — see "Correction" immediately below.

### Correction (same day) — two errors in the original version of this note

The coordinator caught both from evidence already in hand; recorded here rather than silently
rewritten, per this role's "label an inference as one all the way to its destination" discipline.

**1. The `debrief.log` evidence is from the *previous* mission, not this sortie.** DCS writes
`debrief.log` only when a mission ends. The sortie this question is about started at **16:57:24**
(body-layer's own log stamp `20261020-165724`) and was still running at 17:37; `debrief.log`'s mtime
is **16:57**, i.e. written by the mission that ended *just before* this one started — almost
certainly the previous run of the same mission file (restarted seconds apart, which is why the
timestamps and unit roster looked like a match). **Original Findings 1 and 2 (the per-unit
target table, the Leopard-2A5 table) are not evidence about this sortie's `Vulcan-2`/`Ground-1-3`.**
What they *do* still show, unaffected by this correction, is that **an M163 Vulcan's
`SHOOTING_START` is capable of carrying a populated, correctly-named `target` on this install** —
observed twice in that earlier run, including once naming the player. That capability-exists claim
stands; its use as evidence about *this* sortie's specific units does not. This sortie's own
`debrief.log` will exist once this mission ends and would settle what `Vulcan-2` was actually
targeting at t≈335s — not available yet.

**2. The stale-watchdog-latch hypothesis (original Finding 3) is refuted by evidence already in the
sortie note.** At sim 335.692 (per the live `/firing/latest` read the coordinator had), the active
`Vulcan-2` entry carried `since_sim: 335.461` — a `SHOOTING_START` **0.2 seconds old**, not a
180-second-old latch surviving on the watchdog. Per `EmitterTracker._apply` (quoted above), a new
`SHOOTING_START` fully replaces the entry, `targets_ownship` included — so this was a **fresh**
event, resolved to `false` at the moment it arrived, not a frozen value from an old engagement. The
timing argument built in the original Finding 3 (cross-referencing a stale t=289.4s engagement
against the previous mission's `debrief.log`) is therefore moot twice over: it used the wrong
mission's data (error 1) to support a mechanism the real `since_sim` value already rules out
(error 2). Struck entirely rather than kept as a "possible but now unlikely" option.

### Final confirmation — (a) is CONFIRMED from this sortie's own `debrief.log`

This sortie's `debrief.log` (mtime 18:06, written once *this* mission ended — not the previous
run's file used, in error, earlier in this note) carries the actual record:

- **At t=335.461s, `initiatorMissionID 434` ("Vulcan") began `SHOOTING_START` against
  `targetMissionID 447` — the player's wingman, not the player.** The player's own mission ID is
  `344` (pilot name `"sg"`). So the exact event the collector ingested at that `since_sim` really did
  have a non-player target. `targets_ownship: false` was the **correct** answer for that event, full
  stop — branch 4, a genuine mismatch, confirmed rather than inferred.
- **Separately, between t=322.8s and t=331.9s, a *different* Vulcan (`initiatorMissionID 433`) really
  was shooting at the player (`344`).** That engagement had already closed (and its collector-side
  entry expired, `FIRING_MIN_VISIBLE_S = 1.5s` past its own `SHOOTING_END`) by the time the pilot's
  live query landed at sim 335.7s — which is why the *only* active entry visible at that moment was
  unit `434`'s fresh, wingman-targeting one. The pilot's visual impression of "fire aimed at me right
  now" and the collector's snapshot a few seconds later were each individually accurate; they just
  were not describing the same burst. Two real engagements, half a minute apart, from two different
  named Vulcans, briefly looked like one continuous "false reading on an obvious threat" from outside
  the collector's own event-by-event view.

**This closes the question.** (b) — a `targetsOwnship` resolution failure — is not needed to explain
anything observed this sortie, and nothing found this session gives it independent support; it
remains a theoretical code path (four branches exist, as documented above) but not one this
investigation found evidence for.

### Possible Approaches

Not this role's decision (Architect's), now narrowed by the confirmed cause rather than left open:

- **No code defect to fix.** `targetsOwnship`/`EmitterTracker` both did exactly what they are
  documented to do; the confusion was entirely in how a human reconciles a point-in-time API
  snapshot against a continuous, multi-shooter visual impression.
- **If this class of confusion is worth addressing anyway**: surfacing *which* unit is firing and
  *who at* (not just a `true`/`false` bit) on `/firing/latest` — or in whatever reaches the
  player/body-layer — would let "something near me is shooting, just not at me" be distinguished from
  "nothing is shooting" at a glance, without changing any underlying logic. A product/UX call for
  Architect, not a bug fix.
- **The debrief-log-vs-live-Hook distinction this note leaned on earlier turned out not to be load-
  bearing here** (both channels agree for these two Vulcans) — worth remembering it as a real,
  previously-documented gap in general, but not needed to explain this incident specifically.

### Unresolved

- **The two forum threads that returned 403** (`forum.dcs.world/topic/348646-identical-events-not-
  all-receiving-the-same-event-data`, title match for exactly this kind of inconsistency;
  `forum.dcs.world/topic/149831-vulcan-sight-problems-and-combat-use`) — ask the user to open and
  paste if a different, future question needs them; neither was read this session (standing 403
  finding, `forum-dcs-world-fetch` memory). Not needed to resolve this investigation's question.
- **Bash network access to the live collector API (`127.0.0.1:7791`) was denied outright this
  session**, even with `dangerouslyDisableSandbox: true`; `WebFetch` also refuses localhost. Flagged
  as session/environment-scoped, not a project fact — see
  [[feedback_bash_network_to_localhost_blocked_this_session]]. Turned out not to block resolving this
  question (file-based evidence sufficed), but still worth fixing before the next live-read need.

### Sources

- `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` — production Hook source, read in
  full this session (`targetsOwnship`, event registration/poll split).
- `aircraft-layer/src/collector/firing_receiver.py` — `EmitterTracker`/`ActiveEmitter`, read in full
  this session (`FIRING_MIN_VISIBLE_S`, `FIRING_WATCHDOG_S`, the full-replace-on-`SHOOTING_START`
  behavior that refutes the original Finding 3).
- `$DCS_SAVED_GAMES_PATH/Logs/debrief.log`, **first read at mtime 2026-10-20 16:57** (31388 lines,
  791 events) — **from the previous mission run, not this sortie** (see "Correction"). Still valid as
  a capability-exists demonstration (an M163 Vulcan on this install can carry a correct `target`,
  including naming the player), not as evidence about this sortie's specific units.
- `$DCS_SAVED_GAMES_PATH/Logs/debrief.log`, **re-read at mtime 2026-10-20 18:06, once this sortie's
  mission had actually ended** — the record that settles the question (see "Final confirmation"):
  `initiatorMissionID 434` → `targetMissionID 447` (the wingman) at t=335.461s; `initiatorMissionID
  433` → `targetMissionID 344` (the player, pilot name `"sg"`) between t=322.8–331.9s.
- `$DCS_SAVED_GAMES_PATH/Logs/dcs.log` — confirmed mission theatre (Kola) and that
  `PetrobrainFiringEvents` logs only per-poll counts, never per-event detail (so it could not answer
  this question on its own).
- `$DCS_INSTALL_PATH/autoupdate.cfg` — version `2.9.30.28738`.
- `$DCS_INSTALL_PATH/Scripts/Database.edce` — confirmed ED-encrypted/opaque; the M163 Vulcan's own
  unit/AI definition is not readable from this install at all (no `.lua` source exists for stock
  units the way `CoreMods/tech/TechWeaponPack/Database/vehicles/Tanks/Leopard-2A5.lua` exists for
  the third-party Leopard) — this rules out a direct unit-definition comparison as a source.
- Hoggit `DCS_event_shooting_start` (fetched directly, no block) — `target` field description is
  one line, no guarantee-of-presence or per-unit-type language.
- `forum.dcs.world/topic/348646-...`, `forum.dcs.world/topic/149831-...` — **403, not read**; named
  above as candidates for the user to open manually.
- `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md` — prior
  probe establishing the HMMWV/tank baseline, the debrief-log-vs-live-Hook distinction, and
  `world.getPlayer()`/`world.addEventHandler` reachability (Finding 15) this note builds on.
- `docs/acceptance/2026-10-20-sortie-feedback.md`, section F6 — the question's origin, and (via the
  coordinator) the `since_sim: 335.461` live-read detail that is not itself written into that file.
