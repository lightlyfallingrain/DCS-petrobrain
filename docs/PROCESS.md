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

## Keeping the knowledge graph honest

A queryable graph over the current-state design documentation lives in `graphify-out/`, built from
a curated corpus — every `ROADMAP.md` and `CLAUDE.md`, `docs/`, `AGENTS.md`, `NOTES.md`, `todo/`,
all `*/research/`, and the active plan. It exists because this project's recurring failure is not
missing documentation but **failing to find documentation that already exists**, and occasionally
finding a superseded version of it instead.

### The order at merge is load-bearing, not tidiness

**Documents first. Graph second. Merge third.**

1. **Bring the documents current** — what was built, what is left, what this work superseded. A
   superseded section keeps its body and gains a pointer to its replacement (see "Superseding a
   decision"); a plan nothing current cites moves to `plans/archive/`. This is the Definition of
   Done's job.
2. **Rebuild the graph** — `/graphify graphify-corpus --update`. Incremental; only changed files
   are re-extracted.
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
