---
name: doc-conventions-split-consumer-half-fixes
description: NEEDS REVISION on feature/doc-conventions-audio-adapter — a staged doc split updated roughly half of each consumer pair; plus the shingle method for verifying content fidelity across a file split.
metadata:
  type: project
---

Round-4 review of `feature/doc-conventions-audio-adapter` (`6c0325b`), 2026-10-09: the
roadmap/backlog split into 253 per-entry files + the always-loaded compaction.

## The defect pattern: a staged migration updates one half of every pair

Not scattered bugs — **one recurring shape**, worth checking for directly on any staged migration:

| pair | updated | missed |
|---|---|---|
| `CLAUDE.md` backlog-ID table, 5 rows | `AA-B` (Stage 1) | the other four |
| Session Start step 1 / step 2 | `CLAUDE.md` step 2; `session-start.sh` step 1 | `CLAUDE.md` step 1; `session-start.sh` step 2 |
| `status-page/SKILL.md` 3 source rows | the subsystem-card row | the counters and the forward map |
| `WM-M<n>` rename | world-model's own docs | every inbound cross-subproject reference |
| `doc_provenance.py` discovery | Stage 1's `audio-adapter/ROADMAP` | the other six directories |

**So: when a plan converts N things in stages, enumerate the consumer's own sub-parts and check each,
not the consumer.** A file in the "fixed" list can be half fixed. Stage 1 fixing one row is what
makes the remaining four read as deliberate.

**The severity test that ranked these: does the consumer READ or WRITE?** A reading consumer is
rescued by the pointer file's own self-describing prose. A writing consumer never reads it — it
appends. So `merge/SKILL.md` writing a done-entry into a 4-line pointer (real entry stays open,
`push-roadmap-gate.sh` satisfied because *a* `ROADMAP.md` was touched, every gate green) outranks
six role files carrying a stale source-of-truth claim.

**The worst finding was an invariant violation, found by executing a documented rule by hand.**
`CLAUDE.md`'s minting rule is "read the highest existing one in its file". Four rows named pointer
files, so the rule yields `WM-B1` (16 existing), `X-B30` (5), `BL-B43` (4), `AC-B4` (2) — against
never-reuse, which the file itself calls "worse than no ID". **Run a document's own procedure rather
than reading it.**

## Verifying content fidelity across a file split — the method, and the artifact signature

8,224 deleted lines, and every implementer check was written by the converter. Independent method:

1. **Word shingles, not lines.** Normalise to a word stream (markdown stripped, inline tags dropped,
   `[[X]]` → `X`), index every 8-word shingle of the new corpus, report old shingles absent.
   Line-level comparison is useless here — re-wrapping produced 107 false "unaccounted" lines.
2. **Second pass over the whole tree**, because per-directory is blind to content folded *across*
   destinations (a body-layer debt entry into audio-adapter's entry; a preamble into an index).
3. **The boundary artifact has an arithmetic signature: runs of exactly 2×(N−1) words.** 280 of 294
   missing runs were exactly 14 at N=8 — a shingle window straddling a former entry boundary. Filter
   by run length and the real candidates fall out; here 25 remained, all accounted for.
4. **Verify a deliberate folding by its FACTS, not its shape.** The 242-word SPU-8 run was supposed
   to fold into another subproject's entry; the check was grepping for `arg 377` and both constant
   names, not for the paragraph.
5. **The sanctioned-transformation list handed to me was incomplete** — a concurrent ID rename was a
   fourth, worth 44 spurious hits in one source. Derive the transformation set from the diff.

## Gate discovery: plant per directory, restore by shasum

Seven split directories. Proven by planting a violation in **each** and confirming the gate names it
— a green run proves nothing, and this branch's own history had the silent-skip twice. Untracked
plant files touch no tracked content; the one tracked mutation was restored and `shasum`-verified.
All 21 fired. Separately: three new gates were wired to **nothing** while `DOC_CONVENTIONS.md` said
they "run before committing" — `grep` the hook config, never trust the doc's claim of enforcement.

## Relayed claims need re-verification, and one was wrong

A subagent's ID-collision finding was right in conclusion and wrong in mechanism (`X-B1`, not
`X-B30`) because the pointer bodies quote an example ID in prose. **Re-run a relayed claim before
signing it** — see also [[feedback_docstring_so_clause_delete_the_mechanism]].

## The compaction was honest, and this run was the evidence

The orchestrator compacted its own instruction set, which it flagged as an interested-party risk.
Verified by diffing both always-loaded files against the whole tree: only incident narrative moved,
all three destinations carry it, and every operative element survived (all four graph triggers, the
graph-vs-grep table, rule 1's whole harvest protocol, rule 4's full procedure). **Rule 1's keep
decision is correct on its own criterion** — no hook fires after an agent reports. Best evidence:
I hit the stale-base case myself and rule 4's *compacted* text was sufficient to handle it without
opening the destination doc. See [[feedback_worktree_main_based_pytest_pythonpath_trap]].
