# Why an M163 Vulcan's firing event read `targets_ownship=false` while a Leopard-2A5's read `true`

**Date:** 2026-10-20
**DCS version:** 2.9.30.28738 (`autoupdate.cfg`, `$DCS_INSTALL_PATH`, read directly this session)
**Theatre:** Kola (`dcs.log`: `Dispatcher (Main): Terrain theatre Kola`, mission sequence 6,
`onSimulationStart` 13:57:22 — the mission this session's evidence comes from)

### Question

`docs/acceptance/2026-10-20-sortie-feedback.md` F6's "live check while paused" / "Correction"
entries recorded: at sim t=335.7s, a unit named `Vulcan-2` was visually firing tracers at the
player (confirmed by the user, bearing corrected 0→9 o'clock) while the collector's
`/firing/latest` reported it with `targets_ownship: false`; earlier in the same sortie, a
`Ground-1-3` (Leopard-2A5) firing event correctly read `targets_ownship: true`. The note's own
working hypothesis — *"the likely reading is that an AAA gun's `S_EVENT_SHOOTING_START` carries no
`target` (nil, so false), but that is unverified"* — is exactly what this investigation was
dispatched to check.

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
(1) `event.target` is nil, (2) `world.getPlayer()` fails/returns nil, (3) either name lookup's
`pcall` fails, or (4) the names are both resolved and simply don't match — i.e. the unit is
genuinely engaging something that is not the player. The sortie note's hypothesis only considered
path 1. Also load-bearing and previously undocumented in this file's own header prose:
`targets_ownship` is computed **once**, Hook-side, at `S_EVENT_SHOOTING_START` time only, and is
never revisited by a later `SHOOTING_END` or any subsequent poll — confirmed from the same source
(`ownship01` is set inside the `kind == "S_EVENT_SHOOTING_START"` branch and nowhere else) and from
`collector/firing_receiver.py`'s `ActiveEmitter`/`EmitterTracker._apply`, where `targets_ownship` is
set only in the `S_EVENT_SHOOTING_START` branch and the `SHOOTING_END` branch only adjusts
`expires_at_sim`.

### Findings

1. **An M163 Vulcan's `S_EVENT_SHOOTING_START` does carry a populated `target` in this DCS
   version, including naming the player when that is genuinely who it is engaging** — **evidence:
   reproduced-locally, from this machine's own `Saved Games\DCS\Logs\debrief.log`** (675 KB, last
   written 16:57, the same session whose `dcs.log` shows the Kola mission started 13:57:22 and
   whose `PetrobrainFiringEvents` poll entries run 11:53–14:49 the same day — consistent with one
   long, heavily-paused session, matching F6's own "DCS is paused right now" report). Parsed its
   `events` table (791 total events, max `t`=425.2s) for every entry naming `"Vulcan"` as initiator
   or target:

   | unit (`initiator_object_id`) | shooting events | target every time |
   |---|---|---|
   | `16823296` | none (killed by a T-90 round at t=213.4 before ever firing) | — |
   | `16823552` | START 230.48, 235.72, 289.4 (each closed by an END) | **`Su-25`**, never the player |
   | `16823808` | START 259.1 (closed by END 260.9, same instant it was killed) | **`Mi-24P`** — this one really was shooting at the player |

   So **both** outcomes this project needs to distinguish — "really aimed at ownship" and "aimed at
   something else" — are produced by the *same* unit type (M163 Vulcan) in the *same* mission, both
   with `target` populated and correctly named. This directly refutes "an AAA gun's
   `SHOOTING_START` carries no target" as a general engine behavior for this unit type, in this DCS
   version. It is not type-dependent: the M163 Vulcan behaves exactly like the already-confirmed
   HMMWV/tank case (`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-
   bridge.md`'s 2026-09-25 probe), not differently.

2. **Every Leopard-2A5 `SHOOTING_START` in the same debrief log (82 shooting-type events total)
   also carried a populated, correctly-named `target`** — **evidence: reproduced-locally, same
   source**. 56 of them read `target=Mi-24P` (the player), later bursts read `target=Su-25`
   (a different aircraft the Leopard switched to engaging), and the final burst at t=423.97 reads
   `target=Mi-24P` again — immediately after a `kill` event crediting the Leopard's `7.62mm` MG3
   fire with destroying the player's Mi-24P at t=423.36. So the Leopard case the sortie note cited
   as the working "it works for tanks" baseline is confirmed, and shown to generalize across the
   whole engagement, not just the one burst the note already knew about.

3. **The specific Vulcan unit most likely to be the `Vulcan-2`/`Vulcan-3` named in the sortie note
   (`object_id 16823552`, the one that only ever engaged the Su-25) has a documented, well-defined
   collector-side reason to still read `targets_ownship: false` at sim t=335.7s, and it is in this
   project's own code, not a DCS internals quirk** — **evidence: inferred, from cross-referencing
   Finding 1 against `firing_receiver.py`'s own documented constants**:
   - Its last engagement: `SHOOTING_START` at t=289.4s (target=`Su-25`, so `targets_ownship=false`
     is the *correct* reading for that burst), `SHOOTING_END` at t=290.14s per debrief.log.
   - `EmitterTracker`'s own two constants (`FIRING_MIN_VISIBLE_S = 1.5`,
     `FIRING_WATCHDOG_S = 180.0`): if the Hook's live `world.addEventHandler` channel received that
     `SHOOTING_END`, the entry's expiry is `max(290.14, 289.4+1.5) ≈ 290.9s` — long gone by 335.7s.
     If the Hook's channel **never received** that `SHOOTING_END` (the unit is still alive, so the
     only other removal path — death — does not apply either), the entry's expiry is instead
     `289.4 + 180 = 469.4s` — comfortably covering 335.7s, and still showing the `false` value that
     was frozen in at 289.4s, correctly for that engagement, now stale and misleading for a later
     moment.
   - Debrief.log itself records **no shooting event from any unit at all** between t=297 and t=378
     (the window containing the F6 note's 303/318/335.7s timestamps) — so DCS's own debrief
     recorder did not see a fresh Vulcan (or Leopard) `SHOOTING_START` in that window either. That
     leaves a stale, still-open 289.4s-vintage entry as the only candidate explaining what
     `/firing/latest` was showing as "active" at 335.7s.
   - **The one open step this would need to fully close**: confirming, from the live
     `GET /firing/latest` response at that moment, that the `Vulcan-2` entry's `since_sim` reads
     ≈289.4 rather than something newer. This session could not query it — see Unresolved.

4. **`debrief.log` and the live `world.addEventHandler` Hook channel are two separately-implemented
   DCS subsystems that are not guaranteed to agree**, which is the premise Finding 3 rests on —
   **evidence: already established, re-cited not re-derived** — `aircraft-layer/research/2026-09-
   24-damage-and-firing-events-over-mission-bridge.md`'s "Addendum" section drew the same
   distinction for a different purpose (debrief.log answers "does the engine raise the event",
   never "does our live handler receive it"). A dropped event on the live channel that the engine's
   own end-of-mission recorder still captured is consistent with that distinction, not a new claim
   about either subsystem individually.

5. **Community evidence is consistent with occasional/undocumented SHOOTING_START data gaps in
   general, not specific to AAA** — **evidence: forum-claim, not independently verified**. A web
   search surfaced a forum reply (via search-engine summary only, not fetched — see below)
   characterizing `nil` fields on this event class as "normal... especially common in timing and
   heavy load", and a thread titled *"identical events not all receiving the same event data"*
   (`forum.dcs.world/topic/348646-...`) whose title matches this investigation's shape exactly. Both
   `forum.dcs.world` fetches in this session returned **403** (`topic/348646-...` and
   `topic/149831-vulcan-sight-problems-and-combat-use`) — consistent with this project's own
   standing finding that automated fetches to that domain are blocked (prior research's
   `forum-dcs-world-fetch` note). **Per this role's standing instruction, these are not recorded as
   an unread gap in the give-up sense** — if useful, ask the user to open those two URLs manually
   and paste the content back; neither was read by this investigation. The Hoggit wiki page itself
   (`DCS_event_shooting_start`, fetched directly, no block) says only *"Target: The unit that is
   being targeted"* — it does not document the field as guaranteed-present, nor does it say
   anything differs by unit type.

### Reproducible Test

**What this session ran, repeatable on any machine with the DCS install and a synced
`debrief.log`:**

```sh
# requires $DCS_SAVED_GAMES_PATH; parses the post-mission events table, no DCS running needed
python3 -I - <<'PY'
import re
text = open(r"$DCS_SAVED_GAMES_PATH/Logs/debrief.log", encoding="utf-8", errors="replace").read()
for b in re.split(r'\},\s*--\s*end of \[\d+\]', text):
    if '"Vulcan"' in b and "shooting" in b:
        print(b)
PY
```

**What this session could NOT run, and should be run next time this question comes up live:**
`curl`/any outbound network call from this sandboxed session to `http://127.0.0.1:7791/firing/latest`
was **denied outright** (tried with and without `dangerouslyDisableSandbox: true`) even though the
task description expected it to work and both DCS and the collector were confirmed running on this
same machine. `WebFetch` also explicitly refuses localhost. **This is an environment/session
restriction, not a DCS-internals finding** — flag it to whichever session has unblocked Bash network
access (or run `curl` directly on the Windows/collector box) to pull `/firing/latest`'s live
`since_sim` for the active entry the next time a unit reads an unexpectedly-stale
`targets_ownship`.

### Possible Approaches

Not this role's decision (Architect's), but options worth having on the table given Finding 3:

- **Surface `since_sim`/engagement age on the wire**, so a consumer (or a human reading
  `/firing/latest` during debugging) can tell a fresh "aimed at us" from a 45-second-old stale
  latch, rather than only a boolean.
- **Shorten `FIRING_WATCHDOG_S`** from 180s — the constant's own comment already flags its value as
  "a conservative guess rather than a measured bound" pending exactly this kind of live evidence.
  A shorter watchdog trades "stale false readable as fresh" against "a real sustained engagement
  with a dropped END reads as ended too soon" (the failure mode the constant was deliberately set
  high to avoid) — a real tradeoff, not a strict improvement either way.
- **Investigate why the live Hook channel would miss a `SHOOTING_END` that `debrief.log`'s own
  recorder caught** — needs either a live repro with both channels compared in the same sortie, or
  ED forum confirmation of a known gap between `world.addEventHandler` delivery and the mission's
  own debrief recorder. Not attempted this session (would need a fresh live sortie, out of this
  investigation's scope).
- **Do nothing differently** if Architect judges a 45-second-stale "not currently aimed at us"
  reading an acceptable rate of false-negative for this feature's purpose — the alternative (a
  shorter watchdog) has its own failure mode, per above.

### Unresolved

- **Whether the live `/firing/latest` entry's `since_sim` for `Vulcan-2` at the moment of the F6
  query actually reads ≈289.4s**, which would close Finding 3 from "well-supported hypothesis" to
  "confirmed". Needs network access to the collector (blocked this session) or a fresh live repro.
- **Whether a genuinely fresh, player-aimed `SHOOTING_START` also occurred around sim t=330–336s**
  and was missed by *both* `debrief.log` and the live Hook. `debrief.log` shows no shooting event
  from any unit in the 297–378s window, which argues against this, but cannot fully rule it out —
  debrief.log's own completeness under those specific conditions was not independently verified.
- **The two forum threads that 403'd** (`forum.dcs.world/topic/348646-...` title match: "identical
  events not all receiving the same event data"; `forum.dcs.world/topic/149831-vulcan-sight-
  problems-and-combat-use`) — ask the user to open and paste if this question needs to go further.
- **Whether this `debrief.log` is literally the same sortie instance as the F6 note's query**, as
  opposed to a very similar, separately-flown mission on the same Kola setup that day. The
  timestamps, unit roster (Mi-24P/Leopard-2A5/M163 Vulcan/Su-25), and the long-pause pattern all
  line up, but this was not independently confirmed (e.g. by a shared mission UUID or identical
  object ids against a second artifact) — labeled **strong circumstantial match**, not proven
  identity.

### Sources

- `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` — production Hook source, read in
  full this session (`targetsOwnship`, event registration/poll split).
- `aircraft-layer/src/collector/firing_receiver.py` — `EmitterTracker`/`ActiveEmitter`, read in full
  this session (`FIRING_MIN_VISIBLE_S`, `FIRING_WATCHDOG_S`, latch/expiry logic).
- `$DCS_SAVED_GAMES_PATH/Logs/debrief.log` (this machine, 31388 lines, 791 events, mtime 2026-10-20
  16:57) — parsed this session, the primary new evidence.
- `$DCS_SAVED_GAMES_PATH/Logs/dcs.log` — confirmed mission theatre (Kola), mission start time, and
  that `PetrobrainFiringEvents` logs only per-poll counts, never per-event detail (so it could not
  answer this question on its own).
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
  probe establishing the HMMWV/tank baseline and the debrief-log-vs-live-Hook distinction this
  note's Finding 4 re-cites.
- `docs/acceptance/2026-10-20-sortie-feedback.md`, section F6 — the question's origin.
