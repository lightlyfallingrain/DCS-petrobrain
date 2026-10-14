# Definition of Done — BL-14, the attack run (Stages 1–7)

**Scoped to tip `7d0e2774701fc0678ae4c615369e732e91203990`** ("Reviewer: approve BL-14 staleness
fix (AttackRunState reset on re-point)"), `feature/bl14-attack-run`. This verdict describes that
commit only — if the branch has moved since, re-run this check before trusting it.

## Address

This worktree's base (`f25c57c`, unrelated forest-occlusion work) was a strict ancestor of the
named tip with a clean tree. `git merge --ff-only 7d0e277` succeeded; `git rev-parse HEAD` now
equals the expected tip exactly.

## Code Quality

| Subproject | format | lint | type | test | result |
|---|---|---|---|---|---|
| body-layer | pass (126 files) | pass | `Success: no issues found in 58 source files` | **1841 passed, 4 xfailed** | matches expected exactly |
| audio-adapter | pass (29 files) | pass | `Success: no issues found in 15 source files` | **277 passed, 1 skipped** | matches expected exactly |

Run directly from inside each subproject directory, using the main checkout's `.venv` by absolute
path, with import resolution confirmed against *this worktree's own* `src` before trusting any
result (`PYTHONPATH=src:../world-model/src python -c "import belief.attack_run as m;
print(m.__file__)"` and the audio-adapter equivalent both resolved here, not elsewhere).

- No unhandled errors/panics in data paths: `drain_attack_run` runs inside the existing broad
  `except Exception` in `logger.py`'s poll loop (confirmed by security-review.md); no new raise
  path without a caller-side guard.
- No debug output left in committed code: grepped the full feature diff
  (`body-layer/src`, `audio-adapter/src`) for `TODO`/`FIXME`/`breakpoint(` and bare `print(` outside
  the existing `_print` convention — none found.
- No leftover TODO comments introduced by this feature — confirmed by the same grep.

## Scope & Correctness

Matches `plans/attack-run/plan.md`'s Stage 1–7 scope. Deliberately-unbuilt items, all stated as
deliberate rather than silently dropped:

- **Group-as-target** — dropped by user direction (§25 of the direction document): "the target is
  exactly one contact," and the pilot approximates a group attack by picking one unit in it.
- **`attack`/`attack-run` as engage synonyms** — deferred to `AA-B4`/`BL-14`'s own vocabulary gap,
  correctly flagged rather than silently narrowed (the `"tanks"`/`"trucks"` collision risk the
  Reviewer independently re-measured and confirmed real).
- **The 1 s post-readback audio gap** — filed to `AA-B5`/`AC-B6`, not built here; ~80% of it
  already existed as `callouts.py`'s `INTER_UTTERANCE_GAP_S` (0.75 s), found rather than re-built.
- **Damage/fire/destroyed reporting and the automatic stop on destruction** — **a known gap
  against the user's own spec (§13)**, stated plainly rather than glossed: the damage channel this
  needs is probe-answered but unbuilt, so in `BL-14` a run ends only on pilot command
  (`disengage`/`stop attack`/`abort`, dropping the target, or the generic cancel path). Petrovich
  never says "destroyed."

Three deliberately-unset constants, confirmed still unset and untuned by anyone across all three
fix rounds:

```
ATTACK_RUN_LINED_UP_AZIMUTH_DEG: Final[float] = 5.0
ATTACK_RUN_ELEVATION_GATE_DEG:   Final[float] = 10.0
ATTACK_RUN_CHANGE_THRESHOLD_DEG: Final[float] = 3.0
```

plus `ATTACK_RUN_RELATIVE_MAX_AGE_S = 2.0` and `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` — all match the
plan's proposed values exactly, grepped directly from `attack_run.py`/`estimation.py`, not taken
from the implementer's report.

No invariants violated: no DCS-install writes; the one new perception datum
(`RelativeDirection`) crosses the belief boundary through the same `percept_of` mechanism every
other field uses, and is grep-fenced to `percept.py`/`attack_run.py`
(mutation-tested by Reviewer, independently re-traced by Security). All new files are staged —
`git status --porcelain` is clean.

## Spoken vocabulary trace (§§1, 6, 9, 19, 23, 24)

Confirmed directly against source (not the plan's paraphrase), cross-checked against five
independent review passes that each re-verified the same points by mutation/reproduction:

- Qualitative only — `render_alignment`'s word tables, no numeric interpolation anywhere in
  rendered text.
- O'clock outside the ±15° sector, degrees-register retired in favour of "come left"/"a bit
  right"/"higher"/"a little lower" inside it (§9's correction over §6's first reading).
- Silence is the aligned signal; one `"lined up"`, then nothing, re-baselined on the last
  *spoken* value (not the previous sample) after the Stage 4-5 fix closed the busy-channel gap.
- Range spoken once, in the engage readback only; `render_target_readback`/`step`'s readback never
  repeat it.
- `", obstructed"` composes onto both axes, including `"lined up, obstructed"`, confirmed tested
  in both directions (entering/leaving obstruction while lined up).
- One utterance per tier transition, in the register of the tier being entered — confirmed by
  `_should_emit`'s text-comparison re-firing on every transition with no tier-aware special case.

## Testing

Core logic covered: `test_attack_run.py` (29 tests as of the staleness fix, including two
mutation-confirmed pins — the oblique/banked re-rotation case and the 9°-heading re-rotation case
— plus the identity-change reset's three new tests), `test_crew_console.py`'s extensive
`drain_attack_run`/`_handle_step`/`_handle_engage`/`_handle_disengage` coverage, and the
audio-adapter vocabulary/matcher tests for `engage`/`disengage`/`step`. Five independent review
passes mutation-tested or directly reproduced every load-bearing claim rather than accepting the
implementer's tests at face value (see `review.md` for the specific mutations). No existing tests
broken — all four gates pass clean in both subprojects at the counts above.

## Documentation

- Reviewer findings addressed: all five review passes (Stage 1-3, Stage 4-5, Stage 4-5 fix,
  security fix, staleness fix) ended **APPROVED/APPROVE**, with the two required fixes from the
  Stage 4-5 pass and the one required fix from the security deep analysis each closed and
  re-reviewed before the next pass started.
- Non-obvious behaviour explained: `plans/attack-run/implementation.md` carries the "Notable
  Discoveries" sections (the false plan premise on Decision 16, the circular-import resolution,
  the mid-run reselection staleness audit); `docs/STRUCTURE.md`/`body-layer/CLAUDE.md`'s module map
  entries document the new modules.

## Security

- `plans/attack-run/security-review.md` (plan review stage — folded into the whole-feature pass
  per current cadence) and the deep analysis both exist. The deep analysis's one required finding
  (stale `attack_target` task surviving a re-selection) was fixed and re-reviewed
  (`review.md`'s "Security fix review" section, **APPROVE**). A second, related staleness bug
  found *during* that fix's review (altitude carried across a re-point) was fixed separately and
  re-reviewed (`review.md`'s "Staleness fix review" section, **APPROVE**) — this is the commit the
  branch tip names.

## Performance

`plans/attack-run/performance-review.md` — **APPROVED — MONITOR**. Nothing on the attack-run
hot path needs a change. One real finding: `step`'s per-press candidate ordering pays
`BL-B49`'s already-filed, uncached `terrain_divide_qualifier` cost (~7 ms/candidate) through
`describe_contact`'s full enrichment pipeline — a new *caller* of an existing, architect-owned
cost, not a new defect. Recommend `BL-B49`'s entry note `step` as a second confirmed caller
(not yet done as of this check — see "What this changes" below).

## Acceptance boundary — what fixtures structurally cannot reach

Every check above ran against fixtures, mutation tests, and direct reproduction scripts — none of
it is a live cockpit. **Two classes of defect this process cannot catch, named up front so a
fixture pass is never mistaken for a flight pass:**

1. **Whether the vocabulary actually works spoken aloud, in a hover, over an intercom, under
   workload.** "Come left"/"a bit right"/"higher, obstructed" read correctly on a page; whether
   they are distinguishable at speech-synthesis cadence, whether the pilot can act on them in the
   seconds a close-in run allows, and whether the three unset constants (5°/10°/3°) feel right in
   the aircraft, are all judgments only a sortie can make. This is explicitly the point of the two
   deliberately-unset constants — a fixture cannot tune a value the design says must be tuned from
   flying.
2. **Whether the relative-direction channel's `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` assumption
   holds up.** The design treats "looking at the target" as exact guidance. No fixture simulates a
   pilot's actual pointing precision; only a flight can tell whether zero noise reads as too
   twitchy, too forgiving, or correct.

The worked example this role's own instructions cite (`Scan` driving the wrong subsystem,
`Cancel Task` speaking a raw id) is the general case: a fixture that passes tells you the code did
what it says against the inputs you gave it, never whether those inputs match what a live sortie
actually produces.

## Milestone completion — does this change the next milestone or a downstream assumption?

**Yes, in three concrete ways, all already filed rather than newly discovered here:**

- **`BL-B62`** (the relative-vs-map channel generalisation) and **`BL-B63`** (the selective fast
  lane) are both direct products of this feature's own Decision 16/§18 amendment — `BL-14` is the
  first and, as of this tip, only consumer of a mechanism the plan itself says is general. Any
  future feature wanting "point at it, don't describe it" (the deferred general advisory, the
  9K113/ATGM run) should build on this channel rather than reinventing it; both entries already
  say so.
- **`BL-B49`** now has a second confirmed caller (`step`, per the performance review above). The
  fix, whichever shape the Architect eventually picks for `BL-B49`, needs sizing against both
  callers. **Not yet cross-referenced on `BL-B49`'s own entry as of this check — recommend doing
  so as part of the roadmap update below**, since leaving it unlinked would let the Architect
  re-discover `step`'s cost as if it were new.
- **`BL-B64`** (the 9K113 sight, on `main` but not yet merged into this feature branch) already
  names the apparent contradiction with this feature's vertical-axis framing — `BL-14` treats the
  vertical word as a *discrimination* aid (which unit, not how well aimed), while `BL-B64`'s own
  spec says the 9K113 sight gives *poor* vertical understanding. `BL-B64`'s own text resolves this
  as "a different claim about a different instrument" (naked-eye/binocular discrimination vs.
  sighted tracking precision) rather than a live contradiction — not a blocker on this merge, and
  already flagged for its own `/explore` pass per that entry's own text.

**What does not change**: the attention-driven per-unit resolution mechanism this feature
deliberately routed around (§3 of the direction document — stepping walks the belief store, not
the world) remains exactly as open as it was before this feature; `BL-14` neither built it nor
newly depends on it.

## Verdict

**PASS.**

All mechanical gates pass at the expected counts in both touched subprojects. Scope matches the
plan with every deliberate omission stated plainly, including the known gap against the user's
own spec (no automatic stop on destruction). The three agreed-guess constants are unset and
untouched. Five independent review passes (Reviewer ×3 on the implementation, Security ×2 on its
own required fix and a staleness bug found while reviewing that fix) each ended APPROVE/APPROVED
after mutation-testing or directly reproducing the load-bearing claims rather than accepting the
implementer's account. Performance review is APPROVED — MONITOR with one cross-reference action
outstanding. This authorises the merge; acceptance testing with the user (covering Stages 5-7
together, per §24's staging correction) is the next and final step before the feature is
considered flown.
