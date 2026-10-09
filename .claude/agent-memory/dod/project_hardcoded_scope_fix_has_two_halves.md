---
name: hardcoded-scope-fix-has-two-halves
description: Removing a hardcoded scope has a discovery half and a resolution half; fixing discovery makes the resolution bug appear only afterwards, so it reads as a new defect.
metadata:
  type: project
---

**A fix that widens a hardcoded scope usually touches only the discovery half, and the resolution
half's symptom then appears for the first time — looking like a new defect rather than the old
one's remainder.** 1st occurrence at DoD, `feature/doc-conventions-audio-adapter` (2026-10-09);
watch for a 2nd.

Concretely: `.claude/scripts/doc_provenance.py` hardcoded `audio-adapter/ROADMAP` in
`split_entry_dirs`/`find_entries`. Review fix RF4-9 replaced it with the mechanical
`*/pyproject.toml` discovery loop, verified by a measured 22 → 245 entry count, and was signed off.
**Line 202 of the same file kept `f"audio-adapter/research/{filename}"` as the default for a bare
`research/<file>.md` citation** — so 17 citations now resolve confidently into the wrong
subproject (`mi24p-command-surface.md` → `audio-adapter/research/` when it lives in
`aircraft-layer/research/`), and the regeneration command aborts on the first one.

**Why it hides:** before the discovery fix, the resolution default was *correct* — every citation
came from audio-adapter's own entries, so the prefix was right by construction. The literal was
load-bearing in two places for two reasons, and only one of them was visible as a bug. Verifying
the fix by its own stated metric (entry count) cannot see the other.

**How to apply at DoD:** when a required fix was "stop hardcoding X",

- `grep` the **whole module** for the literal, not the function the fix names. One line is the fix;
  two lines is a pattern someone generalised halfway.
- Then **run the thing end to end**, not just the gate that reports. Here the gate ran and reported
  126 failures; the *refresh* path — same `build_target_map`, different error handling — died on
  the first one. A verify-only gate that tolerates a class of error and a writer that aborts on it
  will disagree, and the writer is the one someone has to run.
- Where a bare basename can exist under more than one subproject, **no default prefix is
  correctable** — `2026-10-05-security-audit.md` and `2026-10-05-performance-review.md` each exist
  in two. It has to resolve relative to the citing document and reject the ambiguous case. Say so,
  or the fix will be another default.

Related: [[feedback_execute_the_unblock_condition_of_accepted_debt]] (how this one surfaced),
[[project_recurring_prose_count_of_a_code_set]] (the enumerate-don't-hardcode family this belongs
to).
