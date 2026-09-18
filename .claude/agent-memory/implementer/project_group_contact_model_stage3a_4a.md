---
name: group-contact-model-stage3a-4a
description: Implementation notes for group-contact-model Stages 3a (same-source/same-poll exclusion) and 4a (cardinality surfaced in facts/console)
metadata:
  type: project
---

Stages 3a/4a landed 2026-09-18 on `feature/group-contact-cardinality`, commits `17e398f`
(3a) and `d7e6e4a` (4a), doc commit `54ab108`. Full detail in
`plans/group-contact-model/implementation.md`'s "Stage 3a / Stage 4a" section — this is the
condensed version.

**3a mechanism**: `ContactStore.ingest` (`body-layer/src/belief/contacts.py`) gained a
read-only pre-scan before its existing single-pass loop — memoize `_resolve_continuity` per
observation (`continuity_by_observation_id`), record every continuity-resolved contact under
`claimed[(percept.source, percept.t_sim)]`. Gate branch filters candidates by
`not in claimed[claim_key]` *before* counting; whichever contact an observation lands on
(continuity/gate/founded) gets added to `claimed[claim_key]` before the next observation in the
batch. `association_over_time.py`'s gate radius formulas untouched — verified via
`git diff --stat` per-commit, not just eyeballed.

**Splitting a plan-mandated doc file across two commits**: when one CLAUDE.md edit documents
two stages going into two separate commits, `git diff` on the file, split by `@@` hunk markers
with `awk`, re-prepend the 4-line diff header to each hunk, then `git apply --cached
hunk_N.diff` per commit. Works cleanly when each stage's doc edit lands as its own contiguous
hunk (true here — different paragraphs, no interleaving).

**Mock-flight fixture re-derivation is mandatory, not optional**, per
[[feedback_verify_rebuild_row_counts]]'s spirit — ran the actual fixture via a throwaway
python script (not `pytest`, to print full JSON) to get real contact/cardinality numbers before
writing test assertions or the implementation log. Confirmed: 2 contacts, `CONTACT_1` (truck)
hedges to cardinality (1,2) under the 30s lockout (poll 14 disjoint from held (2,2)), `CONTACT_2`
(infantry) founds fresh with (1,1). Lockout duration vs. fixture length needed explicit
verification — the plan's own design section flagged this rather than asserting it.

**4a "absent-when-unknown" for cardinality**: resolved as `cardinality.lo == UNKNOWN.lo and
cardinality.hi == UNKNOWN.hi` (i.e. the literal (0, inf) root interval from
`belief/cardinality.py`), not a confidence threshold — every `Contact` is seeded with a real
claim at founding so this is reachable only via a contradiction hull spanning everything.
`facts["cardinality"]` is `{lo, hi, confidence}`, no `bucket_name` (a folded interval need not
match any one named `CountBucket`).
