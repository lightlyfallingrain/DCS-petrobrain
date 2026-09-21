# Unit velocity is available — through the mission scripting environment, not Export

**Date:** 2026-09-21. Prompted by the user pushing back on a claim I had relayed as settled:
*"Trackview \[Tacview\] (for example) does get speed. It's such a basic information for an aircraft
simulator that I find it hard to believe it would not be exported somehow."*

They were right, and the correction is worth more than the fact.

## The finding

| Call | Environment | Velocity? |
|---|---|---|
| `LoGetWorldObjects()` | Export (`Export.lua`) | **No** — confirmed by full `pairs()` dump |
| `Object.getVelocity()` | **Mission Scripting** | **Yes** — vec3, m/s, every unit |

`getVelocity()` returns a vec3 of the object's velocity vector and is supported by Object, Unit,
Weapon, Static Object, Scenery Object and Airbase
([Hoggit](https://wiki.hoggitworld.com/view/DCS_func_getVelocity)). It lives in the **Mission
Scripting** environment, which is why three sessions of searching the Export surface never found it.
This is how Tacview records speed for every unit on the map
([Tacview docs](https://www.tacview.net/documentation/dcs/en/)).

The 2026-09-20 deep read's finding 10 — *"`LoGetWorldObjects` carries no velocity — the movement
design must difference in the collector"* — is **correct about the call and wrong as a conclusion**.
Its first clause stands on solid evidence (a `pairs()` enumeration over the raw table, which lists a
dozen fields this project never requests, so no synonym could have hidden). Its second clause does
not follow. **When `investigation/dcs-install-detection-recon` is merged, that finding needs
qualifying rather than deleting** — the evidence is good, the inference overreached.

## Why this matters more than one field

It raises the value of a bridge the project had already identified and parked. The same deep read,
discussing fog, notes *"the mission-sandbox bridge remains the only candidate route, still
unprobed."* That bridge now gates **two** items, not one:

| Parked item | What the bridge would give it |
|---|---|
| Movement detection (`body-layer/ROADMAP.md`) | Exact `v⊥` per unit, instead of differencing two samples of a 5 Hz position feed |
| Detection under real conditions, factor 3 (fog) | The fog/visibility state Export does not carry |

For movement specifically it is not merely more convenient, it is **more accurate**: differencing
positions accumulates sampling noise, needs per-candidate history in the collector, and is exactly
the compute cost the design was trying to avoid by taking velocity omniscient in the first place.

**Still genuinely unknown, and not to be assumed:** whether `net.dostring_in` into the mission
sandbox is reachable from this project's Export.lua/Hook setup in single-player, and what it costs
per poll. That is an Investigator pass plus a probe on the Windows box — the same shape as the
SPU-8 item. Do not design against the bridge until it has been probed.

## The process failure, which is the transferable part

The deep read asked **"Is unit velocity available from `LoGetWorldObjects`?"** and answered it
correctly. The question that mattered was **"can we get unit velocity?"** A correct answer to the
narrower question was then recorded, and relayed to the user, as the answer to the broader one —
*"confirmed, no velocity under any name"* — which turned a fact about one call into a false fact
about DCS.

Nothing in the chain was careless. The investigation was rigorous, the evidence was primary, the
dump was a genuine enumeration. The scope of the question simply never got re-examined once the
answer was in hand.

**What caught it was a working counterexample**, not a better search: a tool that visibly does the
thing the finding said was impossible. That is a cheap and reliable check and it generalises — when
a negative finding says a capability does not exist, ask whether anything in the wild already does
it. A negative result from searching one surface only ever bounds that surface.
