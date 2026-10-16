---
name: speech-aggregation-cost-boundary
description: Any new speech-time aggregation over many contacts must derive from raw Contact objects, never describe_contact facts (63.25ms/contact) — and group_candidates no longer exists, so the push path has no report-space bucketer at all
metadata:
  type: project
---

From the `plans/contacts-callout/plan.md` pass, 2026-10-16. Three things that cost real reading to
establish and that the next aggregation design will need.

**Any speech-time view over *many* contacts must read raw `Contact` objects, not `describe_contact`
facts.**
**Why:** `describe_contact` routes through `WorldEnrichmentCache.get_or_compute` at a measured
**63.25 ms cold / 6.77 ms warm per contact**, cache-missing by construction for a re-observed
contact ([[group-collapse-perf]]). At the real n=52 ungrouped contacts that is ~350 ms per poll
against BL-11's 12.6 ms budget. `group_view.py` already observes this boundary and its own
performance review says that boundary *is* the entire reason group collapse is cheap.
**How to apply:** derive from `Contact.last_position`/`.classification`/`.cardinality` plus
`enrichment.relative_geometry(ownship, pos)`, which is pure arithmetic. Two facts that make this
safe and were verified by reading, not assumed: `perception.geometry.bearing_deg` reads only x/z, so
**the clock hour is bit-identical** to what `describe_contact` would give; `range_m` includes alt,
so the terrain-corrected altitude shifts range by <3 m at 2–6 km, far under `_format_range_km`'s
500 m rounding. A facts-based version of such a view is not slower, it is unshippable.

**`belief.callouts.group_candidates` does not exist** — retired by `plans/group-reporting/plan.md`
Stage 4. Documents and briefs still describe it as live and "almost never firing".
**Why:** it is named in ~10 surviving docstrings, all of them historical. `grep -rn "def
group_candidates"` returns nothing.
**How to apply:** the push path (`CalloutScheduler.tick`) has **no report-space aggregation at
all** — every ungrouped contact speaks its own `CONTACT_DETECTED`. The survivors `group_facts` +
`_chain_by_clock` + `render_group_report` are reachable only from `CrewConsole._handle_report`, the
pull path. Do not plan "widen the existing bucketer"; there is nothing on the push side to widen.

**An event-pool-based aggregation cannot work on this project's measured detection rate, and this
is the fact that kills the obvious design.**
**Why:** `plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md` measured 4.8–5.4
detections/min — one every ~11 s — against `CALLOUT_MAX_AGE_S` of 10 s. So the unacknowledged-event
pool almost never holds two detections at once. That, not the bucket key, is why the old aggregation
never fired; the `(unit word, range word)` key was the *second* reason.
**How to apply:** derive the aggregate from the **store**, with a live event acting only as the
trigger. Any design that buckets the event pool will look correct in tests (where fixtures found
contacts in one poll) and aggregate nothing in flight.

**One register inconsistency to know about before writing a hedged line:** `_cardinality_phrase`
returns the bare stems `"couple"`/`"handful"` (radio brevity, user 2026-09-23, articles cost
speaking time), while `render_group_disclosure`'s undifferentiated-pair branch hardcodes
`"A couple of ..."` (`speech.py:2642`). Two spellings of one hedge. The 2026-10-16 direction
document's own mock transcript was built from the hardcoded one, which is why that plan has to ask
the user which register applies rather than reading it off the shipped code.

Related: [[callout-scheduling-design]] — its "two distinct groupings, unifying them is a known trap"
rule is what says a contacts-set view must group in *report* space (clock bucket, rounded range
word, belief facts only), never via `perception.clustering`.
