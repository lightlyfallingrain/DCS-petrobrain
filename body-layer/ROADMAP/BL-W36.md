# BL-W36 — Group reporting — the disclosure ladder

- [x] **Group reporting: `belief.groups.Group`, the disclosure ladder. Stages 1-4, reviewed,
  security-approved (deep analysis), performance-approved (MONITOR), and DoD-passed 2026-09-29
  pending the sortie's own acceptance verdict.** #status/done #needs-flight `plans/group-reporting/plan.md`, from the
  2026-09-28 sortie's
  log analysis (`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`) — the noise was
  contact *count*, not per-contact chattiness (only 3 of 52 contacts ever plural), which an
  associative `Group` fixes and a per-contact disclosure gate alone cannot. **Stage 1** — `belief.
  callouts.CalloutScheduler` suppresses a scheduled `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  candidate whose rendered text repeats the last one actually spoken for that contact. **Stage 2**
  — `belief/groups.py`'s `Group`/`GroupStore`: relative-gap cohesion (`GROUP_PROXIMITY_GAP_RATIO`
  = 3.0, `GROUP_REPORTING_MIN_MEMBERS` = 2 — lowered from 3 by user direction 2026-09-28,
  deliberately renamed off `perception.group_salience.GROUP_MIN_MEMBERS`'s name so the two floors
  can no longer collide), union-find over fused `Contact.position`, majority-overlap split/merge
  reconciliation once per `ContactStore.tick()` call. Inspectable via `belief.tools`'s new
  absent-not-null `"group"` fact and `console.py`'s `show <id>`. **Stage 3** — `belief.speech.
  render_group_disclosure`, the disclosure ladder (bare `"Group."` while undifferentiated, a
  per-class composition clause once refined, `"Danger, <type>."` leading when a member resolves a
  real `belief.threat.envelope_for` envelope) — since Stage 4, extended with a two-member "pair"
  rung (`"A couple of contacts."` vague, `"Pair of T-72."` exact, tracking classification
  specificity the same way `_cardinality_phrase` already does within one contact). Named `render_
  group_disclosure`, not `render_group_report` — that name belongs to `belief.callouts`' separate,
  still-live report-space aggregation for contacts with no group. **Stage 4** — wired into both
  live speech paths: `CalloutScheduler.tick` reads `store.groups` alongside `store.
  unacknowledged_events` into one shared priority sort (`group_priority` mirrors `callout_
  priority`'s tuple shape), filtering a grouped contact's own `CONTACT_DETECTED`/`CONTACT_
  REACQUIRED` before scoring; `CrewConsole._handle_report` resolves and speaks each in-scope
  group the same way, so a pushed callout and a pulled "report" describe one group identically.
  `belief.callouts.group_candidates` (the event-level, report-space bucketer Stage 4 replaces) is
  deleted. **Stage 5** (common-fate cohesion) remains deferred, gated on a sortie's evidence.
  **A real discovery worth a decision before the next sortie**: at floor 2, `belief.groups`'
  relative-gap cohesion — working exactly as designed (no absolute radius, only a relative one) —
  means any two contacts alone in an otherwise-empty scene always cohere into a "pair," however far
  apart; combined with `_handle_report` speaking a whole group from one in-scope trigger member,
  this can pull a contact from *outside* a requested clock/sector into the answer. Confirmed
  directly (two contacts 500 km apart, nothing else tracked, still form one `Group`), not
  theorised — see `plans/group-reporting/implementation.md`'s Stage 4 "Notable Discoveries" for the
  full readout and the test fixtures it forced to route around it.

  **The n=2 tautology above was fixed on this branch first** (`9ecedaf`/`b0f9518`, user direction
  2026-09-29) with a flat 300 m backstop gated to `< 3` tracked contacts, then **superseded by a
  second mechanism the same day** (`9ecedaf`.. through `718a65a`/`d04412b`) once review flagged two
  problems with the flat figure: it had no notion of what the units meant (300 m is a different
  fraction of a vehicle for infantry vs. an S-300 component), and gating it to n<3 left the
  relative-only rule genuinely unbounded at n>=3 — confirmed against this branch's own
  `test_2c_transcript_fixture_renders_four_lines_not_seven`/`test_report_all_groups_and_
  truncates_multiple_contacts`, both of which had needed a `store._groups._groups = {}`
  workaround precisely because their own fixtures legitimately merged at n>=3.

  **`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS = 20.0` now closes both the n=2 and the n>=3 case**,
  applied to *every* pair at *every* tracked-contact count (not gated by n): a per-pair bound in
  unit widths of the pair's own mean believed physical size (`perception.object_model.size_m`, via
  each contact's `last_class_raw`), so two contacts 500 km apart no longer cohere (n=2, the
  original discovery) and neither do three-plus contacts kilometres apart with little else tracked
  (n>=3, review's finding). The relative-gap rule stays primary and can still be tighter in a dense
  scene; the unit-width bound only ever narrows it, never widens it. Confirmed by tests, not
  theorised (`GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M`/its n<3 gate are deleted; `test_sparse_desert_
  group_can_span_a_wide_gap` recalibrated to a 220 m span, still under the ~120-140 m backstop for
  the vehicles it uses; `test_2c_transcript_fixture_renders_four_lines_not_seven` re-verified
  against real per-tick output — the five-object n>=3 fixture no longer merges into one composite
  group across types).

  **The two attribution consequences the n>=3 risk raised (nearest-member clock/range vs.
  threat-led line; `_handle_report` speaking a whole group past a sector filter) are not separately
  fixed, but their blast radius is now bounded to ~140 m (a 20-unit-width vehicle pair) rather than
  unbounded kilometres** — a sparse merge can no longer put a named threat "somewhere else
  entirely" the way the original 500 km/kilometres-apart discovery could. Security's deep analysis
  (`plans/group-reporting/security-review.md`) independently re-traced this closure through the
  code rather than taking the plan's word for it. Stage 5 (common-fate cohesion) remains the
  intended real fix for cohesion generally and stays deliberately deferred pending this sortie's
  evidence — the unit-width backstop is a stated assumption (20.0, not a measurement), not a
  substitute for Stage 5.

  1349 passed/4 xfailed, `ruff`/`mypy --strict` clean. **Milestone completion question**: does this
  change what's next? Yes, in the direction Stage 5 should take — the sortie flying tonight is the
  first real evidence on whether 20 unit-widths groups the right things (see
  `docs/acceptance/2026-09-29-group-reporting-sortie.md`), and Stage 5's design should be built
  from what that flight actually shows about cohesion misses/false-merges, not from more code
  reading in advance of it.

