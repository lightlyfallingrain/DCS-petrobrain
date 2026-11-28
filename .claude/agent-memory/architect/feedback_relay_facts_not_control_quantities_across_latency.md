---
name: relay-facts-not-control-quantities-across-latency
description: Across a slow route (Hook -> collector -> body-layer -> lease -> Lua, ~1-3 s), relay world-frame facts (terrain points x,z,h) and let the law re-project them every step; never relay a control quantity (a floor, a climb rate) computed from stale state. Also: check whether a "flag" is derivable from data the law already holds before adding one.
metadata:
  type: feedback
---

When planning BL-16 M3 (terrain look-ahead), the brief's fallback said "body-layer computes the
floor and relays it down". Relaying the **points** instead (world x, z, terrain height, with a seq)
was better: a climb rate computed in body-layer from a 2 s old altitude and speed is wrong by however
much both changed, whereas world-frame points do not go stale geometrically. Lua re-projects them
against its current position every law step, so age only shortens the reach by V*age. It also keeps
the law in one place whatever the sampler is (Hook today, `LoGetAltitude` in Export.lua if ever
confirmed: only the sampler changes).

**Why:** latency turns a relayed control quantity into a control error; it turns relayed facts into
a slightly shorter horizon. The user accepted 1-3 s routing on exactly that premise ("it takes a
couple of seconds to travel 200 m").

**How to apply:** any plan that moves data across body-layer <-> Export.lua for the flight law (or
any loop faster than the route): send the facts in a fixed frame with a sequence number, stamp at
receipt on the fast side, age them out there, and compute the decision on the fast side.

Same pass, second lesson: alignment asked for an "explicitly commanded" marker to travel with the
altitude goal. Grepping every writer of an AGL goal showed all of them were the user's explicit
cases, so the floor was derivable (`min(50, AGL goal)`, 50 for baro) with no flag and no wire
change. Before adding a co-moving flag, list the writers of the field it would qualify; a derived
value cannot diverge. See [[feedback_read_the_flight_trace_before_designing_from_its_label]].

Also found: BL-B111 `probe_points` answers `land.isVisible` (0/1), not heights, and is a single
last-wins setter owned by expected-area checks; "reuse probe_points" means a sibling op on the same
mechanism, not the op itself.
