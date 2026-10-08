# 2026-10-08 — sortie feedback, `fix/los-hook-statics` test flight

Captured during the user's live test flight of `fix/los-hook-statics` (the BL-11
Stage 4 statics enumeration). **Written down before exploring or planning**, per
root `CLAUDE.md` "Flight feedback is captured, then explored, then planned".

The user's own words are the specification here. Nothing below is acted on yet.

---

## 1. First poll, open terrain — the change works

Instrumentation line, pasted verbatim:

```
objects_in_bubble=218 statics_in_bubble=168 objects_in_wedge=49 statics_in_wedge=42
candidates=49 sightlines_computed=49 cap_hit=0 static_enum_failures=0 unit_enum_failures=0
```

Reading, for the record:

- Both enumerations ran — **zero failures on both counters**, which is what makes
  `cap_hit` trustworthy rather than biased toward `0` by a silent enumeration
  failure (the exact reason both counters exist; see the Hook's own comment).
- The LOS feed went from **7 candidates to 49**, and **42 of the 49 are statics**.
  That is the 68.8%-no-verdict population the change was built for.
- The cap did not bind here: 49 of 128.

## 2. Over a large city the cap binds — and the user doubts the population is worth LOS'ing

> *"over large City, Damascus in this case, objects_in_bubble=~200+ in wedge=200+
> cap_hit=1. But those are buildings, I believe. We don't really need buildings in
> objects that we track, especially we don't need to LOS them."*

Two separate claims in that, and they need separating because only the first is
measured:

- **Measured:** over Damascus, the wedge population is ~200+ and **`cap_hit=1`**.
  The 128 cap binds. Nearest-first sort means the *farthest* candidates are the
  ones dropped, which is the right failure direction, but it is now a real
  truncation rather than a hypothetical one.
- **The user's belief, not yet measured:** that the 200+ are *buildings*.

**Why that second one needs checking before anything is filtered.**
`coalition.getStaticObjects(side)` returns mission-editor-placed static objects
that *belong to a coalition*. DCS scenery buildings are terrain map objects with
no coalition and should **not** be returned by that call at all. So either the
mission author placed ~200 statics around Damascus, or the population is AI units
rather than statics, or this understanding of `getStaticObjects` is wrong. Each
leads to a different fix, and filtering on "building" would be wrong in two of
the three cases.

**The discriminator is one line of the user's own log** — the scan line's
`statics_in_wedge=` field, which was not included in the Damascus paste:

- `statics_in_wedge` ≈ 200 → it is the statics enumeration, and the question
  becomes which *types* those statics are.
- `statics_in_wedge` small while `objects_in_wedge` is 200+ → it is AI **units**,
  and the statics change is not the cause at all.

**The direction itself stands regardless of the mechanism** and is worth
recording as direction: objects the crew has no reason to track do not belong in
the LOS candidate set, and *especially* not consuming sightline budget. This is
consistent with the project's standing test — a candidate the pilot would never
be told about, and could not evade or attack, is not earning its sightline.

Not yet decided (deliberately, pending exploration): whether the filter is by
object category, by a type allow/deny list, by coalition, or by something else;
and whether the 128 cap should also rise once the population is honest.

## 3. A small stutter every 5 s

> *"Also, there's a small stutter every 5 s. What might that be?"*

Captured as an observation. The leading candidate is mechanism-level and is
**not** the LOS Hook (which polls at 1 Hz, so would stutter at 1 s):

`Export.lua`'s collector reconnect path. `RECONNECT_INTERVAL_S = 5.0`, and
`try_connect` does `sock:settimeout(0.2)` before a **blocking**
`sock:connect(HOST, PORT)` on the sim thread. While `client == nil`, that is a
connect attempt every 5 s that can stall the frame for up to 200 ms — a small
stutter on a 5 s period, which is the observation exactly.

It fires **only when the collector is not connected**, which makes it a usable
test: if the collector process is running and reachable, this is not the cause.
Note the consequence if it *is* the cause — no telemetry is reaching body-layer
at all, and the LOS verdicts (UDP 7796, fire-and-forget, independent of this TCP
socket) are also arriving nowhere, because the same collector process receives
them.

Not yet confirmed against the log. `grep "connect failed" dcs.log` settles it.

---

## Status

All three captured, none acted on. Items 2 and 3 go to `/explore` with the user
before any Architect or Implementer pass — item 2 because the mechanism is
genuinely open and the wrong reading would build the wrong filter, item 3 because
it may be a configuration state rather than a defect.

The two security-required fixes already in flight on this branch (the `;`
name guard and the splice guard test) are unrelated to all three and continue
independently.

---

## Resolution of items 2 and 3, same day

**Item 2 — the Damascus population is identified, and the filtering premise is gone.**
`statics_in_wedge=113` of `objects_in_wedge=152` settles the mechanism: these are
mission-placed statics, not scenery. Counting the mission's own Lua
(`MI24-outpost-M03.miz`, 388 statics) gives 120 infantry, 65 tanks, 70 APCs,
8 ZSU-23-4 Shilka, 60 parked aircraft, 21 `big_smoke`, ~12 carrier crew — and
**zero buildings**. `coalition.getStaticObjects` behaved as documented.

So the user's in-flight reading was mistaken. Recorded plainly because the error
direction matters: filtering on it would have removed exactly the contacts
Petrovich exists to call.

`big_smoke` was then proposed as the one droppable class, and the user rejected
that too:

> *"Big smoke can actually be usefull. In same way as signal smoke and signal
> flares, they work as landmarks for referencing."*

Smoke is a referenceable landmark, not scenery. **Nothing in this population is
filtered.** `BL-B42` is now "the 128 cap is too small for a dense city", not
"which objects to exclude".

**Item 3 — both stutter hypotheses refuted.** `grep "connect failed"` returned
nothing, so the collector was connected throughout and the `Export.lua` reconnect
theory is dead. A filter for `bridge_call_ms > 100` also returned nothing (~2 ms
semi-open, ~5 ms over Damascus), so the LOS poll does not explain it either. The
reported `max 2026` was almost certainly the log line's year. One real 2.645 s gap
in an otherwise steady 1.004 s cadence remains unexplained. **No current
candidate** — do not re-propose either refuted hypothesis without new evidence.
