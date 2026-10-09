---
name: doc-conventions-gate-scaling
description: measured scaling of the three new split-roadmap gate scripts and the graph-corpus ceiling, from the doc-conventions-audio-adapter performance pass
metadata:
  type: project
---

Measured (synthetic tree, `*/pyproject.toml`-discovered, N=22..400 entries, harness-can-fail probe
run first): `roadmap-entry-consistency-gate.sh` and `roadmap-tag-vocabulary-gate.sh` are both
**linear in practice** up to 400 entries (2x the 204-file repo-wide target) — ~17.5 ms/entry and
~13.8 ms/entry respectively, flat ratio across the whole range. Check 1 of the consistency gate
(`grep -qxF "$target" <<< "$ids"` per link) is structurally O(links × ids), but per-file shell
fork/exec overhead dominates at this scale and the quadratic term never surfaces below 400 entries.
`roadmap-toc.sh` is the same shape, ~13.2 ms/entry.

**None of the three run automatically.** Checked `.claude/settings.json`'s `PreToolUse`/Bash `if`
conditions directly: only `commit-quality-gate.sh` (gated on `git commit`) and
`push-roadmap-gate.sh` (gated on `git push`) are wired in, and neither iterates roadmap entries —
both are diff/commit-range scoped, independent of total entry count. The three new scripts are
"Run standalone" only (own docstrings + `docs/DOC_CONVENTIONS.md`). So whatever their asymptotics,
nobody waits for them today. If they are ever wired into the automatic path at the 204-entry
repo-wide target, combined cost would be **~6–9 s added per commit** (204 × ~31ms, or ~44ms with
toc) — past the "gets disabled" threshold this project names explicitly. Mitigation when that day
comes: scope to the roadmap directories the staged diff actually touches, not a full-repo scan
every time.

**Real NOW finding: the knowledge-graph corpus ceiling, not the gates.**
`graph-corpus-files.sh` walking `*/ROADMAP/*.md` pushed the corpus from 173→198 files for *one*
subproject's conversion (22 entries) — 2 files short of `graph-corpus-guard.sh`'s default ceiling
of 200. Repo-wide conversion (204 entries, 7 indexes) would push it past 400, well over double the
ceiling. The guard fails closed (refuses the rebuild, names the fix: raise the ceiling deliberately
or reconsider per-entry corpus granularity) rather than silently degrading, which is the right
failure mode — but it means `/graph-refresh` stops working outright once a second subproject
converts, unless someone addresses this first. Architectural call (what counts as a corpus node for
a split roadmap), not a pure performance fix — flag to Architect, not something to decide solo.

Session Start read-cost claim confirmed by direct measurement, not estimate: audio-adapter's old
single `ROADMAP.md` was 42,058 bytes (~10.5k tokens); pointer+index+median-entry is ~5.9KB
(~1.5k tokens) — ~86% reduction for the common "find next milestone, read one entry" case.

See `plans/obsidian-links-and-tags/performance.md` for full method and per-N tables.
