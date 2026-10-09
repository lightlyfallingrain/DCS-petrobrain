---
name: doc-conventions-round4-consumer-fixes
description: Round-4 fixes for the roadmap/backlog split — the roadmap-source.sh resolver, why doc-provenance-gate stayed unwired, and the latent id_sort_key crash widening discovery exposed.
metadata:
  type: project
---

Review round 4 of `plans/obsidian-links-and-tags/`, 2026-10-09, branch
`feature/doc-conventions-audio-adapter`. Eight documents were split into one file per entry across
seven directories, each original left as a four-line pointer whose first line is the sentinel
`<!-- split-roadmap: see ROADMAP/ -->`.

**`.claude/scripts/roadmap-source.sh` now owns the sentinel.** `<path>` → the index, `--dir` → the
directory, `--entries` → every entry file, `--is-pointer` → silent test; a non-pointer passes
through unchanged, so a consumer pipes every roadmap path through it without first knowing which
were split. The destination is **derived** (`<dir>/ROADMAP` or `<dir>/<stem>`), never listed, so a
ninth split document needs no edit — and it cannot be derived from the sentinel's text, which reads
`see ROADMAP/` even under `todo/`, where that directory does not exist. Prefer calling it over
adding another prose caveat: eleven consumers each carried their own wording and about half of every
pair had been missed.

**`doc-provenance-gate.sh` is deliberately NOT wired into `commit-quality-gate.sh`**, unlike the
other two. The review's premise — "latent only because zero provenance blocks exist" — is false: 32
documents carry a real block. Fixing `find_entries`'s hardcoded `audio-adapter/ROADMAP` (22 entries
→ 245 across all seven directories) means the generator now sees cross-subproject citations it could
not before, so **127 documents' blocks are stale by regeneration** (counterfactual: pre-fix the gate
is `OK` rc=0; post-fix it names 127 files). Wiring it would refuse every commit touching any
`ROADMAP/` path repo-wide until those are regenerated, which is the paused document-graph work.
Unblock condition is written at the wiring site. **If you are told to wire it, check whether those
127 have been regenerated first.**

**Widening that discovery exposed a latent crash worth remembering as a shape.** `id_sort_key` had
`assert m is not None` with no message and a regex demanding letters-then-digits
(`^([A-Za-z]*)(\d*)$`) — but a suffixed ID is digits-then-letter, and **`BL-5a` and `MI-5b` are both
real on disk.** The gate therefore died on an `AssertionError` naming nothing, the instant discovery
could see body-layer or mission-interpreter. Invisible for as long as the function only ever read
one directory that happened to contain no suffixed ID. **A bare `assert` inside a gate converts a
reportable finding into an unexplained crash; make the pattern total instead.**

**Also worth not re-deriving: body-layer's is the only "Live acceptance debt" list that was
dissolved** (into per-entry `#needs-flight`). `world-model`'s and `audio-adapter`'s indexes still
carry a section of that name, so four of the five live references to such a list needed only a path
correction and one needed rewording — treating them uniformly would have been wrong four times.

Related: [[feedback_execute_the_published_recipe_before_trusting_it]],
[[feedback_narrative_prose_stays_in_the_index]], [[project_obsidian_links_stage4_5_final]].
