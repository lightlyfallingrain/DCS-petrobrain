---
name: three-projections-of-a-group-roster
description: body-layer holds three independent projections of a group's roster reading two different Contact fields through two different resolvers — check which one a plan means before calling any of them a flattening of the others
metadata:
  type: project
---

**Measured 2026-10-13 during the `collapse(group, depth)` plan** (`plans/group-collapse/plan.md`,
probes in that plan's `scratchpad/`). `body-layer` holds **three** projections of one group's
roster, and they do not agree:

| projection | source field | resolver | serves |
|---|---|---|---|
| `Group.composition` | `Contact.last_class_raw` | `object_model.profile_for` | `group_matches` only |
| `Group.air_defence_composition` | `Contact.last_class_raw` | the lattice (`parent_class_of`) | `group_matches` only |
| `speech._group_composition_clause` | `Contact.classification` via `describe_contact` facts | `(value, level)` groupby | one spoken line |

**Why:** `profile_for` keyword-matches DCS *type* names, so `OP_ARMORED`/`OP_SPAAG`/`OP_LRSAM`/
`OP_SRSAM`/`OP_MRSAM` all bucket to `OP_GROUPSOMETHING` — 5 of 10 real classes, and class level is
the common case at range. Separately, `last_class_raw` is the *latest percept* while
`Contact.classification` is the *folded best claim*; the lattice's `hold` rule makes them diverge on
purpose (a TYPE claim survives a coarser CLASS re-observation).

**How to apply:**

- **Before accepting "field X is a flattened/lossy projection of Y", check both the source field and
  the resolver.** The 2026-10-13 capture called `air_defence_composition` *"a symptom of the tree
  being flattened"*. It is not — it is a *memory* of a derivation, held through
  `GROUP_REIDENTIFY_WINDOW_S` (60 s) in which the members that produced it are gone from
  `ContactStore` entirely, so no derivation can reproduce it. Measured, not reasoned.
- **Anything user-facing reads `Contact.classification`, never `last_class_raw`.** That is
  `plans/classification-refinement/plan.md`'s own rule and the facts path already follows it.
- **Never route a cheap derivation through `describe_contact`.** `BL-B49` measured its enrichment
  term at 63.25 ms/contact cold against the real 738 MB store; a lattice-only walk over 52 members
  is ~44 µs, ~150× cheaper. The push path (`callouts.py`) already pays the expensive one per member
  per tick, which inverts the usual "deep is expensive" intuition — depth over `Contact` is free,
  and the shape of the *source* is what costs.
- **A derived nested dict is not canonical.** A probe's own first-draft bug proved it: insertion
  order split two rosters that were the same multiset. Sort every level deliberately, and do not
  make a tree a match key.

See also [[project_bl12_amendment_findings]], and the `dod` role's
`project_recurring_air_defence_vocabulary_resolution_gap.md` — this pass was the 5th occurrence of
that family, raised at Architect stage per that memory's own standing advice and filed as `BL-B61`.
