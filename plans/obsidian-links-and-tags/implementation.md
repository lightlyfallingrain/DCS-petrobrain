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

### Implementation Summary — Stage A0 (2026-10-07)

Implemented Stage A0 from `plans/obsidian-links-and-tags/plan-document-graph.md`: lift the
document citations already written in prose inside `audio-adapter/ROADMAP/AA-*.md` into a
generated `doc-provenance` block on the **cited document** (never the entry). No tags, no typed
dependency edges, no git-history inference for the uncited entries — all later stages, out of
scope here per the plan and the task's own scope section. Branch tip before this round: `fbd62b9`
(fast-forwarded into this worktree; see handoff note below).

### Files Changed

- `.claude/scripts/roadmap-entry-consistency-gate.sh` — **R1 fix.** Check 1 (dangling-link
  resolution) now resolves every `[[ID]]` against the **union** of IDs across every converted
  `*/ROADMAP/` and `todo/backlog/` directory, not just the directory the link was written from.
  Previously a per-directory-only ID set meant `[[AA-3]]` written from outside
  `audio-adapter/ROADMAP/` reported as dangling — live now, since Stage A0 writes exactly that
  shape of link into `plans/*/plan.md` and `*/research/*.md`. Check 3 (index membership) stays
  per-directory deliberately — an index only ever lists its own directory's entries, so "exactly
  one" is a per-directory fact, unlike check 1's resolution target.
- `.claude/scripts/doc_provenance.py` — **new.** Shared extraction/generation/verification logic.
  Citation extraction over the 22 entry files (three regex classes: `plans/<name>/`, bare or
  subproject-prefixed `research/<file>.md`, `docs/acceptance/<file>.md`); builds a
  target-document → (kind, ordered citing-entry-ids) map; renders/strips the delimited block;
  drives both `refresh` (writes) and `gate` (verify-only, regenerate-into-temp-and-diff) modes
  from one code path, plus a `plan` mode that prints what would change without touching anything.
  Written in Python rather than bash/awk (there is precedent in this family —
  `commit-quality-gate.sh` already shells out to `python3`) because the block-insertion/strip
  logic is a small stateful text transform that is far more reliably expressed and reviewed with
  real control flow than as an awk state machine attempting the same idempotency guarantee.
- `.claude/scripts/doc-provenance-refresh.sh` — **new.** Thin wrapper: `python3 doc_provenance.py
  refresh`. On demand only, per the plan's "nothing that writes runs in a hook" rule — same
  reasoning as `doc-graph-refresh.sh`'s design (not yet built; this stage does not need it).
- `.claude/scripts/doc-provenance-gate.sh` — **new.** Thin wrapper: `python3 doc_provenance.py
  gate`. Verify-only.
- `docs/DOC_CONVENTIONS.md` — new "Document provenance" section (block format, the three labels
  and which document kind maps to each, the plan-directory-is-one-unit rule, scope, regenerate /
  verify commands); "Gates" section extended from two checks to three. **Deliberately does not
  list which documents are converted** — per the task's R8 instruction, a path check
  (`doc-provenance-gate.sh` itself, or `grep -l doc-provenance:start`) answers that and a written
  list goes stale.
- 13 cited documents gained a `doc-provenance` block (see "Generated blocks" below):
  `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`,
  `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`,
  `aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md`,
  `audio-adapter/research/2026-09-17-tts-audio-transport-recon.md`,
  `audio-adapter/research/2026-09-19-whisper-model-sweep.md`,
  `docs/acceptance/2026-09-18-stage6-sortie.md`,
  `docs/acceptance/2026-09-23-voice-command-sortie.md`,
  `docs/acceptance/2026-10-05-spu8-intercom-probe.md`,
  `docs/acceptance/2026-10-05-spu8-intercom-sortie.md`,
  `plans/callout-scheduling/plan.md`, `plans/inbound-speech/plan.md`,
  `plans/spu8-intercom/plan.md`, `plans/tts-voice-output/plan.md`. No `audio-adapter/ROADMAP/*.md`
  entry file was edited — the entries are the citing side, never the cited side.

### Decisions made during implementation

- **Bare-directory citations (`plans/spu8-intercom/`, `plans/callout-scheduling/`,
  `plans/tts-voice-output/`) all resolve to `plan.md`.** The task named `plans/spu8-intercom/`
  (nominated by `AA-3`) as needing a decision; the same shape recurred twice more
  (`AA-1`, `AA-1.6`), so the decision was generalized rather than special-cased once: a plan
  directory is one unit (plan-document-graph.md §1's own rule for Stage B), so `plan.md` is its
  designated carrier regardless of which sibling file the citing prose actually names, or
  whether it names a file at all. `AA-3` cites `plans/spu8-intercom/{plan.md, implementation.md,
  review.md, security-deep-analysis.md, performance.md, dod-check.md}` by brace-expansion in
  prose — read as one directory-level citation (matching the plan's own accounting: "AA-3's five
  citations are two in `aircraft-layer/research/`, two in `docs/acceptance/`, **one plan
  directory**"), not six separate document citations. Only `plan.md` got a block.
- **One line per citing entry, not one line listing every ID.** `plans/inbound-speech/plan.md` is
  cited by both `AA-4` and `AA-4.1`; it carries two `**Decision for:**` lines rather than one line
  with two `[[ID]]`s. This reads the task's "gains a second line inside the same block, not a
  second block" instruction literally, and generalizes cleanly if a later stage ever needs a
  second *kind* of relation line in the same block.
- **Block placement for a file with no H1 at all.** Every `plans/<name>/plan.md` in this corpus
  opens directly with `### Goal` — none has a top-level `# ` heading, which the parent plan's
  "placed immediately after the H1" rule did not anticipate. Fallback: the block goes at the very
  top of the file when no H1 is found. Flagged below as a real discovery, not a edge case
  invented for completeness.
- **Bare `research/<file>.md` citations (no subproject prefix) resolve to `audio-adapter/`.**
  Two entries (`AA-3`, `AA-4.1`) cite `research/<file>.md` with no leading path segment; both
  files exist only under `audio-adapter/research/`, confirmed by `find` before writing the
  resolution rule, not assumed.

### Idempotency bug found and fixed during implementation

First version of `strip_existing_block` removed at most **one** blank line adjacent to the block,
on whichever side the block's insertion side was. That is correct the first time, but the no-H1
insertion path adds its separator blank **after** the block, and the first real run against
`plans/*/plan.md` left that blank in place on strip (an off-by-one: the removal loop was an `if`,
not a `while`), so a second `refresh` run re-added a second blank — found by actually running
`refresh` twice and reading the file (`cat -A`-equivalent via `Read`), not by inspection. Fixed by
stripping *every* consecutive blank line adjacent to the block on the correct side (a `while`,
not an `if`) — correct both for the one-blank case a clean run produces and for a leftover
multi-blank case from the buggy intermediate state. Re-verified idempotent by sha1 checksum
before/after a second `refresh` run on four affected files (see "Checks" below) and by `git
status --porcelain` staying unchanged across a third run.

### Checks

- `bash -n` clean on `doc-provenance-refresh.sh`, `doc-provenance-gate.sh`,
  `roadmap-entry-consistency-gate.sh`, `roadmap-tag-vocabulary-gate.sh`.
- `python3 -c "import ast; ast.parse(...)"` clean on `doc_provenance.py`.
- **R1 mutation proof** (`roadmap-entry-consistency-gate.sh`): a scratch `body-layer/ROADMAP/`
  with one dummy entry (`BL-99.md`) and its index was created; a temporary `[[BL-99]]` link added
  to `audio-adapter/ROADMAP/AA-5.md` passed under the fixed gate (would have failed as dangling
  under the old per-directory logic); a further `[[AA-99]]` (genuinely nonexistent) in the same
  line still failed, naming the file and the missing target. Both edits and the scratch directory
  were fully reverted before continuing; `git status --porcelain` confirmed clean before the next
  step.
- **Gate exit-path proofs** (`doc-provenance-gate.sh`): (1) ran before any `refresh`, over all 13
  cited documents with no block yet — failed loud on every one, each with a real unified diff and
  a pointer to the refresh command; (2) ran after `refresh`, with every document already
  matching — `OK`, exit 0; (3) hand-edited an extra `**Flight for:** [[AA-99]]` line inside an
  existing block — failed loud, diff showed exactly the injected line, restored, re-ran clean;
  (4) deleted the `<!-- doc-provenance:end -->` line from a block, leaving an unbalanced
  delimiter pair — failed loud naming the exact counts (`1 start delimiter(s) and 0 end
  delimiter(s)`), restored from a pre-edit copy, re-ran clean.
- **Idempotency proof**: ran `doc-provenance-refresh.sh` three times in a row. First run wrote
  all 13 files (fresh generation). Second run (after the blank-line bug fix) wrote the 4 no-H1
  files again correcting the double-blank; `sha1sum` of 4 representative files (one of each
  kind, including the twice-cited `plans/inbound-speech/plan.md`) taken before and after a third
  run were byte-identical, and the third run itself reported "nothing to change"; `git status
  --porcelain` after staging showed no further changes from the third run.
- `.claude/scripts/roadmap-entry-consistency-gate.sh` → `OK`.
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh` → `OK`.
- `.claude/scripts/doc-provenance-gate.sh` → `OK`.
- `.claude/scripts/push-roadmap-gate.sh` → exit 0 (fails open; re-run with `CLAUDE_PROJECT_DIR`
  set explicitly — unbound without it in this standalone invocation, unrelated to this change).
- `.claude/scripts/graphify-dirty-flag.sh` → exit 0.
- audio-adapter checks, via the main checkout's sibling `.venv` (this worktree's own `src` is
  untouched by this round — `git diff --stat audio-adapter/src` is empty):
  - `ruff format --check .` — 63 files already formatted
  - `ruff check .` — all checks passed
  - `mypy --strict src` — no issues, 15 source files
  - `pytest -q` — **222 passed, 1 skipped**

### Generated blocks (full text, as written)

```markdown
aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md
<!-- doc-provenance:start -->
**Evidence for:** [[AA-4.5]]
<!-- doc-provenance:end -->

aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md
<!-- doc-provenance:start -->
**Evidence for:** [[AA-3]]
<!-- doc-provenance:end -->

aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md
<!-- doc-provenance:start -->
**Evidence for:** [[AA-3]]
<!-- doc-provenance:end -->

audio-adapter/research/2026-09-17-tts-audio-transport-recon.md
<!-- doc-provenance:start -->
**Evidence for:** [[AA-3]]
<!-- doc-provenance:end -->

audio-adapter/research/2026-09-19-whisper-model-sweep.md
<!-- doc-provenance:start -->
**Evidence for:** [[AA-4.1]]
<!-- doc-provenance:end -->

docs/acceptance/2026-09-18-stage6-sortie.md
<!-- doc-provenance:start -->
**Flight for:** [[AA-1.6]]
<!-- doc-provenance:end -->

docs/acceptance/2026-09-23-voice-command-sortie.md
<!-- doc-provenance:start -->
**Flight for:** [[AA-4.6]]
<!-- doc-provenance:end -->

docs/acceptance/2026-10-05-spu8-intercom-probe.md
<!-- doc-provenance:start -->
**Flight for:** [[AA-3]]
<!-- doc-provenance:end -->

docs/acceptance/2026-10-05-spu8-intercom-sortie.md
<!-- doc-provenance:start -->
**Flight for:** [[AA-3]]
<!-- doc-provenance:end -->

plans/callout-scheduling/plan.md
<!-- doc-provenance:start -->
**Decision for:** [[AA-1.6]]
<!-- doc-provenance:end -->

plans/inbound-speech/plan.md
<!-- doc-provenance:start -->
**Decision for:** [[AA-4]]
**Decision for:** [[AA-4.1]]
<!-- doc-provenance:end -->

plans/spu8-intercom/plan.md
<!-- doc-provenance:start -->
**Decision for:** [[AA-3]]
<!-- doc-provenance:end -->

plans/tts-voice-output/plan.md
<!-- doc-provenance:start -->
**Decision for:** [[AA-1]]
<!-- doc-provenance:end -->
```

### Entries that produced nothing (15 of 22) — the honest limit, as the plan names it

`AA-1.1`, `AA-1.2`, `AA-1.3`, `AA-1.4`, `AA-1.5`, `AA-2`, `AA-4.2`, `AA-4.3`, `AA-4.4`, `AA-4.7`,
`AA-4.8`, `AA-5`, `AA-B1`, `AA-B2`, `AA-B3` cite nothing matching the three citation shapes in
scope, and correctly produced no block anywhere. Not attempted: inferring a citation from branch
names some of these do mention (e.g. `AA-5`'s `feature/silence-command`) — the plan explicitly
defers that to a later, separate decision.

### Notable Discoveries

- **No `plans/*/plan.md` in this corpus has an H1.** All four touched (`tts-voice-output`,
  `callout-scheduling`, `spu8-intercom`, `inbound-speech`) open directly with `### Goal`. The
  parent plan's "placed immediately after the H1" rule silently assumed one exists everywhere;
  it does not, for the one document kind (`plan.md`) this stage writes into that is not a
  research note or acceptance card. Worth carrying into Stage B/D, which touch the same files.
- **The plan's own citation count held up exactly.** Plan-document-graph.md's Stage A0 section
  measured "7 entries cite a plan/research/acceptance doc; 15 cite nothing" and "~8–10 external
  documents" for `AA-3` alone (2 research + 2 acceptance + 1 plan directory). The implementation's
  mechanical extraction found the same 7 citing entries and the same per-entry citation shapes
  with no manual curation — a real cross-check that the earlier measurement was not an
  undercount or overcount, not just a repeated claim.
- **An off-by-one in blank-line stripping only showed up on the second refresh run of the no-H1
  path**, not the first. A single-run review of generated output would have looked correct; the
  idempotency proof (run twice, diff/checksum) is what caught it, consistent with this project's
  "a counterfactual is evidence only if you ran it" standard.

### Implementation Summary — Stage A (2026-10-07)

Implemented Stage A from `plans/obsidian-links-and-tags/plan-document-graph.md`: the topic-tag
vocabulary rule, the proposer, and the generator/gate extension to carry topic tags in the same
block the provenance lines already occupy. **Built and proven; nothing tagged.** Per the task's
explicit stop point, `docs/TAGS.md` gains no topic rows this round and no document gains a topic
tag — the committed tree is byte-identical to before this round everywhere except the four files
below, and the generator/gate mechanism was proven against a scratch copy outside the repo, then
discarded. Branch tip before this round: `d4b3efb` (fast-forwarded into this worktree — see
handoff note below).

### Files Changed

- `docs/TAGS.md` — rewrote the `#topic/*` admission rule: "crosses at least two subprojects"
  (wrong axis, zero members) replaced with three rules — crosses at least two *document kinds*,
  lands in the measured 3–25 band, flat spelling. Closed-vocabulary argument kept in substance.
  Format changed from a table to one short section per tag (a `|` inside a match-pattern table
  cell is exactly the two-spellings footgun this file warns about).
- `.claude/scripts/doc_tags.py` — **new.** The proposer's logic. `all_units()` enumerates every
  document unit of the four in-scope kinds repo-wide (239 measured live, close to the plan's
  243 — the plan's own roadmap-entry count of 23 included the index file, 22 is correct);
  `in_scope_units()` is Stage A's own 35 (22 `audio-adapter/ROADMAP/AA-*.md` + the 13 documents
  already carrying a doc-provenance block, detected by checking each unit's own representative
  file for the literal block, never a directory-wide text search — see "Notable Discoveries").
  `harvest_occurrences()` gathers candidates from exactly the three sources the plan names
  (graphify community/concept-node labels — borrowed from the main checkout's graph the same way
  `gq.sh` does, since `graphify-out/` is gitignored and absent from this worktree; ID-shaped
  hardware/jargon tokens; capitalised multi-word phrases) in one pass that doubles as the
  repo-wide measurement, deliberately never re-scanning per candidate (see "Performance" below).
  `measurement_from_occurrence()` turns one candidate's occurrence set into both counts the task
  asked for — repo-wide (admission) and in-scope (worth emitting now) — kept as two separate
  fields throughout rather than blended.
- `.claude/scripts/doc-tags-propose.sh` — **new.** Thin wrapper (`doc_tags.py propose` /
  `measure <term>`), matching the `doc-provenance-*` family's shape.
- `.claude/scripts/doc_provenance.py` — **extended**, not replaced. `build_target_map()` now also
  adds every converted roadmap entry as its own document unit (`kind="entry"`, no citation ids —
  "it IS one," per the plan's per-kind table). `block_lines()` takes a `topics` list and returns
  `None` (no block at all) when there is nothing to say, extending the existing "a line with no
  values is omitted entirely" rule from citation lines to the whole block. `regenerate_content()`
  reverts a document to its stripped form when `block_lines` returns `None`, rather than leaving
  the block structurally present with empty content, since Stage A's own real run depends on that
  (zero approved tags → every Topics line empty → every block must either already carry a
  citation or not exist at all). `load_approved_topic_tags()` reads `docs/TAGS.md`'s per-tag
  sections fresh on every run — the vocabulary is enforced here, not just documented in prose.
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh` — extended past `*/ROADMAP/` to a second file
  group: any document whose own text (after this gate's existing fence-strip) still contains the
  literal `<!-- doc-provenance:start -->` delimiter, discovered via `grep -rl` rather than
  enumerated. The fence-strip-then-recheck step is load-bearing, not incidental — see "Notable
  Discoveries."
- `.gitignore` — added `__pycache__/`. `doc_tags.py` is a second script run directly in this
  directory; running it created an untracked `__pycache__/` that nothing previously ignored.

### Tests / proofs (no automated test suite in `.claude/scripts/`, per this family's own
convention — `doc-provenance-gate.sh`'s own header note applies here too: proofs are gate runs
and scratch-copy demonstrations, not pytest)

- **Vocabulary-gate false-positive fix, proven by mutation**: before the fix, `load_approved_tags`
  (doc_tags.py) and `load_approved_topic_tags` (doc_provenance.py) both read `docs/TAGS.md`'s own
  "Format" example — a `### \`#SPU-8\`` section written *inside a fenced code block* to illustrate
  the convention — as a real approved tag. Caught by running `doc_provenance.py plan` against the
  committed tree and seeing `1 approved topic tag(s)` when the prose says "None approved yet."
  Fixed by fence-stripping `docs/TAGS.md` before scanning for `### #tag` sections (mirroring
  `roadmap-tag-vocabulary-gate.sh`'s own existing fence handling, odd-count-fails-loudly included)
  in both modules; re-ran `plan` and confirmed `0 approved topic tag(s)`.
- **`candidate_pattern` regex-escaping bug, found by reading generated output, not by
  inspection**: `re.escape("SPU-8")` produces the literal two characters `\-`; substituting for a
  bare `-` afterwards matches only the second character, leaving `\bSPU\[- ]?8\b` in
  `docs/TAGS.proposals.md` — compiles and runs without error, matches the wrong text. Fixed by
  splitting on hyphen/space first and escaping each part before rejoining
  (`candidate_inner_pattern`/`candidate_pattern`). Re-ran `doc-tags-propose.sh measure SPU-8` and
  confirmed 18 units repo-wide, matching the plan's own independent measurement exactly.
- **Performance**: the first version of `harvest_occurrences` also harvested every lowercase word
  with document-frequency ≥3 (thousands of candidates on a 239-unit corpus) and then re-scanned
  the whole corpus per candidate for the repo-wide count — over two minutes of 100% CPU with no
  completion, killed by hand. Two independent fixes: (1) record occurrence sets during the single
  harvest pass instead of re-scanning per candidate (`harvest_occurrences` now doubles as the
  measurement); (2) drop the generic word-frequency source entirely — it is not one of the plan's
  three named sources, and a project's own documentation is dense enough with generic nouns
  ("panel", "delay", "press") that document-frequency ≥3 alone cannot tell a topic from ordinary
  prose. After both fixes: ~239 units, 46 in-band candidates, runs in under 10 seconds.
- **Boilerplate precision filter, found by reading the first clean run's output**: even after
  dropping word-frequency harvesting, Title-Case section *headings* repeated across every
  `dod-check.md`/`review.md`/`security-*.md` ("Second-Order Effect", "Milestone Completion",
  "Content-Length") surfaced as spurious candidates, both as literal ATX headings and as inline
  cross-references to them ("see Optional Refinements below"). Fixed with an ATX-heading strip
  before harvesting plus a `_PROCESS_VOCAB` denylist of ~20 known structural terms — a precision
  filter on cross-cutting document-template vocabulary, not a hand-seeding of real topic
  candidates (no domain term like `SPU-8`/`BTR-70`/`aircraft-manipulation` is in that list).
- **`doc-provenance-gate.sh`/`doc-provenance-refresh.sh` against the real committed tree, with
  zero approved tags**: `refresh`/`check` report "nothing to change"; `gate` reports `OK`;
  `git status --porcelain` stays empty around both runs. This is the task's own acceptance
  condition for the real tree, run and confirmed rather than assumed from the code.
- **Scratch-copy proof the mechanism works** (`git archive`-equivalent: a plain recursive copy of
  this worktree to a scratchpad directory outside the repo, since the copy's own `.git` file
  resolves `git rev-parse --show-toplevel` to the copy's own path, verified before any write):
  added two `### #tag` sections to the scratch copy's `docs/TAGS.md` (`#SPU-8`,
  `#aircraft-manipulation`, both marked "SCRATCH-RUN-ONLY, not a real approval" in their own
  one-line descriptions) and ran `doc_provenance.py refresh`. 12 files gained a `**Topics:**`
  line — `AA-3` and 11 others matching `#SPU-8` (none matched `#aircraft-manipulation`, which is
  a real finding, not a bug: `AA-3`'s own text never spells it that way, consistent with the
  plan's observation that `#SPU-8` and `#aircraft-manipulation` are two separate tags).
  `plans/inbound-speech/plan.md`'s block gained a Topics line alongside its two existing
  `**Decision for:**` lines, confirming "same block, one more line" rather than a second block.
  A second `refresh` reported "nothing to change" (idempotent); both `doc-provenance-gate.sh` and
  `roadmap-tag-vocabulary-gate.sh` reported `OK` against the scratch-approved vocabulary. The
  scratch copy was then deleted in full; `git status --porcelain` on the real worktree was
  unaffected throughout (confirmed before and after).
- `bash -n` clean on `doc-tags-propose.sh`, `doc-provenance-refresh.sh`, `doc-provenance-gate.sh`,
  `roadmap-tag-vocabulary-gate.sh`, `roadmap-entry-consistency-gate.sh`.
- `python3 -c "import ast; ast.parse(...)"` clean on `doc_tags.py`, `doc_provenance.py`.
- `.claude/scripts/doc-provenance-gate.sh` → `OK`. `.claude/scripts/roadmap-tag-vocabulary-gate.sh`
  → `OK` (both the entry-file group and the new block-carrying-document group). `.claude/scripts/
  roadmap-entry-consistency-gate.sh` → `OK`. `.claude/scripts/push-roadmap-gate.sh` → exit 0 (with
  `CLAUDE_PROJECT_DIR` set explicitly, same pre-existing unbound-without-it behaviour Stage A0
  noted, unrelated to this change). `.claude/scripts/graphify-dirty-flag.sh` → exit 0.
- audio-adapter checks, via the main checkout's sibling `.venv` (no `audio-adapter/src` or
  `tests` file is touched by this round — `git diff --stat audio-adapter` is empty):
  - `ruff format --check .` — 63 files already formatted
  - `ruff check .` — all checks passed
  - `mypy --strict src` — no issues, 15 source files
  - `pytest -q` — 222 passed, 1 skipped

### Candidate table

**Final measurement, taken against the committed tree after this very section was written** —
`plans/obsidian-links-and-tags/` is itself a plan unit, and this section's own prose (candidate
names, counts) feeds back into the next measurement of the same corpus. Rather than report a
table that could not be reproduced by re-running the tool against what actually got committed,
this is the number `doc-tags-propose.sh` reports *after* this file reached its final form —
confirmed by re-running it once more following the last edit below and diffing `docs/
TAGS.proposals.md` byte-for-byte against what is committed.

239 document units measured repo-wide, 35 in Stage A's scope:

| candidate | repo-wide | by kind | in-scope |
|---|---|---|---|
| `#SPU-8` | 17 | 2 roadmap, 5 research, 5 acceptance, 5 plan | 13 |
| `#NET-1` | 6 | 1 roadmap, 2 research, 1 acceptance, 2 plan | 5 |
| `#NET-2` | 4 | 1 roadmap, 2 research, 1 plan | 3 |
| `#russian-accented-english` | 3 | 1 roadmap, 1 research, 1 plan | 3 |
| `#BTR-70` | 19 | 7 research, 4 acceptance, 8 plan | 2 |
| `#apple-silicon` | 3 | 3 research | 2 |
| `#mission-scripting` | 20 | 18 research, 2 plan | 1 |
| `#ZSU-23` | 19 | 5 research, 4 acceptance, 10 plan | 1 |
| `#SA-3` | 18 | 6 research, 3 acceptance, 9 plan | 1 |
| `#BMP-2` | 17 | 2 research, 1 acceptance, 14 plan | 1 |
| `#ZU-23` | 16 | 4 research, 5 acceptance, 7 plan | 1 |
| `#ASP-17` | 9 | 1 roadmap, 5 research, 3 plan | 1 |

12 shown (batch size), 34 more in-band (not expanded — mostly further Soviet/DCS unit designators:
`#BMP-1`, `#BM-21`, `#BTR-60`, `#BMD-1`, `#SA-10`/`#SA-15`/`#SA-2`/`#SA-6`/`#SA-8`/`#SA-9`/`#SA-13`,
`#BTR-80`, `#BM-27`/`#BM-30`, `#ASP-17V`, `#2K12`, `#KS-19`, `#ZPU-4`; plus `#mission-editor`,
`#world-model-builder`, `#petrobrain-runtime`, `#mission-understanding`, `#windows-python`,
`#transverse-mercator`, `#douglas-peucker`, `#low-blow`, `#give-petrovich`, `#IEEE-754`,
`#LGPL-3`, `#eagle-dynamics`, `#jabal-ansariyah`, `#new-hook`, `#sivas-province`). 2 TOO BROAD
(`#9K113` 43, `#saved-games` 38 — both split-before-proposing, not process-vocab misses). 739 TOO
NARROW (<3 units, compact). 6 ALREADY-SAID (every subproject's own directory name). Full ranked
output and both counts for every in-band candidate: `docs/TAGS.proposals.md` (the 12 shown above,
in the section format ready to promote).

The slight upward drift from the mid-implementation measurement quoted in "Notable Discoveries"
below (`#NET-1` 5→6, `#BTR-70` 18→19, …) is this section's own text joining the corpus it
measures — `#NET-1`/`#NET-2` pick up one more `plans/obsidian-links-and-tags/plan.md`-unit match
because this very file (`implementation.md`) is a sibling in that plan directory, and the unit is
matched as a whole. Harmless and expected, not a bug: the mid-implementation numbers in "Notable
Discoveries" are quoted because they are what the fixes below were verified against at the time,
not because they are the final answer.

### Notable Discoveries

- **"In-scope" cannot be `grep -rl` for the delimiter directly.** Two files
  (`docs/DOC_CONVENTIONS.md`, `plans/obsidian-links-and-tags/implementation.md` — this very file)
  *quote* `<!-- doc-provenance:start -->` as documentation, inside a fenced example, and a naive
  `grep -rl` lists both alongside the 13 real provenance-bearing documents. Both `doc_tags.py`'s
  `has_provenance_block` (checks only the unit's own representative file, never a whole-directory
  text search — `plans/obsidian-links-and-tags/plan.md` itself has zero occurrences even though
  its sibling `implementation.md` has thirteen) and the tag-vocabulary gate's new file group
  (fence-strips first, then re-checks the delimiter survives) independently exclude both, and both
  were verified against this exact pair of files, not assumed correct from the code.
- **The task's instruction to reuse `docs/TAGS.md`'s pattern convention cuts both ways.** The
  `Matches:` value in `docs/TAGS.proposals.md` and in `docs/TAGS.md`'s own example (`SPU-?8`) is
  the *inner* pattern with no `\b` word-boundary wrapping — `load_approved_topic_tags` and
  `load_approved_tags` both add that wrapping themselves when compiling. The regex-escaping bug
  above was found precisely because the first version emitted the *wrapped* form into the
  proposals file, which read as `\bSPU\[- ]?8\b` and immediately looked wrong next to the
  documented example.
- **A roadmap entry's own block is genuinely different in shape from every other kind's**: no
  label line is ever possible (an entry is never "cited" by anything the generator tracks), so
  `block_lines` returning `None` for an entry with no matching topic is the *common* case today
  (22 of 22), not an edge case — every other kind's block always has at least one citation line
  and so never exercises the "nothing to say" path in the real tree, only the scratch run.
- **`#9K113`'s 43-unit TOO BROAD reading is a real hardware designator** (the 9K113 Shturm ATGM,
  mentioned across many research/plan documents) and would need splitting by context before it
  could be proposed, same treatment as `#audio` in the parent plan — not a harvester defect.
  `#saved-games` (38) is DCS's own filesystem concept (the `Saved Games/` folder) and is genuinely
  a hub, not boilerplate. Both are correctly reported TOO BROAD rather than silently dropped: the
  tool's job is to measure and band, not to decide a broad term is wrong to have found.
- **A document that merely quotes the provenance delimiter can carry it two different ways, and
  the gate's own fence-strip only caught one.** `roadmap-tag-vocabulary-gate.sh`'s new group-(b)
  discovery excludes a quoting document by checking the delimiter does not survive a fence-strip
  — correct for `docs/DOC_CONVENTIONS.md`'s and this very `implementation.md`'s *earlier* fenced
  examples, but this round's own new prose quotes the delimiter a second way, inside a
  single-backtick inline code span rather than a ``` block (" the literal `<!-- doc-provenance:
  start -->` delimiter"). A block-fence-only strip leaves that survive, which pulled this file
  into tag-scanning and surfaced an unrelated 10-year-old-in-project-time false positive: a
  fence-mutation-test transcript earlier in the same file, documenting a literal
  `#fenced-code-tag` test string, whose own run of stray ``` markers happened to leave it
  unstripped by the simple toggle. Found by running the gate against the real committed tree
  after writing this very paragraph, not by inspection — exactly the self-referential trap this
  file's own "Candidate table" section above calls out for the corpus measurement, now showing
  up in the gate too. Fixed by stripping inline code spans in the real-block check as well
  (the same two-step strip `scan_file` already uses), which is the more general fix and the one
  that should have been there from the start, since "a quote survives one stripping step but not
  two" was never a property specific to fenced examples.

### Implementation Summary — Topic-tag vocabulary approved and generated (2026-10-08)

The seven-tag vocabulary the user approved on 2026-10-08 (`#audio-playback`, `#audio-volume`,
`#speech-synthesis`, `#speech-recognition`, `#push-to-talk`, `#cockpit-manipulation`,
`#intercom`) written into `docs/TAGS.md`, and the generator run for real — no further proposing,
measuring-for-admission, or pattern tuning; the vocabulary was handed over final. Every hardware
designator (`#SPU-8`, `#NET-1`, `#NET-2`, the Soviet/DCS unit designators) is recorded as
deliberately excluded, in the user's own words, so it is not re-proposed.

### Files Changed

- `docs/TAGS.md` — replaced the "None approved yet" Topic tags section: the "Deliberately
  excluded" paragraph (designators, user's own quotes), a fourth rule ("a tag's pattern must
  include the concept's common shorthand" — PTT/STT/ASR/TTS/ICS, with `#field-of-view`/`FOV`
  named as a future illustrative example), a stated band exception under rule 2 (shorthand reach
  can legitimately push a candidate over 25 units — `#push-to-talk`'s 29 is why), and the seven
  tags' own sections in the file's existing one-section-per-tag format. The Format
  sub-section's worked example was changed from `#SPU-8` (now excluded) to the illustrative,
  unapproved `#field-of-view`, so the file no longer demonstrates its own format convention with
  an example it elsewhere says must never be proposed.
- 29 documents — every file `doc_provenance.py refresh` regenerated: the 22
  `audio-adapter/ROADMAP/AA-*.md` entries (20 gained a non-empty `**Topics:**` line; AA-1.4 and
  AA-5/AA-B1/AA-B2 stay topic-less, correctly — their prose matches none of the seven) and the 13
  documents already carrying a `doc-provenance` block from Stage A0 (3 research notes, 4
  acceptance cards, 4 plan.md files, matching Stage A0's own set). No file outside that 35-unit
  scope was touched — `build_target_map`'s own citation-driven target set is exactly Stage A's
  scope, so "generate only in scope" needed no extra gating beyond running the existing generator.

### Tests Added

None — this stage writes vocabulary and runs the existing generator/gates; no new code paths.
`audio-adapter`'s own suite (222 passed, 1 skipped) re-run unchanged as a touched-subproject
check, since the 29 regenerated files include 22 of its own `ROADMAP/` entries and `ruff`/`mypy`
scope includes `src`/`tests`, neither of which this stage edited.

### Checks

(audio-adapter — the only subproject whose own code tree this stage could plausibly affect,
since the change is entirely to Markdown vocabulary/provenance documents)
- ruff format --check: pass (29 files already formatted)
- ruff check: pass
- mypy --strict: pass (15 source files)
- pytest -q: pass (222 passed, 1 skipped)

Mechanical gates (not subproject-specific, run repo-root):
- `doc-provenance-gate.sh`: OK
- `roadmap-tag-vocabulary-gate.sh`: OK
- `roadmap-entry-consistency-gate.sh`: OK
- `push-roadmap-gate.sh`: OK (needs `CLAUDE_PROJECT_DIR` set; unbound-variable otherwise — not a
  regression from this change, the script reads it unconditionally)
- `graphify-dirty-flag.sh`: OK
- `bash -n` on every touched/invoked shell script, `python3 -c ast.parse` on `doc_tags.py` and
  `doc_provenance.py`: all pass. No `.sh`/`.py` file was edited this round — only `docs/TAGS.md`
  and the 29 generated Markdown files — so these are confirmation checks, not regression checks.
- Idempotency: `doc_provenance.py refresh` run twice; second run reported "nothing to change",
  `git status --porcelain` identical before/after the second run.
- Gate-fails-loudly demonstration: hand-edited `AA-1.md`'s `**Topics:**` line to add
  `#not-a-real-tag`. `roadmap-tag-vocabulary-gate.sh` failed naming the file and tag;
  `doc-provenance-gate.sh` failed separately, printing the exact diff back to the approved state.
  Restored by hand to `#speech-synthesis` alone; both gates passed again; `git diff --stat`
  confirmed the file was back to its pre-mutation generated state (4 lines added net, matching
  the original refresh).

### Notable Discoveries

- **The four expected-shape documents named in the task matched exactly**, with no pattern
  adjustment: `2026-10-05-spu8-intercom-write-path-recon.md` →
  `#cockpit-manipulation #intercom`; `2026-10-05-spu8-intercom-sortie.md` →
  `#audio-playback #audio-volume #push-to-talk #intercom`;
  `2026-09-19-whisper-model-sweep.md` → `#speech-recognition #push-to-talk`;
  `2026-09-18-stage6-sortie.md` → `#speech-synthesis`.
- **`load_approved_topic_tags`/`load_approved_tags` wrap a tag's whole `Matches:` string in
  `\b...\b` without adding a grouping `(...)`.** For a top-level alternation with no enclosing
  parens (`#audio-playback`'s, `#audio-volume`'s, `#cockpit-manipulation`'s patterns, as given —
  none of the three wrap their own alternatives in parens), regex `|` has lower precedence than
  the added `\b`, so only the *first* alternative gets a leading boundary and only the *last* gets
  a trailing one; the inner alternatives get no boundary enforcement at all. The three patterns
  that already self-wrap in parens (`#speech-synthesis`, `#speech-recognition`, `#push-to-talk`,
  and `#intercom`'s own `(intercom|\bICS\b)`) are unaffected. This did not produce any observed
  false positive against the real corpus (the false-positive spot-check below found none), but it
  means the *effective* matching behavior for those three tags is "first/last alternative
  boundary-checked, middle alternatives substring-matched" rather than the fully-boundary-checked
  behavior the inner-pattern convention implies elsewhere in this file. Not changed here — the
  patterns were handed over approved and final, and the task's own measured counts (produced by
  `grep -E` against the bare pattern, per the task's header) did not go through this wrapping
  either, so the approved counts and the generator's live behavior are consistent with each
  other; it is the *literal* `\b`-wrapping mechanism in `doc_provenance.py`/`doc_tags.py` whose
  precedence quirk is worth knowing about before writing a future pattern with top-level
  alternation and assuming the wrapper parenthesizes it.
- **The repo-wide drift check (`doc_tags.py propose`) already shows two of the seven tags
  outgrowing the band**: `#push-to-talk` 29→32 units and `#speech-recognition` 21→28 units,
  both now `TOO BROAD` by the drift check's own flag, measured minutes after admission on the
  same tree. Not acted on here — the vocabulary was handed over approved and final, "do not
  re-measure for admission" — but the drift is real and fast, and whoever next runs
  `doc-tags-propose.sh` will see both flagged. Worth deciding soon whether the growth is more
  shorthand reach (same exception already recorded for `#push-to-talk`) or genuine scope creep
  into unrelated documents.
- **`docs/TAGS.proposals.md` needed no change.** Re-running `doc-tags-propose.sh` to get the
  drift-check regenerated it byte-identically (`git diff` empty) — its own top-12 candidate list
  (`#SPU-8`, `#NET-1`, `#NET-2`, …) is unaffected by this round's approvals, since none of the
  seven approved tags appear in it. Left as the regenerated file rather than hand-edited or
  deleted; its own header already says what to do with it next (delete unwanted rows, promote the
  rest by hand) and nothing here changes that guidance.

## 2026-10-09 — Stage 2: `body-layer/ROADMAP.md` split (the stress test)

### Implementation Summary

Converted `body-layer/ROADMAP.md` (2431 lines, 68 checkbox entries, the highest-churn document
in the repo) into one file per entry under `body-layer/ROADMAP/`, per the plan's Stage 2
steps 1-5. `body-layer/ROADMAP.md` is now the 4-line pointer. Done mechanically with a
line-range-extraction Python script (written to the scratchpad, not committed) rather than by
retyping content by hand, specifically to avoid the transcription risk the task flagged as the
highest-value check — every entry file's text is a verbatim slice of the original file's own
lines, not a re-derived paraphrase.

**Folding the debt list.** All 19 "Live acceptance debt" entries were folded into their Status
counterpart (or minted standalone where no counterpart existed) rather than becoming separate
entry files — reusing `#needs-flight` plus the index's grep recipe, per the plan's design. Two
debt entries were pure cross-subproject pointers with no body-layer-owned content
(`feature/dcs-driven-los` → world-model's own entry; `feature/spu8-intercom` → audio-adapter's
`AA-3`) and were folded into the index's "Live acceptance" section as prose rather than minted as
entries — there was nothing body-layer-specific left to put in a file once the pointer was
followed.

**Checkbox vs. flight-status, disentangled.** The source document used `[ ]` throughout the debt
list to mean "not yet flown," conflating code-completion status with flight status. Converting,
every entry's checkbox now reflects code-completion state (`[x]` once merged/DoD-passed) and
`#needs-flight` carries the flight-debt separately — matching the pattern already established by
Stage 1's `AA-2`/`AA-5` (`#status/done #needs-flight` on an entry whose code is finished but
unflown). This was a judgement call, not mechanical: it resolves the "doubling" the plan's own
"The debt-list entries are two different things" section predicted, but it does mean several
entries' checkbox differs from the symbol the source document used for the same content.

### The ID scheme, at full stress

**Minted `BL-W1`…`BL-W38`, in document order** (first point in the document where each resulting
entry's content appears) — not the plan's estimated ~27. The plan's figure assumed a tighter fold
than turned out correct once every entry was actually read: several "debt-list items" (the
2026-09-25 sortie-closure records, the F10-vocabulary closure, the "two things waiting on the
user's machines" closure) are themselves distinct historical records with no separate Status
entry to fold into, and each needed its own ID rather than disappearing into another entry.
Reported as a discovery below, not silently absorbed — this is exactly the kind of "the plan's
test-impact list is a hypothesis" gap the role brief asks to report.

`BR-1`/`BR-2`: only `BR-1` exists in this file, as two stages (`BR-1.1`, `BR-1.2`); no bare `BR-1`
parent file was minted, since neither stage's own content named a separate overview paragraph to
put in one — the index groups them under a plain "BR-1" prose label instead, matching how
`mission-interpreter`'s complete-with-no-further-action milestones are handled. `BL-B23` (already
backlog-numbered) and the ten pre-existing bare `BL-<n>` milestones keep their own IDs unchanged.

### Where I did NOT resolve a contradiction

**One real contradiction found, flagged `**OPEN**`, not silently fixed**: `[[BL-W12]]` (group
cohesion redesign)'s own source text says, in the same paragraph, both "Merged to main 2026-10-01
as `ff7934e`" and "**Not merged as of this entry** — pending the user's acceptance call." Both
sentences are reproduced verbatim in the entry file. I could resolve the underlying *fact*
mechanically (`git merge-base --is-ancestor ff7934e HEAD` confirms it is merged — the "not merged"
sentence is stale leftover text), and said so in the entry, but did not edit the contradiction out
of the document itself, per the task's explicit instruction not to resolve a disagreement found
during conversion.

**Zero `**USER**` items.** The plan named `fix/contact-report-flood` as a "known case" of
disagreement (its "doubling" section: a `[ ]` debt entry against an `[x]` Status entry for the
same work). Read closely, the two records agree on every fact — both say "DoD PASSED, merged
2026-10-05, not yet flown" — and the Status entry explicitly says "see the debt entry above," i.e.
it knows it is the same record. That is the checkbox-convention doubling the previous section
describes, not a factual disagreement, so it was folded without a flag. The same is true of the
other five pairs the plan's "doubling" section names (`silence`, `fix/redundant-group-disclosure`,
the position-belief-runaway fix, `feature/dcs-driven-los`): in every case the debt-list entry is
simply the more recent of two time-ordered records (e.g. "ACCEPTED 2026-10-09" superseding an
earlier "live acceptance still outstanding"), not a dispute about what happened. `BL-W12` above is
the one case this document actually contains that meets the bar of "the same document asserts two
different things" — found by reading every entry's full text rather than trusting the plan's named
example, which turned out not to be one.

### Corpus ceiling

Already breached before this stage touched anything: `graph-corpus-files.sh` emitted 204 files
against the 200 ceiling, from Stage 1 (audio-adapter) alone. Measured post-conversion count: 263.
Raised the ceiling 200 → 300 in `graph-corpus-guard.sh`, with a comment recording the pre-existing
breach, the measured count, and the expectation that Stage 3 (`body-layer/BACKLOG.md` +
`todo/backlog.md`, ~77 more entry files per the plan) will need it raised again.

### Read-cost measurement

Session Start with body-layer active: old file 49,076 tokens (`wc -c`/4) → pointer (114) + index
(1,692) + one median entry (565) ≈ 2,371 tokens — a 95% cut, larger than the plan's projected 78%
across all subprojects combined, consistent with body-layer's `ROADMAP.md` having been the single
largest file converted so far.

### Checks

- `.claude/scripts/roadmap-entry-consistency-gate.sh`: OK (after fixing one self-inflicted false
  positive — the index's own prose example text `` [[link]] `` read as a real wikilink; reworded
  to "a wikilink" in prose, and after adding the four `BL-W3`–`BL-W6` index rows I'd initially
  omitted).
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh`: OK.
- `.claude/scripts/doc-provenance-gate.sh`: OK (no provenance blocks added — out of this stage's
  scope by instruction).
- `push-roadmap-gate.sh`'s regex and `graphify-dirty-flag.sh`'s regex both confirmed matching
  `body-layer/ROADMAP/*.md` paths directly (Stage 0's fixes were already in place on `main` before
  this stage started; nothing to repair here).
- `graphify-dirty-flag.sh` confirmed firing on a staged edit touching the new entry files (60
  doc(s) changed recorded in `graphify-out/.needs_update`).
- body-layer's own commands (from inside `body-layer/`, using the main checkout's `.venv` since
  this worktree has none of its own — gitignored, not copied): `ruff format --check .` (1 file
  flagged, `research/2026-10-05-security-audit.md`, confirmed pre-existing on `main` and untouched
  by this stage), `ruff check .` (clean), `mypy src` (clean, 54 files), `pytest -q` (1551
  passed / 4 xfailed) — all unchanged from baseline, as expected for a docs-only change.

### Notable Discoveries

- **The plan's estimate of 27 new IDs for this stage was off by 11** (38 minted) — see "The ID
  scheme, at full stress" above. The gap is specifically in the debt-list fold: the plan's own
  "~6 genuine duplicates" estimate for the whole debt list undercounted how many debt-list entries
  are *not* duplicates of a Status entry at all, but self-contained historical records (sortie
  closures, a vocabulary-closure note) that needed their own file regardless.
- **The 68-checkbox count the task stated matched exactly** (19 debt-list + 49 Status), which is
  a useful cross-check that no top-level entry was missed during extraction — confirmed
  independently via `grep -n '^- \['`.
- **A rebase-driven worktree mismatch was caught and corrected before any entry was written**: the
  worktree's `HEAD` (`29217c0`) was a strict ancestor of the task's named tip (`b7faa4d`, 7
  commits ahead, mostly Stage 1's own agent-memory/gate-tuning commits); fast-forwarded per
  AGENTS.md rule 4 before reading anything, so none of this stage's work was done against the
  stale copy the task warned a prior attempt had hit.

---

## 2026-10-09 — Stage 3: `body-layer/BACKLOG.md`, `todo/backlog.md` and `todo/todo.md`

### Implementation Summary

Three entry-list documents converted to one file per entry, using Stage 2's method unchanged:
every entry file's body is a **verbatim line-range slice** of its source, extracted by a Python
script written to the scratchpad (not committed), never retyped. The only text a conversion added
to a source line was one `#status/*` tag after the leading bold span, plus — in exactly two cases,
both recorded below — a `[ ]` checkbox marker on a source bullet that had none.

| source | entries | directory | index | pointer |
|---|---|---|---|---|
| `body-layer/BACKLOG.md` (1543 lines) | 46 | `body-layer/ROADMAP/BL-B*.md` | `body-layer/ROADMAP/body-layer-backlog.md` | yes |
| `todo/backlog.md` (1169 lines) | 34 | `todo/backlog/X-B*.md` | `todo/backlog/todo-backlog.md` | yes |
| `todo/todo.md` (472 lines) | 24 | `todo/todo/X-T*.md` | `todo/todo/todo-tasks.md` | yes |

**Zero new `BL-B<n>` and zero new `X-B<n>` were minted** — fewer than the plan's "two new IDs
total" for this stage, and fewer than the task's "at most one each". Both would-be mints turned out
to be an existing entry's own superseded text rather than a new item; see "Mints" below. 24 `X-T<n>`
were minted, which is a new ID space rather than an extension of an existing one.

### The full ID mapping

**`body-layer/BACKLOG.md` → `body-layer/ROADMAP/<ID>.md`.** Every item already carried its ID, so
the mapping is the identity on 46 IDs (`BL-B1`…`BL-B46`) with two structural exceptions:

- **`BL-B34` holds two checkbox blocks.** The source had `BL-B34` (`[x]`, resolved 2026-10-06)
  immediately followed by a block headed `BL-B34 (original text)` (`[ ]`) — the same ID twice,
  deliberately, because the resolution contradicted the original finding's premise. The filename is
  the ID alone, so both blocks live in `BL-B34.md` in source order with their original states
  untouched. This was the plan's one candidate for a `BL-B47` mint; it is not a separate item.
- **`BL-B23` was reconciled, not extracted.** Stage 2 had already created
  `body-layer/ROADMAP/BL-B23.md` from `body-layer/ROADMAP.md`'s own `BL-B23` row. See "The one
  reconciliation" below.

Source-order note: the source listed `BL-B30` and `BL-B31` ahead of `BL-B29`, and `BL-B29` sits
between `BL-B31` and `BL-B32`. Nothing was renumbered; the index lists numerically and says so.

**`todo/backlog.md` → `todo/backlog/<ID>.md`.** Identity on 34 IDs (`X-B1`…`X-B34`). `X-B31` sits
in the source between `X-B4` and `X-B5` because it falls out of `X-B4`; the index preserves that
placement under the 2026-09-25 heading and explains why. `X-B27` holds two checkbox blocks (see
"Mints").

**`todo/todo.md` → `todo/todo/X-T<n>.md`**, minted in document order:

| ID | source lines | state | title |
|---|---|---|---|
| `X-T1` | 25–29 | `[ ]` | Fly the contact/terrain sortie — **USER** |
| `X-T2` | 30–32 | `[ ]` | `/explore` the location-fragment rewrite — **USER** |
| `X-T3` | 58–63 | `[x]` | Player bubble: unit detection bounded to 10 km |
| `X-T4` | 71–110 | `[ ]` | Grouping is the priority — every unit gets its own callout |
| `X-T5` | 111–132 | `[ ]` | Free text reaches the brain and comes back "Unable" |
| `X-T6` | 142–149 | `[~]` | Crossings are announced for contacts he cannot see |
| `X-T7` | 150–160 | `[~]` | Binoculars are barely used |
| `X-T8` | 161–211 | `[~]` | The confirm band asks a question nothing can answer |
| `X-T9` | 212–221 | `[x]` | "full scan" vs "scan full" — no defect |
| `X-T10` | 244–253 | `[x]` | Route crew-text speech callouts to the in-game overlay |
| `X-T11` | 254 | `[x]` | Create the integrity audit skill |
| `X-T12` | 255–257 | `[x]` | Claude workflow changes — auto-advance and autonomy criteria |
| `X-T13` | 258–265 | `[x]` | Roadmap restructure, 2026-09-10 |
| `X-T14` | 266–279 | `[x]` | Enable `performance-reviewer` and `security` in the sequence |
| `X-T15` | 283–334 | `[>]` | Model the 9K113 Raduga-Sh as a selectable optic |
| `X-T16` | 338–354 | `[x]` | Probe the mission-sandbox bridge |
| `X-T17` | 358–380 | `[x]` | Remove `F10_SCAN_RADIUS_M` and make a sector scan unbounded |
| `X-T18` | 381–401 | `[>]` | Anchored limited scan |
| `X-T19` | 407–415 | `[x]` | Show where Petrovich is looking |
| `X-T20` | 416–433 | `[x]` | Scan and Watch must be standing modes |
| `X-T21` | 434–439 | `[x]` | Callouts must not be backlogged |
| `X-T22` | 440–456 | `[x]` | Aggregate repetitive callouts |
| `X-T23` | 457–463 | `[ ]` | No identification on a very close pass |
| `X-T24` | 464–466 | `[ ]` | 16 s flank revisit |

### Mints: both candidates were an existing entry's own superseded text

The plan budgeted one mint per backlog file. Both turned out not to be items, and the reason is the
same shape in each case — a source entry that keeps its own earlier text in place, introduced by a
sentence saying so:

- **`todo/backlog.md`'s un-IDed checkbox at line 844** (*"Measure the line-of-sight call rate per
  poll before considering a world-model service split"*) is immediately preceded by `X-B27`'s own
  closing line: *"Original item follows, kept because its reasoning is what the decision rests
  on."* It is `X-B27`'s pre-decision form, so it was folded into `X-B27.md` as a second block with
  its `[ ]` state untouched, and **no `X-B35` was minted**. The highest `X-B<n>` is still `X-B34`.
- **`body-layer/BACKLOG.md`'s `BL-B34 (original text)`** is the same pattern made explicit in the
  heading itself. No `BL-B47` was minted.

**The lesson for Stages 4 and 5**, since world-model's roadmap is known to carry duplicated debt
entries: *count un-IDed blocks only after reading the line above them.* A naive count of
`^- \[` lines against the ID list reports one mint owed in each of these files, and in both cases
minting would have created a second ID for text that is already an entry's own history — which the
never-renumber rule then makes permanent.

### The one reconciliation: `BL-B23`

`body-layer/ROADMAP/BL-B23.md` already existed (Stage 2, from `body-layer/ROADMAP.md`'s own row).
`body-layer/BACKLOG.md` carried its own `BL-B23`. **The two agree on every fact** — `[x]`, fixed on
`fix/contact-store-pruning`, merged 2026-10-02, same mechanism, same 403 ms → 1.4 ms result — so
there is no contradiction and **no flag was added**.

They are not duplicates either, because each holds material the other does not: the roadmap's copy
has the sign-off trail, the acceptance-boundary reasoning and the milestone-completion answer; the
backlog's copy has the full pre-fix measurement sweep (22→1200 contacts), the fix-shape reasoning as
written *before* the fix, and the player-bubble interaction note. **Both are kept verbatim**, the
backlog's appended below the roadmap's, with a prose note at the junction saying which came from
where and why neither was dropped. Keeping only "the fuller text" would have lost real content in
either direction.

One consequence: `BL-B23` is now a backlog entry living in a directory with two indexes, and the
consistency gate requires exactly one index link per entry. Its `[[BL-B23]]` row was removed from
`body-layer-roadmap.md` and replaced with a plain-prose mention at the same position in that
workstream's sequence, so the narrative order survives without a second link.

### `**USER**` items, and the one judgement call behind them

**Two `**USER**` entries, both new and both from `todo/todo.md`'s *"Owed by the user, nothing else
blocks them"* section:**

- **[[X-T1]] — Fly the contact/terrain sortie.** Card
  `https://claude.ai/artifact/VJZnmdF3aqxhVGZea3iKN4`, branch `main`. Covers contact-flood
  suppression, group-disclosure silence and the `"next valley"` terrain qualifier, whose half *"has
  never been confirmed heard"*.
- **[[X-T2]] — `/explore` the location-fragment rewrite** (item 1 of
  `plans/sortie-2026-10-05-refinements/`) before anything is built.

**Neither was a checkbox item in the source** — both were prose bullets. The task's stated exception
allowed promoting them, and I did, for three reasons: they are real outstanding work rather than
orientation; they are the highest-priority items in the file that root `CLAUDE.md` sends every
session to; and as prose inside a dated narrative they were neither linkable nor greppable by ID.
Promoting each required minting its `[ ]` marker, which is the only text added to the source bullet,
and each entry says so in its own body. The index **links** to them rather than repeating their
text, so there is still exactly one copy — including in the *"Owed by the user"* paragraph itself,
which now reads as two links.

**Zero `**OPEN**` items.** No source entry in any of the three files contradicted itself or another
record. `BL-B23`'s two copies agree (above), and `BL-B34`/`X-B27`'s two blocks are an item and its
own superseded text, which the source labels as such — that is a time-ordered record, not a dispute,
the same distinction Stage 2 drew for the five pairs the plan had named.

### Judgement calls on `todo/todo.md`, each recorded because none was mechanical

1. **Narrative orientation prose stayed in the index, verbatim.** The preamble, the `## User
   priority tasks` framing, the whole `### Where things stand, 2026-10-05 end of day` section, the
   `### Where the state of play lives — not here` section, the per-section prose under three sortie
   headings, and the `## Cross-cutting / unscoped backlog` tail. 68 of the source's 399 non-blank
   lines are this material; all 68 are in the index. This is now written into
   `docs/DOC_CONVENTIONS.md` as a rule, because it is the first conversion that had prose *between*
   entries rather than only a preamble and a tail.
2. **Section headings became index sections**, preserving which sortie produced which finding —
   information that is a relation between entries and so cannot live in any one of them.
3. **Priority items are first and marked.** Root `CLAUDE.md`'s Session Start step 2 and its Backlog
   Management section both send every session here for User priority tasks, so the index opens with
   the two `**USER**` items, then a one-line pointer to the next open ones, before any narrative.
4. **The index is `todo-tasks.md`, not `todo-todo.md`.** Both avoid collision; the first reads as a
   name rather than a stutter. This required adding `*-tasks.md` to the consistency gate's index
   glob — see "Consumer scripts" below.
5. **Five `[x]` items at source lines 244–279 had no heading of their own**, sitting under the
   state-of-play section with a blank-line gap. Grouped in the index under a new `### Done —
   process and workflow items` heading, with a note saying the heading is the conversion's and not
   the source's.
6. **Four entries have no bold lead at all** (`X-T10`–`X-T13` are plain `- [x] prose` rows). Their
   `#status/*` tag went at the end of the checkbox's own physical line, which still satisfies the
   convention's "same line as its checkbox marker" rule.

### Fidelity accounting

Verified mechanically: a multiset comparison of every non-blank line of each original (read from
`git show HEAD:<path>`) against the new corpus, with inserted `#status/*` tags stripped. Every
original line is either present verbatim or named below.

| source | non-blank lines | not carried verbatim | what they are |
|---|---|---|---|
| `body-layer/BACKLOG.md` | 1308 | **12** | H1, the three-paragraph split rationale, the two ID-rule paragraphs — all rewritten into the index preamble, and the rationale additionally into the pointer |
| `todo/backlog.md` | 983 | **17** | H1, preamble (5 paragraphs), and the three `### Added <date>` headings — headings became index sections, preamble rewritten into index + pointer |
| `todo/todo.md` | 399 | **12** | H1; the `../ROADMAP.md` preamble line (now `../../ROADMAP.md`, one directory deeper); `**Owed by the user…**` (now two links); six lines whose backticked `BL-B26`–`BL-B31`/`X-B29` mentions became `[[wikilinks]]`; the tail's closing sentence, extended to name the new backlog index |

**No entry body was paraphrased.** The 12/17/12 lines above are all index or pointer prose, where
the convention requires rewriting (a preamble describing "this file" has to describe the new shape),
plus the wikilink conversions.

**95 cross-references linked** across the three new sets, by script, restricted to IDs that resolve
to a real entry file in a converted directory — so mentions of `WM-B8`, `M11`, `AC-B5` and the like
stayed plain prose, per the convention.

### Consumer scripts: two needed fixing, three did not

Checked each script's own globs against the real new paths rather than assuming recursion:

| script | `body-layer/ROADMAP/BL-B*.md` | `todo/backlog/*.md` | `todo/todo/*.md` | action |
|---|---|---|---|---|
| `graph-corpus-files.sh` | covered (`find "$sub/ROADMAP"`) | covered (`find todo`) | covered (`find todo`) | none |
| `graphify-dirty-flag.sh` | covered (`[^/]+/ROADMAP/[^/]+\.md`) | covered (`^todo/`) | covered (`^todo/`) | none |
| `push-roadmap-gate.sh` | covered | **not matched** | **not matched** | none — see below |
| `roadmap-entry-consistency-gate.sh` | covered | covered | **missed entirely** | fixed |
| `roadmap-tag-vocabulary-gate.sh` | covered | covered | **missed entirely** | fixed |

- **`push-roadmap-gate.sh` deliberately unchanged.** Its pattern is
  `(^|/)ROADMAP(\.md|/[^/]+\.md)$`, which never matched `todo/backlog.md` or `todo/todo.md` either
  — the gate's job is "a *subproject roadmap* was touched in the same push as a feature merge", and
  the `todo/` files were never that. Verified by running the real pattern over the real paths rather
  than reading it. One incidental gain: moving body-layer's backlog into `ROADMAP/` means
  `body-layer/ROADMAP/BL-B1.md` now satisfies the gate, which `body-layer/BACKLOG.md` did not.
- **`roadmap-entry-consistency-gate.sh`** discovered `*/ROADMAP` plus a hardcoded `todo/backlog`,
  so `todo/todo/` was invisible: a dangling link or an orphaned entry there would have passed
  silently. Now both `todo/` directories are named in one loop. Its index glob also gained
  `*-tasks.md`; without that, all 24 `X-T` entries would have reported as linked from zero indexes.
- **`roadmap-tag-vocabulary-gate.sh`** had the same hardcoded `todo/backlog` and the same fix.

**Both fixes were proven by mutation, not by a passing run** (a gate that silently skips a directory
also passes):

| mutation | gate output | restored |
|---|---|---|
| `[[X-T999]]` + `[[BL-B999]]` appended to `todo/todo/X-T24.md` | both reported dangling, exit 1 | `shasum` back to `4820f8e…` |
| `- [[X-T21]]` row deleted from `todo-tasks.md` | `X-T21.md is not linked from any index`, exit 1 | `shasum` back to `947bc6f…` |
| `#topic/not-in-vocabulary` appended to `todo/todo/X-T24.md` | `tag … not listed in docs/TAGS.md`, exit 1 | `shasum` back to `4820f8e…` |

### Corpus ceiling

`graph-corpus-files.sh` emits **369** files post-conversion (104 new entry files + 2 new indexes
against Stage 2's 263). Ceiling raised **300 → 420** in `graph-corpus-guard.sh`, with the measured
count and the ~14% headroom recorded in its own comment — the same margin Stage 2 chose, and
deliberately not pre-raised for Stages 4 and 5, which will need it raised once more. Guard
re-run: `graph-corpus-guard: OK — 369 files (ceiling 420)`.

All three new directory shapes confirmed present in the emitted corpus: 46 `body-layer/ROADMAP/BL-B*`,
35 `todo/backlog/*`, 25 `todo/todo/*`.

### Read-cost measurement

Bytes/4, pointer + index + **median** entry against the whole original file:

| source | before | after | saving |
|---|---|---|---|
| `body-layer/BACKLOG.md` | 28,408 | 2,078 (pointer 232 + index 1,498 + median entry 348) | **93%** |
| `todo/backlog.md` | 21,372 | 2,088 (206 + 1,420 + 462) | **90%** |
| `todo/todo.md` | 9,090 | 2,720 (206 + 2,261 + 253) | **70%** |
| all three | 58,870 | 6,886 | **88%** |

The plan projected "another 45.5k tokens off the common read" for the first two; measured is 45.6k.
`todo/todo.md`'s 70% is the lowest of the five files converted so far, and for a structural reason
worth recording: its index is 2,261 tokens, **larger than its median entry by a factor of nine**,
because the orientation narrative that has to stay in the index is a quarter of the document. A
file that is mostly narrative does not split as profitably as one that is mostly entries — which is
a reason to keep splitting entry lists and not to go looking for narrative documents to split.

### Checks

- `.claude/scripts/roadmap-entry-consistency-gate.sh`: **OK**
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh`: **OK**
- `.claude/scripts/doc-provenance-gate.sh`: **OK** (zero provenance blocks added — out of scope by
  instruction; a pass with zero blocks is the expected result)
- `.claude/scripts/graph-corpus-guard.sh`: **OK**, 369/420
- `bash -n` on all three edited scripts: clean
- body-layer, from inside `body-layer/` using the main checkout's `.venv` (this worktree has none —
  gitignored):
  - `ruff format --check .`: **1 file would be reformatted** — `research/2026-10-05-security-audit.md`,
    the known pre-existing one. Confirmed as `main`'s: `git diff --stat main --` on that path is
    empty, i.e. the file is byte-identical to `main` (`29217c0`) and untouched by this stage.
  - `ruff check .`: **All checks passed**
  - `mypy src`: **Success: no issues found in 54 source files**
  - `pytest -q`: **1551 passed, 4 xfailed** — identical to Stage 2's baseline, as expected for a
    docs-only change.

### Places that name `todo/todo.md` or `todo/backlog.md` by path

**Not edited** — the pointers keep every one of them resolving, and root `CLAUDE.md`/`AGENTS.md` are
the user's to reword. Listed so that decision can be made from a complete set:

| file | lines | what it says |
|---|---|---|
| `CLAUDE.md` | 53, 92, 348, 369, 383 | "Current priority"; Session Start step 2; Backlog Management opener; the `X-B<n>` prefix table; the moves-between-files rule |
| `.claude/scripts/session-start.sh` | 17, 66 | the injected Session Start reminder's step 2 |
| `.claude/scripts/status-page-refresh.sh` | 89 | names `todo/todo.md` among the page's sources |
| `.claude/scripts/graph-corpus-files.sh` | 60 | a comment about the case-insensitive `*/BACKLOG.md` glob |
| `.claude/skills/merge/SKILL.md` | 48, 77 | "only touch `todo/todo.md` / `todo/backlog.md` if …" |
| `.claude/skills/status-page/SKILL.md` | 11, 49, 64 | the page's source list and the forward-only map |
| `.claude/skills/explore/SKILL.md` | 69 | the out-of-corpus `grep` recipe |
| `.claude/skills/integrity-audit/SKILL.md` | 3, 28, 65 | its description and read list |
| `.claude/agents/architect.md` | 3, 140 | its description; *"do not start tasks marked `[?]` in todo/todo.md"* |
| `.claude/agents/dod.md` | 193 | "only touch `todo/backlog.md` if …" |
| `docs/status/README.md` | 25, 26 | which file carries which ids |

`AGENTS.md` itself contains **no** by-path reference to either file (the task expected one; `grep`
found none). The two highest-value rewordings, if the user wants any, are `CLAUDE.md:92` and
`.claude/scripts/session-start.sh:66` — both tell every session to *read* `todo/todo.md`, which now
means reading a pointer and following it one hop.

### Notable Discoveries

- **The dangerous consumer gap was the one the task predicted and the gate did not report.** Both
  link gates discovered split directories as `*/ROADMAP` next to a `pyproject.toml` plus a
  hardcoded `todo/backlog`. `todo/todo/` matched neither, so the gates would have passed while
  never looking at 25 files — the exact "a gate that silently skips is worse than a failing one"
  shape. A passing run was no evidence either way; only the mutation was.
- **An index whose basename fits no existing pattern is a silent orphan generator.** Check 3 of the
  consistency gate finds indexes by globbing `*-roadmap.md` / `*-backlog.md`. An index named
  anything else makes every entry in its directory report "linked from zero indexes" — loudly, in
  that case, which is the good direction. Worth knowing before Stages 4 and 5 invent a name.
- **Two of the three files' "next mint" was already taken by an entry's own history.** Recorded
  above as a rule for later stages. The tell is a sentence immediately above the un-IDed block:
  *"Original item follows"*, *"Original text follows"*, or an explicit `(original text)` in the
  bold lead.
- **A mostly-narrative document splits at 70%, not 90%+.** `todo/todo.md`'s index is nine times its
  median entry. The plan's per-file saving estimates assume an entry-dense file; that assumption is
  visible for the first time here and should temper expectations for any future document that is
  more prose than list.
- **`body-layer/ROADMAP/` now holds two indexes, and "exactly one index per entry" became load-bearing
  for the first time.** The gate's check 3 is per-directory by design and fired correctly on
  `BL-B23`'s double listing. Stage 2 could not have exercised this, since the directory had only one
  index then. Any future subproject that splits both a roadmap and a backlog into one directory
  will hit the same thing with any entry its roadmap narrative wants to mention.
- **The worktree's `HEAD` was again a strict ancestor of the named tip** (`29217c0` vs
  `4b08b52`, 1 commit behind — Stage 2's own harvest). Fast-forwarded per AGENTS.md rule 4 before
  reading anything. Worth noting that the stale commit did not contain
  `plans/obsidian-links-and-tags/implementation.md`, `docs/DOC_CONVENTIONS.md` or
  `body-layer/ROADMAP/` at all — i.e. none of this stage's primary inputs existed in the tree as
  created. That is the "a stale base is dangerous for inputs" case AGENTS.md records, met for the
  second time.

---

## 2026-10-09 — Stages 4 and 5: `world-model`, `aircraft-layer`, `mission-interpreter`

### Implementation Summary

The last three roadmaps converted, completing the set: every subproject's roadmap and backlog now
lives as one file per entry. Method unchanged from Stages 2 and 3 — each entry body is a
**verbatim line-range slice** of its source, extracted by a Python script written to the
scratchpad (not committed), never retyped.

| source | entries | directory | index | pointer |
|---|---|---|---|---|
| `world-model/ROADMAP.md` (1398 lines, 42 checkboxes) | 40 | `world-model/ROADMAP/` | `world-model-roadmap.md` | yes |
| `aircraft-layer/ROADMAP.md` (164 lines, 13 checkboxes) | 13 | `aircraft-layer/ROADMAP/` | `aircraft-layer-roadmap.md` | yes |
| `mission-interpreter/ROADMAP.md` (177 lines, 9 checkboxes) | 9 | `mission-interpreter/ROADMAP/` | `mission-interpreter-roadmap.md` | yes |

62 entry files and 3 indexes. `brain-layer/` has no `ROADMAP.md` of its own — confirmed by
listing it; its `BR-*` entries remain in `body-layer/ROADMAP/`, so nothing was owed there.

### The full ID mapping

**`world-model/ROADMAP.md`.** Three ID spaces, all irregular and all kept that way.

*Milestones — identity on 12 bare `M<n>`:* `M0` (src 183), `M1` (184), `M2` (185), `M3` (186),
`M4` (187), `M5` (188), `M6` (189), `M7` (190), `M8` (192), `M10` (204), `M9` (275), `M11`
(489–637). `M11` describes Stages 1–5 inside one checkbox item, so it stays one file — no
`M11.1`…`M11.5`, matching Stage 2's treatment of `BL-W32` ("Stages 1 through 5").

*Work items — `WM-W1`…`WM-W12` minted in document order* (first point in the document where each
resulting entry's content appears):

| ID | source lines | what it was |
|---|---|---|
| `WM-W1` | 460–487 + 16–41 | LOS elevation-tolerance fix, folded with its own debt record |
| `WM-W2` | 43–79 | `feature/dcs-driven-los` (debt list, no Status counterpart) |
| `WM-W3` | 91–125 | `fix/landform-relief-gate` (debt list, no counterpart) |
| `WM-W4` | 127–158 | `feature/terrain-landform-features` (debt list, no counterpart) |
| `WM-W5` | 160–181 | `feature/multi-theatre-afghanistan` (debt list, no counterpart) |
| `WM-W6` | 193–202 | Line-of-sight query primitive ("no M-number") |
| `WM-W7` | 221–249 + 1343–1354 | Road-junction memory fix, folded with the backlog's `RESOLVED` bullet |
| `WM-W8` | 251–260 | Road-junction progress logging ("no M-number") |
| `WM-W9` | 262–273 | HTTP API server ("no M-number") |
| `WM-W10` | 294–312 | OSM streaming-ingest memory fix ("no M-number") |
| `WM-W11` | 314–337 | OSM classified-feature persistent cache ("no M-number") |
| `WM-W12` | 339–458 | OSM ingest optimization + landcover split ("no M-number") |

Each "no M-number" entry's own parenthetical reason — *a bug fix on M10, not a milestone*, *a
cross-subproject refactor*, *a performance optimization* — is carried verbatim inside the entry,
because it is the justification for the `WM-W` ID rather than a bare `M<n>`, and the next reader
would otherwise wonder why `M9` and `WM-W10` sit next to each other.

*Backlog — identity on `WM-B1`…`WM-B14`, plus two mints:*

- `WM-B1` (644–717 + the debt record at 81–83) and `WM-B6` (783–1236 + 85–89) each absorb the
  live-acceptance-debt record that names them in its own text.
- `WM-B7` (1238–1259 + 1261–1298) holds **two checkbox blocks in one file**: the rejection and the
  `WM-B7 (original text)` block the source kept beneath it. The same ID twice in the source is one
  entry. **No `WM-B15` was minted for it** — this was the trap the task warned about, and it
  behaved exactly as Stage 3 predicted.
- `WM-B15` (1317–1341) and `WM-B16` (1356) **are mints, and they were not on the task's list.** See
  "The two mints the task did not predict" below.

**`aircraft-layer/ROADMAP.md`.** `AC-1`…`AC-8` minted in the bare space (not `AC-W<n>`), per the
convention's "no declared milestone series consuming the bare space" rule: `AC-1` (10–15), `AC-2`
(16–19), `AC-3` (20–21), `AC-4` (22–26), `AC-5` (27–32), `AC-6` (34–47), `AC-7` (48–64), `AC-8`
(66–85). `AC-B1`…`AC-B5` identity (92–104, 106–116, 118–124, 125–131, 133–164). **The task said
"count the un-IDed Status entries yourself; the plan says 8" — counted, and it is 8.** Worth
noting the plan's figure was right here while being wrong in both measured stages before it; the
difference is that aircraft-layer has no debt list to fold.

**`mission-interpreter/ROADMAP.md`.** **Zero mints, verified rather than assumed**: all nine
checkbox items already carry an ID — `MI-0` (20–26), `MI-1` (27–35), `MI-1.5` (36–44), `MI-2`
(45–57), `MI-3` (58–73), `MI-4` (74), `MI-5` (75–94), `MI-5b` (95–96), `MI-6` (97–120). `MI-5b`
keeps its letter suffix rather than becoming `MI-5.1`. `MI-4`'s single ~2000-word line is carried
as one line, unreflowed.

### The two mints the task did not predict

**The task's list of what to mint named only the "no M-number" entries and the debt-list head. It
missed three top-level prose bullets in the Backlog section** — items in every respect except that
they carry no checkbox and no ID, so `grep -cE '^- \['` never counted them and a scan for ID-shaped
leads never saw them. They were found by the boundary-derivation pass matching `^- \*\*` as well as
`^- \[`, which is the only reason they surfaced at all.

Each needed a decision, and they went three different ways:

- **`WM-B15` — Multi-theatre support (Afghanistan, Caucasus, Kola)** → promoted, `[~]`. Real
  outstanding work, actively in flight (*"Started 2026-10-04 with Afghanistan, then Caucasus, Kola
  last (user direction)"*), and it is what `WM-W5`'s Afghanistan record is a slice of. The marker is
  the conversion's; the entry says so and says where it came from. Note the source's bold lead still
  reads *"not yet scoped"*, which predates the "Started" sentence below it — carried as written.
- **`WM-B16` — Incremental per-layer pipeline builds** → promoted, `[ ]`. A distinct wanted
  capability, cited from `plans/m9-osm-geofabrik/plan.md`.
- **`RESOLVED: roadnet/junctions.py memory issue`** → **not promoted.** It is the backlog-side
  record of the fix `WM-W7` already is, agreeing with it on every fact, so minting a `WM-B17` would
  have created a second permanent ID for one piece of work — the thing the plan's whole
  debt-list argument rules out. Folded into `WM-W7` instead, keeping its original no-checkbox bullet
  form (so no marker was minted) and both copies' distinct material, with a prose note at the
  junction. Same shape as Stage 3's `BL-B23` reconciliation.

**The lesson generalises Stage 3's.** Stage 3's rule was *count un-IDed blocks only after reading
the line above them* — aimed at a block that is an entry's own history. This stage adds the
opposite error: a bullet that **is** an item but was never written as a checkbox, which no
checkbox-shaped count can see. So the enumeration has to be of every top-level bullet, then a
per-bullet judgement, not a count of `^- \[`.

### Where I did not resolve a contradiction — three `**OPEN**`, zero `**USER**`

The task predicted world-model's Status head was the most likely place yet for a real one. It was,
and there are three. All are mechanically settled rather than needing the user's judgement, so all
are `**OPEN**`; every half of every one is carried verbatim and no source sentence was edited.

1. **`AC-8`** says *"not yet merged, not yet flown"*, against `WM-W2`'s *"FLOWN 2026-10-05"* with
   101,091 live verdicts read off `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`.
   Settled by `git ls-tree main`: `aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua` is
   on `main`, and `main`'s log carries the branch's whole DoD trail (`3b904fc`). `AC-8`'s text is the
   stale half. `#needs-flight` deliberately withheld while the marker stands.
2. **`WM-B6`** carries two stale merge claims — *"merge pending (`feature/landform-geomorphons`)"*
   and *"`feature/terrain-callout-stages-345` — not yet merged"* — against the debt record folded
   into the same file and against `main`, which holds `world-model/src/terrain/geomorphons.py`,
   `world-model/src/terrain_cache/` and `world-model/src/query/divides.py`.
3. **`WM-W4`** says *"Parked 2026-10-01"* and *"Stages 3-5 … remain unbuilt"* against `WM-B6`'s own
   *"Unparked 2026-10-01, same day it was parked"* and *"Stages 3-5 built, Revision 3, 2026-10-05"*.
   `query/divides.py` on `main` settles it.

**Three pairs that look like contradictions and are not**, each checked by reading the full text
rather than by shape:

- `WM-W1`'s two records (debt `[x]` ACCEPTED 2026-10-09 vs. Status *"Unflown — see 'Live
  acceptance debt' above"*). The Status entry **points at the list it is paired with**, i.e. it
  knows it is the same record — the same self-aware doubling Stage 2 ruled on for
  `fix/contact-report-flood`. Time-ordered, not disputed.
- `WM-W2`'s own body: *"FLOWN 2026-10-05"* above *"Original entry follows … not yet merged, not yet
  flown"*. Self-labelled superseded text, the `BL-B34`/`X-B27` pattern.
- `WM-B7`'s two blocks, for the same reason.

### Fidelity accounting

Verified mechanically: a multiset comparison of every non-blank line of each original (read via
`git show HEAD:<path>`) against the new corpus, with the three transformations a conversion is
allowed to make normalised out first — an inserted `#status/*`/`#needs-flight` tag, a minted
checkbox marker, and a backticked ID rewritten as `[[ID]]`.

| source | non-blank lines | not carried verbatim |
|---|---|---|
| `world-model/ROADMAP.md` | 1235 | **0** |
| `aircraft-layer/ROADMAP.md` | 145 | **0** |
| `mission-interpreter/ROADMAP.md` | 160 | **0** |

**Zero on all three, including the H1s and preambles** — unlike Stages 2 and 3, which had 12/17/12
index-prose lines to account for. That is not a better conversion, it is a different index-building
method: the three indexes **splice their reusable source passages in verbatim by line range**
(`world-model`'s "Decisions locked in" bullets, its live-acceptance-debt preamble, its backlog
preamble and its "Not doing yet" tail; `aircraft-layer`'s preamble and backlog preamble;
`mission-interpreter`'s entire 16-line decision preamble and its whole 56-line narrative tail)
rather than being rewritten by hand around them. Worth adopting if this is ever done again: it
turns "which lines did I paraphrase" from a judgement into a measurement.

**The fidelity check was proven able to go red**, not just observed green: deleting
`world-model/ROADMAP/WM-W9.md` produced 12 MISSING lines naming that entry's own text; restored by
`shasum`, back to 0.

**56 cross-references linked**, by script, over backtick spans whose entire content is an ID
resolving to a real entry file in one of the seven converted directories (245 resolvable IDs),
skipping fenced blocks and self-references. Bare prose mentions were deliberately left alone —
world-model has several hundred bare `M5`/`M7` mentions inside paths, SQL and code examples.
Cross-subproject links now land for the first time at scale: `[[BL-11]]`, `[[X-B29]]`, `[[X-B30]]`,
`[[X-B26]]` from world-model entries, `[[WM-W2]]` from `AC-8`.

### Consumer scripts: three needed a fix, four did not

| script | reaches the three new dirs? | action |
|---|---|---|
| `graph-corpus-files.sh` | yes (`find "$sub/ROADMAP"`) | none |
| `graphify-dirty-flag.sh` | yes (`[^/]+/ROADMAP/[^/]+\.md`) | none |
| `push-roadmap-gate.sh` | yes (`(^\|/)ROADMAP(\.md\|/[^/]+\.md)$`) | none |
| `doc-provenance-gate.sh` | n/a (zero blocks added) | none |
| `roadmap-entry-consistency-gate.sh` | directory yes, **ID shape no** | fixed |
| `roadmap-tag-vocabulary-gate.sh` | directory yes, **ID shape no** | fixed |
| `roadmap-toc.sh` | directory yes, **ID shape no** | fixed |

**Discovery was proven, not reasoned** — the task's own instruction, after Stage 3 found both link
gates silently skipping 25 files. Both gates discover `*/ROADMAP` beside a `pyproject.toml`, which
does reach all three new directories; the loop was reproduced standalone and printed all seven
directories with their real counts (13 / 40 / 9 entries in the new ones, plus one index each).

**But the gap this time was not the directory, it was the ID shape, and it was half-silent.** All
three scripts spelled an entry ID `^[A-Z]+-[A-Za-z0-9.]+$`, which `M5` does not match. Widened to
`^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$`, enumerated rather than loosened to `^[A-Z]` (which
would also match a stray `README.md`). Consequence of the gap, measured against the pre-fix regex in
a scratch copy:

| check | pre-fix behaviour on a bare-`M<n>` entry |
|---|---|
| 1, dangling link | 12 **false** danglings on a clean tree — loud, caught immediately |
| 2, filename vs. H1 | wrong H1 planted in `M5.md` → reported **0 times** |
| 3, exactly one index | `- [[M5]]` row deleted from the index → reported **0 times** |

So the loud half would have been "fixed" by someone deleting twelve correct links, leaving the two
silent checks skipping twelve files permanently. **The first attempt at this counterfactual was
worthless and said so**: a `sed` expression to revert the regex failed with *"bad flag in
substitute command"*, the copied script was never written, and the harness still printed
"0 findings" — a perfect false confirmation. Redone in Python with an assertion that three sites
were actually reverted.

**Gates proven by mutation, one per new directory plus the two bare-`M<n>`-specific checks**, each
restored by `shasum`:

| mutation | gate output | restored |
|---|---|---|
| `[[M999]]` → `world-model/ROADMAP/M5.md` | dangling link, exit 1 | `621c9679…` |
| `[[AC-999]]` → `aircraft-layer/ROADMAP/AC-3.md` | dangling link, exit 1 | `f8ec3d4a…` |
| `[[MI-999]]` → `mission-interpreter/ROADMAP/MI-5b.md` | dangling link, exit 1 | `799a9259…` |
| `- [[M5]]` index row deleted | `M5.md is not linked from any index`, exit 1 | `13306581…` |
| `M5.md`'s H1 changed to `# M99 — …` | `filename ID 'M5' does not match H1 first token 'M99'`, exit 1 | `621c9679…` |
| `#topic/not-in-vocabulary` → `M5.md` | `tag … not listed in docs/TAGS.md`, exit 1 | `621c9679…` |

`push-roadmap-gate.sh` was checked by running its **real** regex over the **real** new paths, not
by reading it: all twelve sampled paths match, including the three pointers. Unlike Stage 3's
`todo/` case this is correct and wanted — these are genuine subproject roadmaps, so a feature merge
touching one now satisfies the gate.

### Corpus ceiling

`graph-corpus-files.sh` emits **434** files post-conversion (62 entry files + 3 indexes against
Stage 3's 369 — exactly the ~65 the task predicted). Ceiling raised **420 → 520**.

**Sized differently from the three previous raises, deliberately.** Each of those left ~14% for one
known-coming stage. There is no next stage, so the headroom is for ongoing growth instead: 520 is
~20% over 434, which at the plan's own ~+50 entry files/year is upwards of eighteen months, and
still nowhere near the 1182-file blowout this guard exists to catch. Recorded in the script's own
comment alongside the measured count. Guard re-run: `graph-corpus-guard: OK — 434 files (ceiling 520)`.

All three new directory shapes confirmed present in the emitted corpus: 41 `world-model/ROADMAP/*`,
14 `aircraft-layer/ROADMAP/*`, 10 `mission-interpreter/ROADMAP/*` (entries plus index each).

### Read-cost measurement

Bytes/4, pointer + index + **median** entry against the whole original file:

| source | before | after | saving |
|---|---|---|---|
| `world-model/ROADMAP.md` | 29,541 | 2,210 (pointer 166 + index 1,708 + median entry 336) | **93%** |
| `aircraft-layer/ROADMAP.md` | 3,256 | 970 (123 + 661 + 185) | **70%** |
| `mission-interpreter/ROADMAP.md` | 3,990 | 2,101 (169 + 1,628 + 305) | **47%** |
| all three | 36,788 | 5,281 | **86%** |

**`mission-interpreter`'s 47% is the lowest of the eight files converted, and it confirms Stage 3's
structural finding rather than contradicting it.** Stage 3 observed that `todo/todo.md` split at
only 70% because its index carries orientation narrative nine times the size of its median entry. In
`mission-interpreter`, 44 of 160 non-blank lines — 28% of the document — are the acceptance record
and the MI-6-goes-nowhere finding, both of which have to stay whole in the index. Its index is five
times its median entry. **A mostly-narrative document does not split profitably, and this is now
measured twice.** The plan already said the token case for Stage 5 was weak and that it was being
done on browsability grounds alone; that judgement holds up exactly.

### Checks

- `.claude/scripts/roadmap-entry-consistency-gate.sh`: **OK**
- `.claude/scripts/roadmap-tag-vocabulary-gate.sh`: **OK**
- `.claude/scripts/doc-provenance-gate.sh`: **OK** (zero provenance blocks added — out of scope by
  instruction; a pass with zero blocks is the expected result)
- `.claude/scripts/graph-corpus-guard.sh`: **OK**, 434/520
- `.claude/scripts/roadmap-toc.sh` on all three new directories: all 62 entries listed with correct
  titles and status tags, exit 0
- `bash -n` on all four edited scripts: clean

Per touched subproject, from inside each one, using the main checkout's `.venv` (this worktree has
none — gitignored). Commands as each subproject's own `CLAUDE.md` states them, i.e. scoped to
`src`/`tests`:

| | world-model | aircraft-layer | mission-interpreter |
|---|---|---|---|
| `ruff format --check` | pass (118 files) | pass (56 files) | pass (46 files) |
| `ruff check` | pass | pass | pass |
| `mypy src` | pass (72 files) | pass (21 files) | pass (31 files) |
| `pytest -q` | **565 passed, 3 skipped** | **256 passed** | **108 passed, 3 skipped** |

Docs-only change, so these are no-regression confirmations.

**A `ruff format --check .` / `ruff check .` over the whole of `world-model/` reports 7 unformatted
files and 23 lint errors** — all in `world-model/research/*.md` fenced examples and
`world-model/tools/*.py`, neither of which is in the documented command's scope. Confirmed
pre-existing rather than asserted: `git diff --stat main --` on each named path is empty, and
`git diff --name-only main -- world-model/ | grep -v '^world-model/ROADMAP'` is empty, i.e. this
branch touches nothing in that subproject outside `ROADMAP/` and `ROADMAP.md`.

### The plan's "Stop point: complete" claim, tested

The plan says: *"`ls */ROADMAP/` shows five subprojects plus `todo/backlog/`, and no file anywhere
lists which."* Run:

```
$ ls -d */ROADMAP/          $ ls -d todo/*/
aircraft-layer/ROADMAP/     todo/backlog/
audio-adapter/ROADMAP/      todo/todo/
body-layer/ROADMAP/
mission-interpreter/ROADMAP/
world-model/ROADMAP/
```

**The first half holds, for the predicted reason.** Five, not six, because `brain-layer/` has no
roadmap of its own and its `BR-*` entries live in `body-layer/ROADMAP/` — which is what the plan's
Stage 2 step 4 decided and what `body-layer-roadmap.md` says in its own index line.

**"plus `todo/backlog/`" understates it:** there are two directories under `todo/`, because the user
overrode the plan's scope table and Stage 3 split `todo/todo.md` as well.

**The second half does not hold.** `grep` finds one file that lists which subprojects are converted:
**root `CLAUDE.md` line 367**, in the Backlog Management prefix table —

```
| `AA-B<n>` | `audio-adapter/ROADMAP/` (split; `audio-adapter/ROADMAP.md` is now a pointer) |
```

— which names audio-adapter as the split one and, by omission, implies the other four are not. It
was accurate the day Stage 1 wrote it and is now wrong about five subprojects: it is exactly the
stale-list failure `docs/DOC_CONVENTIONS.md`'s own opening paragraph warns about, in the file that
sends every session to read it. Four sibling rows in the same table (`BL-B<n>` →
`body-layer/BACKLOG.md`, `AC-B<n>` → `aircraft-layer/ROADMAP.md`, `WM-B<n>` →
`world-model/ROADMAP.md`, `X-B<n>` → `todo/backlog.md`) now point at 4-line pointers. **Nothing is
stranded** — every pointer is kept and resolves — but each row reads as if that file holds the
items. **Not edited**: root `CLAUDE.md` is out of this stage's scope by instruction, and the
rewording is the user's call. The smallest correction that would make the table honest is to drop
the parenthetical from the `AA-B<n>` row entirely and let `ls */ROADMAP/` answer, which is what the
convention doc already prescribes.

No script hardcodes a converted-subproject list — checked, and every one either discovers the
directories or keys off the `<!-- split-roadmap: see ROADMAP/ -->` sentinel.

### Notable Discoveries

- **An irregular ID space is a standing tax on every consumer that has to recognise an ID, and the
  bill arrives late.** `M<n>` was accepted as "recorded, not fixed" in Stage 1's convention doc, at
  a time when no consumer had met it. Converting world-model needed three scripts widened, and two
  of the three checks involved had been **failing silently** on exactly the shape being introduced.
  The decision was still right — several hundred prose mentions outweigh one regex — but the cost
  belongs next to it, and is now written into `docs/DOC_CONVENTIONS.md`.
- **Fold order decides what an entry's state looks like, and getting it wrong is silent.** Putting
  `WM-B6`'s `[x]` debt record above its own `[~]` block made `roadmap-toc.sh` report an in-progress
  item as **done**, and would have done the same to any `grep '#status/'`. Caught by reading the
  TOC's real output after the conversion rather than by inspecting the entry. Source order is the
  right rule for an item plus its own superseded text and the **wrong** rule for a folded debt
  record, because the debt list sits at the head of the document, far above what it refers to.
- **A checkbox-shaped count cannot see an item that was never written as a checkbox.** Stage 3's
  lesson was the inverse — a `^- \[` block that is not a new item. Here three top-level `- **…**`
  prose bullets in a Backlog section were items (or an item's duplicate record) with no checkbox
  and no ID, invisible to `grep -cE '^- \['`, and the task's own mint list did not name them. Two
  became `WM-B15`/`WM-B16`; one was folded. **Enumerate every top-level bullet, then judge each.**
- **Reading the source from the working tree makes the conversion a one-shot.** Writing the pointer
  over `world-model/ROADMAP.md` and then re-running the converter sliced line ranges out of the
  8-line pointer and corrupted the entry files. Fixed by reading every source through
  `git show HEAD:<path>` (which the fidelity checker already did), making the whole pipeline
  idempotent and re-runnable. Caught immediately by the fidelity check, which is the second time
  that check has earned its place this stage.
- **A `sed` that fails still lets a harness print a confident number.** The first
  revert-the-regex counterfactual printed "0 findings" for both probes while the script it was
  supposed to run had never been written. The result happened to be the *same* as the real answer,
  which is worse than being wrong — it would have been recorded as evidence. Redone in Python with
  an assert on the substitution count.
- **The plan's mint estimate was high rather than low this time** (20 `WM-W` predicted, 12 minted),
  the opposite direction from Stage 2's undercount of 11. The difference is the debt-list fold: two
  of world-model's seven debt records name their own backlog ID in their own text, and the plan
  counted the "no M-number" Status entries and the debt list as disjoint sets when `WM-W1` is both.
  **Across four stages the plan's mint counts have now been high once, low once, and exactly right
  twice** — which is an argument for deriving them from the document every time rather than
  calibrating a correction factor.
- **The worktree's `HEAD` was again a strict ancestor of the named tip** (`29217c0` vs `004a1cd`,
  26 commits behind — the whole of Stages 1 through 3 plus the document-graph work, 253 files).
  Fast-forwarded per AGENTS.md rule 4 before reading anything. Third consecutive stage, and the
  prediction in the task brief was exactly right: none of `docs/DOC_CONVENTIONS.md`,
  `plans/obsidian-links-and-tags/implementation.md`, `body-layer/ROADMAP/` or `todo/todo/` existed
  in the tree as created.

---

## Round 4 fixes — 2026-10-09

All ten required fixes from `review.md`'s "Review round 4" section, plus its Observations list. Two
commits: `959c034` (RF4-1…RF4-5) and `2b3bcd2` (RF4-2, RF4-6…RF4-10 and the observations).

**Addressing.** Worktree `HEAD` was `29217c0`, a strict ancestor of the named tip
`2856770` with a clean tree, so `git merge --ff-only` per `AGENTS.md` rule 4 — 35 commits. Fifth
consecutive stale dispatch. All five named input documents verified present afterwards.

### What each fix changed

**RF4-1 — the ID table, and a second collision found by executing the recipe instead of reading
it.** Four of five rows named a pointer file, so the minting rule nine lines below would read a
four-line pointer and mint `WM-B1`/`X-B30`/`BL-B43`/`AC-B4` against 16/5/4/2 live items. The rows
now name the split directories, and the rule names a command rather than describing one.

**The command the task supplied is itself broken, and so was the one already published.** Measured:

| recipe | returns | real highest | would mint |
|---|---|---|---|
| `ls body-layer/ROADMAP/ \| grep -oE '^[A-Z]+-B[0-9]+' \| sort -t B -k2 -n \| tail -1` | `BL-B9` | `BL-B46` | `BL-B10`, collides |
| `ls world-model/ROADMAP/ \| grep -oE '^[A-Z]+-W[0-9]+' \| sort -t W -k2 -n \| tail -1` | `WM-W9` | `WM-W12` | `WM-W10`, collides |

`-t B` splits on the literal `B`, which the `BL-` prefix contains; `-t W` on the `W` in `WM-`. Every
affected file then shares an empty second field and the tie decays to a lexicographic comparison.
The second row is the form `docs/DOC_CONVENTIONS.md:142` had carried since the convention was
written, so **minting the next `WM-W` item from the repo's own published recipe would have produced
the exact collision RF4-1 exists to prevent.** Both are now `sort -V`, verified correct for all
five `-B` spaces and both `-W` spaces. Nothing about either recipe looks wrong on the page; this is
only visible by running it.

**RF4-2 — the three gates, two of them wired.** See "Where this round departed from the review"
below for why `doc-provenance-gate.sh` is not the third.

**RF4-3 — the `#needs-flight` recipe.** As published it returned 9 entries and **exited 0**. Fixed,
executed: 13 tagged entries across four subprojects, including the four the review named
(`AC-8`, `WM-W2`, `AA-2`, `AA-5`). The sweep for the same recipe shape found two more copies —
world-model's index (now identical) and audio-adapter's (marked as deliberately subproject-scoped,
with a pointer to the repo-wide form). All three now carry one spelling, with a note in each saying
to change the others in the same commit.

*One correction to the task brief's framing:* it expected "all 14 unflown items". The measured truth
is **13** tagged entry files. The 14 came from counting the broken recipe's 10 returned paths (9
entries + 1 index) plus the 4 missing ones; the correct recipe returns 16 paths, 3 of which are
index files that match because they discuss the tag. The `grep -v` in the fixed recipe drops those.

**RF4-4 / RF4-5 — the `WM-M<n>` rename.** The corrupted sentence was rewritten, not renumbered: it
claimed "several hundred bare `WM-M5`/`WM-M7` mentions" where the measured truth is **422 bare
`M5`/`M7` and zero `WM-M5`/`WM-M7`**, so it asserted the opposite of its own point while arguing
against a rename that had happened. Eleven live documents still asserted a bare `M<n>` — the five in
`BL-11.md`, one each in `BL-12`/`BL-B26`/`BL-B30`, four in `todo/backlog/` — now `[[WM-M<n>]]` links
that resolve, plus `aircraft-layer/CLAUDE.md` as backticked `WM-M4`/`WM-M5` (plain, not a wikilink:
it sits outside any split directory, so no gate would check a link there).

After the sweep, `(^|[^-A-Za-z0-9_])M[0-9]+([^A-Za-z0-9_]|$)` over every live surface returns
**only** two standing false positives the pattern cannot avoid — `MI24-outpost-M03.miz` (a mission
filename) and `Soldier M4 GRG` (a weapon name) — both now named in `DOC_CONVENTIONS.md` so the next
sweeper does not chase them.

`RUN.md` and `NOTES.md` were named on neither side of the boundary, so the boundary is now written
as a **rule**: a document asserting what is true *now* is rewritten; one recording what was true
*then* keeps the bare form. It puts the two on opposite sides, which is the useful part. `RUN.md`
tells you which flags exist today, so its bare `M3` was a stale instruction — fixed. `NOTES.md`'s 40
mentions are dated citations ("Finding 1 of `M1` verification note") and rewriting them would
falsify the record.

**RF4-6 / RF4-7 — the resolver, and the consumer sweep.** `.claude/scripts/roadmap-source.sh` is
new: `<path>` → the index, `--dir` → the directory, `--entries` → every entry file, `--is-pointer` →
a silent test, and a non-pointer passes through unchanged so a caller can pipe every roadmap path
through it unconditionally. The destination is **derived**, not listed (`<dir>/ROADMAP` or
`<dir>/<stem>`), so a ninth split document needs no edit; the sentinel's own text cannot be used
because it reads `see ROADMAP/` under `todo/` too.

Writing consumers fixed: `dod.md` ×3, `merge/SKILL.md` ×2 paths, `retro/SKILL.md` ×3. Counting and
searching consumers fixed: `status-page/SKILL.md` ×5 sites, `status-page-refresh.sh`'s Phase 1
prompt, `docs/status/README.md`, `explore/SKILL.md`, `integrity-audit/SKILL.md` ×4. The full sweep
beyond the review's eight spot-checks added: **root `ROADMAP.md`'s status table**, whose six
`Roadmap` links all pointed at pointers — the single most-followed pointer in the repo, and the one
five other consumers are explicitly told to take their list from, so fixing it there fixes them at
the source. Plus the block all six role files carry verbatim, four subproject `CLAUDE.md`s,
`architect.md` ×2, root `CLAUDE.md` ×5 and `docs/concept/WORLD_MODEL_BUILDER.md`.

**A finding the review did not have, and it changes the fix in four of five cases:
body-layer's is the only "Live acceptance debt" list that was dissolved.** `world-model`'s and
`audio-adapter`'s indexes still carry a section of that name. So of the five live references,
four needed only a path correction (pointer → index) and one needed rewording. Treating them
uniformly — the obvious reading of RF4-6 — would have been wrong four times out of five.

**RF4-8 — reverting Phase 1 as a set.** `revert_page()` became `revert_phase1()` at all four
post-Phase-1 exit paths (enumerated: `grep -c` gives 5 = 1 definition + 4 call sites, and 0 stale
references). It reverts `git diff --name-only HEAD` as a set, logs a WARNING naming any file outside
`$PAGE`, and then **re-checks the tree and logs a loud ABORT** if anything remains — because
`git checkout --` cannot undo a staged addition, so the function would otherwise report a clean
revert it did not achieve. Process substitution, not a pipe, so the loop is not a subshell.

**RF4-9 — discovery, and a crash underneath it.** `find_entries()` went from a hardcoded
`audio-adapter/ROADMAP` (22 entries, prefix `AA` only) to all seven split directories: **245 entries
across 7 directories** — 13 + 22 + 103 + 9 + 34 + 24 + 40. `doc_tags.entry_units()` had the same
missing-`todo/` gap (187 → 245) and was brought level, because fixing one half of a pair is the
error this entire round is about.

Widening discovery exposed a latent crash: `id_sort_key` has `assert m is not None` with no message,
and its regex `^([A-Za-z]*)(\d*)$` requires letters-then-digits — but a suffixed ID is
digits-then-letter. **`BL-5a` and `MI-5b` are both real on disk**, so the gate died on an
`AssertionError` naming nothing the moment it could see body-layer or mission-interpreter. Invisible
while the function only ever saw `audio-adapter/ROADMAP/`, which has no suffixed ID. The pattern is
total now, ordering verified (`BL-5` < `BL-5a` < `BL-6`).

**RF4-10 — Session Start.** Both halves fixed in both homes, plus `CLAUDE.md`'s Current priority,
Milestone Completion and subproject-pointer paragraphs, the six role files' shared block and the
four subproject `CLAUDE.md`s making the same claim.

### Observations

Three gate scripts' header comments described a removed bare-`M<n>` regex alternative and a retired
`M5`→`WM-5` cost argument as live. Each now states what the code does and keeps only the part worth
carrying forward — that the loud half of that episode was the trap. `roadmap-entry-consistency-gate.sh:87`
turned out **already accurate** (its closing parenthesis says the form is gone), so only the header
needed the fix. Corpus guard: 434 → re-measured **435**. The two latent word-splitting loops now
read line by line **via process substitution rather than a pipe** — a pipe would run each loop in a
subshell, discarding every `FAIL=1` at the `done` and exiting 0 with findings already printed to
stderr, which is worse than not checking. Both re-proven red afterwards. The `cd "$CLAUDE_PROJECT_DIR" || exit 0`
under `set -u` in `commit-quality-gate.sh` and `push-roadmap-gate.sh` now uses the sibling gates'
pattern; verified fail-open with the variable unset. And `DOC_CONVENTIONS.md` now says the
sentinel's literal `see ROADMAP/` spelling is correct under `todo/` and must not be adapted.

### Where this round departed from the review, and why

**`doc-provenance-gate.sh` is deliberately not wired into `commit-quality-gate.sh`.** RF4-2 named
all three gates, resting on RF4-9's statement that the provenance gate was *"latent only because
zero provenance blocks exist."* **That premise is false: 32 documents carry a real block today.**
Fixing RF4-9's discovery means the generator now finds the cross-subproject citations it previously
could not, so **127 documents' blocks are stale by regeneration.** Established by counterfactual,
not inference:

| `doc_provenance.py` | gate result |
|---|---|
| pre-fix (`git show HEAD:…`, copied in) | `doc-provenance-gate: OK`, rc=0 |
| with the RF4-9 fix | 166 FAIL lines over **127 distinct files** |

Restored by checksum (`18d2222…` before and after). Wiring it would refuse **every commit touching
any `ROADMAP/` path, repo-wide**, until all 127 are regenerated — and regenerating them is the
Obsidian document-graph work, paused by user direction, adding ~200 keyword-derived citations nobody
has reviewed. A gate that refuses every roadmap commit is precisely the *"cries wolf, gets
bypassed"* failure this review names as the thing to avoid, and is strictly worse than the status
quo. The gate remains correct and runnable standalone; the reason and the one-line unblock condition
(`doc-provenance-refresh.sh`, once the work unpauses) are written at the wiring site and in
`DOC_CONVENTIONS.md`. **This needs a decision rather than a quiet choice.**

**`doc_tags.py` was fixed although the review named only `doc_provenance.py`.** Same one-line
discovery gap, same two missing directories. Leaving it would have been this round's own diagnosis
repeated verbatim.

### Verification

- **All four doc gates run.** The two wired ones `OK` rc=0; `graph-corpus-guard.sh` `OK — 435 files
  (ceiling 520)` against a freshly generated corpus. `doc-provenance-gate.sh` fails on the 127
  pre-existing stale blocks described above.
- **`bash -n` clean** on all ten shell scripts touched; `py_compile` clean on both Python helpers.
- **Mutation proofs, restored by `shasum`:**
  - dangling `[[ZZ-999]]` staged ⇒ `commit-quality-gate.sh` returns `continue:false` naming it.
  - **a `.py`-only commit is silent, rc=0, *while the dangling link is still in the tree*** — which
    is what proves the staged-path condition rather than the gate merely passing.
  - a non-executable gate script ⇒ skipped, not reported (fail-open on internal error).
  - `CLAUDE_PROJECT_DIR` unset ⇒ still reaches the refusal, so the `cd` fix works.
  - after the loop rewrites, `[[QQ-404]]` and an unlisted `#not-a-real-tag` **each drive their gate
    to rc=1** and surface through the commit gate — the tag one specifically proves `FAIL=1` survives
    the new `while`-read form. `doc-provenance` appears nowhere in that output, as intended.
  - every target restored byte-identically (`c9406c68…`, `43eb2596…`, `18d2222…`).
- **RF4-8's failure path was executed, not reasoned about**, since this script has wedged the repo
  once. From a clean tree, two tracked files dirtied:
  - reverting only `$PAGE` (the old behaviour) ⇒ guard 2's exact command returns
    `[ M docs/status/README.md]` — **the permanent-skip wedge, reproduced.**
  - reverting the whole set ⇒ guard 2 returns `[]`, next run proceeds.
  - a staged new file ⇒ survives `git checkout --`, so `$still` is non-empty and the ABORT branch
    fires naming the file — the information the old silent failure denied.
  - tree afterwards: `git diff --stat HEAD` empty, byte-identical to the commit.
- **Executed rather than inspected:** the `#needs-flight` recipe (13 entries), `find_entries()` (245
  across 7 directories, all seven prefixes), `roadmap-source.sh` (all eight pointers resolve, a
  non-pointer passes through, every mode and both error paths), and the gate's ID resolution —
  `BL-11`, `WM-M5`, `X-B29`, `X-T1`, `AA-3`, `AC-8`, `MI-5b`, `BL-5a` all resolve while `ZZ-999` is
  still rejected. That last one is the discriminating test: a green run would not distinguish a
  widened gate from a gate that accepts everything.
- **Per-subproject checks, all five touched subprojects**, run from inside each with the main
  checkout's venv (every file my diff touches in a subproject is markdown — no source, tests or
  tools):

  | subproject | `ruff format` | `ruff check` | `mypy --strict` | `pytest -q` |
  |---|---|---|---|---|
  | world-model | pass (118) | pass | pass (72) | 565 passed, 3 skipped |
  | body-layer | pass (118) | pass | pass (54) | 1551 passed, 4 xfailed |
  | aircraft-layer | pass (56) | pass | pass (21) | 256 passed |
  | audio-adapter | pass (29) | pass | pass (15) | 222 passed, 1 skipped |
  | mission-interpreter | pass (46) | pass | pass (31) | 108 passed, 3 skipped |

  **2702 passed, 7 skipped, 4 xfailed, 0 failed** — identical to the review's own baseline, so no
  regression. The known pre-existing `ruff format` non-conformances in `body-layer/research/`,
  `world-model/tools/` and `world-model/research/` are outside the documented `src tests` scope and
  were **confirmed, not asserted**: my commits touch 0 files there, `git diff main --` over those
  paths is empty, and the diff machinery was sanity-checked against a file this branch does change
  (`docs/DOC_CONVENTIONS.md`, 492 insertions).
