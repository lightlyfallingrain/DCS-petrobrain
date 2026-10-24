---
name: feedback-list-shape-output-schema-hides-dedup-bugs
description: when a generator's output schema moves from scalar fields to parallel lists (cmds/args/arg_values), any upstream dedup of one list silently mismatches the others' arity -- check for it specifically
metadata:
  type: feedback
---

Found on BL-B90 Stage 0b's second pass (`body-layer/tools/generate_effector_registry.py`,
`plans/effector-sequences/plan.md`): the raw-table-literal parser resolved `action = {X, X}` (two
*identical* command refs, e.g. `STICK-PTT-PTR`'s LMB/RMB both mapping to the same DCS command) via
a helper that deduplicated refs before resolving them. `arg`/`arg_value` were parsed as plain
ordered lists (no dedup), so the two lists ended up different lengths -- `cmds=[id]` against
`args=[738, 738]`/`arg_values=[1.0, 0.5]`. This was invisible under the old scalar schema (`cmd` was
just "the first one"); it only became a correctness bug once the output schema moved to parallel
lists meant to be read by position/index.

**Why:** a dedup helper written for a single-value era (`_distinct_dotted_refs`, dropping repeats)
kept getting reused once the schema generalised to lists, because it still type-checked and still
passed every existing test (none of which checked cross-list arity).

**How to apply:** whenever a change makes several output fields parallel lists meant to line up by
index, specifically check every upstream helper that built one of those lists for a dedup/distinct
step, and add a test asserting the lists are the same length (or an explicit correspondence) for
the case that motivated the list shape in the first place -- not just that each list is individually
correct. A per-field unit test can pass while the real correctness property (index i of list A
corresponds to index i of list B) is silently broken.
