### Implementation Summary

`BL-11` Stage 4. The DCS line-of-sight Hook walked `coalition.getGroups()` ->
`grp:getUnits()` only, so **static objects were absent from the enumeration entirely** and could
never receive a LOS verdict — **278 of 404 objects, 68.8 %**, in the measured sortie's own mission
(`aircraft-layer/research/2026-10-06-unit-id-join-results.md`; the same fact as the 323-of-425
objects that got no verdict on 2026-10-05). In that mission the statics were 112 infantry, 31 T-55,
34 T-72B/B3 and eight `ZSU-23-4 Shilka` — killable, and in the Shilka's case shooting. "Static" in
DCS means placed without AI or waypoints, not decorative.

`coalition.getStaticObjects(coa)` is now walked for the same three coalition sides, through the
**same filter implementation** as units, into the **same** `candidates` list and the **same** wire
entry shape. The join key stays `getName()` — `Unit:getObjectID()` matches the `LoGetWorldObjects`
key but does not exist on `StaticObject` (`<NONE>`, 94/94), so no integer key spans both
populations. Nothing on the wire branches on unit-vs-static, so body-layer needs no change.

**Live behaviour is unverified and unverifiable from here** — it needs Windows and a running DCS.
Nothing below is a claim that it works in the sim; only that it parses, has no hoisting bug, and
passes every mechanical check this environment can run.

### Files Changed

- `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`
  - **Statics enumeration.** A second pass over the same three sides calling
    `coalition.getStaticObjects`, `pcall`'d per side, feeding `considerCandidate(st, true)`.
  - **One shared filter, not a copy.** The bubble/wedge/name/ownship logic was extracted from the
    unit loop into `considerCandidate(obj, isStatic)`, which both populations call. A copy-pasted
    second filter is the failure this avoids: "same filters as units" has to be structurally true,
    not re-typed. It is declared *below* every local it closes over.
  - **`isExist` is advisory for statics.** If the call itself fails on a `StaticObject` the object
    is still considered — dropping a live Shilka is worse than carrying a dead one, whose verdict
    is simply never joined on the body-layer side. For units the existing `isExist` gate is
    unchanged (and now `pcall`'d).
  - **Ownship exclusion hardened.** `player:getID()` was called unprotected inside the loop and
    was the only exclusion test; it is now resolved once under `pcall`, with `player:getName()` as
    a backstop so a failed `getID()` cannot silently let ownship through as a candidate.
  - **Cap literal de-duplicated.** `:322`'s hardcoded `128` now reads `MAX_SIGHTLINES`, spliced
    into the bridged chunk from `MAX_SIGHTLINES_PER_CALL` at module load time
    (`"local MAX_SIGHTLINES = " .. string.format("%d", …)`). The chunk lives in a string literal
    and cannot see this file's `local`s, which is why a splice rather than a reference.
  - **Cap instrumentation** (below).
  - Header and the `LOS_CODE` doc comment rewritten to state the statics enumeration, why the join
    key must stay `getName()`, that `units_in_*` now count objects, and that the nearest-first sort
    is load-bearing now that truncation is reachable.
- `aircraft-layer/src/schema/line_of_sight.py` — **docstring only**, no behaviour. Records that the
  population is units + statics, that a static is indistinguishable on this wire, that
  `units_in_bubble`/`units_in_wedge` are now object counts keeping their names for compatibility,
  and that `sightlines_computed < units_in_wedge` is the thing to watch.
- `aircraft-layer/CLAUDE.md` — added a `dcs-export/petrobrain-line-of-sight-hook.lua` bullet to the
  Structure list. It did **not** state the unit-only enumeration: it did not mention this Hook at
  all (nor does `WORKFLOW.md`). An absent description is worse than a stale one here, so one
  accurate bullet was added rather than leaving a shipped Hook script undocumented.

### The cap instrumentation, and what the sortie must answer

`MAX_SIGHTLINES_PER_CALL = 128` is **unchanged** — retuning it is a decision that needs the
measurement first. Pre-statics: median 43, max 71 units per result, `bridge_call_ms` ~1 ms. With
~278 more candidates in a 404-object mission the cap **may bind for the first time**, and that is
currently unmeasured. Three additions make one sortie answer it:

1. **Hook-side, `dcs.log`.** The result's leading counters are pulled out with a `string.match`
   (a pattern, not a splice) and logged as
   `objects_in_bubble= objects_in_wedge= sightlines_computed= cap=128 cap_hit=0|1`, replacing a
   truncated `result_head=`. On a pattern miss the counters read `?` and `cap_hit` reads `?` rather
   than a confident `0`.
2. **A dedicated `LOS cap bit:` line** naming how many candidates were dropped, so the question is
   one grep rather than an inference.
3. **`env.info` from inside the scripting state**, carrying what cannot cross the `dostring_in`
   boundary (one scalar return, fixed wire format): `statics_in_bubble`, `statics_in_wedge`,
   `candidates`, and **`static_enum_failures`**. That last field is the point of the line — without
   it, a `coalition.getStaticObjects` failing on every side would look *exactly* like the old
   unit-only behaviour, and nobody would know statics had gone missing again.

**What the sortie must answer:**

- Does `cap_hit=1` ever appear? If so, how often, and at what `bridge_call_ms`?
- `statics_in_bubble` > 0 on a mission known to contain statics — i.e. the enumeration is actually
  running. `static_enum_failures=0`.
- Does `bridge_call_ms` stay near ~1 ms with the tripled candidate population? The filter cost is
  per *candidate*; only the capped survivors pay the two engine calls.
- Do statics appear in body-layer's own join (contacts that previously had no LOS verdict now
  getting one)?

### Tests Added

None. The Python change is a docstring; the Lua change has no automated behavioural test by this
subproject's own standing policy (`aircraft-layer/CLAUDE.md` Testing: Hook scripts need a real DCS
process). The existing `tests/test_line_of_sight_hook_lua.py` static-text guards all still pass —
they target `SET_LOOK_TEMPLATE`, which was not touched; the new load-time splice is a separate
construct and deliberately does not live in that template.

Test-impact check: `grep -rln 'line_of_sight|LineOfSight|units_in_wedge|sightlines_computed'` over
`aircraft-layer/tests` found four files (`..._schema`, `..._api`, `..._cache`, `..._receiver`) plus
`test_line_of_sight_hook_lua.py`. None assert on the docstring prose or on the Lua text that
changed, so none needed editing. Full suite run unfiltered, not `-k`.

### Checks

aircraft-layer/ (the only subproject touched):
- `ruff format --check src tests`: **pass** (56 files already formatted)
- `ruff check src tests`: **pass**
- `mypy src` (run from inside `aircraft-layer/`): **pass**, 21 source files
- `pytest tests -q`: **pass**, 252 passed

No other subproject was touched, so no other suite applies.

Lua:
- `luac5.1 -p` on the **outer** file: pass.
- `luac5.1 -p` on the **bridged chunk extracted to its own file**, including the spliced
  `local MAX_SIGHTLINES = 128` prefix line: pass. (`luac -p` on the outer file proves nothing about
  the chunk — it lives inside a string literal.)
- `luac5.1 -p` over every file in `dcs-export/`: pass.
- **GETGLOBAL sweep, outer:** `loadfile, log, math, net, os, package, pcall, require, string,
  tonumber, tostring, type` — Lua stdlib plus genuine Hook-state DCS APIs.
- **GETGLOBAL sweep, chunk:** `coalition, env, ipairs, land, math, Object, pairs, PB_LOOK_FOV_DEG,
  PB_LOOK_HOUR, pcall, table, timer, tostring, type, world` — Lua stdlib, genuine scripting-state
  DCS APIs, and the two mission-scripting globals this channel reads on purpose.
- Neither list contains any of the script's own helpers (`considerCandidate`, `wrapSigned180`,
  `buildingClear`, `terrainClear`, `MAX_SIGHTLINES`), which is the mechanical ruling-out of the
  no-hoisting bug.

### Notable Discoveries

- **`aircraft-layer/CLAUDE.md` and `WORKFLOW.md` never documented this Hook script at all.** Every
  sibling Hook (overlay, F10 commands) has a Structure bullet; the LOS Hook had none, and neither
  did `WORKFLOW.md`'s deploy steps. The deploy gap is left as-is — out of scope here, but it means
  the deploy procedure for this script exists only in the file's own header.
- **The bubble radius is duplicated exactly the way the cap was.** `PLAYER_BUBBLE_RADIUS_M = 10000.0`
  in the outer file; `if rangeM > 10000.0` re-typed inside the chunk. Likewise `HOUR_DEFAULT`/
  `FOV_DEFAULT_DEG` versus the chunk's `or 0`/`or 45`. The splice mechanism added here would fix all
  three in one line each, but only the cap was in scope and only the cap had been flagged by a
  performance pass. Flagging the other two rather than fixing them.
- **An unnamed object no longer counts toward `units_in_bubble`.** The name is now fetched before
  the bubble counter increments, so the counter equals the joinable population rather than the
  observed population. Previously a nil-named unit counted in bubble and wedge but produced no
  entry — and worse, a nil name would have hit a nil-concat error at the entry-building step, and
  an empty name would have produced an entry the Python parser rejects (`empty unit_name`), killing
  the whole snapshot. The probe measured names as non-null 50/50 units and 94/94 statics, so this
  is defensive rather than a fix for an observed failure.
- **`coalition.getGroups` was being called unprotected** (`ipairs(coalition.getGroups(coa) or {})`),
  as were `grp:getUnits()`, `unit:isExist()` and `unit:getID()`. All are now `pcall`'d — an error
  inside `onSimulationFrame` takes the mission with it.
- **Statics cost is filter-only until they survive the wedge.** `getPoint` + arithmetic per
  candidate; only the capped survivors pay the two engine calls (`searchObjects` + `isVisible`).
  So the tripled population's cost is dominated by the cheap half unless the wedge is wide.
