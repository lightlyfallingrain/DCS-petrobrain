# The mission-scripting bridge is already in production

**Date:** 2026-09-22. Resolves the item filed as *"probe whether `net.dostring_in` reaches the
mission sandbox"*. **No probe was needed. The bridge has been shipping since 2026-09-13.**

## The finding

`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua` is built on it. Its own header:

> *"This Hook script registers three fixed F10 → Other → Petrovich radio-menu items in the
> mission-scripting state via `net.dostring_in("scripting", ...)` at `onSimulationStart`, drains
> player selections back out by polling the same bridge once a second…"*

and line 201 is the call itself:

```lua
local callOk, result, success = pcall(net.dostring_in, state, code)
```

So the F10 command vocabulary — flown, accepted and closed by the user as *"tested and good
enough"* — **is** the bridge, running at 1 Hz in production.

## Three things that were wrong, and they compounded

A probe was written and run, and it returned a clean negative that was itself misleading:

```
net present: false
net.dostring_in present: nil
call ok: false  result: attempt to index global 'net' (a nil value)
```

1. **Wrong environment.** `net` does not exist in the Export.lua sandbox at all. It lives in the
   **GameGUI/Hook** environment — `Saved Games/DCS/Scripts/Hooks/`. The probe was written for
   Export.lua, where the answer could only ever be "no".
2. **Wrong state name.** The probe passed `"mission"`. The working call uses **`"scripting"`**. Even
   in the right environment it would have failed.
3. **A missed precondition.** `net.dostring_in` is **gated off without an `autoexec.cfg` opt-in**,
   documented in `aircraft-layer/WORKFLOW.md`. Without it every state returns
   `"Invalid state name"`. The user already has it, because the F10 menu works.

## Why this happened, which is the part worth keeping

The research note
(`2026-09-21-unit-velocity-via-mission-scripting.md`) said the bridge *"remains the only candidate
route, still unprobed"*. **That was already false when written** — the F10 hook had been citing the
bridge in its own header for eight days.

The claim was inherited from
`2026-09-20-dcs-install-detection-deep-read.md`, which said the same while discussing fog, and it
propagated unchecked into a backlog item, a status-page blocker, a test card, and finally a probe
written to answer a question the repository had already answered.

**This is the third instance in two days of the same failure**, and the graph carries a hyperedge
naming it: *a negative over one surface, recorded once, then inherited without re-checking*. The
first two were `LoGetWorldObjects` velocity and the ED movement/dwell claim. The pattern is not
carelessness at the point of investigation — each original finding was honest about its own scope.
It is that **the scope qualifier does not survive the first citation**.

Worth noting what would have caught it: the F10 hook's header names the mechanism in plain text, and
`grep -rn 'dostring_in' aircraft-layer/` finds it in under a second. The graph would also have
returned it. Neither was tried, because the claim arrived pre-labelled as settled.

## What this unblocks, and what it changes

**`Object.getVelocity()` is reachable today** through machinery already deployed and already polling
at 1 Hz. Movement detection does not need a new channel — it needs a second query on an existing
bridge.

- **`body-layer/ROADMAP.md`'s movement entry** — the velocity route is no longer "gated on probing
  that bridge". The fallback (differencing positions in the collector) is no longer needed, along
  with its three recorded consequences: per-`object_id` position history, poll-interval sensitivity,
  and `object_id` continuity becoming load-bearing.
- **The fog half of "detection under real world conditions"** — same bridge, same conclusion. Fog is
  reachable, subject to the same `autoexec.cfg` opt-in.
- **`todo/todo.md`'s probe item** — closed as already-answered, not as done.
- **The status page's "mission-sandbox probe" blocker** — not a blocker. It should come off the
  "waiting on you" list.

**What is still genuinely unknown:** the per-call cost at the rate movement detection would need.
The F10 hook polls once a second and that is comfortable; a per-poll velocity query for every
candidate is a different load. That is a real question, and it is a *performance* question rather
than a feasibility one.
