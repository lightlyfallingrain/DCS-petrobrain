# Definition of Done check: multi-theatre-afghanistan

**Checked at `0690a74`** (confirmed via `git checkout --detach 0690a74` + `git rev-parse HEAD`
before anything else ran) — the full linear chain from `381f828` through Reviewer, Security,
Performance, the security fix (`f7f2827`), test tightening (`91fd8a1`), and fix review 2
(`0690a74` itself). All checks below ran with `cwd` inside this worktree's own `world-model/`
and `body-layer/` directories, fresh `.venv`s built per each subproject's own setup instructions
(neither existed in this worktree beforehand).

## Branch-state finding — report before anything else

**`feature/multi-theatre-afghanistan`'s own branch ref is currently at `381f828`, not `0690a74`.**
`git rev-parse feature/multi-theatre-afghanistan` returns `381f828` (the implementer's last
commit, before Reviewer ever ran). The entire review/security/performance/fix chain this DoD
pass verified (`9c72256` through `0690a74`) exists only as commits reachable by sha across
several detached-HEAD worktrees (`git worktree list` shows separate worktrees sitting at
`c3bf204`, `91fd8a1`, `5e30050`, `f7f2827`, `58fa966`, `80461ef`, and two at `0690a74` including
this one) — **none of it is reachable from the branch name a `git checkout
feature/multi-theatre-afghanistan` would give the user.**

This needs fixing before the acceptance card is actionable: the branch ref must be fast-forwarded
(or the commits cherry-picked) to `0690a74` so that checking out `feature/multi-theatre-
afghanistan` actually gives the reviewed, security-fixed, test-tightened code. The acceptance
card already names this explicitly and tells the user what to check (`git log --oneline -3`
should show `0690a74`, not `381f828`) so the gap is visible if it isn't fixed first — but the main
loop should fast-forward the branch rather than rely on the user to notice.

## Mechanical gate — both subprojects, both pass cleanly

| subproject | ruff format --check | ruff check | mypy --strict | pytest |
|---|---|---|---|---|
| world-model (`src`/`tests`) | pass (116 files) | pass (All checks passed!) | pass, 71 source files | 542 passed, 3 skipped |
| body-layer (`src`/`tests`) | pass (114 files) | pass (All checks passed!) | pass, 53 source files | 1407 passed, 4 xfailed |

All four numbers match the implementer's own report in `implementation.md` and the Reviewer's
independent reproduction in `review.md` exactly, across all three re-verification points
(initial, post-security-fix, post-test-tightening).

No debug output, `print()`, `TODO`/`FIXME`/`XXX`, or bare error-swallowing introduced by this
diff (`git diff 14ca593..HEAD` grepped directly). The one `except (sqlite3.Error, OSError):`
block added (`logger.py`'s mismatch guard) raises `parser.error(...)` — a loud `SystemExit`, not
a silent swallow; confirmed by reading it directly.

`git status --porcelain` is clean at `0690a74` — all new/modified files are committed, nothing
left unstaged. No `world-model/data/` artifacts are tracked (gitignored, confirmed clean).

## Required fixes addressed

- **Security's one required fix** (unsanitized `theatre` string from a mission-understanding
  artifact flowing into a path join and, transitively, a SQLite URI) — fixed in `f7f2827`:
  `THEATRE_PROJECTIONS` exact-key membership check immediately after derivation, before any path
  is built. Confirmed present in code at this tip (`logger.py:1894`, `if theatre not in
  THEATRE_PROJECTIONS:`).
- **Security's optional item** (raw traceback on an unbuilt/missing store) — also fixed in the
  same pass: `try/except (sqlite3.Error, OSError)` around the mismatch guard's open+query,
  converted to a clean `parser.error`.
- **Reviewer's fix-review finding** (the new regression tests didn't actually fail when the
  required registry check specifically was removed, because the optional `except` converted the
  resulting downstream error into the same generic `SystemExit`; plus a payload that didn't
  reproduce the demonstrated SQLite URI-injection mechanism) — fixed in `91fd8a1`, re-verified by
  Reviewer in fix review 2 (`0690a74`): **APPROVED**, both gaps closed, verified by independently
  reproducing the disable-required-fix-alone / restore cycle rather than trusting the
  implementation note.
- Reviewer's two **optional** refinements (a harmless duplicate `isinstance` check in
  `mission_phase.py`; a documentation pointer for the junction-sparsity finding) are explicitly
  not blocking and not required before merge — noted, not actioned, per the Reviewer's own
  verdict.

No other required fixes outstanding. Reviewer's main pass: **APPROVED**, no required fixes at
all. Security's deep analysis: **NEEDS FIXES → fixed → re-reviewed clean**. Performance: **APPROVED
— MONITOR** (no required fix; one architecturally-relevant finding carried forward, see below).

## Scope & correctness

- Implementation matches `plans/multi-theatre-afghanistan/plan.md`'s Stages 1, 2, 3, 5 exactly
  (Stage 4 explicitly deferred to the user, as planned). The two extra test files touched
  (`test_towns_lua.py`, `test_beacons_lua.py`) are a plan omission the implementer caught and the
  Reviewer confirmed as correctly in-scope, not drift.
- No invariants violated: provenance/confidence preserved (`confidence="provisional"` stated
  everywhere, with an explicit upgrade path); DCS-internals claims recorded in dated `research/`
  notes before being relied on; read-only DCS access throughout; `world-model/data/` stays
  gitignored; coordinate math confined to `coordinates/`; the mismatch guard is real and tested,
  not decorative (all independently re-verified by Reviewer against the real diff and the real
  built stores, not taken on the implementer's word).
- All new files are staged and committed (confirmed via `git status --porcelain` at `0690a74`).

## Testing

Core logic covered: per-theatre count-guard `ValueError`s, the Afghanistan provisional-fit
self-consistency test (explicitly disclaimed as self-consistency, not live/real-world — per
`world-model/CLAUDE.md`'s control-point-test rule), `load_mission_understanding`'s new
`theatre` field parsing, all three of `logger.py`'s new `parser.error` paths (explicit-flag-or-
mission-understanding exclusivity, missing `--world-model-dir`, store/theatre mismatch), and the
security-regression suite (4 parametrized injection/unknown-theatre cases + 1 unbuilt-store case,
tightened in the fix-review loop to assert the specific rejection reason and prove
`open_world_model` is never reached). No existing tests broken (world-model 542/3 vs. a
pre-feature baseline of 539/3 passed/skipped; body-layer 1407/4 vs. 1177/4 main baseline, both net
additions only).

## Documentation

- `review.md`'s findings (junction sparsity, 7-of-26 airfields) are both investigated and
  recorded as real-but-out-of-scope, with concrete numbers, not hand-waved.
- `world-model/research/2026-10-05-afghanistan-theatre-build.md` records the Stage 2 pre-check
  and the full Stage 3 build results, dated, before `RUN.md`/`region.py` cite it.
- `world-model/RUN.md` §7 and `body-layer/CLAUDE.md`'s logger-running section both document the
  new behavior accurately (independently spot-checked against the real argparse block and the
  real built store in this DoD pass — see the acceptance card's own verification notes).

## Security sign-off

`plans/multi-theatre-afghanistan/security.md` (deep analysis, post-Reviewer) exists:
**NEEDS FIXES**, both the required and optional item, with the fix (`f7f2827`) and the follow-up
test-coverage fix (`91fd8a1`) independently re-reviewed clean (fix review 2, `0690a74`,
**APPROVED**). No separate `security-plan-review.md` exists for this feature — consistent with
the project's current cadence (one security pass per whole feature, immediately before DoD, per
root `CLAUDE.md`'s "Agents" section and this DoD role's own prior-session memory on this point),
not a gap.

## Acceptance boundary — what DoD's own checks structurally cannot reach

Everything above is fixture/static verification: unit tests, a reproducible residual-check script
run against a synthetic JSON (never real DCS output), and a real-but-offline sqlite build. **None
of it can confirm the one thing this whole feature rests on — whether Afghanistan's beacon-fitted
projection actually matches what DCS's own live `coord.LOtoLL` reports.** A fixture can prove the
fit is self-consistent; it cannot prove it is *right*, the same gap Syria's own M1 had before its
live verification closed it. That live check needs the user's hands on a Windows DCS box and
cannot be simulated, guessed, or waived here.

Acceptance card published: `docs/acceptance/2026-10-05-afghanistan-projection-check.md` /
https://claude.ai/artifact/YBRPNY1LcAb37u6GMBB1Vu. Every command in it was actually executed this
session (the residual-check script against a synthetic probe-output file with the real JSON
shape; the `describe_position` spot-checks against the real built `afghanistan-full.sqlite`; the
`logger.py` explicit-theatre-flag resolution and mismatch-guard paths, against an unreachable
collector URL so only the network call fails) — the one thing that cannot be verified from here,
labeled as such on the card, is the real live-DCS numbers themselves.

**This is deferred, not waived.** The plan always scoped Stage 4 to the user; it is tracked as
live-acceptance debt in `world-model/ROADMAP.md` (new entry added this pass) rather than left as
a one-off caveat, per this role's own standing practice.

## Milestone Completion question

**Does this change what the next milestone should be, or invalidate a downstream assumption?**

Yes, in one specific way: **the terrain-semantics (ridge/valley) build stage processes every
`.hgt` tile physically staged in `--srtm-dir`, not just the ones overlapping the region's own
padded bbox** (Performance Reviewer finding #3, pre-existing code, not introduced by this plan,
but measured concretely for the first time here — 288 staged tiles, only 158 needed, 44.0 of this
build's 82 total minutes in that one stage). This matters specifically because `RegionDefinition`
grew rectangular half-extents *for Kola's benefit* — Kola's real footprint is a long, narrow
strip, and staging its DEM tiles the natural way (a bounding rectangle over the whole theatre)
will hit exactly the waste that rectangular half-extents were built to avoid, in the one pipeline
stage that fix never reached. **Recommendation: resolve this (filter `ingest_terrain`'s tile list
to the region's bbox, or require DEM staging to pre-clip) before a Kola build is attempted, not
after discovering it from a slow build.** Not a blocker for Afghanistan itself (82 min absolute,
one offline per-theatre build, "minutes not hours"); flagged here because the finding directly
constrains how the next multi-theatre milestone (Caucasus or Kola) should be staged. Recorded in
`world-model/ROADMAP.md`'s live-acceptance-debt entry for this feature and in
`plans/multi-theatre-afghanistan/performance.md` itself.

Caucasus, by contrast, needs no such prerequisite — its real footprint is smaller than Syria's,
so even an unfiltered tile set costs less there, not more.

## Milestone NOT marked done

Per dispatching instructions: the milestone is **not** marked `[x]` in `world-model/ROADMAP.md` —
live acceptance (Stage 4) is outstanding. A new `[ ]` live-acceptance-debt entry was added instead
(see above), and the root `ROADMAP.md` status table's "Multi-theatre support" line was updated
from "backlog, needed soonish" to the current real state (built, DoD-passed, live check
outstanding) — it was stale before this pass (still describing Afghanistan as unbuilt backlog).

## Verdict

**DoD: PASSED** (mechanical gate, scope, testing, documentation, security all clean). **Acceptance
testing: NOT YET PERFORMED** — card published, Stage 4 requires the user's own hands on the
Windows DCS box. Do not merge to `main` until acceptance returns, per standing DoD process; and
fast-forward `feature/multi-theatre-afghanistan`'s branch ref to `0690a74` first, since it
currently is not, and the acceptance card's own checkout instructions depend on it being so.
