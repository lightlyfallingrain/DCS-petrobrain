# Live terrain sampling — user design input, 2026-09-29

Captured from the user during the session that diagnosed the missed insurgent AAA
(`plans/missed-aaa-detection/debug.md`). The 12 m LOS tolerance merged that night is the
*mitigation*; this is the direction for the real fix. Feasibility recon that precedes it:
`aircraft-layer/research/2026-09-28-live-terrain-probing-feasibility.md`.

## The sampling scheme, in the user's own words

> - sample tiles around aircraft
> - coarse grid up to player bubble limit
> - medium grid up to ~6 km
> - fine grid up to ~3 km
> - fine grid for 9K113 FOV up to 20 km
>
> Save tiles to world model so they persist. Different SQLite file than main model data, so world
> model rebuild does not overwrite sampled data.
>
> Already sampled region is not resampled at existing or coarser grid.

Four properties worth naming, because each answers a cost problem the earlier discussion raised:

1. **Resolution follows attention, not distance alone.** Fine where detail changes decisions (close
   in, and along the 9K113's narrow field out to 20 km), coarse where it does not. The 9K113 tier
   mirrors the player-bubble exception already recorded for it (`todo/todo.md`, "Model the 9K113
   sight as an optic") — same 20 km, same FOV-only justification: a narrow cone, not a raised
   radius.
2. **A separate SQLite file from the main model.** This is the load-bearing detail. Sampled terrain
   is *earned* data — it accumulates over many sorties and cannot be regenerated from the offline
   pipeline. Putting it in the same file as the built model means a rebuild destroys it. M8's probe
   store (`world-model/src/probe_store/`) already exists as a separate store with its own paths, so
   the seam is built; what is new is that it would be written from a live mission rather than an
   offline pass.
3. **Never resample what is already held at equal or finer resolution.** M8's `chunk_coverage` is
   tri-state (`UNQUERIED` / `QUERIED_VOID` / covered) with row-absence meaning unqueried — the
   "don't rescan" mechanism exists. What it does not yet carry is *resolution* per chunk, which this
   scheme needs: a chunk sampled coarse must still be resamplable fine, but not the reverse.
4. **It is fog-of-war.** The user's own framing, earlier in the same conversation: the map fills in
   as you fly. `docs/concept/PETROBRAIN_RUNTIME.md`'s "expanding known-area bubble" section is the
   same idea, written weeks earlier — and its recorded blocker was corrected on 2026-09-29 after
   proving the live bridge has existed since 2026-09-13.

## The open question the user raised, and it is the right one

> Should investigate: can we sample directly from DCS terrain grid files dynamically during flight,
> or do we need to live probe DCS.

These are materially different builds:

- **Reading DCS's own terrain files** would be fast, unlimited in volume, and need no in-mission
  calls at all — no frame-rate risk, no bridge throughput ceiling. It also matches the project's
  standing preference for DCS-native extraction over probing. The unknowns are format and
  accessibility, and whether a file read gives the same surface DCS's own `land.getHeight` reports.
- **Live probing** via the mission-scripting bridge is known to work as a channel (the F10 and
  velocity hooks ride it), but its throughput under a terrain-probe batch is **unmeasured**, and a
  probe batch is orders of magnitude more per-call work than anything flown so far.

The file route, if viable, dominates. It should be investigated **before** any probing design is
committed to, not after.

## Side quest the user raised: world-model as its own service, on the Windows box

> Related side quest: world model should be its own service as well. A natural place for it is the
> windows box, since the DCS terrain files are there. Then http api to body layer on Mac.

The motivation is sound and gets stronger if terrain files turn out to be readable: the data lives
on the Windows box, and shipping it to the Mac to answer questions about it is backwards.

**But this collides with a documented, deliberate architectural decision, and the collision is on a
hot path.** Root `CLAUDE.md`: body-layer ↔ world-model is *the sole sanctioned in-process
cross-subproject import*, narrowed to "same box always" by `plans/pb1-perception-logger/plan.md`
decision 3. It is not an accident of convenience — it is used per-candidate, per-poll:
`perception/visibility.py:769` calls `line_of_sight_clear` inside the visibility gate chain, which
runs for every candidate the naked-eye channel evaluates, at 5 Hz.

So the real question is not "should world-model be a service" but **"what is the per-LOS-check cost
over the LAN, and how many checks does a poll actually make?"** A dense scene at 5 Hz can be
hundreds of LOS checks per second. Over loopback that is free; over HTTP to another machine it is
not, and the answer probably decides the design:

- If the call count is high, the seam has to change shape — batch every candidate's LOS into one
  request per poll, or move the whole visibility gate to the Windows side, or cache terrain
  locally and keep the query in-process (which is what exists today).
- If it turns out low, a plain HTTP seam may be fine and the module-independence rule gets simpler,
  not more complex.

**Do not start this by moving code.** Measure the LOS call rate from a real sortie first — the
detection trace already records every `check_visibility` call, so the number is one reduction away
from data the project already knows how to collect.

## Status

Nothing here is built. Recorded as the direction, with the two investigations that gate it:
terrain-file readability (before any probing design), and LOS call rate (before any service split).
