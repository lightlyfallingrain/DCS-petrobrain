# Definition of Done — `feature/doc-conventions-audio-adapter`

**Verdict: PASS-WITH-DEBT.** Scoped to tip **`3ef2d5a496948fb9e7cd31b42107b5308dbbe0cc`**. A DoD
verdict is a statement about one commit; if the branch moves, this is stale.

Covers both pieces of work: the roadmap/backlog split (`plan.md`, Stages 0–5 + the `WM-M<n>`
rename) and the always-loaded compaction (`plans/always-loaded-compaction/plan.md`).

**Addressing.** Worktree HEAD was `29217c0`, a strict ancestor of the named tip with a clean tree,
so `git merge --ff-only 3ef2d5a` per `AGENTS.md` rule 4. Seventh consecutive stale dispatch. All
five named input documents verified present afterwards, plus both plans and
`docs/AGENT_WORKTREE_PROTOCOL.md`.

---

## 1. Mechanical gate

### Per-subproject checks — all six, PASS

Subproject list taken from root `ROADMAP.md`'s status table on this branch, cross-checked
mechanically against `git ls-files '*/pyproject.toml'` (six, agreeing). Each subproject's own
`CLAUDE.md` "Commands" section; `mypy` run from inside each subproject (CWD-only config
discovery); tools resolved from the main checkout's `<subproject>/.venv/bin/` since this worktree
has no venvs.

| subproject | `ruff format --check src tests` | `ruff check src tests` | `mypy src` | `pytest tests -q` |
|---|---|---|---|---|
| aircraft-layer | OK (56 files) | OK | OK (21 files) | **256 passed** |
| audio-adapter | OK (29 files) | OK | OK (15 files) | **222 passed, 1 skipped** |
| body-layer | OK (118 files) | OK | OK (54 files) | **1551 passed, 4 xfailed** |
| brain-layer | OK (12 files) | OK | OK (7 files) | **45 passed** |
| mission-interpreter | OK (46 files) | OK | OK (31 files) | **108 passed, 3 skipped** |
| world-model | OK (118 files) | OK | OK (72 files) | **565 passed, 3 skipped** |

**Total: 2747 passed, 7 skipped, 4 xfailed, 0 failed.** rc=0 on all 24 commands.

brain-layer is untouched by the diff and was run anyway; the review's five-subproject figure
(2702 passed) plus brain-layer's 45 reconciles exactly to 2747.

Aircraft-layer's Lua syntax check (`luac5.1 -p` over `dcs-export/*.lua`) is not applicable: the
diff touches no `.lua` file.

### Out-of-scope `ruff format` non-conformances — 25 of 28 proven pre-existing

A repo-wide `ruff format --check .` reports 28 files. Each was checked against `main` with
`git diff --stat main -- <path>`, and the diff machinery was sanity-checked against a file this
branch does change (`docs/DOC_CONVENTIONS.md`, +492). Result:

- **25 byte-identical to `main`** — genuinely pre-existing, outside every subproject's documented
  `src tests` scope (`world-model/research/` ×5, `world-model/tools/` ×2, `plans/` ×11,
  `.claude/skills/` ×2, plus `body-layer/research/`, `aircraft-layer/research/`,
  `brain-layer/tools/`, `.claude/scripts/los-verdict-coverage.py`).
- **`docs/concept/WORLD_MODEL_BUILDER.md`** is touched by this branch (10/10, the `WM-M` rename),
  but `main`'s own copy is equally non-conformant — pre-existing, not introduced.
- **`.claude/scripts/doc_provenance.py` (+558) and `doc_tags.py` (+698) are new on this branch and
  are non-conformant.** See §5.

### The four doc gates — real output

```
roadmap-entry-consistency-gate: OK                                      rc=0
roadmap-tag-vocabulary-gate: OK                                         rc=0
graph-corpus-guard: OK — 435 files (ceiling 520).                       rc=0
doc-provenance-gate: FAIL (166 lines, 126 distinct files)               rc=1
```

`graph-corpus-files.sh` emits **435** files with no directory contributing zero (body-layer 126,
world-model 84, todo 64, docs 54, aircraft-layer 52, audio-adapter 31, mission-interpreter 15,
plans 4, brain-layer 1, plus the four root documents). The round-4 observation that the guard
recorded 434 against a live 435 is **fixed** — the header now says 435 and records that it was
re-measured by running the script.

The provenance gate's red state is the judgement call. See §2.

---

## 2. The provenance gate: ACCEPTED as documented debt — with one required correction

**`doc-provenance-gate.sh` is deliberately not wired into `commit-quality-gate.sh`, and it exits
1. I accept that for DoD.** The reasoning at the wiring site
(`commit-quality-gate.sh:165-182`) is sound and its arithmetic is independently reproducible. But
the record it leaves is wrong in three ways, one of which breaks the unblock condition itself.

### What I verified, by execution

**Nothing runs this gate automatically.** Confirmed by grep across `.claude/settings.json`,
`install-git-hooks.sh`, `.git/hooks/` and `commit-quality-gate.sh`: the only non-self references
are docstring mentions in sibling scripts and `docs/DOC_CONVENTIONS.md`. A red standalone gate
blocks no one today.

**The counterfactual holds, and I ran it rather than reading it.** Monkeypatching
`split_entry_dirs` back to the pre-RF4-9 hardcoded `audio-adapter/ROADMAP` and calling the same
`gate()` entrypoint:

```
post-fix discovery dirs: aircraft-layer/ROADMAP, audio-adapter/ROADMAP, body-layer/ROADMAP,
                         mission-interpreter/ROADMAP, world-model/ROADMAP, todo/backlog, todo/todo
post-fix entry count: 245
pre-fix entry count: 22
doc-provenance-gate: OK
PRE-FIX GATE rc = 0
```

So the red gate is caused entirely by RF4-9's discovery fix, exactly as claimed. The fix is
correct and must not be reverted — reverting it reinstates a gate that rejects a correct
`[[BL-11]]`/`[[WM-M5]]`/`[[X-B29]]` citation.

**Wiring it would refuse every commit touching any `ROADMAP/` path, repo-wide.** Proven
by mutation in §4.

### The three corrections to the record

**(a) The figure is 126 documents, not 127.** 166 FAIL lines = **126 "is stale or hand-edited"**
(one per distinct file) + **40 "cited document missing"**. The 127 comes from counting the literal
word `cited` as a 127th filename — I made the same off-by-one on my first pass before splitting
the classes.

**(b) "126 documents' blocks are stale" misdescribes 120 of them: they have no block at all.**
The regeneration diff is purely additive — 230 added citation lines, **zero removed** — and 120 of
the 126 gain a whole new `<!-- doc-provenance:start -->…end -->` pair. Only 6 have an existing
block that wants more citations. So the operative framing is not "regenerate stale blocks" but
**"the gate is ahead of the work it checks"**: `plan-document-graph.md` Stage B step 2 — *"Run over
`*/research/`, `docs/acceptance/`, `audio-adapter/ROADMAP/`. Commit the blocks"* — has never been
run. Wiring the gate now would block every roadmap commit because a **paused stage has not been
built**, which is a nonsense gate rather than a quality gate. That is a stronger argument for the
departure than the one written down, and it is why I accept it.

**(c) REQUIRED FOLLOW-UP — RF-DoD-1: the named unblock command does not work.** The condition says
*"once the 127 blocks have been regenerated and reviewed (one command,
`.claude/scripts/doc-provenance-refresh.sh`)"*. I ran it (in dry-run `check` mode, which shares
`refresh()`):

```
$ python3 .claude/scripts/doc_provenance.py check
doc-provenance-refresh: ERROR: cited document missing: audio-adapter/research/mi24p-command-surface.md
rc=1
```

**It aborts on the first mis-resolved citation and writes nothing** — `refresh()` validates
everything up front, by design, so there are no partial writes and no progress.

Cause: `doc_provenance.py:202`

```python
target = f"{sub}/research/{filename}" if sub else f"audio-adapter/research/{filename}"
```

A bare `research/<file>.md` citation with no subproject prefix is resolved to **`audio-adapter/`
unconditionally**. This is the *same hardcoding class RF4-9 fixed, surviving in the other half of
the same file*: entry **discovery** was generalised to seven directories, citation **path
resolution** was not. Measured: of the 19 `audio-adapter/research/` missing-document failures,
**17 are mis-prefixed** and exist under another subproject —

| cited as | actually at |
|---|---|
| `audio-adapter/research/mi24p-command-surface.md` | `aircraft-layer/research/` |
| `audio-adapter/research/2026-09-12-miz-file-structure.md` | `mission-interpreter/research/` |
| `audio-adapter/research/2026-09-03-m1-coordinate-transform-verification.md` | `world-model/research/` |
| `audio-adapter/research/2026-10-05-performance-review.md` | `body-layer/research/` |
| …13 more | |

Two are genuinely absent, and the remaining 21 missing-document failures are citations to
`plans/<f>/plan.md` files that do not exist (`plans/bl11-tick-cost/` has no `plan.md`;
`plans/post-review-fixes/` holds only `explore-notes.md`) — a data issue in entry prose, not a
code bug.

**The fix is the same shape as RF4-9's**: resolve a bare `research/` citation relative to the
*citing entry's own* subproject, and **reject an ambiguous basename rather than guessing** —
`2026-10-05-security-audit.md` and `2026-10-05-performance-review.md` each exist in two
subprojects, so a fixed prefix cannot be right for both. Lines 5, 42, 237 and 383 of the same file
also still describe the audio-adapter-only scope, as does
`doc-provenance-refresh.sh`'s own header (*"into every document already cited, in prose, by
`audio-adapter/ROADMAP/AA-*.md`"*) — which now understates the command's blast radius by 6×, in
the one place somebody deciding whether it is safe to run would look.

**Not a merge blocker.** The gate is unwired, the fix lives inside the paused work's own
territory, and nothing in the repo behaves differently today. But the unblock condition **is**
written down and **is not** correct, and whoever resumes Stage B hits this on their first command.

### The two rejected options, stated for the record

- **Regenerate the 126 now** — overrides the user's pause, and adds ~230 keyword-derived citations
  nobody has reviewed into 120 research/acceptance documents. It is also impossible as written
  (RF-DoD-1 blocks it).
- **Revert the discovery fix** — reinstates a gate that rejects correct cross-subproject
  citations. Strictly worse.

---

## 3. Round-4 required fixes — spot-checked by execution

`review.md`'s "Review round 4" is the fix spec. Content fidelity was independently verified there
(word-shingle index, two passes, every divergent run accounted for) and was **not** redone.

| fix | verified how | result |
|---|---|---|
| RF4-1 | read `CLAUDE.md:352-358` + executed the minting recipe in all 8 ID spaces | **FIXED** (below) |
| RF4-2 | grep for all three gates across settings/hooks/gate; read `DOC_CONVENTIONS.md:422-439` | **FIXED, with a documented departure** (§2) |
| RF4-3 | executed the published recipe | **FIXED** (below) |
| RF4-4 | read both world-model documents; re-measured the figure | **FIXED**, one false negative (below) |
| RF4-5 | prescribed-pattern sweep over 324 live documents | **FIXED** (below) |
| RF4-6 / RF4-7 | executed `roadmap-source.sh` on all 8 pointers + 3 non-pointers | **FIXED** (below) |
| RF4-8 | not re-executed — targets the main checkout and spawns `claude -p` | read only, see §6 |
| RF4-9 | counterfactual run (§2) | **substantially fixed; RF-DoD-1 is its remainder** |
| RF4-10 | read `CLAUDE.md` step 1/2 and `session-start.sh:66` | **FIXED** |

### RF4-6/RF4-7 — `roadmap-source.sh` resolves all eight pointers

```
aircraft-layer/ROADMAP.md      -> aircraft-layer/ROADMAP/aircraft-layer-roadmap.md           rc=0 exists
audio-adapter/ROADMAP.md       -> audio-adapter/ROADMAP/audio-adapter-roadmap.md             rc=0 exists
body-layer/ROADMAP.md          -> body-layer/ROADMAP/body-layer-roadmap.md                   rc=0 exists
body-layer/BACKLOG.md          -> body-layer/ROADMAP/body-layer-backlog.md                   rc=0 exists
mission-interpreter/ROADMAP.md -> mission-interpreter/ROADMAP/mission-interpreter-roadmap.md rc=0 exists
world-model/ROADMAP.md         -> world-model/ROADMAP/world-model-roadmap.md                 rc=0 exists
todo/backlog.md                -> todo/backlog/todo-backlog.md                               rc=0 exists
todo/todo.md                   -> todo/todo/todo-tasks.md                                    rc=0 exists
```

Every target exists on disk. Non-pointers pass through unchanged (`ROADMAP.md`,
`docs/DOC_CONVENTIONS.md`, `body-layer/ROADMAP/BL-11.md` → themselves, rc=0). This is the single
structural fix the round-4 observations asked for, and it closes RF4-6 and RF4-7 together rather
than by eleven prose caveats that drift independently.

### RF4-3 — the `#needs-flight` recipe

Executed verbatim as published in `body-layer/ROADMAP/body-layer-roadmap.md:27` (identical to
`docs/TAGS.md:7`):

```sh
grep -rl '#needs-flight' --include='*.md' */ROADMAP/ todo/backlog/ todo/todo/ \
  | grep -vE -- '-(roadmap|backlog|tasks)\.md$'
```

Returns **13 entries across four subprojects**, no errors, and includes all four the broken form
silently missed: `aircraft-layer/ROADMAP/AC-8.md`, `world-model/ROADMAP/WM-W2.md`,
`audio-adapter/ROADMAP/AA-2.md`, `audio-adapter/ROADMAP/AA-5.md`. Plus `body-layer/ROADMAP/`
BL-11, BL-W1, BL-W5, BL-W6, BL-W12, BL-W35, BL-W36, BR-1.1, BR-1.2. `*/ROADMAP/` covers all five
subprojects that have one (brain-layer has none, by design), so the glob plus the two `todo/`
directories reaches all seven split directories — the negative is trustworthy.

### RF4-1 — the ID-minting recipe, executed in all eight spaces

`sort -V` against an independently-computed truth (numeric sort on the digit run alone, per
prefix):

| directory | shape | n | published `sort -V` | independent truth | old `sort -t <X> -k2 -n` |
|---|---|---|---|---|---|
| body-layer/ROADMAP | `-B` | 46 | `BL-B46` | `BL-B46` ✓ | **`BL-B9`** ✗ |
| body-layer/ROADMAP | `-W` | 38 | `BL-W38` | `BL-W38` ✓ | `BL-W38` |
| aircraft-layer/ROADMAP | `-B` | 5 | `AC-B5` | `AC-B5` ✓ | `AC-B5` |
| audio-adapter/ROADMAP | `-B` | 3 | `AA-B3` | `AA-B3` ✓ | `AA-B3` |
| world-model/ROADMAP | `-B` | 16 | `WM-B16` | `WM-B16` ✓ | `WM-B16` |
| world-model/ROADMAP | `-W` | 12 | `WM-W12` | `WM-W12` ✓ | **`WM-W9`** ✗ |
| todo/backlog | `-B` | 34 | `X-B34` | `X-B34` ✓ | `X-B34` |
| todo/todo | `-T` | 24 | `X-T24` | `X-T24` ✓ | `X-T24` |

`sort -V` is correct in all eight. **Both documented failures of the old form reproduce exactly**
— `BL-B9` against a real `BL-B46`, `WM-W9` against a real `WM-W12` — so the two measured claims in
`CLAUDE.md:374-378` are true as published, and `sort -V` is right for `-B`, `-W` and `-T` alike.
All five rows of the prefix table now name a directory. Incidentally: highest ID equals item count
in every space, so nothing has been renumbered.

### RF4-4/RF4-5 — the `WM-M<n>` rename sweep

Prescribed pattern `(^|[^-A-Za-z0-9_])M[0-9]+([^A-Za-z0-9_]|$)` over **324 live documents** (all
`*/ROADMAP/` and `todo/` entry files, every `CLAUDE.md`, `AGENTS.md`, root `ROADMAP.md`,
`NOTES.md`, `docs/`, `world-model/docs/`, `RUN.md`). **69 hits, against 238 for the naive
`\bM[0-9]+\b`** — the `-` exclusion is load-bearing as stated, and buries nothing.

All 69 are legitimate:

| where | n | why it is fine |
|---|---|---|
| `NOTES.md` | 40 | dated citations to the milestone each insight was earned in — explicitly out of scope per `DOC_CONVENTIONS.md:123-124` |
| `docs/DOC_CONVENTIONS.md` | 14 | the rename's own account, incl. the superseded prior decision kept per `docs/PROCESS.md` |
| `docs/acceptance/`, `docs/handoff/` | 11 | dated records, deliberately untouched |
| `world-model/ROADMAP/world-model-roadmap.md` | 2 | the search-asymmetry note (below) |
| `mission-interpreter/.../-roadmap.md`, `body-layer/ROADMAP/BL-B42.md` | 2 | `MI24-outpost-M03.miz` (mission filename), `Soldier M4 GRG` (weapon) — the two false-positive classes `DOC_CONVENTIONS.md:131` names |

**Zero live documents assert a bare world-model `M<n>` as a milestone ID.** Every RF4-5 target is
clean: `world-model/ROADMAP.md`, `aircraft-layer/CLAUDE.md`, `body-layer/ROADMAP/{BL-11,BL-12,
BL-B26,BL-B30}.md`, `todo/backlog/{X-B4,X-B18,X-B26,X-B32}.md`.

RF4-4's corrupted sentence is fixed and now asserts the measured fact rather than its negation, and
the index says the ID space **is** regular.

**One false negative in the replacement sentence**, found by re-measuring it rather than reading
it. `world-model/ROADMAP/world-model-roadmap.md:23-24` claims *"422 bare `M5`/`M7` mentions across
`plans/` and `world-model/research/` and **no** `WM-M5`/`WM-M7` ones."* Measured now: **425 bare**
(a three-mention drift from prose written on this branch after round 4) and **14 `WM-M5`/`WM-M7`**,
all 14 inside `plans/obsidian-links-and-tags/{review,implementation}.md` — this feature's own
documents, which discuss the rename. The claim was true of the historical record it is about and
was falsified by the act of writing it down. Harmless; the operative point (`WM-M5` contains `M5`,
so the bare form finds both) holds. Noted because it is the sixth instance of this project's
prose-count-of-a-set pattern.

---

## 4. `commit-quality-gate.sh`'s staged-path condition — proven by mutation, restored by `shasum`

Recorded shasums first: `03f3bcc0…` `body-layer/ROADMAP/BL-11.md`, `acdcfbb5…`
`.claude/scripts/los-verdict-coverage.py`.

**Test 1 — a commit touching only a `.py` file must not trigger the roadmap gates.** A dangling
`[[ZZ-999]]` was planted in `body-layer/ROADMAP/BL-11.md` and left **unstaged**; only the `.py`
change was staged. The gates scan the whole tree, so if they had run they would have caught the
planted link — the discriminator is exact.

```
staged: .claude/scripts/los-verdict-coverage.py
rc=0, no output
```

**Test 2 — a staged dangling `[[ID]]` must be refused.** Staging the roadmap entry as well:

```
staged: .claude/scripts/los-verdict-coverage.py
        body-layer/ROADMAP/BL-11.md
{"continue":false,"stopReason":"…
## roadmap-entry-consistency-gate — FAIL
roadmap-entry-consistency-gate: body-layer/ROADMAP -- dangling link [[ZZ-999]], no ZZ-999.md in any converted directory"}
```

Both halves hold. Restored and verified: `shasum -c` → both `OK`, `git status --porcelain` clean.

Incidental, and **not a branch defect**: test 2 also reported `body-layer toolchain — FAIL:
missing tool(s): ruff mypy pytest`, because this worktree has no `.venv`. The main checkout does.
Worth knowing before anyone reads a worktree gate run as a real result.

---

## 5. Report, do not fix

**~1,400 lines of gate-enforcing Python are linted by nothing — confirmed, not closed.**
`.claude/scripts/doc_provenance.py` (+558, new) and `doc_tags.py` (+698, new) sit outside every
subproject's `src tests` scope; `commit-quality-gate.sh` does not reach them; there is no root
`ruff.toml`. An unconfigured `ruff` flags **both files for formatting** and **6 `ruff check`
findings** (incl. `PIE810` at `doc_tags.py:230` and two `BLE001` on lines the author deliberately
annotated `# pragma: no cover`). The findings matter less than the gap: **these scripts are the
quality gates.** Already surfaced to the user as a decision; unchanged here.

**Plan staleness.** `plans/obsidian-links-and-tags/plan.md` still excludes `todo/todo.md` from
scope in two places — the out-of-scope bullet at `:43-49` (*"Decision 2 scopes this to roadmaps and
backlogs; `todo/todo.md` is neither"*, and the argument that minting 24 permanent IDs for migrating
notes *"would collide"*) and the cost table at `:308` (`todo/todo.md | 9.1k | 9.1k | —`). The user
overrode this and Stage 3 split it into `todo/todo/X-T1…X-T24`, with `X-T<n>` now a declared ID
space in `docs/DOC_CONVENTIONS.md`. The override **is** recorded, at
`plans/obsidian-links-and-tags/implementation.md:1573-1574` — not in
`plans/always-loaded-compaction/plan.md` as round 4 states. Three stale assertions, one
mis-citation; none affects behaviour.

**Three gate scripts' header comments contradict their own code** (round-4 observation, unfixed by
design) — and `doc-provenance-refresh.sh`'s header is a fourth, which round 4 did not list. See
§2(c): that one is load-bearing, because it is what a reader checks before running the command.

---

## 6. Not verified, and why

- **Content fidelity** — independently verified in review round 4 by word-shingle reconstruction
  over all eight sources plus a whole-tree pass; deliberately not redone.
- **`status-page-refresh.sh` end to end (RF4-8)** — it targets the main checkout and spawns
  `claude -p --permission-mode acceptEdits`. Read only. Round 4 exercised its forward-count
  assertion against crafted pages instead.
- **Obsidian rendering** — no Obsidian here; the vault is the repo root and `.obsidian/` is
  gitignored. This is the user's to look at, and §7 explains why it is not a merge gate.
- **The "paused by user direction" status of the document-graph work.** Asserted in four places on
  this branch (`commit-quality-gate.sh:175`, `DOC_CONVENTIONS.md:436`, `implementation.md:1786`,
  `review.md:750`) — all written by this branch's own implementer and reviewer, so one claim
  repeated, not corroborated. I found no user-authored record of it in `todo/` or
  `docs/acceptance/`; `plan-document-graph.md`'s own verdict says *"Stages A + B, then stop"*, and
  Stage B has not run. **Worth the main loop confirming with the user.** It does not change the
  decision in §2: even unpaused, authoring 120 unreviewed provenance blocks is not a DoD step, and
  RF-DoD-1 blocks it mechanically anyway.

---

## 7. Acceptance testing — no user step is warranted as a gate

**This feature has no flyable behaviour and no user acceptance gate. Stating that plainly rather
than papering over it.**

Nothing reaches the aircraft, the crew, or any runtime path: no product source, test or tool file
in any subproject is touched. The entire observable surface is documents, conventions and
developer tooling — and that surface *is* mechanically verifiable, which is what §§1–4 did by
execution rather than inspection. There is no sortie to fly, and a card would be fabrication.

### The acceptance boundary — what this verification structurally cannot reach

- **Whether the split roadmaps are actually navigable in Obsidian.** Every gate here proves the
  *graph is well-formed* — no dangling `[[ID]]`, no orphan, exactly one index per directory, every
  tag in the vocabulary. **None of them can tell a well-formed graph from a useful one.** Whether
  clicking `#needs-flight` or `[[BL-11]]` lands somewhere a reader wants to be is a human
  judgement, and it is exactly what `plan-document-graph.md` Stage B's own stop point reserves:
  *"open Obsidian, click `#SPU-8`, and see whether the sketch is actually there."* Folding that in
  now would gate this merge on the **paused** work's acceptance criterion.
- **Whether the compaction lost something that mattered.** The always-loaded files dropped ~2.4k
  tokens with the incident evidence moved verbatim to three on-demand documents. A test suite
  cannot detect an agent that stops doing the right thing because the reason moved one file away.
  The honest evidence is behavioural and accumulates over the next week of dispatches — round 4
  noted one data point in its own favour (rule 4's compacted text sufficed to handle a stale base
  correctly without opening the protocol document), and this run is a second: same thing, seventh
  stale dispatch, handled from the compacted text alone.

### What the user may usefully do, at their leisure — not blocking

Open the repo root as an Obsidian vault on the branch and click around:
`body-layer/ROADMAP/body-layer-roadmap.md` → a `[[BL-B*]]` link → back; then the `#needs-flight`
tag. **Branch: `feature/doc-conventions-audio-adapter`** (`git checkout
feature/doc-conventions-audio-adapter`). Their checkout has been on `main` all session, so none of
this has been seen.

No artifact card: a card is for judgement needed where a terminal is not — a sortie, a Windows
session. This is a browse on the Mac they are already sitting at, and publishing a card for it
would be the friction the project's own rules warn trains the user to skip past.

---

## 8. Milestone completion — does this change what comes next?

**No subproject milestone moves, and no subproject's next milestone changes.** This is
cross-cutting documents-and-tooling work; the status of every milestone in all six subprojects is
untouched.

**One downstream assumption is invalidated, in the paused work's favour.**
`plan-document-graph.md` says Stage D is *"blocked on the corpus-ceiling decision and on Stage B's
observed value."* This branch **resolves the corpus-ceiling half**: the guard's ceiling is now 520
against a measured live 435, sized for ongoing entry growth rather than a next conversion, and the
plan's note that a subproject's conversion *"blocks Stage D"* is dissolved — every subproject's
roadmap and backlog is now split, so nothing is left to convert. Stage D remains blocked on Stage
B's value alone.

**Two things change the shape of Stages B–D, and both make them larger than planned:**

1. **RF-DoD-1 is now a prerequisite for Stage B** that did not exist when the plan was written.
   The named regeneration command aborts rc=1 writing nothing until the bare-`research/` citation
   path resolution is fixed (§2c). Resuming Stage B starts with a code fix, not a run.
2. **Stage B's "commit the blocks" step is measured at 126 documents and ~230 citations**, 120 of
   them gaining a block for the first time — against the plan's "151 units" estimate. Those 230
   citations are keyword-derived and unreviewed, which is the review step the plan already names
   and should be budgeted as the bulk of the stage.

**The accumulated debt this branch leaves is one item, and it is not a flight item:** the
provenance gate stays unwired until Stage B lands. It is recorded at the wiring site, in
`docs/DOC_CONVENTIONS.md:430-439` ("Standalone only, deliberately, and this is a temporary state
with a stated exit"), and now here with its condition corrected. **No live-acceptance debt is
created** — there is nothing to fly, so this adds nothing to any subproject's `#needs-flight` set
(still 13 entries, unchanged by this branch).

---

## 9. Checklist

**Code quality**
- [x] All six subprojects' format/lint/type/test pass — 2747 passed, 0 failed, rc=0 on 24 commands
- [x] No unhandled errors or panics in data paths — no product code touched
- [x] No debug output left in committed code
- [x] No leftover debug code or TODO comments introduced

**Scope & correctness**
- [x] Implementation matches the plans, with one declared and recorded user override
- [x] No unplanned scope added silently
- [x] No `CLAUDE.md` invariant violated — `world-model/data/` still gitignored, nothing staged
- [x] All new files staged and committed

**Testing**
- [x] Core logic covered — the four gates, proven by mutation across all seven split directories
      (round 4) and re-proven here on the staged-path condition
- [x] Tests meaningful, not decorative — every claim in §§2–4 was executed, not read
- [x] No existing tests broken

**Documentation**
- [x] Round-4 findings addressed — nine fixed, one with a documented departure I accept, plus
      RF-DoD-1 as its remainder
- [x] Non-obvious behaviour explained — `NOTES.md` harvest below

**Security**
- [N/A] `security-plan-review.md` — the 2026-09-24 cadence is one pass per feature immediately
  before DoD, not a plan-stage pass
- [x] `plans/obsidian-links-and-tags/security.md` — deep analysis, **APPROVED** (`f00df8b`)
- [x] `plans/obsidian-links-and-tags/performance.md` — gate scaling measured (`fa0bdc6`)

**`NOTES.md`** — two entries added under "Planning & Process Lessons":
- accepted debt's unblock condition must be executed, not just written down
- generalising a hardcoded scope has two halves, discovery and resolution

---

## Verdict

**PASS-WITH-DEBT**, scoped to `3ef2d5a`.

Mergeable. Every mechanical check passes across all six subprojects; the one red repo gate
(`doc-provenance-gate.sh`) is **accepted as documented debt** — it is unwired, nothing runs it,
reverting the fix that reddened it would be strictly worse, and its red state means "a paused stage
has not been built" rather than "the repo violates its own convention".

**One required follow-up, not a merge blocker: RF-DoD-1.** The unblock condition's named command
aborts rc=1 and writes nothing, because `doc_provenance.py:202` resolves a bare `research/`
citation to `audio-adapter/` unconditionally — RF4-9's hardcoding surviving in the path-resolution
half of the same file. Fix it before resuming Stage B, not before merging.

**No acceptance sortie, no artifact card, no live-acceptance debt.** An optional Obsidian browse
is offered on `feature/doc-conventions-audio-adapter`.
