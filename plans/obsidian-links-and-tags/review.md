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
