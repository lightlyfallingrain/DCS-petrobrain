---
name: project-recurring-grouped-helper-branch-undertested
description: generate_effector_registry.py's helper-grouped value/signature logic has now missed per-entry test coverage twice in the same file -- a process signal, not just a code defect
metadata:
  type: project
---

`feature/switch-reference-values` (BL-B90), DoD pass 2026-10-23, tip `59aebd7e`. Reviewer's
required fix in `review-switch-values.md` was a mutation-coverage gap in
`_value_range_for_helper`'s grouped `if helper in (...)` branches (`default_blue_cover` removable
with the full 84-test suite staying green) — the **same defect class** this file's own
`_HELPER_SIGNATURES` table had already been caught on once before, at Stage 0b
(`[[feedback-static-lookup-table-entries-need-per-entry-mutation]]`, reviewer memory).

**Why this is a process signal, not just "reviewer caught it again, good."** The reviewer memory
from Stage 0b already names the exact shape — "a hand-maintained table/grouped-branch structure
needs per-entry mutation, not a by-eye check" — and recommends checking it on any future touch to
this generator. It recurred anyway on the very next addition (`values`/`helper_args`) to the same
file, within the same milestone. That means either the memory wasn't consulted when the new
grouped branches were written, or a memory written at Reviewer is reachable only by the next
Reviewer pass, not by whoever writes the code the first time.

**How to apply:** for `generate_effector_registry.py` specifically (and any future generator with
the same "helper name groups into a shared value/signature rule" shape), the Architect/Implementer
step — not just Reviewer — should require one assertion per grouped entry whenever a new grouped
`if helper in (...)` branch is added, before handoff. If this recurs a third time anywhere in this
codebase, it is worth a project-wide check (e.g. a lint rule or `/invariant-check` addition) rather
than relying on Reviewer's mutation pass to keep catching it per-touch.
