# BL-B26 — Group member facts gathered three times per tick

- [ ] **BL-B26 — `CalloutScheduler.tick` gathers each group's full member facts up to three times
  per tick, whether or not anything changed.** #status/open Found by the performance pass on
  `feature/terrain-callout-stages-345` (2026-10-05); **pre-existing to that change, not caused by
  it** — it is `group-reporting` Stage 4's scheduling-loop architecture.

  For every tracked group, every 5 Hz tick, `tick()` gathers full member facts — one
  `describe_contact` call per member, and now one `divides_between` query per member as well —
  in three separate places: scoring, candidate re-render, and `group_membership_state`'s own
  re-gather. **The "nothing changed, skip" check runs *after* the gather, not before it**, so the
  work is done and then discarded on every tick where the group is unchanged, which is most of
  them.

  **UPGRADED 2026-10-05 — the estimate below is two orders of magnitude out. Scheduled as
  [[BL-11]] Stage 3.** Measured against the real 738 MB `syria-full.sqlite` at the sortie's own
  scale: `describe_position` is **median 51.6 ms, 41.4 ms even on a repeat** (CPU-bound Python,
  not cold I/O), not the ~0.3 ms the figure below assumes, and one tick was observed making **47
  calls for 1,579 ms**. Worse, `WorldEnrichmentCache` **misses by construction** for exactly the
  contacts that get spoken about: its key is exact structural equality of `Contact.last_position`,
  which a re-observed contact updates every poll — 92 % hit rate overall, but
  `distinct_positions == describe_calls == cache_misses` in *every* callout-bearing tick, and a 1 m
  nudge costs the full 42 ms. Cheapest fixes, neither touching the scheduling loop this entry
  correctly assigns to Architect: memoize `describe_position` per tick on a quantised `(x,z)`, and
  quantise the cache key. Full evidence: `body-layer/research/2026-10-05-performance-review.md`.
  World-model's own half of the cost — `nearest_feature` spending 73 % of `describe_position`
  proving that 86 theatre-wide features are not nearby — is world-model's [[WM-M11]].

  **Order of magnitude, estimated rather than measured** (no live sortie log was available to the
  pass): ~15 ms/tick for 5 groups × 10 members. That is not alarming on its own, and the terrain
  qualifier adds one cheap SQL query (0.02–0.11 ms measured) to each redundant gather rather than
  creating the redundancy. Recorded because the multiplier is what matters: any future per-member
  enrichment pays 3× for nothing.

  **Escalate to Architect, not to a one-line fix.** Hoisting the changed-check above the gather
  sounds trivial and is not — scoring needs facts to decide whether the group is worth speaking
  at all, so the three gathers are not obviously redundant from inside any one of them. This is a
  scheduling-loop design question. Related: [[BL-B23]] was the same shape of finding (cost scaling
  with something other than the threat picture) and the fix there was to filter the input, not to
  restructure the loop.

  See `plans/terrain-feature-probing/performance-rev3.md`.
