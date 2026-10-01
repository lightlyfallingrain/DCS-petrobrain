### Definition of Done Check: player-bubble

Branch `feature/player-bubble`, tip `9ca1cb1` (verified via `git rev-parse HEAD` before reading
anything — matched the expected sha). Real change set: `6e3a2b7` (`824fea5`/`5c5bde6`/`6fd2e0a`/
`9ca1cb1` are review/correction/sign-off commits, no further source changes). `.venv` built fresh
from `body-layer/pyproject.toml` inside this worktree (no `.venv` existed in the fresh worktree —
`python3 -m venv .venv && .venv/bin/pip install -e .`, plus `ruff`/`mypy`/`pytest` and an editable
`world-model` install for the seam import).

#### Code Quality

- `ruff format --check src tests` — **PASS** (114 files already formatted)
- `ruff check src tests` — **PASS** (all checks passed)
- `mypy src` (strict, run from inside `body-layer/`) — **PASS** (no issues in 53 source files)
- `pytest tests -q` — **PASS** — `1379 passed, 4 xfailed`, matching the expected figure exactly
  against the stated `main` baseline of `1367 passed, 4 xfailed` (+12 new tests, no regressions).
- No unhandled errors/panics in data paths: the new arithmetic (`filter_player_bubble`'s
  `range_m`) fails closed on `nan` by IEEE-754 comparison semantics, confirmed by Security's deep
  analysis, not merely assumed.
- No debug output or leftover TODO/FIXME/XXX introduced — grepped the diff (`git diff
  53f8b0b..HEAD` over the five touched source/tool files) for `print(`/`TODO`/`FIXME`/`XXX`/`pdb`/
  `breakpoint`: none found.

Only `body-layer/` is touched by this feature (`git show --stat 6e3a2b7`); no other subproject's
commands apply.

#### Scope & Correctness

- No separate Architect `plan.md` exists for this feature, and that is a deliberate, documented
  choice, not a gap: `todo/todo.md`'s "Player bubble: 10 km, settled 2026-09-28" section is itself
  the full, user-settled spec (radius, independence constraint, scope boundary against world
  features, the memory/9K113 exceptions) — `implementation.md` states this explicitly ("the spec
  in `todo/todo.md` was the authoritative, already-complete source for this feature's scope").
  Checked against CLAUDE.md's allowance ("for small features, one role may handle the whole
  task") and against the actual spec in `todo/todo.md` line-by-line: implementation matches it
  (bubble applied immediately after `filter_ownship()` in both pollers; ground/air only; ownship-
  relative, omnidirectional; equal-to-radius kept; independence from `NAKED_EYE_RANGE_CAP_M`
  structurally guarded by two `dir()`-namespace tests).
- No unplanned scope added. The one piece of work beyond the spec's literal text — the
  `tools/summarize_detection_trace.py` fix — is a correctness bug the new `GateOutcome` exposed,
  not scope creep (Reviewer confirmed this is necessary, not optional, and traced every other
  `GateOutcome` consumer to rule out a second instance).
  `plans/player-bubble/implementation.md`'s own "Correction, Reviewer 2026-10-02" note shows a
  wording error (calling `RANGE_CAP_M` "forward-hemisphere only") was caught and corrected in the
  log rather than silently left — the conclusion it supported held regardless, and the review
  agrees it's no longer wrong on disk.
- No CLAUDE.md invariants violated. Checked specifically: (1) DCS stays authoritative — this
  feature narrows computation, does not touch DCS data or world-model geography at all
  (`test_enrichment_module_never_references_the_player_bubble` pins this structurally); (2) code
  owns facts, models interpret — the bubble is a pure pre-filter on already-typed
  `WorldObjectCandidate`/`Contact` data, no model in this path; (3) no omniscience — Security's
  deep analysis traced the new `GateOutcome.PLAYER_BUBBLE` trace row end to end and confirmed it
  writes only to a local offline debug file, never back into `ContactStore`/`Percept`/belief
  state, so Petrovich's own knowledge is unaffected either way; (4) provenance/timestamps —
  untouched, no new cross-source data mixing is introduced.
- All new files staged: `git status --porcelain` on `HEAD` is empty (clean working tree, nothing
  to stage — see Testing section's verification below).

#### Testing

- Core logic covered: 12 new tests across `test_association.py` (pure boundary logic: just-inside/
  just-outside/exactly-at-radius, omnidirectionality, the two independence guards) and the new
  `test_player_bubble.py` (source + belief integration: never reaches `check_visibility`,
  unaffected in-bubble contrast case, hybrid channel never associates a bubble-excluded
  candidate, memory/object-permanence survive a bubble-induced gap, enrichment has no seam into
  the bubble).
- Tests are meaningful, not decorative: Reviewer independently confirmed the two structural
  `dir()`-namespace independence tests actually fail under the aliasing case the spec warns
  against (a direct `from ... import CONST`), and that the memory-persistence test uses a real
  `NakedEyePerceptionSource` + real `ContactStore` across two polls rather than a stub.
- No existing tests broken: 1367/4 baseline on `main` → 1379/4 on this branch, a pure addition.

#### Documentation

- Reviewer findings addressed: **Required Fixes: None.** Verdict APPROVED. The three "Optional
  Refinements" (the `RANGE_CAP_M` wording correction, the value-derivation aliasing gap, the
  velocity-join ordering) are explicitly non-blocking by the Reviewer's own classification; the
  wording one was already applied as a correction commit (`5c5bde6`) before this gate ran.
- Non-obvious behavior explained: both new constants' docstrings state the computation-scope-vs-
  perception-limit distinction and the "not measured, deliberately" framing; `implementation.md`
  documents the rejected seams and the hybrid-channel no-op reasoning in detail.

#### Security

- `plans/player-bubble/security-review.md` exists: **APPROVED.** No `security-plan-review.md`
  exists, consistent with there being no separate `plan.md` to review in the first place (the
  plan-review stage reviews an Architect plan before implementation starts; here the spec was
  already the user-settled `todo/todo.md` entry, so there was nothing to plan-review against that
  the deep analysis didn't already cover post-hoc). No dependency change, no new network/parsing
  surface, fails closed on malformed numeric input, no path into belief state from the new trace
  row.

#### Performance

- `plans/player-bubble/performance.md`: **APPROVED — MONITOR.** Filter cost negligible at any
  realistic or burst scale (0.53 us/candidate). The measured end-to-end saving is small today
  (~1.4%, 0.955 ms/tick) because both channels' pre-existing range gates (`NAKED_EYE_RANGE_CAP_M`
  = 10 000 m, `associate()`'s `RANGE_CAP_M` = 5 000 m) already bounded LOS/association
  reachability at or below the bubble radius — this is recorded as the honest finding, not a
  defect, and the architectural decision (independence from those constants) is what makes the
  real payoff available once the 9K113 sight (20 km) makes the constants diverge.

### Verdict: PASS

All mechanical checks pass against the expected figures. No required fixes outstanding from
Reviewer, Security, or Performance. Working tree clean, everything committed on `feature/player-
bubble` at `9ca1cb1`.

### Acceptance boundary — stated plainly, not left implicit

**This feature changes nothing a sortie can hear or see, today.** The player bubble is a
computation-scope cut applied *before* work that both perception channels' own pre-existing gates
already rejected at or inside this same radius (`NAKED_EYE_RANGE_CAP_M` = 10 000 m for naked-eye,
`associate()`'s `RANGE_CAP_M` = 5 000 m, stricter, for hybrid). No candidate that would have been
admitted, spoken, or remembered before this branch is now excluded, and no candidate that was
excluded before is now admitted — the Performance review measured this directly (76.6% of
candidates sit beyond 10 km in the real trace, but the end-to-end saving is 0.955 ms/tick, ~1.4%,
because the expensive work those candidates would have reached was already unreachable). A
fixture or unit-test pass here is a claim about *computation scope*, not about anything observably
different in the cockpit — there is no "F10 vocabulary"-style gap this feature could be hiding,
because there is no new behavior for a gap to hide in.

**Acceptance decision: no live acceptance is owed, and this is a waiver, not deferred debt.**
Unlike `body-layer/ROADMAP.md`'s "Live acceptance debt" list (items whose plan expects a real
in-cockpit observable and the flight simply hasn't happened yet — confirm-band-affirmatives,
sortie-2026-09-26-fixes, group-cohesion), this feature has no in-cockpit observable to defer. The
condition that would create one is explicit and already named in the spec: the 9K113 sight's
20 km cone, which will make `PLAYER_BUBBLE_RADIUS_M` and `NAKED_EYE_RANGE_CAP_M` diverge and give
the bubble a real, flight-observable effect (a unit between 10 km and 20 km that the sight could
otherwise see). Until that lands, there is nothing for a card to ask the user to judge — publishing
one would be the "card nobody can act on" failure mode this role is warned against, not caution.

No acceptance testing plan or test card follows, by design — there is nothing in this feature a
flight could distinguish from the previous build.
