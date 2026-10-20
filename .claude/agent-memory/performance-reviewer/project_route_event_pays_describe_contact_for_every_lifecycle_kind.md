---
name: route-event-pays-describe-contact-for-every-lifecycle-kind
description: belief/speech.py route_event calls describe_contact (BL-B49's ~63ms/contact enrichment) unconditionally for every lifecycle event kind, even ones whose rendered text discards most of result["facts"] — not this review's finding to fix, but the next one's baseline
metadata:
  type: project
---

Found 2026-10-20 reviewing `fix/taking-fire-visible-shooter` (second half, F6 follow-up —
`plans/taking-fire-visible-shooter/performance-review.md`), not a finding against that branch.

**`belief/speech.py::route_event` (`:3274`) calls `describe_contact(store, event.contact_id,
now_sim, enrichment=enrichment)` unconditionally, before dispatching to `_render_lifecycle_text`,
for every `Event.kind` that function handles** — `CONTACT_DETECTED`, `CONTACT_FIRING_SEEN`,
`CONTACT_BURNING_SEEN`, etc. This pays the full [[project_report_query_enrichment_dominates]]/
[[project_step_reuses_bl_b49_describe_contact_cost]] cost (~63 ms/contact `semantic_facts_for` +
~6.8 ms/contact uncached `terrain_divide_qualifier`) even for branches that only use a tiny slice
of `result["facts"]` — e.g. `CONTACT_FIRING_SEEN`'s bypass-needed wording ("Something firing, X
o'clock, far.") reads only `facts["relative_now"]["clock_position"]` and discards classification,
range, semantic fragments, cardinality, terrain qualifier, motion — everything else `describe_contact`
computed.

**Why this was traced and not flagged NOW:** `CONTACT_FIRING_SEEN` (and every other lifecycle kind
routed through here) is cooldown-gated (`ContactStore._cooldown_elapsed`, `EVENT_COOLDOWN_S`), not
fired every poll per contact — so this is not a per-poll multiplier, and it predates the branch
reviewed (the taking-fire-visible-shooter diff only changed which *wording* is picked from an
already-fetched `result`, not whether `describe_contact` is called). Confirmed by reading
`route_event` directly: it is unchanged across the diff that triggered this review.

**Why it's worth recording anyway:** the next time a lifecycle-event wording is added or a
performance pass looks at `route_event`/`CalloutScheduler`, this is the shape to check for —
a dispatcher that pre-fetches the maximal result before the branch that decides how much of it is
actually used. A narrow-path `describe_contact` variant (bearing/range only, no semantic/terrain
query) for the branches that only ever speak a clock position would be the mitigation, mirroring
[[project_step_reuses_bl_b49_describe_contact_cost]]'s own "no narrow geometry-only path" framing —
but this has never been measured as a live cost (events are cooldown-gated, so volume is low) and
should not be assumed to need fixing without first counting how often the discarding branches
actually fire in a real sortie.
