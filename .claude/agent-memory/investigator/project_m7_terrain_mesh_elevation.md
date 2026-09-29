---
name: m7-terrain-mesh-elevation
description: Byte-level verdict on whether Syria's terrain-mesh files can supply offline elevation, superseding M4/M5's filename-only "no-go"
metadata:
  type: project
---

Session 2026-09-05 re-litigated M4/M5's elevation conclusion by actually reading bytes already
captured in `2026-09-04-m5-terrain-files-deep-probe-raw-2.txt` (Part 2, never previously read for
this question). Verdict details in `world-model/research/2026-09-05-m7-terrain-mesh-elevation-relitigation.md`.

Key facts (reproduced-locally from real head/tail hex dumps of the live Syria install):
- `Syria.scn5` = static-object placement scene graph (building/vehicle/clutter names) — NOT elevation.
- `Syria.tile` = texture/material/UV-atlas definitions — NOT elevation.
- `Syria.ng5` header string is literally `navGraph5File` — AI pathfinding graph, not terrain mesh;
  body is an adjacency/offset index, not a flat coordinate array (unlike `.routes`). Not ruled out as
  *indirectly* carrying node (x,y,z) positions — unread past first 512 bytes.
- `Syria.onlay.sup4` = `landscape4::lSuperficialFile`, radar/building overlay data — NOT elevation.
- `Syria.surface5` (30.4 GB, by far largest terrain file) = `landscape5::Surface5File`, a recursive
  named-property TLV container (same shape as `.tile`) whose field vocabulary (`Pbase`/`Nbase`,
  `maxEdge`, `depth`, `TRITYPE`/`TRI`) matches a LOD-quadtree triangulated terrain mesh — **the one
  real, unproven lead for offline elevation**. One float32 triple near the header start pattern-matches
  a plausible (x, elevation, z) anchor point in Syria's known coordinate scale — inferred, not confirmed.
- No public documentation or community RE of `landscape5::`/`Surface5File`/`navGraph5File`/`Scene5File`
  exists anywhere (harder search pass than M4's original, still negative). The only DCS-terrain
  open-source project found (`JonathanTurnock/dcs-global-terrain-database`) is a manually-curated
  GeoJSON db, not a binary parser — confirmed by reading its README.

Recommendation given to Architect: keep M4's live-`land.getHeight`+SRTM pipeline as the shipped M7
mechanism (it works); treat `Syria.surface5` decoding as a separate, timeboxed, optional follow-on
(1-2+ weeks, probabilistic — could stall on undecoded `TRI` compression), not an M7 blocker. A cheaper
partial win exists: walk just the quadtree node headers (skip `TRI` bodies via their length fields) for
a coarse elevation grid without full mesh decode.

Unresolved: two directly-on-topic ED forum threads (`forum.dcs.world/topic/157234-can-i-export-terrain-mesh-for-app/`,
`.../topic/48556-dcs-terrain-tool-for-3rd-party-developers`) 403'd on fetch, need user to paste manually.
`TRI` payload compression scheme unknown (no zlib magic found in head samples, may just not have reached it).

**Update 2026-09-29 (X-B26, `world-model/research/2026-09-29-x-b26-terrain-file-vs-live-probe.md`):**
nothing decoded further — still exactly where this note left it, 24 days later, zero commits touching
`surface5`/terrain-mesh since. New this pass: `DCS-files.txt` confirms the identical file family
(`.scn5`/`.ng5`/`.onlay.sup4`/`.surface5`) ships under every installed terrain (Afghanistan, Caucasus,
Kola, MarianaIslands, Syria) — the *shape* of this lead generalizes across theatres by filename, but
the byte-level decode has only ever been attempted against Syria's copy; re-verify per terrain, don't
assume. Also ruled out clipmaps as a second lead: only `colortexture`/`normalmap`/`splatmap` subdirs
exist, no `heightmap` clipmap layer anywhere. Recommended next step is unchanged in spirit but now
concrete: **one cheap spike** — decode one `.surface5` quadtree node's anchor float32 triple and
cross-check it against a live `land.getHeight` call at the same `(x,z)` (now easy to run — the
mission-telemetry bridge already flies at 1Hz, see `aircraft-layer/research/
2026-09-28-live-terrain-probing-feasibility.md`) — before committing to either the 1-2wk full decode
or the live-probe plumbing. This is hours of work, not weeks, and resolves the yes/no question
directly.
