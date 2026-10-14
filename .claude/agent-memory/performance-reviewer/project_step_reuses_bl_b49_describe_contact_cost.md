---
name: step-reuses-bl-b49-describe-contact-cost
description: belief.tools.describe_contact has no narrow geometry-only path -- any new caller that only wants bearing/range (e.g. BL-14's step) pays the full uncached terrain_divide_qualifier term (6.77 ms/contact, never cached) plus cold semantic_facts_for (63.25 ms/contact) per candidate, the same BL-B49 cost against a new caller
metadata:
  type: project
---

`describe_contact` (`body-layer/src/belief/tools.py`) runs the *full* enrichment pipeline
(`_add_enrichment_facts`) whenever an `EnrichmentContext` is passed, with no "just give me
bearing_deg/range_m" shortcut. `BL-B49` measured this against the real `syria-full.sqlite`:
`terrain_divide_qualifier` 6.77 ms/contact (**never cached** — ownship-relative, must be
recomputed every call per that function's own docstring), `semantic_facts_for` 63.25 ms/contact
cold (cached per contact-id/50 m cell, cheap once warm). `BL-B49` was filed against `report`/
`_report_scope`, architect-owned, three candidate mitigations named, deliberately not fixed
inline because "every candidate fix changes a shared tool."

**Why this keeps recurring and is worth checking for on any new command/feature that resolves
contact geometry**: `describe_contact` is the only general-purpose entry point for "where is this
contact relative to ownship," so anything that calls it for a *list* of contacts (not just one)
pays the uncached terrain term once per contact in the list, synchronously inside
`handle_command`'s poll-body dispatch. Found a second instance of this exact shape in BL-14's
`step` (`crew_console.py::_step_candidates`/`_handle_step`), which calls `describe_contact` once
or twice per group member on every press — group size is not tightly bounded in this codebase
(`BL-B61`'s class-level composition bucketing, `BL-B48`'s 6 km infantry cohesion bridge both argue
a believed group can be wider than a real platoon), so a `step` press against a large/loosely-
grouped formation can stall the poll loop for ~200+ ms of terrain-query cost alone, before any
cold-cache semantic hit.

**Judged MONITOR, not a required fix**, on `plans/attack-run/performance-review.md`: the
mechanism is `BL-B49`'s, not something the new caller introduces, and the common case (a few
candidates) is cheap. The right move is cross-referencing the new caller on `BL-B49`'s own entry
so the eventual Architect-owned fix is sized against every known caller, not re-discovered once
per feature.

**How to apply**: before approving a performance pass on any feature that calls `describe_contact`
(or anything that walks `get_contacts`) for more than one contact per user action, check whether
the loop is bounded and whether `BL-B49` is still open — if it is, name the new caller on that
entry rather than writing a fresh, disconnected finding each time. See [[BL-B49]] if that memory
exists elsewhere; otherwise the roadmap entry at `body-layer/ROADMAP/BL-B49.md` is the source of
truth for the measured numbers above.
