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
