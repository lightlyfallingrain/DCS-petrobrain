---
name: independent-transcription-claim-needs-source-math-not-diff
description: when a plan/implementation claims a test table was "independently transcribed" (not copied from the module under test), a byte-identical diff against the module's own table is not evidence of cheating -- verify against the cited source document's own arithmetic instead
metadata:
  type: feedback
---

On BL-B90 Stage 0's re-review (`plans/effector-sequences/review-stage0.md`, 2026-10-23), the fix
pass added `_EXPECTED_HELPER_SIGNATURES` to the test file with a docstring claiming it was "a
second, independent transcription" of the recon note's Q3 table, deliberately not read from the
shipped module's own `_HELPER_SIGNATURES`. Diffing the two literals showed they are byte-identical,
same key order included -- which looks, on a skim, like exactly the "copied from the module, then
claimed independent" failure this project's "show the red" discipline exists to catch.

It was not. The recon note's own Q3 code block lists all 22 helper signatures in that same fixed
order, so two honest, separate transcriptions of the same ordered source naturally land on an
identical dict literal and order. **The diff-against-each-other check cannot distinguish "copied
from the module" from "both correctly transcribed the same external source in its own order."**
What actually distinguishes them: (1) hand-computing each entry's `crew_idx`/`n_commands` from the
recon's own positional-parameter lists (not from either Python table) and checking both literals
against that independently derived arithmetic -- all 22 checked out; (2) mutating the shipped
module's table and confirming the test literal, being a separate textual object, does not move
with it and so still fails the mutated case (already covered by the existing "mutate an untested
entry" check, `feedback_static_lookup_table_entries_need_per_entry_mutation.md`).

**Why:** a byte-diff is cheap and tempting as "proof," but it only detects textual divergence, not
provenance. The question "is this table trustworthy" has to be answered against the cited source
of truth, not against its sibling.

**How to apply:** whenever a plan/implementation claims two tables were derived independently from
a shared external source (a recon doc, a spec, a schema dump), do not stop at diffing the two
tables against each other. Recompute at least a sample of entries directly from the cited source's
own data, and rely on the mutation test (does a bug in one literal fail a test that reads the
other) rather than textual comparison to establish independence.
