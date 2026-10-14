# BL-B49 — A narrow `report` query is priced as `report_all`

- [ ] **BL-B49 — `_report_scope` iterates `tools.get_contacts`, which enriches *every* contact before any
  slot filter runs, so a narrow query costs what `report_all` costs — inside the poll body.** #status/open
  Found by the Performance Reviewer during [[BL-13]], 2026-10-10, verdict **APPROVED — MONITOR**;
  full measurements and three candidate mitigations in `plans/crew-query-path/performance.md`.
  **Architect-owned** — every candidate fix changes a shared tool or the position the answer's range
  is computed from, so it was deliberately not improvised onto the BL-13 branch.

  Measured per contact against the **real** `syria-full.sqlite` (738 MB), not a synthetic store:

  | term | per contact | at 52 contacts | cached? | read by BL-13's summary? |
  |---|---|---|---|---|
  | `semantic_facts_for` (one `describe_position`) | 63.25 ms | **3,289 ms** | yes, per contact id / 50 m cell | **no** |
  | `terrain_divide_qualifier` | 6.77 ms | 352 ms | **never** | **no** |
  | all of BL-13 Stages 1–3's own new code | 0.00065 ms | 0.034 ms | — | yes |

  `handle_command` runs inside the poll body (`logger.py:1668-1672`), so this is a **~3.6 s stall of
  perception and callouts on a cold cache, ~352 ms even warm**. The enrichment cache is not warmed by
  the poll loop — only command handlers and `CalloutScheduler.tick`'s per-callout calls warm it,
  which [[BL-11]]'s 12.6 ms poll figure demonstrates.

  **BL-13 did not create this cost and did not increase the number of `get_contacts` calls.**
  `report_all` paid exactly the same before, and the enumeration BL-13 replaced did strictly *more*
  post-enrichment work (group resolution plus per-group full disclosure). What changed is that the
  work is now **discarded**: Stage 3's summary reads only `classification`, `cardinality`,
  `relative_now` and `last_seen_ago_s`, while the enumeration read `facts["semantic"]` and
  `facts["terrain_qualifier"]` via `_contact_report_text`. All four report token families now route
  to the summary, so every report command pays for enrichment it never speaks.

  **Why that makes it newly worth filing rather than newly broken.** The slot filters run *after*
  enrichment, so `report armor two o'clock near` is priced as `report_all` — and BL-13's whole
  product argument is that short answers invite *frequent, narrow* questions. The feature is
  designed to increase the rate of exactly the query whose cost this entry describes. A pilot asking
  three narrow questions in a hover would stall perception for ~1 s each time on a warm cache.

  Three mitigations are written up in `performance.md` with their obstacles: an enrichment opt-out on
  `get_contacts`, filtering before enriching, and caching the currently-uncached
  `terrain_divide_qualifier` term. Picking between them is the Architect pass this entry is asking
  for; the shared-tool blast radius is why it is not a one-line change.

  Not related to [[BL-B48]]: closing the `belief.groups` cohesion defect will not change this path's
  cost either way, because BL-13's summary never walks a group roster.

  **Second confirmed caller: `[[BL-14]]`'s `step`, found by the Performance Reviewer during BL-14's
  whole-feature pass, 2026-10-14 (verdict APPROVED — MONITOR,
  `plans/attack-run/performance-review.md`).** `_step_candidates`/`_handle_step` call
  `describe_contact` once for the current target and once per "other" candidate on every press,
  paying the same uncached `terrain_divide_qualifier` term (6.77 ms/contact) unconditionally — up
  to `2G+1` calls for a group of size `G`. Illustratively (not reproduced against a live sortie):
  a 15–20 member group costs ~210–280 ms of terrain-query time alone per `step` press, a
  synchronous stall of the same kind this entry already describes, through the same shared
  function, with a new caller. Not a `BL-14` defect — `step` is correctly recomputed from
  ownship's present position on every press by user direction, and the expensive part is this
  entry's mechanism, not that one. **Whichever mitigation is picked here should be sized against
  both callers** — `report`'s narrow-query path and `step`'s per-press ordering — not resolved
  against one and rediscovered against the other.
