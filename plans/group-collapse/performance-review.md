### Performance Review

Feature: `collapse(group, depth)`, Stages 1-4. Branch `feature/group-collapse` @
`ed50840a2b43ef117773f4624951eb9a0c6c960b`. Budget context: BL-11's poll loop measures ~12.6 ms/poll;
this phase carries no hard real-time budget (root CLAUDE.md), so the bar is "does not meaningfully
erode that headroom," not a hard deadline.

### What was re-measured, and how

Ran the architect's own probes unmodified (`plans/group-collapse/scratchpad/probe_collapse_cost.py`,
`probe_collapse_scaling.py`) plus a new adversarial probe,
`plans/group-collapse/scratchpad/perf_review_adversarial_scaling.py`, which:
- asserts the harness can fail before quoting any number (an empty-collapse sanity check, plus a
  deliberately-false assertion inside a `try/except` to prove `assert` actually distinguishes a
  true result from a false one here — this project's own standing lesson on benchmarks that cannot
  fail);
- drives member counts far past any realistic group (6 -> 4000, the plan's own ceiling is ~52
  contacts across a *whole scene*, not one group) at the worst-case shape for the single-pass
  bucket-then-recurse code: many distinct `TYPE`-level values spread across all five air-defence
  sub-classes, forcing `_type_children`'s dict-build on every bucket at `CollapseDepth.CONTACT`,
  the deepest and most work-per-member rung;
- re-prices the "10 groups x 6 members" push-path shape the plan quotes, with a *mixed* realistic
  roster (some TYPE, some CLASS, some presence-level, air-defence and non-air-defence) rather than
  the plan's own uniform-armor sanity sample.

All runs used `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python3` with
`PYTHONPATH=src:../world-model/src`, cwd inside this worktree's `body-layer/`. Confirmed
`belief.group_view.__file__` resolves to this worktree's own `src/` before trusting any number.

### Findings

#### `collapse_members` is linear in members, confirmed at 77x the plan's own ceiling
- **Location:** `belief/group_view.py`, `_class_children`/`_subclass_children`/`_type_children`.
- **Measurement:** worst-case roster (many TYPE values per air-defence sub-class), `CollapseDepth.CONTACT`:
  per-member cost *falls* from 6.24 us (n=52) to 2.45 us (n=4000) as n grows 77x — the opposite of
  quadratic, consistent with one-pass bucketing plus a bounded number of buckets (5 sub-classes cap).
  `collapse_members([], ...)` returns a zero-contact `GROUP` node, confirming the harness distinguishes
  real from broken output. Single-pass shape confirmed by the architect's own
  `probe_collapse_scaling.py` re-run: naive nested re-filter costs 2.57x-4.26x a single pass and the
  shipped code is the single-pass form (read in `_class_children`/`_subclass_children` — one bucketing
  pass per depth level, never a re-filter of an already-built bucket).
- **Risk:** none at any plausible scale. A degenerate, maximally class-diverse group of 4000 members
  (which cannot occur — `GroupStore` cohesion/reconcile bounds real group size far below this) still
  costs under 10 ms *total* for 4000 members at the deepest, most expensive depth; a realistic 6-52
  member group costs single-digit to low-double-digit microseconds.
- **Action:** NONE.

#### Decision 3's `describe_contact` prohibition holds in the shipped code
- **Location:** `belief/group_view.py` (whole module).
- **Check:** `grep -n "describe_contact\|enrichment\|WorldEnrichmentCache\|semantic_facts_for\|terrain_divide" src/belief/group_view.py` — the only hits are in the module's own docstring, explaining *why* it avoids that path, not a call. No import of `belief.tools`, `belief.enrichment`, or any world-model query package. Independently confirmed by reading every line, not just the grep: `collapse`/`collapse_members` touch only `Contact.classification`, `Contact.cardinality`, `Contact.position`/`.id`, and `belief.decay.classification_confidence_at` (the one explicitly-sanctioned confidence read, `CONTACT`-depth only).
- **If this had been wrong:** `BL-B49`'s 63.25 ms/contact cold figure would apply per member, and a
  full-depth collapse over even 6 members would cost ~380 ms — multiple polls' worth of budget in one
  call. The 150x cost advantage the plan claims is real only because this boundary holds.
- **Action:** NONE (verified, not just inherited).

#### Stage 3's `_group_composition_clause` calls `collapse_members` exactly once per invocation
- **Location:** `belief/speech.py:1981` (`_group_composition_clause`), and both its call sites
  (`_render_full_group_composition:2343,2353`, `_render_member_delta_clause:2481`).
- **Check:** read every branch of `render_group_disclosure`/`render_group_full_disclosure`. Each of
  the five taxonomy branches (never-spoken-full, never-spoken-delta, leader-changed, first-
  differentiation, later-arrival-delta) renders through exactly one of
  `_render_full_group_composition`/`_render_member_delta_clause`, and each of those calls
  `_group_composition_clause` (hence `collapse_members`) exactly once. No loop wraps a `collapse_members`
  call; no branch calls it twice for the same roster (e.g. once to compute `content_signature` and
  again to render text — both are derived from the same single `text` value).
- **Action:** NONE.

#### Redundant `collapse(SUBCLASS)` across a group's own members in one poll — real, but dwarfed
- **Location:** `belief/tools.py:_group_facts` (called from `_contact_facts`, called from
  `describe_contact`), reached from `belief/speech.py:_group_member_facts` (one `describe_contact`
  call per group member, pre-existing) and `belief/callouts.py:1132` (one `describe_contact` call
  per live *event*, which can itself be a member of the same group).
- **Risk:** when several members of the same group each have a live event or are each independently
  described in one poll, `collapse(store, group, CollapseDepth.SUBCLASS, now_sim)` recomputes the
  *same* tree once per member instead of once per group — a genuine "redundant query" in this review's
  terms. Measured cost of one such recomputation for a realistic 6-member group at `SUBCLASS` depth:
  ~12-70 us depending on classification mix (see the adversarial probe's "realistic mixed members"
  table). Even a fully pathological case — every one of 6 members independently triggering its own
  `describe_contact` call in the same poll — adds on the order of several hundred microseconds at
  worst, against a 12.6 ms budget (<1%).
- **Why NOW is not warranted:** this redundancy existed in shape before this feature — `_group_member_facts`
  already called `describe_contact` once per member, paying the *far* larger `BL-B49` enrichment term
  (63.25 ms cold, 6.77 ms warm) redundantly per member long before `collapse` existed. `collapse` adds
  a second, much cheaper redundant computation riding the same existing call pattern; fixing it in
  isolation (e.g. caching the collapse result per group per poll) would not move the needle on total
  poll cost and would add a cache-invalidation surface for no measured benefit.
- **Action:** MONITOR. If a future change makes `collapse` itself route through anything enrichment-shaped
  (which Decision 3 currently forbids), or if a caller starts invoking it at `CollapseDepth.CONTACT`
  from a hot per-event path rather than `SUBCLASS`/`TYPE`, this redundancy stops being free and should
  be revisited together with the pre-existing `describe_contact`-per-member redundancy it rides along
  with — not patched alone.

#### The plan's own "~5 us/tick shallow" push-path figure does not match the Stage 2 caller's actual depth
- **Location:** `plans/group-collapse/plan.md`, the "Measured answers" section's push-path sentence,
  vs. `belief/tools.py:328` (`collapse(store, group, CollapseDepth.SUBCLASS, now_sim)` — the real
  Stage 2 caller depth).
- **Finding:** the plan's per-member-count table gives, for 6 members: depth 0 (`GROUP`) = 0.45 us,
  depth 2 (`SUBCLASS`) = 5.2 us, depth 4 (`CONTACT`) = 7.8 us. The push-path sentence computes
  "~5 us/tick shallow" (10 x 0.45 us -> depth **0**) and "~78 us/tick at full depth" (10 x 7.8 us ->
  depth 4), but the actual shipped caller at this cost point (`_group_facts`, Stage 2) requests
  `CollapseDepth.SUBCLASS` (depth 2), not `GROUP` (depth 0) — so the real per-tick shallow figure from
  the plan's own table is ~52 us (10 x 5.2 us), not ~5 us. Re-measured directly with a realistic mixed
  roster (not the plan's uniform-armor sample): 10 groups x 6 members at `SUBCLASS` costs ~235 us/tick
  (1.86% of the 12.6 ms budget); at `CONTACT` (Stage 3's speech-path depth is `TYPE`, one rung
  shallower, not measured separately here but bounded above by the `CONTACT` figure) ~415 us/tick
  (3.3%).
- **Risk:** the plan's headline percentage (0.04%/0.6%) is roughly 47x/5x understated against what
  the shipped depths and a realistic mixed roster actually cost. The absolute numbers remain trivial
  (well under 1% to ~3% of a budget this phase does not even enforce as hard real-time), so this is a
  documentation/arithmetic discrepancy in the plan, not a performance defect in the code.
- **Action:** MONITOR / note for the record. No code change requested — the conclusion ("depth is not
  what costs anything here") still holds at the correct, higher figure. Worth correcting in the plan
  or implementation notes so a future reader does not cite the understated 0.04%/0.6% figures as the
  measured cost of the depth actually shipped.

#### Stage 2/3's caller-side FOV/mask gate (`callout_observable`, "any member" not "all") is itself free
- **Location:** `belief/tools.py:322-326`, `belief/callouts.py:1155-1160` — both read
  `ContactStore.callout_observable`, a single `now_sim - contact.last_observable_sim < CALLOUT_OBSERVABILITY_GRACE_S`
  comparison against bookkeeping already stamped once per `ContactStore.tick`, per Decision 6a's own
  docstring ("a read of bookkeeping, not a second mask computation").
- **Assessment:** this gate's own cost is O(members) field reads, independent of whether it prunes
  0% or 100% of `collapse` calls in a given scene — and `collapse` itself is cheap enough (above)
  that the gate's pruning *rate* has no measurable effect on poll cost either way. The plan calls this
  a "cost mechanism," but at `collapse`'s actual price the mechanism's value is correctness (matching
  the no-omniscience boundary, Decision 6) rather than a load-bearing performance saving — there was
  never enough cost on the line for pruning rate to matter. Not re-measuring prune rate in a simulated
  scene, because the number would not change the verdict either way.
- **Action:** NONE. Observation only — this is the plan's one "mechanism" framing that performance
  review disagrees with rhetorically, not technically: the gate is correct and essentially free, just
  not for the reason "it saves cost" implies.

### Verification run

From inside `body-layer/` (worktree has no `.venv`; borrowed
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/*` by absolute path with cwd kept in the
worktree — confirmed `belief.group_view.__file__` resolves to the worktree's own `src/` before
trusting any result):

```
ruff check src tests   -> All checks passed!
mypy src                -> Success: no issues found in 57 source files
pytest                  -> 1748 passed, 4 xfailed
```

Matches the plan's own stated baseline exactly.

### Verdict

**APPROVED — MONITOR.**

Nothing here rises to a required change. The two MONITOR items (the per-member redundant `collapse`
recomputation riding the pre-existing per-member `describe_contact` redundancy, and the plan's own
understated push-path percentage) are both real but both bounded well under 5% of a budget this
phase does not enforce as hard real-time. Neither is worth a code change on its own; both are worth
remembering if a later stage (attention tiers, a `CollapseDepth.CONTACT` push-path caller, or any
change that routes `collapse` through enrichment) changes the cost base they ride on top of.

### For a future sortie, not a bench

A bench cannot show whether real scenes actually produce groups with 5+ simultaneously-live events
in one poll (the scenario the redundant-recompute finding depends on for its cost to be anything
other than theoretical) — that needs `sortie-log-triage` over a real `dcs-belief-truth`/
`dcs-detection-trace` pair once this is flown, to see how often multiple members of one group each
mint their own event in the same poll.
