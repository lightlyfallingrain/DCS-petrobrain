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
