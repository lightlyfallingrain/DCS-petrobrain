# Review — obsidian-links-and-tags, Stage 0 + Stage 1 (audio-adapter conversion)

Branch `feature/doc-conventions-audio-adapter`, tip `a982bb9` (3 commits on `dcd3aee`: `ac6f008`
Stage 0 consumer fixes, `a6056b2` the audio-adapter conversion, `a982bb9` agent-memory
housekeeping).

**Worktree addressing (AGENTS.md rule 4):** this worktree's `HEAD` was `ab18d03`
(unrelated `main` work), not the named tip `a982bb9` — the branch was already checked out
elsewhere, so git could not check it out here. Tree was clean (nothing at risk). Verified instead
via `git archive a982bb9 | tar -x` into a scratch directory, plus individual `git show a982bb9:<path>`
reads. All findings below are against that snapshot.

### Review Summary

Content fidelity is clean: all 577 lines of the old `audio-adapter/ROADMAP.md` are faithfully
preserved across 22 entry files + 1 index, including every user quotation, measured figure, and
the deliberately-carried-forward `AA-3` contradiction. Stage 0's consumer fixes are correct and
tested on both path shapes (pointer and entry file), including the independent `BACKLOG.md`
dirty-flag bug fix. Scope discipline held — nothing outside audio-adapter touched, `.obsidian/`
untracked and deleted from disk per spec, no history rewrite.

Two real gaps found by mutation in the two new gates, both inside the exact failure classes the
task asked to probe for. Neither is in the hot, dominant risk (R1), which itself is the most
important finding this review surfaces — see below.

### Required Fixes

- **`roadmap-entry-consistency-gate.sh` check 3 only verifies "at least one index," not "exactly
  one."** Confirmed by mutation: adding a second index file with the same `[[AA-B2]]` link passes
  silently (`roadmap-entry-consistency-gate: OK`, exit 0). This contradicts the plan's own R5
  statement ("every entry appears in exactly one index") and `docs/DOC_CONVENTIONS.md`'s "Gates"
  section, which documents the gate as checking "exactly one" when the code checks "at least one."
  Either strengthen the gate to detect duplicate links across indexes in the same directory, or
  correct the doc to say what the gate actually does — but the two must agree, and the stronger
  gate is worth having before body-layer's two-index (`ROADMAP/BACKLOG` sharing one directory)
  case in Stage 2 makes a duplicate link a live possibility rather than a contrived test.

- **`roadmap-tag-vocabulary-gate.sh` has two more false-positive classes in the same family the
  implementer already fixed one instance of.** The implementer's fix (require a tag to start with
  a letter, `#[A-Za-z]...`) correctly stops prose ordinals like "RECOMMENDED #1" from matching.
  But the same regex, with no "inside a code span" or "inside a URL" exclusion, false-positives on:
  - **A `#` inside inline code**: `` `#heading` `` (exactly the string this project's own
    `docs/DOC_CONVENTIONS.md` uses, describing the Front Matter Title plugin setting) is read as
    tag `#heading` and fails the gate if it ever appears in a converted entry.
  - **A URL fragment**: `https://example.com/docs#section-heading` is read as tag
    `#section-heading`.
    Both confirmed by mutation (appending each line to a real entry file and re-running the gate;
    reverted after). Neither pattern happens to appear in the 22 converted files today, which is
    why the baseline passes — but `AA-3`'s own prose links to
    `aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md` and other paths; it is a
    matter of time before a converted entry's prose contains a code span with `#` or a URL with a
    fragment, at which point the gate blocks a legitimate commit with no real tag violation. Fix:
    strip inline code spans (`` `[^`]*` ``) and URLs before scanning for tags, the same way the
    ordinal fix stripped bare `#1`.

### Optional Refinements

- **The dominant risk (R1) is mitigated entirely by prose inside a prompt handed to a `claude -p`
  subprocess, not by any programmatic check.** `status-page-refresh.sh`'s `$PROMPT` instructs the
  LLM invocation to "assert a non-zero forward-item count before publishing… Stop and say so rather
  than publish" — this is the entire implementation of the "assertion" the plan's R1 risk called
  for. There is no code path in the script itself that can independently refuse to publish; the
  mitigation's reliability is exactly as strong as that invocation's instruction-following on that
  run, which is the same category of failure this project's own `CLAUDE.md` describes elsewhere
  ("a rule nobody can see being broken stays broken") applied to a sub-agent rather than to this
  agent. I could not empirically test this by construction the way the other gates were tested
  (pointing it at an empty index and confirming failure) without actually invoking a live `claude
  -p` call, which this review did not do. **This is not a required fix** — building a real
  mechanical check here (e.g., a post-generation HTML grep for an empty open-items list before the
  commit step, run as actual shell code rather than as an instruction to the generating agent)
  would close the gap cheaply and is worth doing before this mechanism is trusted at repo-wide
  scale, where a silent empty-page regeneration would be much harder to notice by eye than it is
  on a single audio-adapter card. Flagging rather than blocking because the script's three
  mechanical guards (dirty tree, non-main branch, no commits) already bound how often it runs, and
  because it is optional/manual, not gating anything (user already rejected auto-scheduling, X-B24).

- **`docs/DOC_CONVENTIONS.md`'s "Gates" section slightly overclaims** what the consistency gate
  checks (see required fix above) — fold the doc fix into whichever side of that fix is chosen.

### What 22 files revealed that will hurt at 204 (the question this review most needs to answer)

- **The tag-vocabulary gate's false-positive surface is a recurring failure class, not a one-off
  bug.** This is the second false positive found in it within the same conversion (the first,
  prose ordinals, was already fixed before this review). A regex scanning raw markdown for `#word`
  without excluding code spans and URLs will keep finding new false positives as prose grows —
  and 204 files' worth of varied prose (especially body-layer's, which quotes code identifiers and
  file paths constantly) will hit this far more often than audio-adapter's comparatively narrow
  technical vocabulary did. Fix the class, not the instance, before Stage 2.
- **The "exactly one index" gap only became visible because audio-adapter has exactly one index.**
  It is invisible until a subproject gets a second index sharing one `ROADMAP/` directory — which
  is precisely body-layer's planned shape (`body-layer/ROADMAP/body-layer-roadmap.md` +
  `body-layer/ROADMAP/body-layer-backlog.md`, per the plan's "Structure" section). Stage 2 is the
  first time this gap is live rather than theoretical; fix it before Stage 2, not during it.
- **The entry-file convention itself held up well at 22 files** — no friction found in the ID
  scheme, the bare-link form, or the dotted-stage IDs. The one piece of friction that did surface
  (AA-4.8 linking to AA-1.6 rather than duplicating identical "Stage 6" content) was handled
  correctly by the implementer rather than by the convention; nothing in `docs/DOC_CONVENTIONS.md`
  currently says what to do when two milestones share a literal duplicate entry, and body-layer's
  larger roadmap is more likely to have another instance of this than audio-adapter's did. Worth a
  sentence in the convention doc, not urgent.
- **Nothing about scale itself strained the corpus or gate runtime at 22 files** — both gates ran
  in well under a second against the whole converted tree. At 204 files plus 7 indexes the
  per-file `grep`/`awk` cost in both gates will grow roughly linearly; nothing here suggests a
  redesign is needed, just confirming the "cost rises linearly with indexes, which is fine" claim
  in the plan held at this scale.

### Verdict

**APPROVED WITH MINOR FIXES.** The two required fixes are gate-logic bugs with concrete, cheap
fixes (see above) and are independent of the actual content conversion, which is correct and
faithful. Nothing here blocks moving forward with the fixes; nothing requires re-doing the
audio-adapter conversion itself.

### Review Confidence

**Full read** of all 22 entry files, the index, the old 577-line roadmap (diffed by full read, not
tooling), the plan, `docs/DOC_CONVENTIONS.md`, `docs/TAGS.md`, and every changed script. **Every
Stage 0 consumer and both new gates were exercised by actually running them** against a git-backed
copy of the converted tree (not read-only inspection) — including constructing and confirming four
real violations (dangling link, H1/filename mismatch, orphaned entry, duplicate-index entry) and
two false positives (code-span `#`, URL fragment). The one item not empirically tested is the
`status-page-refresh.sh` LLM-prompt "assertion" (R1's mitigation), which cannot be tested without
invoking a live `claude -p` subprocess — flagged as a risk rather than treated as verified.
`ruff format --check`, `ruff check`, `mypy --strict src`, and `pytest -q` were re-run against
audio-adapter's own `.venv` (borrowed from the main checkout, per this project's standing worktree
convention) and reproduced the implementer's reported 222 passed / 1 skipped, clean lint/type
results.

---

## Review round 2 — the fix (2026-10-06)

Reviewing fix commit `6f1b327` on `feature/doc-conventions-audio-adapter` (tip `6f1b327`, 1 commit
on `a95913d`), per AGENTS.md's "a change written in response to a review is ordinary new code" —
this is the review of the Implementer's response to the two required fixes above plus the R1
upgrade the Optional Refinements section invited.

**Worktree addressing (AGENTS.md rule 4):** this worktree's `HEAD` was `ab18d03` (unrelated `main`
work, 1-2 commits further along than the previous round's `ab18d03`), not the named tip `6f1b327`
— the branch was checked out elsewhere, so git could not check it out here either. Tree clean.
Verified via `git archive 6f1b327 | tar -x` into a scratch directory under the session scratchpad,
all commands run with `cwd` inside that extracted tree (or, for mypy/ruff/pytest, inside the main
checkout's `audio-adapter/`, justified below since `audio-adapter/src` and `audio-adapter/tests`
are byte-identical between the two — confirmed by `diff -rq`, the only differences being
`ROADMAP.md`/`ROADMAP/` and build caches).

### Scope

Exactly the four files the task named, nothing else in `src`:
`.claude/scripts/roadmap-entry-consistency-gate.sh`, `roadmap-tag-vocabulary-gate.sh`,
`roadmap-toc.sh`, `status-page-refresh.sh`, plus `plans/obsidian-links-and-tags/implementation.md`
and an implementer agent-memory file. `git diff a95913d 6f1b327 --stat` confirms no fifth file.

### Fix 1 — exactly-one-index: verified correct, pushed further than the author's own proof

Re-ran the author's own mutation (second index linking `[[AA-B2]]`) and it reproduces exactly:
`AA-B2.md is linked from 2 indexes in this directory, expected exactly one`, exit 1; reverted,
`OK`, exit 0. Then pushed past the author's proof as the task asked:

- **Three indexes linking the same ID** — generalizes correctly: `linked from 3 indexes...`
  (count is not hardcoded to 2).
- **An index linking an ID with no entry file** (`[[AA-B99]]`, no `AA-B99.md`) — correctly falls
  through to check 1's existing dangling-link message, not misreported as a duplicate-index issue.
- **An entry file with no index at all** — correctly caught by the unchanged zero-count branch
  ("not linked from any index").
- **A second index in a *different* directory, linking the same literal ID string** (created
  `world-model/ROADMAP/world-model-roadmap.md` linking `[[AA-B2]]`, since `world-model/` is a real
  subproject with a `pyproject.toml`) — the per-directory scoping is correct: this is reported as
  a dangling link in `world-model/ROADMAP` (no `AA-B2.md` lives there), not conflated with
  audio-adapter's own `AA-B2.md` as a cross-directory duplicate. The directory-scoped loop
  (`for dir in $DIRS`, with `ids` and the index search both confined to `"$dir"`) means an ID is a
  defect-detection unit *per directory*, which is the right shape — IDs are namespaced by
  subproject prefix in practice, and nothing here lets a same-named entry in two subprojects
  silently cancel out.

No gaps found in this fix. **Confirmed correct**, including under adversarial generalization.

### Fix 2 — strip code/URL before tag scan: the three named mutations hold, but the strip itself has two new failure modes

Re-ran all three of the author's own mutations against a real entry file
(`audio-adapter/ROADMAP/AA-B2.md`): inline-code `` `#heading` ``, URL fragment
`.../docs#section-heading`, and the author's own third discovery (a bare `#tag` on its own line
inside a fenced block) — all three stripped correctly, `roadmap-tag-vocabulary-gate: OK` / `AA-B2
#status/open` (no fake tags) from `roadmap-toc.sh`, reverted clean. Confirmed a genuinely unknown
tag (`#totally-unknown-tag`) is still caught — the fix does not over-strip in the common case.
Confirmed a tag immediately following an inline code span on the same line
(`` `inline_code`#totally-unknown-tag ``) is still caught, and a tag following a URL that ends a
sentence (`https://example.com/foo. #tag`) is still caught — both of the task's named probe cases
for the strip mechanism itself pass.

Probing further, as the task asked, found two real gaps, of different severity:

- **Required: an unterminated (odd-count) fenced code block silently swallows every line after it
  for the rest of the file, including a real, unknown tag — in both
  `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh`.** The shared `awk '/^```/{fence=!fence;
  next} fence{next} ...'` toggle has no concept of end-of-file; an opening ``` with no matching
  close leaves `fence` permanently true for every subsequent line, however far past the mistake
  they are. Confirmed by mutation: a file containing an opening ``` fence with no closing fence,
  followed later by `#totally-unknown-tag` in plain prose, makes `roadmap-tag-vocabulary-gate.sh`
  exit 0 (`OK`) and `roadmap-toc.sh` print the entry with no tag at all — the real violation is
  invisible to both tools, not flagged, not logged, nothing. This is exactly the risk the task
  named going into this review: *"a gate that now misses a real tag is worse than the false
  positives it fixed."* It is also a genuinely new failure mode, not a pre-existing one carried
  forward — the pre-fix gate had no fence-awareness at all, so the worst it could do was
  over-flag; this fix adds a state machine that can now under-flag silently for an entire file on
  nothing more than an editing slip (a forgotten closing ```` ``` ````, which this project's own
  prose is full of). Needs a fix before this is trusted at 204 files: either detect an odd fence
  count and fail loudly (consistent with how this same diff treats every other new failure mode —
  check 3's duplicate case and the R1 mechanical check both choose "fail loudly" over "degrade
  silently"), or scope the fence toggle so it cannot carry state past a point a human would notice.
- **Optional: the fence-opener regex `/^```/` only matches at column 0, so a fence indented inside
  a list item is not recognized as a fence at all, and a `#tag`-shaped string inside it leaks
  through as plain prose — a false positive, the exact class this fix targeted, just a member it
  missed.** Confirmed by mutation: a 4-space-indented ` ``` ` block inside a list item, containing
  `#fenced-in-list-tag`, is flagged as an unknown tag by `roadmap-tag-vocabulary-gate.sh` rather
  than stripped. Lower severity than the item above — it is loud and blocks a real commit, not
  silent — but it is the same "this class keeps finding new members" pattern the first review
  round already named once; worth closing with the same pass rather than finding it a third time
  at 204 files. A one-line `/^[[:space:]]*```/` match (or a leading-whitespace strip before the
  existing match) would close it.

### Fix 3 (R1 upgrade) — mechanical check in `status-page-refresh.sh`

(a) **Genuinely pure bash, no LLM in the path**, confirmed by reading: `FORWARD_COUNT=$(awk
'/id="graph-upcoming"/,/<\/pre>/' "$PAGE" | grep -v '^[[:space:]]*classDef' | grep -c ':::' ||
true)` runs between the two `claude -p` invocations, touching only the file Phase 1 wrote to disk.

(b) **Runs before anything is published or committed** — confirmed by control flow: the `PUB_PROMPT`
string and the `claude -p "$PUB_PROMPT"` call are both defined textually *after* the `[
"$FORWARD_COUNT" -eq 0 ] && ... exit 1` branch, so a failing check returns before Phase 2's
publish/commit code is even reached, let alone run.

(c) **Fails non-zero on an empty forward map** — re-ran the author's exact extraction logic against
a stubbed copy of the real `docs/status/petrobrain-status.html` with every `:::`-tagged node
stripped from the `#graph-upcoming` block: `FORWARD_COUNT=0`, reproduces the script's own failure
message and `exit 1`. Also reproduced the non-failure count (24) against the unmodified real file,
matching the author's proof exactly.

(d) **The failure path is NOT clean — this is the gap the task said the author's proof did not
cover, and it is real.** `exit 1` on `FORWARD_COUNT -eq 0` happens with no `git checkout`, no
revert, nothing — `docs/status/petrobrain-status.html` is left on disk exactly as Phase 1's
(bad/empty) regeneration wrote it, modified and uncommitted. Reading the script's own guard 2
(`if [ -n "$(git status --porcelain --untracked-files=no)" ]; then say "SKIP: working tree has
uncommitted changes..."; exit 0; fi`), which runs at the *top* of every future invocation, shows
the consequence directly: the very next scheduled run (intended to be launchd at 05:00, per the
file's own header) will see that leftover modified file, log "SKIP: working tree has uncommitted
changes," and exit 0 without even attempting to regenerate — silently, every day, forever, until a
human notices the status page is stale and manually runs `git checkout -- $PAGE`. **A one-time
mechanical-check failure becomes a permanent silent outage of the whole refresh mechanism.** This
is worse than the pre-fix state in one specific way: before the split, a single `claude -p` call
that heeded its own "stop and say so rather than publish" prompt instruction could plausibly leave
the same kind of dirty file behind too, so this isn't strictly introduced by this fix — but the fix
had the opportunity to close it (the task's own framing, "that last one is the point of the
check"), and the author's proof tested only the check's true/false arithmetic, never the
script's own self-blocking consequence of taking the false branch. Fix: on the `FORWARD_COUNT -eq
0` branch, before `exit 1`, restore the working tree (`git checkout -- "$PAGE" 2>/dev/null ||
true`) so the next scheduled run starts clean and can try again rather than being locked out.

### Did the split break the normal path?

No. Phase 1 (generate-only, no publish/commit/push) → mechanical check → Phase 2 (publish, commit,
push) preserves the prior single-call behavior on the success path; the three pre-existing
mechanical guards (repo missing, `claude` missing, dirty tree / not-main, no commits in 24h) are
untouched and still "SKIP, never block." The only behavioral change on the happy path is that
generation and publish/commit now run as two separate `claude -p` invocations rather than one,
which loses no state the script itself depends on (every fact Phase 2 needs — the page already
written, the check already passed — is read from disk or passed by the mechanical check's own
exit code, not carried in an LLM conversation).

### bash -n and gate re-runs

`bash -n` clean on all four changed scripts. Re-ran all three gates against the real converted
`audio-adapter/ROADMAP/` tree in the `6f1b327` snapshot (via `CLAUDE_PROJECT_DIR=<snapshot>`, since
the snapshot has no `.git` for the scripts' own `git rev-parse --show-toplevel` fallback to find):
`roadmap-entry-consistency-gate.sh` → `OK` (0.36s), `roadmap-tag-vocabulary-gate.sh` → `OK`
(0.25s), `roadmap-toc.sh audio-adapter/ROADMAP/` → prints all 22 entries with correct tags,
matching the pre-fix baseline.

### Checks (audio-adapter/)

Re-ran against the main checkout's `audio-adapter/.venv` (justified above — `src`/`tests`
byte-identical to the snapshot): `ruff format --check .` → 40 files already formatted;
`ruff check .` → all checks passed; `mypy --strict src` → no issues, 15 source files; `pytest -q`
→ 222 passed, 1 skipped — matches the implementer's reported baseline exactly, zero diff under
`audio-adapter/`.

### Will these gates stay fast and quiet at 204 files?

Measured, not estimated: `roadmap-tag-vocabulary-gate.sh` ran in 0.25s and
`roadmap-entry-consistency-gate.sh` in 0.36s against the 22-file, 1-index audio-adapter tree. Both
gates' cost is dominated by a fixed per-file subprocess pipeline (one `awk` + two `sed` + one
`grep` for the tag scan; one `grep`/`awk` pass per file plus an O(ids × indexes) nested loop,
negligible at 1-2 indexes per directory, for consistency) — no step is quadratic in file count, so
cost should scale roughly linearly with file count. At 204 files across 7 indexes that extrapolates
to roughly 2-4 seconds total per gate at commit time, which is cheap enough to stay invisible in a
normal commit — **performance is not the risk here; the two correctness gaps above (items (d) and
the unterminated-fence swallow) are.** A silent, hard-to-notice gap that erodes trust in "the gate
caught it" is the failure mode that gets a check disabled, not a few extra seconds of `bash`.

### Known-open items, not defects

- `AA-3`'s accepted-vs-debt contradiction remains deliberately unresolved, per the task — correctly
  left untouched by this fix.
- **Agree with the author's decision to decline the `#` inside a markdown link's quoted title
  attribute** (`[text](url "title with #not-a-tag")`). Re-verified independently, more broadly
  than the author's own check: `grep` for that link-with-quoted-title shape across the *entire*
  repository (not just the 22 converted audio-adapter files) finds exactly one hit — the author's
  own sentence describing the pattern in `implementation.md` — and a separate check of the three
  subprojects' not-yet-converted `ROADMAP.md` files (`world-model`, `aircraft-layer`, `body-layer`,
  the content that will actually flow into entry files next) finds zero occurrences of the
  `](... "...")` title-attribute shape at all. "Not in the repo today" is as strong an argument as
  it can be made here, since it holds against the corpus that is actually coming next, not just the
  corpus already converted — this is a legitimate decline, not a speculative one.

### Required Fixes (this round)

1. **`status-page-refresh.sh`: the mechanical-check failure path does not restore the working
   tree**, leaving a modified, uncommitted `docs/status/petrobrain-status.html` on disk. The
   script's own guard 2 then silently skips every subsequent run as "working tree dirty," turning
   one bad regeneration into a permanent, silent outage of the daily refresh until a human notices
   and manually reverts the file. Fix: `git checkout -- "$PAGE"` (or equivalent) before `exit 1` on
   the `FORWARD_COUNT -eq 0` branch.
2. **`roadmap-tag-vocabulary-gate.sh` / `roadmap-toc.sh`: an unterminated fenced code block
   silently disables tag scanning for the rest of the file**, including real unknown tags, with no
   warning and a clean exit. This is a new failure mode introduced by the fence-toggle added in
   this fix (the pre-fix gate had no fence state to leak), and it is a false negative rather than a
   false positive — the more dangerous direction, per the task's own framing. Fix: detect an
   odd/unbalanced fence count per file and fail loudly, rather than leaving `fence` true past the
   last real close.

### Optional Refinements (this round)

- **The fence-opener regex only matches `` ``` `` at column 0**, so a fence indented inside a list
  item is not recognized, and a tag-shaped string inside it is flagged as a false positive — the
  same class this fix targeted, a member it missed. Cheap fix (`/^[[:space:]]*```/` or a
  leading-whitespace strip), worth doing in the same pass rather than finding it again at scale.

### Verdict

**NEEDS REVISION.** Fix 1 (exactly-one-index) is fully correct under adversarial generalization —
no further work needed there. Fix 2's three named mutations are solid, but the strip mechanism
itself introduces one required-severity gap (unterminated fence silently swallows real tags — a
new false-negative mode, worse in kind than what was fixed) and one optional one (indented fence
false-positive). The R1 upgrade's mechanical check is correctly placed, pure, and ordered before
publish/commit, but its failure path leaves the working tree dirty in a way that self-blocks every
future run — required fix 1 above. None of these require re-doing fixes 1-3's actual logic; each
is a small, localized addition (a cleanup line, a fence-balance check) to code that is otherwise
sound.

### Review Confidence

**Full read** of the diff (`git diff a95913d 6f1b327`), `implementation.md`, and all four changed
scripts in full. **Every claim was re-run, not re-read**: both required fixes from round 1 were
re-mutated from scratch (not just the author's pasted transcripts), generalized beyond the
author's own test cases (3-way duplicate, cross-directory duplicate, dangling-link interaction for
fix 1; fence-adjacent tag placement, list-indented fence, unterminated fence for fix 2), and the
R1 mechanical check was reproduced against a real stubbed copy of the actual generated HTML file
rather than trusted from the author's pasted proof. `ruff format --check`, `ruff check`, `mypy
--strict src`, and `pytest -q` were re-run against audio-adapter's own `.venv` and reproduced the
implementer's reported 222 passed / 1 skipped, clean lint/type results, with `src`/`tests`
confirmed byte-identical between the main checkout and the `6f1b327` snapshot before relying on
that venv. Gate runtimes were measured directly, not estimated, before extrapolating to 204 files.

## Review round 3 — the fix (2026-10-06)

Reviewing the round-3 fix commit `66e7244` on `feature/doc-conventions-audio-adapter`, scoped to
`git diff 6241fa9 66e7244` (three scripts and two documentation files) per AGENTS.md's "a change
written in response to a review is ordinary new code" — this addresses the two required fixes from
round 2 above. Rounds 1 and 2 are not re-reviewed.

**Worktree addressing (AGENTS.md rule 4):** this worktree's `HEAD` was `ab18d03` (1-2 commits of
unrelated `main` work ahead of round 2's base), not `66e7244` — the branch was checked out
elsewhere. Confirmed `ab18d03` is a strict ancestor of `66e7244` with a clean tree, so per rule 4's
correction path (not a stop condition) ran `git merge --ff-only 66e7244`, landing exactly on the
named tip rather than reading from a snapshot.

### Fix 1 — `status-page-refresh.sh` revert-on-failure: all four exit paths, correctly

Read every exit path after Phase 1 writes `$PAGE`: `GEN_STATUS -ne 0`, `[ ! -f "$PAGE" ]`,
`FORWARD_COUNT -eq 0`, `PUB_STATUS -ne 0` — all four now call `revert_page()`. This is the full
enumeration; there is no fifth path between Phase 1 and the final `exit 0` that touches `$PAGE`
and skips the helper.

Re-ran the author's own mutation independently (strip all `:::` markers from the real
`docs/status/petrobrain-status.html`, re-derive `FORWARD_COUNT` with the script's own awk/grep
pipeline, confirm it reproduces 0, run `git checkout -- "$PAGE"`, confirm `git status --porcelain`
comes back clean, confirm a second `FORWARD_COUNT` re-derivation against the restored file returns
24): reproduces exactly as claimed, not re-read from the pasted transcript.

`git checkout -- "$PAGE"` is correctly a no-op when the file already matches HEAD (nothing to
undo) and correctly restores a file Phase 1 deleted outright (confirmed separately below). On "a
file already committed by Phase 2" — that path cannot occur as written: `revert_page()` runs only
on the `PUB_STATUS -ne 0` branch, i.e. only when Phase 2 reported failure, so a legitimate Phase-2
commit is never followed by a revert call in the same run. The comment's own hedge ("if it already
committed... this is a no-op") covers the one real edge case: Phase 2 commits, then a *later* step
in the same phase (the push) fails, which the comment correctly reasons would be a no-op since the
committed file matches the new HEAD. Not independently re-verified by mutation (would require
faking a `claude -p` publish call), but the control-flow argument holds on inspection and the
`git diff --stat` for this round shows no behavior change to that branch beyond adding the call.

**The untracked-`$PAGE` case the task flagged as untested — probed, and the author's gap is real
but lower-severity than the tracked case, and not currently reachable in production.** Confirmed by
mutation in this worktree (untrack `docs/status/petrobrain-status.html` via `git rm --cached`,
commit, restore the same bytes to disk as an untracked file, then run `git checkout --
"$PAGE"` directly): it fails exactly as predicted (`error: pathspec '...' did not match any
file(s) known to git`, exit 1), which `revert_page()`'s `2>/dev/null || true` swallows with no log
line. **But guard 2 at the top of the script — `git status --porcelain --untracked-files=no` —
explicitly excludes untracked files from its own dirty-check**, confirmed by running it against
the probe state: empty output, i.e. guard 2 reads the tree as clean despite the stray untracked
file sitting there. So the severe consequence round 2 found (next run sees dirty tree, skips
forever) does **not** happen here — the next run proceeds normally and either overwrites the stray
file with a fresh regeneration or, if that one also fails and `$PAGE` stays untracked, repeats the
same harmless-but-silent no-op. This is a real third instance of "a failure path degrades silently
instead of being logged" (see Standing Question below), but it is not production-reachable today:
`$PAGE` is already a tracked, committed file in this repo (confirmed via `git diff 66e7244 --stat
-- docs/status/petrobrain-status.html`, empty — this round didn't touch it, and it already exists
from an earlier commit), so the only way to reach "first ever run, untracked" would be deleting it
from git tracking first. Reverted the probe cleanly (`git revert`, confirmed `git status
--porcelain` clean and `git diff 66e7244 -- docs/status/petrobrain-status.html` empty afterward).
**Optional, not required** — logging the swallowed failure (`say "WARN: could not revert $PAGE
(untracked?)"` instead of bare `|| true`) would close it cheaply if the file's tracked status is
ever not guaranteed, but nothing today depends on that.

### Fix 2 — fence-balance detection: correct for this repo's actual markdown, one theoretical gap found and sized

Re-ran all three of the task's named proofs independently against real/probe files in
`audio-adapter/ROADMAP/` (not re-reading the author's pasted transcript):
- Unclosed fence (one opening ` ``` `, no close, followed by a real `#totally-unknown-tag` in
  plain prose) → both `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh` fail loudly
  (`unbalanced fenced code block (1 delimiter(s))`), exit 1. Confirmed.
- Indented fence inside a list item containing a `#tag`-shaped string → stripped, not flagged, by
  the gate; the real unknown tag outside the fence is still caught in the same run. Confirmed —
  this is the regression check the task called the one that matters, and it holds.
- A genuinely unknown tag in ordinary prose, with no fence involved at all → still caught
  (baseline case, re-verified first, before any fence mutation).

Went further with `grep -cE '^[[:space:]]*```' ` ` 's own blind spots, as the task asked:
- **Four-or-more-backtick fences** (```` ```` ````) — **not a gap**. The regex is not
  end-anchored, so a 4-backtick opener/closer still matches `^[[:space:]]*```` and both lines
  count as delimiters; parity comes out even and the fenced content is correctly stripped.
  Confirmed by mutation (4-backtick fence wrapping a fake tag, plus a real tag outside it — only
  the real tag flagged).
- **`~~~` (tilde) fences — a real gap, not handled at all.** The delimiter-count regex and the
  `awk` strip pipeline both match only backtick fences; a `~~~`-fenced block is invisible to this
  check entirely. Confirmed by mutation: a `~~~`-fenced block containing a fake tag is *not*
  stripped and gets flagged as an unknown tag — a false positive (loud, blocks the commit), not
  the dangerous false-negative direction this round exists to close, so it is the same severity
  class as round 2's already-accepted-and-deferred indented-fence-regex gap, not the unterminated-
  fence class. Checked whether this repo actually uses `~~~` fences: `grep -rlE '^~~~'` across
  every `.md` file in the repo (excluding `.venv`/`node_modules`) found zero hits outside my own
  probe file. Same bar the author and round-2 review already applied to the declined `#`-in-link-
  title case ("not in the repo today, including the corpus that's coming next") — **theoretical
  for this repo, not a required fix.** Worth a one-line comment if anyone later pastes
  CommonMark-authored content that happens to use tilde fences, but not urgent.
- **A line that is a close, not an open, inside an already-open fence** — not a risk by
  construction: the check is parity over delimiter *lines*, with no open/close role tracking, so
  it is correct regardless of which occurrences are semantically opens vs. closes. This is the
  same mechanism round 2's own unterminated-fence proof already relies on (an odd *count*, not a
  mismatched open/close pair), so there's nothing new to verify here.
- **A 4-space-indented, non-fenced block whose own content happens to start with literal
  backticks** — probed out of caution; behaves consistently (treated as a fence, stripped) because
  the regex can't distinguish "real fence" from "indented block that happens to start with the
  same three characters." Vanishingly rare in practice (would require someone to indent-format a
  literal fence example rather than escape it), and the outcome isn't wrong either way for content
  that doesn't actually contain a real tag. Not flagging as a practical risk.

### `roadmap-toc.sh`'s new non-zero exit — no caller breaks

Grepped the whole worktree for every reference to `roadmap-toc.sh` (hooks in `.claude/settings.json`,
every file under `.claude/skills/`, every other script in `.claude/scripts/`, `commit-quality-gate.sh`,
and prose in `docs/DOC_CONVENTIONS.md`): the only invocations are the usage comment inside the
script itself and the author's own manual test runs recorded in `implementation.md`. Nothing wires
it into a hook, a skill, or the commit-time gate — `docs/DOC_CONVENTIONS.md`'s own description
("`.claude/scripts/roadmap-toc.sh <subproject>/ROADMAP/` restores [the TOC] with standard bash
tools... No index read needed") frames it as a manual, human-invoked helper, not a gate, consistent
with `roadmap-tag-vocabulary-gate.sh` and `roadmap-entry-consistency-gate.sh` being the only two
scripts that carry "gate" in their name and "fail loudly" language in `DOC_CONVENTIONS.md`'s own
prose. The author's own flag in `implementation.md` ("worth knowing if anything downstream
currently assumes this script never fails non-zero") is answered: nothing does.

### Checks

- `bash -n` clean on all three changed scripts (`status-page-refresh.sh`,
  `roadmap-tag-vocabulary-gate.sh`, `roadmap-toc.sh`), re-run independently.
- `roadmap-tag-vocabulary-gate.sh` → `OK`, exit 0, against the real converted
  `audio-adapter/ROADMAP/` tree (23 entries including the one index).
  `roadmap-entry-consistency-gate.sh` → `OK`, exit 0 (unaffected by this round, confirmed
  unchanged by the scoped diff). `roadmap-toc.sh audio-adapter/ROADMAP/` → prints all 22 entries
  with correct tags, exit 0. `push-roadmap-gate.sh` and `graphify-dirty-flag.sh` (unchanged files)
  both exit 0 cleanly against this tree.
- `audio-adapter/.venv/bin/ruff format --check .` → clean; `ruff check .` → all checks passed;
  `mypy --strict src` → no issues, 15 source files; `pytest -q` → 222 passed, 1 skipped — all
  re-run directly, not re-read from `implementation.md`. `git diff 6241fa9 66e7244 --stat --
  audio-adapter/` is empty, confirming this round touched only `.claude/scripts/` and plan docs.
- Gate runtime re-measured: `time bash .claude/scripts/roadmap-tag-vocabulary-gate.sh` → 0.309s
  real, consistent with the author's reported ~0.32-0.33s (round 2's baseline was 0.25s) — the
  added per-file fence-count `grep` is the entire delta, as claimed, and the extrapolation to
  ~0.6-0.7s extra at 204 files is unaffected by anything found in this round.

### Standing question — a third instance of the silent-degrade shape

Yes, found one, as the task asked to call out plainly if found: **`revert_page()`'s own `2>/dev/null
|| true` is a third instance of a failure path degrading silently instead of failing loudly or
logging**, surfaced by the untracked-`$PAGE` probe above. It differs from the first two in a way
worth being precise about rather than lumping together: the first two ("odd fence count",
"PUB_STATUS failure with nothing on the happy path check it") were *introduced* by this round's and
the previous round's own new mechanisms and were live risks at today's state of the repo. This
third one is pre-existing in the sense that `revert_page()` itself is this round's new code, but
the specific input that trips it (an untracked `$PAGE`) cannot occur given the file's current
tracked state — so it's the same shape, caught one layer earlier than it would have mattered. Listed
as optional above rather than required for that reason, but the pattern recognition the task asked
for holds: **every new guard this feature has added, across two rounds, has had at least one
failure path that said nothing.** Worth naming as a repo-wide habit to watch for in bash gates
generally (per-script `say`/log-to-stderr on every swallowed error, not just the `|| true` idiom),
rather than something to fix script-by-script as it's found a fourth time.

### Known-open, not defects (unchanged from round 2, re-confirmed in scope)

- `AA-3`'s accepted-vs-debt contradiction — still needs the user, untouched by this round.
- The declined `#`-in-link-title case — still absent repo-wide (not re-verified this round, out of
  scope; round 2's finding stands).
- The exactly-one-index gate — untouched by this round's diff, not re-tested.

### Required Fixes (this round)

None.

### Optional Refinements (this round)

- **`revert_page()` swallows a failed `git checkout` with `2>/dev/null || true` and no log line.**
  Reachable only if `$PAGE` is ever untracked when a revert is attempted (not possible today, since
  the file is already tracked and committed) — but if that ever changes, the failure is invisible.
  A one-line `say "WARN: revert of $PAGE failed (untracked?)"` on the `||` branch would close it at
  negligible cost.
- **`~~~`-fenced blocks are invisible to the new fence-balance check and the strip pipeline in both
  `roadmap-tag-vocabulary-gate.sh` and `roadmap-toc.sh`.** Zero uses in this repo today (verified
  by `grep` across every `.md` file), same bar applied to the already-declined link-title case —
  theoretical, not required. Worth a one-line comment noting the limitation if this project ever
  ingests externally-authored CommonMark content.

### Verdict

**APPROVED.** Both of round 2's required fixes are correctly and completely addressed: the
`revert_page()` helper covers all four of the real exit paths (not just the one named), and the
fence-balance check fails loudly on an unterminated fence in both scripts while the widened
indent-tolerant regex closes round 2's optional finding too. Every mutation probe the task asked
for was re-run independently against real files rather than trusted from the pasted transcript,
including two the author didn't test (untracked `$PAGE`, tilde fences) — both turned out to be
real-but-low-severity gaps that are correctly left as optional given this repo's actual content.
`roadmap-toc.sh`'s new non-zero exit has no live caller to break. Checks, gate runtimes, and the
audio-adapter test suite all reproduce cleanly and match the author's reported numbers.

### Review Confidence

**Full read** of the scoped diff (`git diff 6241fa9 66e7244`), `implementation.md`'s round-3
section, and both changed gate scripts in full, with the worktree corrected to the exact named tip
(`git merge --ff-only`) rather than reviewed from a snapshot. Every claim was re-run: both required
fixes were re-mutated from scratch against real files in `audio-adapter/ROADMAP/` and the real
`docs/status/petrobrain-status.html`, not re-read from `implementation.md`'s pasted output; the
fence mechanism was probed past the task's four named edge cases (4+ backticks, tilde fences,
close-not-open parity, a non-fenced indented block starting with literal backticks); the
untracked-`$PAGE` gap the task flagged as untested was reproduced and traced through guard 2's own
`--untracked-files=no` to confirm it does not wedge; `roadmap-toc.sh`'s caller set was checked by
grep across the whole worktree rather than assumed from the task's framing. `bash -n`, all five
gate/helper scripts, and all four audio-adapter checks were re-run directly against this worktree,
not against `main`'s copies.

---

## Review round 4 — the whole branch before DoD (2026-10-09)

Branch `feature/doc-conventions-audio-adapter`, tip `6c0325b`. 34 commits, 335 files,
+15,943/−8,224 against `main`. Covers both pieces of work: the roadmap/backlog split
(`plans/obsidian-links-and-tags/`, Stages 0–5 + the `WM-M<n>` rename) and the always-loaded
compaction (`plans/always-loaded-compaction/`).

**Addressing.** Worktree HEAD was `29217c0`, a strict ancestor of the named tip with a clean tree,
so `git merge --ff-only 6c0325b` per `AGENTS.md` rule 4. All five named input documents verified
present after the fast-forward. Worth recording: this is the fourth consecutive stale dispatch, and
rule 4's *compacted* text was sufficient to handle it correctly without consulting
`docs/AGENT_WORKTREE_PROTOCOL.md` — direct evidence for the compaction judgement reviewed below.

### Content fidelity — no loss found, and the sanctioned-transformation list was incomplete

This was the irreversible risk, so it was verified independently rather than by re-reading the
implementers' own scripts. Method, in two passes:

1. **Word-shingle reconstruction.** For each of the eight sources, `git show main:<path>` reduced to
   a normalised word stream (markdown stripped, inline tags dropped, `[[X]]` → `X`), every 8-word
   shingle indexed, and checked against the same reduction of the destination directory + pointer.
   This is robust to re-wrapping, which line-level comparison is not — a first line-level pass
   produced 107 "unaccounted" lines that were almost entirely re-flowed prose.
2. **Whole-tree pass** over all 1,432 tracked `.md` files, to catch content that moved *across*
   destinations (a body-layer debt entry folded into audio-adapter's own entry, a preamble moved to
   an index). The per-directory pass is blind to that by construction.

Divergence was 1.8–4.8% per source, and the distribution resolves it cleanly: **280 of 294 missing
runs are exactly 14 words**, which is 2×(N−1) — the arithmetic signature of a shingle window
straddling an entry boundary that is now a file boundary. Nothing at that length is loss.

Of the 25 runs longer than 15 words that survived the whole-tree pass, every one was accounted for:

| class | disposition |
|---|---|
| file-header preambles (`body-layer/BACKLOG.md:3-15`, `todo/backlog.md:3-18`, etc.) | reworded into the indexes and the pointer bodies; substance present |
| `### Added <date>` group headers | dissolved, but **the dates survive** — `todo/backlog/todo-backlog.md:44,50,75` preserves the groupings |
| positional cross-references ("see the Slice 1 entry **above**", "the voice-character entry **below**") | correctly rewritten; the facts they pointed at are present |
| the ~365-line "Live acceptance debt" preamble and its 18 entries | the deliberate Stage 2 folding; verified below |
| `## Backlog (body-layer)` / "Moved to BACKLOG.md" pointer sections | obsolete by construction |

**The folding was verified by its facts, not its shape.** The largest single run (242 words, the
SPU-8 debt entry) resolves to `audio-adapter/ROADMAP/AA-3.md`, which carries `arg 377` and both
uncalibrated constants (`ON_GROUND_AGL_THRESHOLD_M`, `MISSION_START_ICS_DELAY_S`). `#needs-flight`
landed on 12 entry files across four subprojects, and the two out-of-subproject debt items were kept
as explicit pointers in `body-layer/ROADMAP/body-layer-roadmap.md:30-35`.

**One correction to the task's framing:** the three sanctioned transformations were not enough. The
`M<n>` → `WM-M<n>` rename is a fourth, and without tolerating it the world-model source alone
reports 44 spurious unaccounted lines. Anyone re-running this check needs all four.

**The three `**OPEN**` flags are accurate**, and better than declared — `body-layer/ROADMAP/BL-W12.md:73`
resolves its own contradiction mechanically (`git merge-base --is-ancestor ff7934e HEAD`) and
records the finding without editing the source claim, exactly as instructed.

### Gates — proven by mutation across all seven directories

Discovery coverage was established by planting a violation in each of the seven split directories in
turn, not by a green run. All 21 checks fired and named the right file; a tracked-file mutation
(`world-model/ROADMAP/WM-M5.md`) confirmed tracked content is scanned too, restored byte-identically
by `shasum`. `graphify-dirty-flag.sh` matches all 20 relevant paths including all eight pointers, and
**the pre-existing `BACKLOG` hole the plan flagged as its highest-value line is genuinely fixed**.
`graph-corpus-files.sh` emits 435 files with no directory contributing zero. The corpus guard still
refuses when the count exceeds the ceiling (verified by temporarily lowering it). The
`status-page-refresh.sh` revert-on-failure fix from round 3 is present on all four exit paths.
Sentinel is byte-identical in all eight pointers, so a fixed-string test catches every one.

### Required Fixes (this round)

**RF4-1 — root `CLAUDE.md:337-341`: four of five rows in the backlog-ID table name pointer files, and
the stated minting rule then collides with existing IDs.** The `AA-B<n>` row *was* updated in Stage 1
to `audio-adapter/ROADMAP/ (split; …is now a pointer)`; the other four were never updated in Stages
2–5. The rule nine lines below is *"A new item takes the next unused number in its file. Read the
highest existing one rather than counting items."* Applied to the file each row names:

| row | file named | highest readable there | actually highest | mints | collides with |
|---|---|---|---|---|---|
| `WM-B<n>` | `world-model/ROADMAP.md` | none | `WM-B16` | `WM-B1` | 16 items |
| `X-B<n>` | `todo/backlog.md` | `X-B29` (prose) | `X-B34` | `X-B30` | 5 items |
| `BL-B<n>` | `body-layer/BACKLOG.md` | `BL-B42` (prose) | `BL-B46` | `BL-B43` | 4 items |
| `AC-B<n>` | `aircraft-layer/ROADMAP.md` | `AC-B3` (prose) | `AC-B5` | `AC-B4` | 2 items |

This violates the same file's *"Numbers are never reused and never renumbered"* invariant, which it
itself calls *"worse than no ID, because a commit message or plan citing the old meaning now reads as
evidence for the new one."* Lines 320-322 compound it: they still call `todo/todo.md` and
`todo/backlog.md` *"the source of truth"* and say *"prefer the User priority tasks at the top of the
file"* — that file is now 11 lines of pointer. **Fix first.**

**RF4-2 — none of the three new gates is wired to anything, while `docs/DOC_CONVENTIONS.md:354`
reads as though they are.** `grep` for all three across `.claude/settings.json`,
`install-git-hooks.sh` and `commit-quality-gate.sh` returns nothing; `install-git-hooks.sh` installs
only `graphify-dirty-flag.sh` and `graphify-ast-refresh.sh`. The convention doc says they are *"run
before committing a converted file (and available to run standalone)"*, which states a mechanical
guarantee that does not exist. Concrete failure: a dangling `[[ID]]`, an orphaned entry or an
unlisted tag commits clean across 253 entry files and surfaces only when someone clicks or greps.
This is precisely the condition `AGENTS.md` says *"will keep being broken"* — and the gates are
cheap enough that all four ran in seconds over the full tree. Fix: a block in
`commit-quality-gate.sh` conditioned on `$STAGED` matching
`(^|/)ROADMAP/|^todo/(backlog|todo)/|^docs/TAGS\.md$`.

**RF4-3 — `body-layer/ROADMAP/body-layer-roadmap.md:27`: the published `#needs-flight` recipe names
two pointer files and omits audio-adapter entirely.** As written it returns 10 files and **exits 0**,
silently missing four real unflown items — `aircraft-layer/ROADMAP/AC-8.md`,
`world-model/ROADMAP/WM-W2.md`, `audio-adapter/ROADMAP/AA-2.md`, `audio-adapter/ROADMAP/AA-5.md`.
This recipe *is* the replacement for the dissolved debt list and the whole of the plan's benefit (d).
`docs/TAGS.md:4` already carries the correct form (`*/ROADMAP/ todo/backlog/`), so this is a
one-line defect, not a judgement call.

**RF4-4 — the `WM-M<n>` rename left two live documents describing the old scheme, and corrupted one
sentence.** `docs/DOC_CONVENTIONS.md:74-77` is the authority: *"world-model is now regular … There is
no irregular ID shape left anywhere in the repo."* Against that:

- `world-model/ROADMAP.md:4` — *"bare `M<n>` for a milestone, e.g. `M5.md`"*. The file is
  `WM-M5.md`; `M5.md` does not exist. This is the first file a reader of that subproject opens.
- `world-model/ROADMAP.md:7` — *"why this subproject's three-shape ID space is recorded rather than
  fixed"*. It was fixed.
- `world-model/ROADMAP/world-model-roadmap.md:17-18` — *"The ID space in this directory is
  deliberately irregular, and `docs/DOC_CONVENTIONS.md` records it rather than fixing it.**
  Milestones are bare `M<n>` (`WM-M0.md`…`WM-M11.md`)"* — self-contradictory within one sentence.
- `world-model/ROADMAP/world-model-roadmap.md:21` — **corrupted by the substitution**: *"several
  hundred bare `WM-M5`/`WM-M7` prose mentions across `plans/` and `research/`"*. Measured: **422**
  bare `M5`/`M7` and **zero** `WM-M5`/`WM-M7` in those trees. The sentence now asserts the opposite
  of the fact it was written to record, and it is arguing against a rename that has since happened.
  (Swept for other instances: `grep "bare WM-M"` hits this line only.)

**RF4-5 — eleven live documents still assert a bare world-model `M<n>`.** The miss class is uniform
and worth naming: the rename scoped by *owning* subproject and missed every **inbound
cross-subproject reference**. `world-model/ROADMAP.md:4,7` (in RF4-4); `aircraft-layer/CLAUDE.md:93`
(always-loaded, *"Mirrors `world-model/`'s M4/M5 pattern"*); `body-layer/ROADMAP/BL-11.md:47,272,368,371,461`
(five backticked bare IDs that `DOC_CONVENTIONS.md` says should now be `[[WM-M11]]`, and which
resolve to nothing as written); `body-layer/ROADMAP/BL-12.md:45`; `body-layer/ROADMAP/BL-B26.md:27`;
`body-layer/ROADMAP/BL-B30.md:29`; `todo/backlog/{X-B18.md:6, X-B26.md:24, X-B32.md:34, X-B4.md:114}`.
The sweep pattern matters, since the value of the negative depends on it:
`(^|[^-A-Za-z0-9_])M[0-9]+([^A-Za-z0-9_]|$)` — excluding `-` is load-bearing, because `\bM[0-9]+\b`
matches the `M7` inside `WM-M7` and buries the real hits in ~200 false ones.

**RF4-6 — consumers instructed to *write into* a pointer file.** These are the dangerous half: a
reading consumer is rescued by the pointer's own prose, a writing one never reads it.

- `.claude/agents/dod.md:105` — *"Record the outstanding item in … `body-layer/ROADMAP.md`'s 'Live
  acceptance debt' section"*. That section exists in **no** file: `grep -rl "Live acceptance debt"`
  shows the phrase is absent from `body-layer/ROADMAP/body-layer-roadmap.md` too, the list having
  been dissolved into per-entry `#needs-flight`. A DoD agent either reports the debt in a one-off
  note — the exact failure the rule was added after a retro to stop — or creates the section inside
  a 7-line pointer where nothing reads it.
- `.claude/agents/dod.md:193` and `:278`; `.claude/skills/merge/SKILL.md:42-49, 74-78`;
  `.claude/skills/retro/SKILL.md:139, 161`. The merge case is the sharpest: a merge writes a
  done-entry and its merge-commit hash into the pointer, the real entry file stays open,
  `roadmap-toc.sh` and `grep '#status/done'` still report it open, and `push-roadmap-gate.sh` is
  satisfied because *a* `ROADMAP.md` was touched — so the drift the skill exists to prevent happens
  while every gate reports green.

**RF4-7 — consumers that count or search a pointer and report success.** `status-page/SKILL.md:45,49,64`
(the sentinel caveat is on the subsystem-card row only; the five counters and the forward map omit
46 `BL-B*` + 34 `X-B*` + 24 `X-T*` = 104 items, and the non-zero-forward-item backstop *passes*
because the correctly-read subproject roadmaps supply nodes); `status-page-refresh.sh:87-95` (names
`todo/todo.md` as a source, and conditions the sentinel test on *"a subproject ROADMAP.md"*, which
excludes it); `docs/status/README.md:15` — *"Take the `ROADMAP.md` list mechanically: `git ls-files
'*ROADMAP.md'`"*, which now returns **only the seven pointers** and not one `ROADMAP/` directory;
`.claude/skills/explore/SKILL.md:69` (`grep … todo/backlog.md` — a one-character fix to
`todo/backlog/`, and this is the recipe added because a captured user direction was *"missed by four
review reports"*); `.claude/skills/integrity-audit/SKILL.md:28,65,70` (seven of ten named audit
sources are pointers — it would report *no drift* from an empty comparison, and would have missed
every fix in this list).

**RF4-8 — `status-page-refresh.sh:124`: `revert_page()` reverts only `$PAGE`, re-opening the
permanent-outage wedge one file sideways.** Phase 1 runs `claude -p --permission-mode acceptEdits`
with a *prose* instruction not to touch anything outside `docs/status/`. If it edits any other
tracked file and the forward-count check then fails, the script reverts the page and leaves the
other file modified — and guard 2 (line 66, `--untracked-files=no`) skips **every subsequent run
forever**, logging only *"working tree has uncommitted changes"*. Identical failure class to the
round-3 fix. Guard 2 proved the tree clean before Phase 1, so everything dirty afterwards is
Phase 1's and can be reverted as a set, or the script can abort loudly.

**RF4-9 — `.claude/scripts/doc_provenance.py:93-95` hardcodes `audio-adapter/ROADMAP`.** Measured
live: `find_entries()` returns 22 entries, prefix `AA` only, against `doc_tags.entry_units()`'s 187
across five directories. Six of the seven split directories are invisible to it, so the gate's own
*"a generated `[[ID]]` that does not resolve to a real entry file"* check would reject a correct
`[[BL-11]]`/`[[WM-M5]]`/`[[X-B29]]` citation. A Stage-1 artifact never generalised in Stages 2–5;
latent only because zero provenance blocks exist, and it fires on the first one written after the
Obsidian work unpauses. `roadmap-entry-consistency-gate.sh:57-63` already has the correct
`*/pyproject.toml` discovery loop to copy.

**RF4-10 — Session Start: `CLAUDE.md` and `session-start.sh` each had the *opposite* half fixed.**

| | step 1 (subproject roadmap) | step 2 (`todo/`) |
|---|---|---|
| root `CLAUDE.md:88, 92-94` | **not fixed** — "the `ROADMAP.md` of whichever subproject", no caveat | fixed, names `todo/todo/todo-tasks.md` |
| `.claude/scripts/session-start.sh:66` | fixed, carries the sentinel clause | **not fixed** — names `todo/todo.md`, `todo/backlog.md` |

Low severity individually, since both pointers self-redirect, but it is the session-start path and
the inconsistency sits three lines apart in `CLAUDE.md`. `CLAUDE.md:45-46` and `:304` carry the same
untouched claim (*"which is that subproject's source of truth"*, *"marking a milestone done in a
subproject's `ROADMAP.md`"*), as do the six role files' shared "Where things live" block
(`architect:40`, `implementer:38`, `debugger:40`, `investigator:36`, `reviewer:38`,
`performance-reviewer:38`) and five subproject `CLAUDE.md`s — the irony being that the block sits
directly beneath its own warning not to trust a structure cached in a role definition.

### Observations (optional)

- **The compaction was applied honestly, and this round is evidence rather than assertion.** Every
  operative element survives in the always-loaded files: all four observable graph-query triggers,
  the graph-vs-`grep` table, both mechanical subproject-enumeration commands, rule 4's full
  procedure (name the sha, `rev-parse` first, `--ff-only` if a strict ancestor, the `git archive`
  snapshot method, the `pythonpath` trap, tooling-staleness), rule 1's entire harvest protocol
  including the `git rev-parse` tip check, the `--force` denial and "read what it names". Only
  incident narrative moved, and all three destinations carry it (`AGENT_WORKTREE_PROTOCOL.md` has
  `6b8a86e`, `19143fa`/`dce2534`, the `*.egg-info` case; `PROCESS.md` has the zero-queries lapse,
  the crossing-callout cost, the 5 Hz retro; `AGENT_ROLES.md` has the `dod` model change and the
  lapsed blanket skip). **Rule 1's keep decision is correct** on the stated criterion — no hook
  fires after an agent reports, so memory is the only enforcement there. The two staleness
  corrections made in passing (the retired three-step rebuild order, Session Start step 2) are real
  and were worth making.
- **~1,400 lines of gate-enforcing Python are linted by nothing.** `.claude/scripts/doc_provenance.py`
  and `doc_tags.py` sit outside every subproject, so no subproject's command set and not
  `commit-quality-gate.sh` reaches them, and there is no `ruff.toml` at the repo root — an
  unconfigured `ruff` flags 2 files for formatting and 6 `ruff check` findings (two of them
  `BLE001` on lines the author deliberately annotated `# pragma: no cover`). The findings matter
  less than the gap: **these scripts are the quality gates.** A decision for the user, not a defect.
- **Three gate scripts' header comments now contradict their own code**
  (`roadmap-entry-consistency-gate.sh:20-23,87`, `roadmap-tag-vocabulary-gate.sh:107`,
  `roadmap-toc.sh:26-27`), still describing a removed bare-`M<n>` regex alternative and the retired
  `M5`→`WM-5` cost argument. The authoritative-looking explanation a future maintainer reads before
  widening the regex again.
- **One structural fix would close RF4-6 and RF4-7 together.** Only four files in the repo know the
  sentinel exists. A `roadmap-source.sh <path>` resolver (or a one-line `grep -q 'split-roadmap'`
  helper) that these consumers call would beat eleven prose caveats that drift independently —
  which is this project's own stated preference for a mechanical backstop over a remembered rule.
- `graph-corpus-guard.sh:19` records a measured 434 against a live 435. One character, next time
  the file is touched, to keep "each raise carries a measured count" literally true.
- Latent word-splitting in `roadmap-tag-vocabulary-gate.sh:129` and
  `roadmap-entry-consistency-gate.sh:120` (`for f in $candidates` / `for target in $links`),
  unreachable with current filenames. `push-roadmap-gate.sh:9` / `commit-quality-gate.sh:10`:
  `cd "$CLAUDE_PROJECT_DIR" || exit 0` under `set -u` aborts before reaching the `|| exit 0`;
  behaviour is still fail-open for a PreToolUse hook, but not by the written mechanism.
- `world-model/RUN.md` and `NOTES.md` are named on neither side of the rename's stated boundary.
  RUN.md is live and carries one bare `M3` (`:237`). One sentence in `DOC_CONVENTIONS.md` either way.
- The sentinel's literal `see ROADMAP/` spelling under `todo/` is **correct and should not be
  "fixed"** — adapting it would break every fixed-string test at once. Worth saying so in
  `DOC_CONVENTIONS.md`, which currently shows only the `ROADMAP/` form.

### Scope

**Clean.** No source, test or tool file in any subproject is touched — the entire diff is markdown
plus `.claude/scripts/`, `.gitignore` (adding `__pycache__/`; `.obsidian/` is correctly unanchored
at `:32` and nothing under it is tracked) and one plan sketch image. The `world-model/data/`
invariant holds: still gitignored, nothing staged. The `todo/todo.md` split is outside
`plan.md`'s scope table but recorded as a user override in
`plans/always-loaded-compaction/plan.md`, as declared.

### Verification run

All four doc gates `OK`, rc=0 (`graph-corpus-guard: OK — 435 files (ceiling 520)`). `bash -n` clean
on all 13 modified shell scripts; `py_compile` clean on both helpers. Per-subproject checks for the
five subprojects the diff touches (aircraft-layer, audio-adapter, body-layer, mission-interpreter,
world-model — brain-layer untouched): **2702 passed, 7 skipped, 4 xfailed, 0 failed**, `ruff
format --check` / `ruff check` / `mypy --strict` clean in all five over their documented `src tests`
scope. Import resolution was proven local, not assumed: every pytest rootdir is under this
worktree, and body-layer's `../world-model/src` entry resolved to **this worktree's** world-model.
The nine `ruff format` non-conformances outside the documented scope were each confirmed
byte-identical to `main` by an empty `git diff main -- <path>`, with the diff machinery
sanity-checked against a file this branch does change — so all nine are genuinely pre-existing.

### Verdict

**NEEDS REVISION**

The irreversible risk is clear: no content loss, verified two ways, with the deliberate foldings
checked by their facts. The gates are real and proven by mutation in all seven directories. The
compaction is honest. Scope is clean and every subproject check passes.

What blocks it is a single recurring pattern rather than scattered defects: **the split was applied
to the files, and the consumers were updated one at a time, with roughly half of each pair missed.**
`CLAUDE.md`'s ID table updated one row of five; its Session Start updated step 2 and not step 1
while the hook updated step 1 and not step 2; `status-page/SKILL.md` caveated one source row of
three; the rename covered world-model's own documents and missed every inbound reference;
`doc_provenance.py` covered Stage 1's directory and never grew. Each is individually small and
mechanically checkable. RF4-1 is the one that must not ship — it silently mints a colliding ID
against an invariant the project calls worse than having no IDs — and RF4-2 and RF4-3 together mean
the convention's enforcement and its headline benefit are both currently non-functional.

### Review Confidence

**Full read**, with the depth concentrated where the task asked. Content fidelity was reconstructed
independently (word shingles, two passes, whole-tree) rather than taken from the implementers'
own verification, and the entry-boundary artifact was identified arithmetically rather than
assumed. Gate discovery was proven by planting a violation in each of the seven directories and
restoring by `shasum`, not by a green run. Every required fix below was re-verified first-hand
before being recorded, and one relayed claim was **corrected in the process**: the ID collision is
real, but it mints `X-B30`/`BL-B43`/`AC-B4` (the pointer bodies quote an example ID in prose), not
`X-B1` as first reported — the conclusion held, the mechanism did not. Not independently re-derived:
the exact line numbers in the eleven bare-`M<n>` hits of RF4-5 and the per-consumer line numbers in
RF4-6/RF4-7 beyond the eight spot-checked (`dod.md:105`, `explore/SKILL.md:69`,
`docs/status/README.md:15`, `BL-11.md:47`, `aircraft-layer/CLAUDE.md:93`, `X-B18.md:6`, plus both
world-model files in full). `status-page-refresh.sh` was not executed end-to-end — it targets the
main checkout and spawns `claude -p` — so its forward-count assertion was exercised verbatim against
crafted pages instead.
