---
name: bl5a_urgentcall_pattern
description: UrgentCall vs Event dispatch pattern in belief/speech.py — how to judge if it's still clean when BL-6/7 extend it
metadata:
  type: project
---

BL-5a (`belief/speech.py`) introduced `UrgentCall` as a small separate type instead of adding
`bypass_gate` to `belief.events.Event` (whose `EventKind` is a closed `Literal`, and `events.py`
was out of that milestone's scope). `route_event(store, event: Event | UrgentCall, ...)`
dispatches via `isinstance` check first. Confirmed clean at BL-5a: exactly one producer
(`crew_console.py`'s `!inject-urgent` test harness) and one consumer (`route_event`).

**Why:** avoids grafting an unused field onto a shared BL-4 dataclass for one caller, and avoids
widening a closed Literal for a kind (`"urgent call"`) that isn't a `ContactStore`-derived
lifecycle transition at all.

**How to apply:** if BL-7 (real threat-detection-driven urgent calls) or any later milestone adds
a second producer of `UrgentCall`, or a second dispatch site beyond `route_event`, re-check
whether this is still "one narrow union, one dispatch point" or has drifted into two parallel
"speakable thing" types that need reconciling — that was the risk the implementer's own deviation
note named but concluded didn't apply yet.
