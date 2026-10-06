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
