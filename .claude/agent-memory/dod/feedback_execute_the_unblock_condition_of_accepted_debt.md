---
name: execute-the-unblock-condition-of-accepted-debt
description: When accepting a documented departure/debt at DoD, run the command its unblock condition names and paste the output — the reasoning gets scrutinised, the remedy does not.
metadata:
  type: feedback
---

**When a DoD gate accepts a deliberate departure or documented debt, execute the unblock condition
it names before accepting it.** Not read it, not judge it plausible — run it.

**Why:** on `feature/doc-conventions-audio-adapter` (2026-10-09) an implementer declined review fix
RF4-2 for one of three gates, and the departure was *exemplary* — argued at the wiring site in 18
lines, with a reproducible counterfactual measurement, the cry-wolf precedent named, and an
explicit exit: *"Condition for adding it to this list: once the 127 blocks have been regenerated
and reviewed (one command, `.claude/scripts/doc-provenance-refresh.sh`)."* The dispatching
orchestrator had independently verified the reasoning and agreed. **The named command aborts `rc=1`
on its first validated citation and writes nothing**, because the same file's path resolution kept
the hardcode its discovery half had just lost. So the condition could never have been satisfied as
written, and the debt was recorded as temporary while being permanent — the exact failure class
this repo calls a standing exemption with no lapse condition.

The asymmetry is the lesson: **the argument for a departure gets read as an argument and attracts
scrutiny; the one-line remedy attached to it reads as housekeeping and attracts none.** Reviewer,
implementer and orchestrator all read that sentence. Nobody ran it. It cost one command.

**How to apply:** at DoD, for any FAIL being accepted rather than fixed —

1. Run the command the unblock condition names, in dry-run mode if it has one, and paste the real
   output into `dod-check.md`. A `plan`-style listing mode is *not* the dry run; find the one that
   shares the write path (here `check`, not `plan` — I got that wrong first).
2. If it does not work, that is a required follow-up with a named id, reported as such — not a
   reason to refuse the merge, when the gate is unwired and nothing behaves differently today.
3. Check the figure in the condition against the gate's own output, split by failure class. Here
   166 FAIL lines were 126 stale-block + 40 missing-document, two different causes with different
   fixes, published as one number.

Related: [[project_recurring_prose_count_of_a_code_set]] (the published figures were also off by
one), [[feedback_verify_roadmap_prose_claims]] (same instinct, applied to prose rather than to a
command).
