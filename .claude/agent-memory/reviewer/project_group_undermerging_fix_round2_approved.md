---
name: project_group_undermerging_fix_round2_approved
description: fix/group-undermerging round-2 re-review (0317431) outcome — APPROVED; article removal correct, undiff-member fix stands, kept "a couple of" is a real distinct idiom not a missed case
metadata:
  type: project
---

Re-review of `fix/group-undermerging`'s two fix rounds (`8c9708a`, `adb7d19`, `0317431`) against
the two Required Fixes in `plans/group-cohesion-redesign/review.md` (round 1). Verdict: APPROVED,
no new findings.

What happened: round 1 (`8c9708a`) "fixed" the indefinite-article defect by growing a vowel-initial
exception set (`"a armor"` → `"an armor"`), which is still wrong — `armor` is a mass noun and takes
no article in any form, and more decisively, every one of the user's own worked utterances
(`plans/group-cohesion-redesign/explore-notes-delta-taxonomy.md`) carries no indefinite article in
a composition clause at all, count noun or mass noun. I sent that back. Round 2 (`adb7d19`) removed
`_with_indefinite_article`/`_VOWEL_INITIAL_CLASS_WORDS` entirely rather than growing the exception
set — correct, and verified consistent with `_contact_report_text`/`_identification_lead`'s
pre-existing bare-noun convention (checked, not assumed).

**Worth remembering for next time an exception-set fix shows up**: a request to "add the missing
vowel case" can be fixing the wrong half of a two-part defect (wrong mechanism, not just an
incomplete one) — check the fix against the specification's actual phrasing, not just against
whether it stops the one reported string from looking broken. "An armor" reads as fixed on a skim.

**The one kept article, `"A couple of contacts."`**: real distinction, not a rationalization.
`_cardinality_phrase`'s `"a couple of"` is a fixed cardinality-hedge idiom (same family as `"a
handful of"`, `"several"`) quantifying a plural noun phrase, structurally different from
`_with_indefinite_article`'s removed per-noun a/an choice on a bare singular class word. Different
function, different grammatical slot, nothing in the diff touched it.

**Call-site grep paid off again** (the standing "grep for the new mechanism's own call site, not
the file list" check, from `project_precise_position_belief_hybrid_gap.md`): Finding 2's fix lives
inside `_group_composition_clause` itself, and all three call sites
(`speech.py:1356`/`:1366`/`:1632` — the air-defence leading/rest line, the main composition line,
the delta clause) route through it, confirming the implementer's "same latent bug on an untested
second code path, fixed for free" claim rather than accepting it on narration.

Worktree landed on `main`'s tip again (same failure class as `project_position_belief_runaway_*`
memories) — `git rev-parse HEAD` caught it immediately per rule 4, and since the target branch was
not checked out elsewhere, `git checkout fix/group-undermerging` inside the worktree itself fixed
it (no `git archive` snapshot needed for the final verification pass, though one was built first
for the actual review work before realizing the branch was free to check out directly).
