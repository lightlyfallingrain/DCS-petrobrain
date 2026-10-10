---
name: report-query-enrichment-dominates
description: Any body-layer path that goes through tools.get_contacts pays ~63ms/contact semantic enrichment + ~6.8ms/contact uncached terrain-divide before any filter runs; measured on real syria-full.
metadata:
  type: project
---

Measured 2026-10-10 on the BL-13 crew-query-path review, against the **real**
`world-model/data/world-model/syria-full.sqlite` (738 MB), warm SQLite page cache, so these are
floors:

| term | per contact | at 52 contacts | cached? |
|---|---|---|---|
| `enrichment.semantic_facts_for` (= one `query.describe.describe_position`) | **63.25 ms** | 3,289 ms | yes — `WorldEnrichmentCache`, per contact id / 50 m cell |
| `enrichment.terrain_divide_qualifier` | **6.77 ms** (no-divide case) | 352 ms | **never**, deliberately (ownship-relative) |

Three things that follow, and that cost real time to re-derive:

- **`tools.get_contacts` enriches every contact before the caller can filter.** `_contact_facts`
  pays both terms unconditionally. So *any* filter applied in the caller's loop — the report path's
  clock/sector/relative/band/descriptor slots, for instance — makes the answer shorter and the query
  no cheaper. A narrow query is priced as the whole scene.
- **The enrichment cache is NOT warmed by the poll loop.** The only `get_contacts`/
  `describe_contact` callers in `body-layer/src/` are command handlers, the typed console, and
  `CalloutScheduler.tick`'s two per-callout calls, which enrich only the contacts about to be
  spoken. BL-11's measured 12.6 ms poll work is itself proof the poll does not enrich 50 contacts.
  So assume **cold** for the first query of a scene, not warm.
- **`CrewConsole.handle_command` runs inside the poll body** (`logger.py:1668-1672`), so a query's
  cost is a one-off stall of perception and callouts, not work on a separate thread. Under the
  sleep-after-work loop the 2026-10-05 pass documented, 352 ms of warm-cache floor already makes a
  ~1.35 s poll.

BL-13's Stage 3 made both terms' output **unread** on the report path (`render_report_summary` reads
only `classification`/`cardinality`/`relative_now`/`last_seen_ago_s`; the enumeration it replaced
read `facts["semantic"]` and `facts["terrain_qualifier"]` via `_contact_report_text`). Filed as
MONITOR + Architect escalation rather than a change request, because every fix changes a shared tool
or the position the range is computed from. See `plans/crew-query-path/performance.md`.

Related: [[enrichment-cache-axes]], [[world-model-query-layer-costs]], [[bl11-measured-outcome]],
[[synthetic-store-calibration]].
