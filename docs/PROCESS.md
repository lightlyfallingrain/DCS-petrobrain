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

Maintain `NOTES.md` for non-obvious findings: bugs, perf bottlenecks, framework quirks, chosen solutions, workarounds.
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
a mirror silently breaks cache keying and leaks its own name into node ids) — every `ROADMAP.md` and `CLAUDE.md`, `docs/`, `AGENTS.md`, `NOTES.md`, `todo/`,
all `*/research/`, and the active plan. It exists because this project's recurring failure is not
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
