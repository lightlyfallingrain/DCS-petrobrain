---
name: event-cursor-tracker-pattern
description: body-layer's standing answer to "does this walk every item ever founded" -- a tracker dataclass with a _scanned_event_count cursor into ContactStore.events, never a full contact/event rescan.
metadata:
  type: project
---

body-layer's `mission_memory/admission.py` has a repeated pattern for per-run trackers that react
to rare belief-state-transition events (`FiredOnTracker`, and now `LostContactTracker`,
BL-B112): a small `@dataclass` holding `_scanned_event_count: int = 0`, consumed each `step` call
as `contacts.events[tracker._scanned_event_count:]` -- the slice since the last call -- then
`tracker._scanned_event_count = len(events)`. Cost per poll is O(new events since last poll), never
O(all contacts ever founded) or O(full event history).

**Why this matters for review**: BL-B38 is an open backlog item worried about exactly this class
of bug ("walks every contact ever founded"). When a new per-poll tracker shows up in
`mission_memory/admission.py` (or anywhere reacting to `ContactStore.events`), check it follows
this cursor shape before assuming a full-iteration risk -- `LostContactTracker` (BL-B112,
`plans/motion-aware-certainty/performance.md`) was confirmed to follow it correctly, as was
`FiredOnTracker` before it. The write side (`MissionMemoryLogWriter`) is unbuffered
(`open(path, "a")` per write) by deliberate design given the documented volume bound (a handful to
a few dozen entries per sortie, ~3600 worst-case over two hours) -- that is not a hotspot either,
it is a stated crash-safety tradeoff at an already-small volume.

**What would actually be a risk**: a new tracker that reads `contacts.events` (or
`contacts.contacts`) in full every `step` call instead of slicing from a stored cursor. Look for
the cursor field and the slice; its absence is the tell.

See also [[project_certainty_of_growth_cost]] for the sibling finding on `belief.decay.
certainty_of`'s per-contact cost in the same review.
