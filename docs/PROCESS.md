# Process

Generic engineering heuristics and protocols — not petrobrain-specific, but binding for
all work in this repo. Split out of `CLAUDE.md` to keep that file to per-session
essentials; consult this file when planning, implementing, or debugging.

## Phrasing Convention

State prohibitions with their positive alternative: "Don't X — use Y instead," not a bare
negative. A bare "don't use `unwrap()`" leaves the replacement unstated; "don't use `unwrap()` —
use `?` or `.expect(\"reason\")` instead" is actionable on its own.

## Decision Heuristics

1. Prefer stable, predictable behavior over clever optimizations
2. Prefer simple, debuggable solutions over clever ones
3. Prefer precomputation over per-request work if it reduces runtime cost
4. Avoid new abstractions unless they remove clear duplication
5. Choose solutions that can be iterated later

## Implementation Strategy

Build in stages: minimal working version → validate correctness → validate performance → refine.
Do not attempt final-quality implementation first.

## Debugging Protocol

1. Reproduce deterministically
2. Isolate subsystem
3. Add minimal instrumentation
4. Form hypothesis
5. Apply smallest fix
6. Verify
7. Remove debug code

No speculative fixes.

## Dependencies

Prefer the existing stack. New dependencies must be justified (purpose, safety, license). Keep dependencies minimal.

**Missing tool or library: ask, don't work around.** If an established tool or library would solve the task at hand (a syntax checker, parser, CLI, test utility) but isn't installed, stop and ask the user to install it — name it, give the install command, and say why this task needs it. Don't hand-roll a substitute or skip the check for something an existing solution already solves. Applies to dev tools on the machine as much as to project dependencies; a new *runtime* dependency in a subproject still needs the justification above. (User direction, 2026-09-13: a DCS Hook probe went unchecked because `luac` wasn't installed, when installing it was the fix.)

## Autonomy

Stop and ask when: architectural tradeoff is unclear, tests require rewriting, new dependency is needed, or scope significantly changes.

For a request that is technically challenging, also weigh value created against effort spent and
flag a bad trade before building — see `AGENTS.md`'s "Effort/Value Check" for what to cover and
when it applies (kept there, not restated here, because that file is always in context).

## Engineering Notes

Maintain `notes/` for non-obvious findings: bugs, perf bottlenecks, framework quirks, chosen solutions, workarounds. One file per topic, indexed by `notes/notes-index.md`; root `NOTES.md` is a pointer (`docs/DOC_CONVENTIONS.md`, "Split notes").
- Short, factual entries — one idea per bullet, no narrative
- Add when something non-trivial is discovered; never duplicate code comments
- Consult before making decisions in areas where prior issues are recorded

## Superseding a decision

When a decision is overturned, **do not rewrite it**. The original reasoning is usually why the
revision makes sense, and this project has repeatedly found the discarded argument to be the useful
part of the record.

Two rules make that safe rather than confusing:

1. **The revision goes above, as its own section** — `Decision 4 REVISED`, `Decision 1 REVISED` —
   carrying what changed, why, and what evidence overturned it.
2. **The original opens with a pointer to its replacement.** One blockquote naming the successor and
   summarising the change in a line.

Rule 2 is the one that is easy to skip and expensive to miss. Without it, a reader arriving at the
original — by search, by scroll, or as an agent retrieving that section alone — gets the superseded
design presented exactly as confidently as current material. **The failure mode this project keeps
hitting is not only missed information; it is the wrong version found, with nothing in the text to
distinguish it.** Anything that retrieves sections rather than whole documents makes that worse, so
the signal has to live in the section itself.

Plans that nothing current cites — no document, no code docstring — move to `plans/archive/`, which
is excluded from search indexes. That is a much smaller set than it sounds: most `plans/` content is
live reference material, and most staleness sits *inside* living documents, which is what rule 2 is
for.

## Keeping the knowledge graph honest

A queryable graph over the current-state design documentation lives in `graphify-out/`, built from
a curated corpus (`.claude/scripts/graph-corpus-files.sh` — a **file list, never a copied mirror**;
a mirror silently breaks cache keying and leaks its own name into node ids) — every `ROADMAP.md` and `CLAUDE.md`, `docs/`, `AGENTS.md`, `notes/`, `todo/`,
all `*/research/`, and the active plan. **A split roadmap's `ROADMAP/` entry files follow the
directory, not the filename** (`docs/DOC_CONVENTIONS.md`), so the corpus keeps covering a
subproject's milestone content after it splits rather than silently dropping it the moment
`ROADMAP.md` becomes a 4-line pointer. It exists because this project's recurring failure is not
missing documentation but **failing to find documentation that already exists**, and occasionally
finding a superseded version of it instead.

### Documents before the graph — that dependency is load-bearing

**Bring the documents current, then rebuild. The merge can sit anywhere around them.**

An earlier version of this section said "documents first, graph second, merge third", which
overstated it. The graph is gitignored and local, so merging changes nothing the rebuild would
index — only the documents-before-graph order actually matters. Stated as a rigid three-step
sequence it invited exactly the wrong trade the first time it was applied: holding up a merge for a
twenty-minute rebuild to honour a step whose position was arbitrary. What must not happen is the
rebuild being **skipped**; when it happens relative to the merge does not matter.

1. **Bring the documents current** — what was built, what is left, what this work superseded. A
   superseded section keeps its body and gains a pointer to its replacement (see "Superseding a
   decision"); a plan nothing current cites moves to `plans/archive/`. This is the Definition of
   Done's job.
2. **Rebuild the graph** — `/graph-refresh`. The corpus is a file list
   (`.claude/scripts/graph-corpus-files.sh`), not a directory, and extraction is cache-aware so
   only genuinely changed files cost anything.
3. **Merge and push.** Afterwards code, documents and graph describe the same state.
4. **Clear the flag** — `rm -f graphify-out/.needs_update`.

Getting this backwards is **worse than skipping the rebuild entirely.** A graph built from stale
documents does not merely lag — it *launders* the staleness. The next query returns the outdated
claim with a citation and a confidence score attached, which is considerably more convincing than
the stale paragraph was on its own. A tool that makes wrong information easier to find and harder
to doubt is a net loss.

### Why the rebuild is not automatic

Semantic extraction over prose needs an LLM, and an LLM inside a commit hook would be slow,
non-deterministic, and fire on typo fixes. So the hooks deliberately do almost nothing:

| hook | script | does |
| --- | --- | --- |
| `pre-commit` | `graphify-dirty-flag.sh` | appends changed doc paths to `.needs_update` |
| `post-commit` | `graphify-ast-refresh.sh` | re-runs AST extraction on changed `.py` |

**Structure per commit, meaning per merge.** AST extraction is deterministic, needs no API key, and
took 1.56s across all 141 Python files here — and it emits nodes for **docstrings**, which matters
more in this repo than most: the design reasoning lives there, and the things most often missed (the
binocular premise, the measured cockpit angles, the association gate's ratio lesson) are docstrings,
not markdown.

What AST cannot do is link two ideas sharing no import and no citation. The graph's most useful
finding so far — that a world-model latency note and a speech-recognition band fix are the same
error, *a number measured against one quantity and applied to another* — needed semantic
extraction. That is the part which waits for merge.

Install once per clone: `.claude/scripts/install-git-hooks.sh`. Both hooks fail open.

### The graph says where to look, not what the text says

Edge annotations quote fragments, and a fragment can lose its tense — the first build cited "a
standing no-omniscience violation" from a passage whose *next sentence* records the fix. Read as an
assertion it is simply wrong; read as a coordinate it points at exactly the right paragraph.

**This is enforced mechanically rather than left as advice, because it was forgotten within the
hour it was first written down.** `.claude/scripts/gq.sh` is the documented way to query: it ends
every answer with the source files already assembled, and re-renders annotations as `fragment@path`
so they present as coordinates rather than claims. A rule that fires at the moment of use survives;
a rule in a document competes with every other line in that document — including, evidently, this
one.

### What it cost when the rule had an unobservable trigger

Moved here from root `CLAUDE.md` on 2026-10-09 under the criterion in
`plans/always-loaded-compaction/plan.md`. `CLAUDE.md` keeps the rules and the graph-versus-`grep`
table; this is the evidence behind them, which `.claude/scripts/graph-query-reminder.sh` makes
redundant at the point of use by firing on every architect/debugger/investigator dispatch.

**The rule used to read "query it before concluding something is undocumented", and it was followed
zero times on 2026-09-26/27** — across two whole-subproject audits, a four-finding sortie diagnosis,
an architect pass, two review rounds, a DoD gate and a performance pass. The last real query
predated the previous rebuild. The rule was not the problem. Its **trigger** was: "before
concluding" names an internal state, so nothing can observe it failing, and a rule nobody can see
being broken stays broken. `AGENTS.md` had already reached exactly this conclusion about the
worktree rule — *"a rule that must be remembered at the exact moment attention is elsewhere will
keep being broken. This one is structural instead."* That is why the triggers in `CLAUDE.md` are now
all things that visibly happen, and why *"before saying 'there is no X'"* is one of them: that
sentence is the observable form of the old trigger.

**What it cost concretely.** A debugger dispatched onto the crossing-callout defect re-derived a
mechanism that `plans/callout-outside-gaze/debug.md` had already diagnosed *and partly fixed*,
finding it eventually by reading plans. One query would have opened with it.

**Why the `grep` half earns its own rule** (user direction, 2026-10-06, from the retro). The retro
found a stale "5 Hz" figure corrected in one memory file and left asserted in four others — one of
them another role's — propagating a rate that is 5× wrong, in a project where that same number had
already produced an entire wrong backlog premise. *A per-file correction is not a correction.* And
the graph could not have proved the correction complete: it had been built 24 hours earlier while
the intervening run wrote ~80 commits of documents, so asking it whether the stale figure was gone
would have returned a confident, stale yes.

**`.claude/agent-memory/` is deliberately outside the corpus** — `graph-corpus-files.sh`,
*"recalled automatically; not reference material"* — so a memory sweep is `grep`-only by
construction, not by preference. Do not add memory to the corpus to fix this: it would double-index
content that already arrives by recall and leak memory vocabulary into the graph's own terms, which
is the same failure as the removed `graphify-corpus/` mirror.

## What the condensed counts in `CLAUDE.md` refer to

Root `CLAUDE.md` states several rules with a **count** of the incidents behind them rather than the
incidents themselves — *"four times"*, *"five of this project's important corrections"*. The count
does the rule's work; the list is what it refers to, and it is here because it is read when a rule
is challenged, not on every session and every agent dispatch.

**Why a count and not the list** (user direction, 2026-10-18, and the reasoning is in
`.claude/scripts/always-loaded-budget-gate.sh`): a *mechanism* — why a rule works — is one
non-obvious sentence and always stays. A *calibration* example — what the rule rejects — makes a
rule applicable rather than abstract, and one or two stay. A list of incidents all establishing the
same single point is *reinforcement*, and a count replaces it without weakening anything. This repo
ran the A/B on itself: the graph-query rule's evidence was a 60-word enumeration of eight passes,
was cut to nine words on 2026-10-09, and the rule is still followed — because what fixed it was a
hook firing at the point of use, not the words.

### The five corrections that came from the user reading *why*

Cited by `CLAUDE.md` "Talking to the user", which requires the reasoning behind a claim to be shown
compressed rather than hidden. None of these was reachable from a status line:

- a slew limit read off the wrong instrument
- a *"no velocity anywhere"* finding refuted by naming a tool that does get velocity
- aspect angle mattering to recognition
- ten trucks in one glance being one perceptual event, not ten
- the naked eye belonging as the default optic

### The four flight-feedback readings that a conversation reversed

Cited by `CLAUDE.md` "Flight feedback is captured, then explored, then planned". Each arrived
*after* a reading that looked obviously right, and each would have been built wrong:

- the Bekaa reversal
- the water-flow analogue replacing rooms-and-doorways
- *"still one clock hour at a time"*, correcting a 90° cone that was about to be built
- the direction word turning out to be per-kind rather than universal

### The four times a written list went stale

Cited by `CLAUDE.md` "Current priority", which is why the subproject list is taken from the status
table or `git ls-files '*/pyproject.toml'` and never from prose. Three subprojects were named in
`CLAUDE.md` long after six existed; `AGENTS.md` and four skills inherited the same stale three, and
those skills could report PASS while never looking at half the repo. Found by the 2026-09-27 and
2026-10-09 integrity audits (`audits/system-integrity/`).

## Binary sources: images, PDFs, and anything grep cannot read

A `.jpg`, a `.png` or a `.pdf` is invisible to search, to the knowledge graph, and to every agent
that was not explicitly told to open it. This project has lost information to that three times:

- the behaviour design sat in `docs/concept/state-transitions.jpg` for weeks and was re-derived by
  guesswork until someone transcribed it;
- 52 calibration screenshots sat in an ephemeral sync directory undocumented;
- the **DCS Mi-24P manual** sat in `docs/concept/mi-24_info/` since 11 September, unread, while a
  plan recorded the 9K113's magnification and field of regard as unresearched placeholders. Four
  pages of it answered all of them.

**The rule: a binary source must be accompanied by a text file that carries its content**, not a
pointer to it. A transcription, a findings note, or a manifest — dated, in the relevant
`research/` directory. Write it while the source is still in front of you.

### `win-mac-sync/` is a delivery mechanism, not storage

Anything the user drops there — screenshots, logs, exports — may vanish without warning. Extract
what matters into a dated `research/` note **the same session it arrives**. Filenames survive
nothing.

### The Mi-24P manual

`docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` — 138 pages, Russian, and the authoritative
source for how the real aircraft's systems behave. **Consult it before speculating about Mi-24
functionality.** Read it with the `pages` parameter; the contents are on pages 3–5. The sections
that have already paid for themselves:

| section | pages | what it settles |
|---|---|---|
| 2.4 Прицел ПКИ | 23 | the operator's sight |
| 4.6.7 комплекс УРВ 9К113 | 66–75 | the sight: magnifications, reticle, control console |
| — field of view / ×10 elements | 68–69 | **×3.3 and ×10**, switchable |
| — reticle stadia dimensions | 70 | **stadiametric ranging, 1000 m and 5000 m marks, 2.5 m reference target** |
| — ПУ ПН control console | 70 | **slew limits ±40° azimuth, −15°/+20° elevation** |
| 1.6 Прицел АСП-17ВП | 15, 46–53 | the pilot's sight |
| 5.4 range entry into the АЦВУ | 124 | how range reaches the sighting computer |

Findings from it go in a dated `research/` note like any other source — see
`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`.

## Tests the user has to run

Acceptance work only the user can perform — a sortie, a Windows session, anything needing their
hands — is published as an artifact card via the `test-card` skill, not left as a markdown section.
The source of truth stays in `docs/acceptance/`; the card is a view of it, the way the status page
is a view of the roadmaps.

The reason is not presentation. A card is read in glances, at the controls, possibly in VR, and it
has to carry verified commands, an explicit statement of what is *not* testable this time, per-block
expectations as numbers where numbers exist, and checkboxes that survive an interruption. A plan
file satisfies none of that while being just as correct.

## Moved from `CLAUDE.md` and `AGENTS.md`, 2026-11-14 (verbatim)

Root `CLAUDE.md` was 6,253 words against a 4,201-word always-loaded guideline and `AGENTS.md` 4,674
against 3,194 (2026-11-14 integrity audit, Tier 2). The passages below were cut from them by the
test the budget hook states — a rule a hook delivers at the point of use, a procedure a script or
skill holds, or a third-plus incident for a rule that already carries one — and are kept here
verbatim so a revert is a copy, not a rewrite. Each names the section it came from.

### `CLAUDE.md` "Whose job is whose"

This is written down because the failure it prevents is silent and has happened: work that is
internally coherent and correct, aimed at nothing the pilot would notice or use. Two of this project's
own corrections were exactly that — a planned transport removed once mission frequency was considered,
and an F10 contact-list menu dropped because the player would still have to click through it. Both
were caught by asking this question, and the cost of asking it is one paragraph in a plan.

### `CLAUDE.md` "Current priority"

A written list goes stale silently while reading as an instruction — four skills inherited a stale
three-subproject list and could report PASS while never looking at half the repo. `todo/` no longer
duplicates milestone narrative. (Not restated here on purpose: two copies of one fact drift. The
roadmap files' own "Keeping this current" note has how that is enforced at merge time.)

### `CLAUDE.md` "Agents" — why the "whole feature" wording had to go

It was unenforceable on this project's actual shape, where a feature's stages routinely ship in
separate merges days or weeks apart. Read strictly it would hold both passes until the last stage of
`BL-14` or the 9K113 series; read loosely it justifies a pass per stage, which is what practice
drifted into. Neither was intended. The drift was found by *counting commits in a retro*, not by
anyone noticing at the time: a cadence nobody re-checks outlives its premise.

**`investigator`** is this project's recon role, needed because much of the World Model Builder
depends on unverified DCS internals (file formats, coordinate systems, scripting-API availability).
It sits *before* Architect's plan is finalized, not in the Implementer→Reviewer→DoD chain:
**Architect invokes it proactively whenever a plan would otherwise depend on an unverified
DCS-internals claim** (see `.claude/agents/architect.md` step 2) — this is not a user-invocation-only
role. It writes dated findings to the `research/` directory of whichever module the finding is about
(e.g. `world-model/research/`, `aircraft-layer/research/`), per the format in
`docs/concept/WORLD_MODEL_BUILDER.md`, and does not write pipeline code.

### `CLAUDE.md` "Session Start" — the five steps and the incident in full

1. Read root `ROADMAP.md` for the cross-subproject picture, then the `ROADMAP/` index of whichever
   subproject looks most active — `<subproject>/ROADMAP/<subproject>-roadmap.md` (its Status table
   row says which subproject). **Not `<subproject>/ROADMAP.md`**, which is a four-line pointer.
2. Read `todo/todo/todo-tasks.md` for any User priority tasks, and `todo/backlog/todo-backlog.md`
   for cross-cutting/unscoped backlog items. (`todo/todo.md` and `todo/backlog.md` are now pointers
   to those; both were split into one file per item on 2026-10-09 — `docs/DOC_CONVENTIONS.md`.)
3. Identify the next actionable milestone (first non-done, non-deferred/blocked item in the
   relevant subproject's roadmap).
4. Show that milestone and its subitems to the user.
5. Ask what they want to work on.

**The `grep -v` is not cosmetic.** 41 already-cherry-picked `worktree-agent-<id>` branches cannot
be told apart from unharvested work, so they stay; without the filter an unfiltered `head -20`
buried the only live feature branch among them. The handoff now deletes each one at harvest
(`AGENTS.md`, rule 1), so the backlog does not grow — see `docs/AGENT_WORKTREE_PROTOCOL.md`.

**Clearing context between tasks is the right habit** (it is what keeps long sessions affordable),
and it is safe *only* because this repo records its decisions. The cost of a clear is paid at
session start by reading, not avoided by remembering.

**This step exists because it was skipped, 2026-09-25.** A cleared session was told "continue with
brain layer work", read the roadmap, saw BR-1 Stage 2 as next, and built it — while
`feature/br1-stage2` already held a near-identical implementation from earlier the same day, and
`feature/d10-structured-candidates` held the follow-on. Two implementations of one milestone,
~2000 lines each. The roadmap was not wrong and the user's instruction was not ambiguous; the state
was simply never checked. `git branch` costs one second and would have caught it.

### `CLAUDE.md` "Knowledge graph"

A copied `graphify-corpus/` mirror was tried and removed: it keyed cache lookups and node names on
the staging path, leaking the mirror directory into the graph's own vocabulary. **Do not reintroduce
a mirror** — `/graph-refresh` carries the full reasoning.

The two stores hold different things and the memory half was, until now, unreachable in practice.
**Search every role, not only the one you are in** — the cross-role hit is the one the old per-role
indexes could not surface at all.

**Why a tool and not the `MEMORY.md` index that used to sit in each directory.** That index was
loaded on every agent dispatch while no role file ever told an agent to read it — unconditional
cost, optional benefit — and it drifted. The tool derives the same index on demand from each file's
`description:` frontmatter, so it cannot drift and cannot be asked to shrink. Full account, and why
the compaction it was repeatedly asked for was impossible as phrased: `todo/todo/X-T25.md`.

The graph goes first — that is what the section above is for. But the sentence immediately above
decides a second case against it, and the distinction is the verb. A correction sweep is the second
kind, so *"the graph found no remaining mention"* is not evidence the claim is gone. The graph says
*where* to look, not what the text says: edge annotations quote fragments, and a fragment can lose
its tense. The wrapper assembles the sources and re-renders annotations as `fragment@path` so they
read as coordinates rather than claims. They keep the graph's structural spine current per commit
(AST over changed `.py`, ~1.5s) and record that a semantic rebuild is owed when docs change. The
merge can sit anywhere around those two; what must not happen is the rebuild being skipped.

### `CLAUDE.md` "Verification" — tuning

The procedure, the three measured traps (constants bind by value at import; `lo`/`hi` must be AST
literals; per-key bounds cannot catch cross-key couplings) and the inclusion test live in
`.claude/agents/implementer.md`. **The one habit worth repeating, because it is where every `X-T26`
defect hid:** check the **rendered** `defaults.toml`, not the `#:` comment it was generated from. The
generator emits only the first sentence, so a warning written second reaches nobody — and that
survived three review passes by readers reading the diff.

### `CLAUDE.md` "Do not reinvent the wheel"

Reuse before declaring is already the rule for tuning constants ("Behaviour-affecting constants are
tunable"); this generalises it. **Finding the existing thing is the work.** This project's recurring
failure is not missing documentation but failing to find documentation that already exists — which
is why the knowledge graph and `memory-search.py` have observable triggers rather than a "before
concluding" rule. The same applies here: *"I did not see one"* is not evidence there is none, and a
skill, a script or a convention you did not look for is the most expensive kind to duplicate. That
line is the difference between a deliberate exception — like the body-layer ↔ world-model in-process
import, which carries its justification everywhere it is mentioned — and a second way of doing
something that nobody decided on.

### `CLAUDE.md` "Direction before speed"

This is not a counsel of slowness. Most of what this project does is ordinary work that should be
done briskly and merged. It is a rule about *one specific moment*: when new information arrives
and the obvious next move is to act on the first reading of it. Paraphrasing the user's words loses
the part that decides the design. This is `AGENTS.md`'s "Explore Before Deciding" applied to the
case it most obviously covers. Three hooks, because a rule that must be recalled at the exact
moment attention is elsewhere will keep being broken — the same reasoning `AGENTS.md` applies to the
worktree rule. A hook that refused to dispatch would be the hook overruling the user. The hooks were
written the same day the failure happened: five observations arrived from a sortie and an Architect
was dispatched on all five within one turn. Nothing was lost, but only because the user separately
asked for the feedback to be written down.

### `CLAUDE.md` "Talking to the user"

Most turns need a few lines. Drop the walkthrough, keep the load-bearing step. Repeating mechanics in
chat is noise that buries the line that mattered. Self-corrections about process stay internal.
"I'll dispatch a reviewer, then DoD" tells them nothing they can use. Note the last clause of the
visualisation direction: a visual **replaces** the text rather than decorating it. **Rough and early
beats polished and late**, for the same reason `/explore` asks for mock output — an o'clock bearing
missing from a mock callout, spotted 2026-10-17, is one such correction. **Honest limit, to be stated
rather than promised around:** there is no image-generation model here, so "visual" means SVG,
Canvas, HTML or Mermaid — geometry, charts, mock interfaces and diagrams, not photographic or
artistic renderings. **This direction already existed and was scoped too narrowly to fire.** The
2026-09-18 version lives in `.claude/skills/explore/SKILL.md`, which only runs during an `/explore`
conversation; the restatement in `CLAUDE.md` is general and applies to any answer. Brevity is not
the same as smoothing.

### `CLAUDE.md` "Workflow"

The feature-branch bullet read *"checkout `main` first, then create the branch"* until 2026-10-09 —
the pre-worktree procedure, and the one action rule 3 now forbids. The stale wording and the hook
that enforced it were found together by the 2026-10-09 integrity audit, findings 2 and 3. The user
parks the root wherever they like — usually `main`, so they can add input documents or check out a
branch to fly without colliding with anything running. So naming the branch is the only way they
learn what to test: the root's branch no longer tells them, and that former backstop is gone.
Committing cross-cutting work on `main` from the root is no longer the way: the root is the user's,
and moving its branch under them is what rule 3 forbids. A short code comment saying what a testing
aid is for is enough.

### `CLAUDE.md` "Backlog Management"

`todo/todo/` and `todo/backlog/` were separated 2026-09-27 — each edit used to re-extract the other
into the knowledge graph — and split to one file per item on 2026-10-09. `--list` is why no
prefix-to-directory table is written in `CLAUDE.md`: it derives the map from where each prefix's
files actually are. The two ways the hand-rolled command has been got wrong — a prefix-agnostic
pattern reading another space's maximum, and `sort -t B -k2 -n` returning `BL-B9` against a real
`BL-B46` — are both measured, both silent, and both impossible in the script, which carries the
account in its header. An ID that silently comes to mean a different item is worse than no ID,
because a commit message or plan citing the old meaning now reads as evidence for the new one. For
the same reason an item moving between spaces takes a **new** ID: an ID belongs to one directory's
sequence, and carrying one across would make two sequences collide.

### `AGENTS.md` "A change request from Security or Performance Reviewer re-enters the loop" — the worked case

The reason is the same one that put Reviewer after Implementer in the first place: a fix written in
response to a review is ordinary new code, arriving late, usually under time pressure, and touching
a path the original author had already stopped thinking about. It deserves the same reading as the
code it patches. The failure this prevents is specific and was demonstrated on
`feature/watch-reporting` the day this rule was written. The performance review asked for one
short-circuit; applying it also skipped a piece of masking bookkeeping the review had not mentioned,
which would have made a contact read as line-of-sight-masked on its first tick back in range with
no masked sample ever taken there. The fix was correct in the end, but *the review that requested
it was not the review that would have caught that* — it had already reported and finished.

### `AGENTS.md` "Explore Before Deciding" and "Effort/Value Check"

Menus are for settling a decision whose shape is already understood, not for finding that shape.
Observing real output is what cues recall — several of this project's most important corrections
arrived that way rather than in answer to a question. `.claude/skills/explore/SKILL.md` has the
procedure and the graph-versus-`grep` split. Not money — engineering effort, added complexity, new
failure surface, and future maintenance. Ending at "this is expensive" without a route forward is
not useful. This role supplies implementation insight and the effort/value read the user cannot get
without looking at the code. Applied to routine work the check becomes friction and trains the user
to skip past it.
