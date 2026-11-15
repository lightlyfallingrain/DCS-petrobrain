---
name: certainty-of-growth-cost
description: belief.decay.certainty_of's tracked/estimated boundary became growth-distance-based (BL-B112) -- still O(1) per call via object_model.profile_for's functools.cache, not a new hot-path risk.
metadata:
  type: project
---

As of BL-B112 (`plans/motion-aware-certainty/`), `belief.decay.certainty_of`'s tracked/estimated
split no longer compares elapsed time against `POSITION_HALF_LIFE_S` alone -- it calls
`distance_since_last_seen_m`, which calls `association_over_time.contact_growth_rate_mps(contact)`,
which calls `perception.object_model.profile_for(contact.last_class_raw)`. That last call is
`@cache`d (`functools.cache`), so repeated calls for the same `object_type` string are O(1); the
keyword-tuple linear scan only runs on a genuine cache miss (new object type seen for the first
time), and the table is a few dozen rows. Net effect: `certainty_of` went from "one float compare"
to "one cached dict lookup + arithmetic" -- still O(1) per call, no allocation, no I/O.

**Why this is worth remembering**: `certainty_of` is called from several places per contact per
tick (`belief/contacts.py` inside `ContactStore.tick`, `belief/callouts.py`, `mission_memory/
admission.py`) plus brain-tool-API-driven iterations over the whole contact set (`belief/tools.py`,
gated by request frequency not poll frequency). None of these call it more than once per contact
per actual event -- `belief/speech.py`'s `_needs_hedge` and `crew_console.py` read an
already-computed `facts["certainty"]` string rather than re-calling `certainty_of`, confirming the
project's convention of computing a belief-state fact once and threading it through, not
recomputing per consumer. If a future change makes `certainty_of` itself heavier (e.g. a
non-cached lookup, or something per-call that isn't O(1)), re-check every one of those call sites
multiplies that cost by the live contact count, which stays in the tens given the project's 50-800m
AGL operating envelope ([[project_operating_altitude_envelope]] in other roles' memory).

See also [[project_event_cursor_tracker_pattern]] for the sibling finding in the same review.
