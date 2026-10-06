### Implementation Summary

Applied the Reviewer's two required fixes plus the R1 upgrade from
`plans/obsidian-links-and-tags/review.md` (Stage 0 + Stage 1 review, tip `a95913d`). No content
conversion, no other subproject touched, `AA-3`'s open contradiction left alone.

### Files Changed

- `.claude/scripts/roadmap-entry-consistency-gate.sh` — check 3 now counts, per entry ID, how many
  index files in the directory link `[[ID]]`, and fails on 0 (orphan, unchanged) **and** on >1
  (new: duplicate-index). The old code only ever set a 0/1 `found` flag, so a second index linking
  the same ID passed silently — invisible at audio-adapter's single-index shape, live the moment a
  subproject gets two indexes sharing one `ROADMAP/` directory (body-layer's planned shape).
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh` — before the existing `#[A-Za-z]...` tag scan,
  each file is piped through: strip fenced code blocks (`awk` fence toggle), strip inline code
  spans (`` `[^`]*` ``), strip URLs (`https?://` up to whitespace/bracket/quote). Fixes the class
  the Reviewer named (inline-code `#heading`, URL-fragment `#section-heading`) rather than adding
  two more special cases, and also catches a third member of the same class I found while looking
  for more: a `#tag`-shaped string on its own line inside a fenced code example.
- `.claude/scripts/roadmap-toc.sh` — same three-stage strip applied to its tag-extraction line
  (it shares the exact regex the Reviewer flagged, just unmentioned by name in the required fix).
- `.claude/scripts/status-page-refresh.sh` — restructured from one `claude -p` call that
  generates-then-publishes into two: Phase 1 generates `docs/status/petrobrain-status.html` on
  disk only (no Artifact publish, no commit, no push); a new mechanical check between them greps
  the real generated file for the forward-only map's (`#graph-upcoming`) node count and fails
  loudly (exit 1) if it is zero; Phase 2 (publish + commit + push) only runs if the check passes.
  This replaces "assert a non-zero forward-item count before publishing" as a prompt instruction
  with an actual grep over output the subprocess produced, which is what the Reviewer's optional
  refinement asked for.

### Tests Added

None — these are bash gate/tooling scripts with no existing test suite of their own; they are
proven by mutation (constructing the real violation, running the real gate, reverting) per the
task's and Reviewer's own verification standard. See mutation proofs below.

### Checks

(audio-adapter/ — the only subproject with code in scope; the four changed files are
`.claude/scripts/`, outside any subproject's own check suite)

- `bash -n` on all four changed scripts: pass
- `ruff format --check .`: pass (63 files already formatted)
- `ruff check .`: pass (all checks passed)
- `mypy --strict src`: pass (no issues, 15 source files)
- `pytest -q`: 222 passed, 1 skipped — matches the Reviewer's reproduced baseline exactly; zero
  diff under `audio-adapter/`

### Mutation Proofs

**Fix 1 — exactly-one-index (`roadmap-entry-consistency-gate.sh`)**

```
$ .claude/scripts/roadmap-entry-consistency-gate.sh
roadmap-entry-consistency-gate: OK          # baseline, exit 0

# added audio-adapter/ROADMAP/second-index-roadmap.md containing "- [[AA-B2]] -- Duplicate link"
$ .claude/scripts/roadmap-entry-consistency-gate.sh
roadmap-entry-consistency-gate: audio-adapter/ROADMAP -- AA-B2.md is linked from 2 indexes in
this directory, expected exactly one
exit: 1                                     # mutated, caught

# removed the second index file
$ .claude/scripts/roadmap-entry-consistency-gate.sh
roadmap-entry-consistency-gate: OK          # reverted, exit 0
```

**Fix 2 — strip code/URL before tag scan (`roadmap-tag-vocabulary-gate.sh`, `roadmap-toc.sh`)**

Appended to a real entry file (`audio-adapter/ROADMAP/AA-B2.md`):
```
See the `#heading` setting and https://example.com/docs#section-heading for details.

```
#fenced-code-tag
```
```

Old (unstripped) regex on that file: `#fenced-code-tag`, `#heading`, `#section-heading`,
`#status/open` — three false positives.

New gate: `roadmap-tag-vocabulary-gate: OK`, exit 0 — real tag (`#status/open`) still caught, all
three false positives gone. `roadmap-toc.sh audio-adapter/ROADMAP/` on the same mutation still
prints `AA-B2 ... #status/open`, not the fake tags. Reverted, both re-run clean.

**Upgrade — mechanical forward-item check (`status-page-refresh.sh`)**

Could not invoke a live `claude -p` call (sandboxed), but the check itself is pure bash/grep with
no LLM in the loop, so it was proven directly: stubbed a copy of the real
`docs/status/petrobrain-status.html`'s `#graph-upcoming` block to an empty `flowchart LR` (the
shape produced by reading a 4-line `ROADMAP.md` pointer as the full roadmap), ran the script's
exact check logic —

```
2026-10-06 ...  --- FAILED: forward-only map has zero items -- likely a split-ROADMAP pointer
read as the full roadmap. NOT publishing or committing. ---
exit code: 1
```

— restored the real file, re-ran:

```
2026-10-06 ...  forward-only map has 24 item(s) -- proceeding to publish
exit code: 0
```

### Notable Discoveries

- The tag-scan regex is shared verbatim between `roadmap-tag-vocabulary-gate.sh` and
  `roadmap-toc.sh` (the task named the gate as required, the TOC helper as "same treatment") — both
  needed the identical three-stage strip; worth remembering if a fourth consumer of this pattern
  ever appears, rather than re-deriving the strip pipeline each time.
- Looked for, and found, a third false-positive class beyond the two the Reviewer named: a bare
  `#tag`-shaped string on its own line inside a fenced code block (` ```\n#fenced-code-tag\n``` `).
  No entry file currently contains one, same as the two named classes before this fix, but the
  task explicitly asked to go looking for the next member of the class and this is it — handled by
  the same fence-toggle `awk` pass, not a special case.
- Looked for a fourth class the review didn't name — a `#` inside a markdown link's quoted title
  attribute, e.g. `[text](url "title with #not-a-tag")` — and decided **not** to handle it: `grep`
  over the whole repo's markdown found zero uses of that syntax anywhere, including in
  `docs/DOC_CONVENTIONS.md` itself, so stripping it would be speculative complexity for a pattern
  this project does not use. CSS colors (`#1a1a1a`) and issue references (`#1234`) are already
  excluded by the existing "tag starts with a letter" rule from the first fix and needed no new
  work.
- `status-page-refresh.sh`'s restructuring is a design change (one `claude -p` call became two)
  but the file's existing "SKIP, never block" philosophy for infrastructure failures (repo not
  found, `claude` missing, dirty tree, no commits) was deliberately preserved for both subprocess
  calls — only the new mechanical check itself exits non-zero, per the task's explicit "fail
  loudly and non-zero" instruction. The script otherwise still always exits 0 on paths that were
  already "log and continue" before this change.

### Implementation Summary — Round 2 fix (2026-10-06)

Addressed the two required fixes from `review.md`'s "Review round 2 — the fix" section, both
defects the previous round's own fix introduced.

### Files Changed

- `.claude/scripts/status-page-refresh.sh` — every non-success exit path *after* Phase 1 may
  write (or have written) to `$PAGE` on disk, and guard 2 ("working tree dirty → SKIP") turns any
  leftover modified/missing file into a silent permanent outage of every future run. Added a
  `revert_page()` helper (`git checkout -- "$PAGE" 2>/dev/null || true`, a no-op when the file
  already matches HEAD) and called it on **every** exit path after generation, not only the one
  the review named:
  - `GEN_STATUS -ne 0` (Phase 1's own `claude -p` failed) — may have left a partial write.
  - `[ ! -f "$PAGE" ]` (file missing after generation) — `git checkout` recreates a tracked file
    that was deleted, same lockout risk as a modified one.
  - `FORWARD_COUNT -eq 0` (the review's named required fix) — the forward-only map read empty.
  - `PUB_STATUS -ne 0` (Phase 2's publish/commit/push failed) — Phase 2 is supposed to commit on
    success; a non-zero exit means that may not have happened. If it *did* already commit (e.g.
    the failure was in the push step), the revert is a no-op since the file already matches HEAD.
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh` — added a per-file fence-balance check
  (`grep -cE '^[[:space:]]*```' "$f"`, odd count → `FAIL=1`, loud message to stderr, `continue`)
  *before* the existing strip-and-scan, so an unclosed fence is a loud failure rather than a
  silent "scanning stopped here." Also widened the fence-opener match in the strip pipeline from
  `/^```/` to `/^[[:space:]]*```/` so a fence indented inside a list item is recognized as a fence
  (the optional finding) rather than leaking its contents through as prose.
- `.claude/scripts/roadmap-toc.sh` — mirrored both changes: the same fence-balance check (prints
  `!!UNBALANCED-FENCE!!` in the tags column plus a stderr message, sets an overall `FAIL` the
  script now exits with — previously this script had no non-usage exit-1 path at all) and the
  same `/^[[:space:]]*```/` widening in its own strip pipeline.
- `plans/obsidian-links-and-tags/implementation.md` — this section.

### Tests Added

No new unit tests — these are standalone bash gate scripts with no existing pytest harness (same
as round 1). Verified by direct mutation against real files, as the task required; see "Mutation
proofs" below.

### Mutation proofs

**Fix 1 — `status-page-refresh.sh` revert-on-failure**, run against the real
`docs/status/petrobrain-status.html` (24 forward-map nodes at baseline):

```
=== baseline git status (expect clean) ===
(empty)
=== RUN 1: simulate a bad Phase-1 regeneration (strip all ::: markers) ===
 docs/status/petrobrain-status.html | 162 ++++++++++++++++++-------------------
 1 file changed, 81 insertions(+), 81 deletions(-)
FORWARD_COUNT=0
--- FAILED: forward-only map has zero items. NOT publishing or committing. ---
run_check exit code: 1
=== after failure: git status --porcelain (expect CLEAN, proving revert worked) ===
(empty)
=== RUN 2: second invocation on the now-clean tree ===
FORWARD_COUNT=24
forward-only map has 24 item(s) -- proceeding to publish
run_check exit code: 0  (proceeds normally, not blocked by guard 2)
=== guard 2 logic re-check ===
proceed: working tree clean
```

This exercises the exact `FORWARD_COUNT`/`revert_page` logic now in the script (lifted verbatim
into a harness, since the script itself shells out to `claude -p`); the real file was mutated in
place and the real `git checkout` reverted it — not a simulation of git's behavior.

**Fix 2 — unbalanced fence, both scripts**, a temporary probe file
`audio-adapter/ROADMAP/AA-B98.md` with one opening ``` and no closing one, followed by a real
unknown tag in plain prose:

```
$ grep -cE '^[[:space:]]*```' AA-B98.md
1
--- gate run ---
roadmap-tag-vocabulary-gate: audio-adapter/ROADMAP/AA-B98.md -- unbalanced fenced code block (1 delimiter(s)) -- cannot safely scan for tags
exit=1
--- toc run ---
roadmap-toc: audio-adapter/ROADMAP//AA-B98.md -- unbalanced fenced code block (1 delimiter(s)) -- cannot safely scan for tags
AA-B98     Unterminated-fence mutation probe (temporary, for review proof)        !!UNBALANCED-FENCE!!
toc overall exit=1
```

Before this fix, the same file made both scripts exit clean with the real tag never reported —
confirmed by inspection of the pre-fix `awk` toggle (`/^```/{fence=!fence;next}` has no
end-of-file check, so `fence` stays true for the rest of the file once set).

**Fix 2 (optional) — indented fence**, probe file with a 5-space-indented fence inside a numbered
list item containing `#fenced-in-list-tag`, plus a real unknown tag outside any fence:

```
--- gate run (expect: flags #totally-unknown-tag, NOT #fenced-in-list-tag) ---
roadmap-tag-vocabulary-gate: audio-adapter/ROADMAP/AA-B98.md -- tag #totally-unknown-tag not listed in docs/TAGS.md
exit=1
--- toc run ---
AA-B98     Indented-fence mutation probe (temporary, for review proof)            #status/open
```

This is the regression check the task called out as the one that matters: the fenced, indented
`#fenced-in-list-tag` is correctly stripped (not flagged), while the real unknown tag in ordinary
prose outside the fence is still caught. Both probe files were removed after proving the fix;
`git status --porcelain audio-adapter/ROADMAP/` is clean.

### Checks (audio-adapter/, via the main checkout's sibling `.venv`, read-only)

- `ruff format --check .` — 40 files already formatted
- `ruff check .` — all checks passed
- `mypy --strict src` — no issues, 15 source files
- `pytest -q` — 222 passed, 1 skipped
- `git diff --stat audio-adapter/` (this worktree) — empty; `audio-adapter/` was not touched by
  this round, only `.claude/scripts/`

### bash -n and gate re-runs (this worktree, real converted `audio-adapter/ROADMAP/`)

- `bash -n` clean on all three changed scripts.
- `roadmap-entry-consistency-gate.sh` → `OK` (unaffected by this round's changes; ~0.39s,
  consistent with round 2's 0.36s measurement, within noise).
- `roadmap-tag-vocabulary-gate.sh` → `OK`, ~0.32–0.33s (up from round 2's 0.25s baseline — the
  added per-file `grep -cE` fence-count pass is one extra subprocess per file; at 22 files that is
  the full ~0.07–0.08s difference observed). Extrapolating the same way round 2 did (linear in
  file count, no quadratic step introduced), 204 files would add roughly another 0.6–0.7s on top
  of round 2's 2–4s estimate — still comfortably sub-5s and invisible at commit time.
- `roadmap-toc.sh audio-adapter/ROADMAP/` → prints all 22 entries with correct tags, exit 0,
  matching the pre-fix baseline (toc.sh's own runtime was not separately measured in round 2 and
  is not commit-gating).
- `push-roadmap-gate.sh` and `graphify-dirty-flag.sh` — both unchanged by this round; re-ran with
  `CLAUDE_PROJECT_DIR` set (unbound without it, unrelated to this fix) and both exit 0 cleanly.

### Notable Discoveries

- The reviewer's framing — "a gate that now misses a real tag is worse than the false positives
  it fixed" — turned out to generalize past the fence case it was written about: both new checks
  in this round (unbalanced fence, and the PUB_STATUS-failure revert) are instances of the same
  shape, "a failure path that degrades silently is worse than one that fails loudly," which is
  also why `revert_page()` was applied to all four `status-page-refresh.sh` exit paths rather than
  just the one named — the three unnamed ones share the identical guard-2 lockout mechanism, just
  reached by a different trigger.
- `roadmap-toc.sh` had no non-usage exit-1 path before this round (every row printed unconditionally,
  function always exited 0 past the usage check). Adding the fence-balance failure gives it one for
  the first time — worth knowing if anything downstream currently assumes this script never fails
  non-zero past argument validation.
