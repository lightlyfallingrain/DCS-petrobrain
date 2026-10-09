---
name: recurring-prose-count-of-a-code-set
description: 6th+ occurrence of a prose enumeration/count of a set that lives in code being wrong; fix is to derive it by import at writing time, at Architect/Implementer not Reviewer.
metadata:
  type: project
---

**A count or enumeration stated in prose about a set that lives in code is wrong often enough to
treat as a category, not an incident.** On `fix/callout-observability-gate` (2026-10-06) the
breadth claim was wrong **three times across two review rounds** — "two kinds" then "three" then a
tally that was wrong twice inside one paragraph — and was only settled when round 3 derived it by
import (`len(_TEMPLATED_KINDS) == 6`, `len(_OBSERVABILITY_EXEMPT_KINDS) == 1`). Every instance was
caught by a Reviewer, never by the author.

**Why:** this repo already documents the same defect four times over in a different guise — root
`CLAUDE.md` records three subprojects named while six existed, four skills inheriting that list and
reporting PASS while never looking at half the repo, and one recurrence in the commit gate that
itself warns about it. The mechanism is identical: prose asserts the cardinality of a set that is
maintained elsewhere for an unrelated reason, so it reads as an instruction while going stale
silently. It gets *worse* when a gate discriminates on the subject rather than the kind, because
then the set that decides breadth is not at the call site at all — see
[[feedback_subject_discriminating_gate_breadth]] territory in the implementer's own memory.

**How to apply:** when a plan, debug report or roadmap entry is about to state "N of M kinds" /
"covers X, Y, Z" about something enumerable from code, derive it by import or `grep` *at the moment
of writing* and say so in the text. Raise it as a **process** signal in the DoD report when a
feature's required fixes are all of this shape: the check belongs at Architect/Implementer, and
catching it at Reviewer every time is the debt. Related but distinct:
[[project_recurring_plan_test_file_naming]] (a plan citing a wrong file) and
[[project_recurring_keyword_table_vocabulary_mismatch]] (a table under-joining a name source) are
the same family — prose about a code artifact, not checked against it.

**6th occurrence, `feature/doc-conventions-audio-adapter` (2026-10-09), and this one is about
documents rather than code — the pattern is wider than "a set in code".** Round 4 found a sentence
in `world-model/ROADMAP/world-model-roadmap.md` *corrupted into asserting the opposite of the fact
it was written to record* ("several hundred bare `WM-M5`/`WM-M7` mentions", where the measurement
is 0 `WM-M5` and ~425 bare `M5`). The round-4 **replacement** sentence then shipped its own false
negative — *"and no `WM-M5`/`WM-M7` ones"* — falsified by 14 occurrences, all inside the feature's
own plan documents, i.e. **the claim was made false by the act of writing it down.** A document
corpus is as enumerable as a code set and gets checked far less often, because a `grep` over
`plans/` does not feel like a measurement. The same branch also published two counts of its own
gate's output that were off by one (127 vs a real 126) in three separate files, by counting the
word `cited` in `awk '{print $3}'` output as a filename.

**Added to how to apply:** a prose *negative* ("no X remains", "nothing still asserts Y") is the
highest-risk form, because it is the one a reader cannot falsify by reading further — and root
`CLAUDE.md`'s own graph-vs-`grep` rule already says a trustworthy negative needs `grep`, not the
graph. Re-run the negative's own command immediately before committing the sentence that states
it, including over the file being written.
