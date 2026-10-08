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
