# Definition of Done — BL-B70 (attack-run-sortie-fixes)

**Scope of this verdict: `feature/attack-run-fixes` at tip `3b69371`** (Security deep analysis,
APPROVED). Verified by `git rev-parse HEAD` against this sha in a fresh worktree started from
`origin/HEAD`, fast-forwarded (`git merge --ff-only 3b69371`, clean fast-forward, no divergence).
If the branch moves past this sha, this verdict is stale and must be re-run.

## Mechanical checks (re-run directly, not taken on trust)

All commands run from `body-layer/` inside this worktree, using the main checkout's venv
(`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/`) since this fresh worktree has none of
its own — per CLAUDE.md, tools resolved explicitly rather than assumed on `PATH`.

| check | command | result |
|---|---|---|
| format | `ruff format --check src tests` | 132 files already formatted — PASS |
| lint | `ruff check src tests` | All checks passed! — PASS |
| type | `cd body-layer && mypy src` | Success: no issues found in 60 source files — PASS |
| test | `pytest -q` | 2016 passed, 4 xfailed — PASS, matches `implementation.md`'s claimed figures exactly |

(First `ruff format --check .` run against the whole directory, not `src tests`, flagged one
reformat in `research/2026-10-05-security-audit.md` — a markdown file with embedded Python code
blocks, pre-existing, untouched by this branch's diff `main...3b69371`, and outside the project's
own stated check scope (`body-layer/CLAUDE.md` "Commands": `ruff format body-layer/src
body-layer/tests`). Re-run scoped correctly; not a BL-B70 defect.)

**Subproject scope**: `git diff main...3b69371 --name-only` touches only `body-layer/` (plus
`.claude/agent-memory/` and `plans/`, which carry no checks). No other subproject's commands are
owed.

**No debug output / TODO**: `git diff main...3b69371 -- body-layer/src | grep -nE
"TODO|FIXME|print\(|except:|XXX"` — no matches.

**Staging**: `git status --porcelain` clean after the roadmap edit and this file, both added below.

## Review chain (already run, confirmed rather than re-litigated)

- `review.md` (first pass): NEEDS REVISION — two required fixes (gate-order reversal in
  `_no_look_cause`, `<where>` clock-hour spoken twice via a raw int instead of
  `_ALIGNMENT_CLOCK_WORDS`). Both are read-from-source findings, not claim-trusting.
- `571e898`: both fixes applied.
- `review-2.md`: APPROVED. Re-derived the gate order from `visibility.py:990-1023` directly (mask →
  optic FOV → `range_or_size` → `live_los_clear` → forest) and confirmed `_no_look_cause` now
  matches; confirmed `where` reuses the same `azimuth_deg` already passed to `alignment_phrase`,
  one variable not two. No new fresh-construction site (F4), no new undeclared tuning constant.
- `performance.md`: APPROVED, no material cost — pure functions, no new per-tick allocation beyond
  what the dataclass already carried.
- `security.md`: APPROVED — cause taxonomy strengthens the no-omniscience disclosure (tells the
  pilot *less*, more honestly) rather than loosening anything; no new external input, no new
  dependency.

Agent memory checked before writing this report (`memory-search.py attack run cause taxonomy
obstructed`): both relevant entries (`security/project_attack_run_cause_taxonomy_approved.md`,
`reviewer/feedback_claimed_gate_order_mirroring_needs_checking_against_source.md`) describe
exactly the gate-order defect already caught and fixed above — no new lesson, confirms the loop
worked as intended. Knowledge graph queried (`gq.sh`) — returned the existing module structure,
nothing beyond what the review chain already traced.

## §1/§2/§4/§8/§9 and §5's fallback phrasing — verified against the acceptance document, in source

Read `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md` §1/§2/§4/§8/§9 directly (not the
plan's paraphrase of them) and traced each against the committed code:

- **§1 (repeats on unchanged speech)** — `_should_emit` (`attack_run.py:498`) is now `return text !=
  state.last_spoken_text`; the deleted angular-threshold clause (`ATTACK_RUN_CHANGE_THRESHOLD_DEG`)
  no longer exists anywhere in `src/` (grepped) or `defaults.toml`. Matches §1's own fix shape
  verbatim: *"compare what would be said, not what is believed."*
- **§2 (silence behind the cockpit mask, run stays active)** — `decide` returns `(state, None)`
  immediately on `cause == "masked"` (`attack_run.py:627`), before any `OutgoingSpeech` is
  constructed, and before `last_spoken_text`/`last_spoken_clock_hour`/`last_spoken_unresolved` are
  touched (confirmed against the Co-moving Fields table in `implementation.md` and against the
  dedicated tests `test_decide_masked_tick_is_silent_and_run_stays_engaged`,
  `test_decide_masked_tick_never_moves_the_cadence_or_unresolved_baseline`). The run object itself
  is untouched by this branch, so "stays active" holds by the absence of any early-return from the
  run loop.
- **§4 (twelve o'clock marker)** — `alignment_clock_hour` (`speech.py:560`) exported as the same
  sector test `alignment_phrase` uses internally; `decide` computes `announce_twelve` from entry
  into the sector against `state.last_spoken_clock_hour` (`attack_run.py:633`), passed into
  `render_alignment(..., announce_twelve=...)`, which prefixes `"Twelve o'clock, "` rather than
  speaking a second utterance — matches §4's explicit ordering requirement ("the announcement
  precedes the qualitative guidance rather than replacing it").
- **§8 (`", obstructed"` is DCS LOS only)** — `decide` sets the qualifier only when `tier == 2 and
  cause == "obstructed"` (`attack_run.py:687-688`), and `cause == "obstructed"` in `_no_look_cause`
  requires a fresh (`<= ATTACK_TARGET_LOS_MAX_AGE_S`) `live_los_clear is False` — a genuine DCS
  live-LOS verdict, not a missing one (`"unknown"` gets no qualifier at all). Matches the three-row
  table in §8 exactly: mask → silence, DCS LOS → `", obstructed"`, range/size → optic ladder/
  remembered-sighting language (deferred to `BL-B71`, correctly out of scope here).
- **§9 (attack target has first claim on LOS)** — **not a priority fix** in this branch, by the
  roadmap entry's own recorded user decision (observe density-dependent cost before tuning). What
  shipped instead is the tripwire the roadmap entry commits to: `belief_truth_log.py`'s
  `_write_attack_run_tripwire`, fed from `logger.py`'s two `write_poll` call sites via
  `runner.attack_run_state.last_contact_id`, recording `present_in_snapshot`/`join_skew_s`/
  `live_los_clear` once per poll while a run is active. This is a measurement instrument, not a
  behavioural fix — correctly represented as such in the roadmap update below, not oversold as "§9
  implemented."
- **§5's fallback phrasing** — superseded mid-implementation by §10/§11 (pulled in from `main`
  during the task, per `implementation.md`'s own branch-state note), which the plan's dispatch
  brief explicitly includes ("§5's fallback phrasing"). What shipped is the four-state register:
  `render_attack_run_lost_sight`/`render_attack_run_regained_sight` in `speech.py`, keyed in
  `decide` on `cause == "too_far"` transitions (`attack_run.py:649`), not on tier and not on having
  been masked — matches §11's explicit instruction ("the important question is whether Petrovich
  sees the target... when we turn to see what is happening," not whether a mask interrupted it).
  `_attack_run_last_seen_phrase` is a new function, deliberately not `_spoken_age_phrase` reused
  verbatim (which would have doubled "old"/"ago" — checked by reading both functions, not assumed).

No scope drift found: `BL-B71` (§6/§7 optic ladder) is absent from the diff (`git diff
main...3b69371 --name-only` touches no `optic_policy.py`/`optics.py`), matching the roadmap entry's
explicit split.

## Milestone-completion question

**Does BL-B70's completion change what BL-B71 should be, or invalidate a downstream assumption?**
Yes, in BL-B71's favour: BL-B71's optic ladder can now key its naked-eye → binoculars → 9K113
escalation directly on `_no_look_cause`'s `"too_far"` arm instead of re-deriving "no fresh look" on
its own — one less thing for that plan to design. It does **not** invalidate anything BL-B71 was
already going to need; the cause taxonomy was built with BL-B71 as a stated future consumer
(roadmap entry's "Related" list), so this is confirmation, not surprise.

**BL-B76** (filed on `main`, 2026-10-15, narrowed 2026-10-16) is the one place this milestone's own
work is presently unverifiable even by a successful flight: `Contact.live_los_clear` cannot carry
`False` through the live admission pipeline as currently gated, so the `"obstructed"` arm of
`_no_look_cause` may never actually fire against real DCS data. BL-B70 built the *correct* taxonomy
against the *wrong* input source for one of its four branches — a pre-existing gap this plan traced
and correctly declined to fix (outside its Affected Modules), not a defect of this diff. This does
not block BL-B70's merge; it does mean the acceptance sortie should not be surprised if `",
obstructed"` is never heard, and that absence is not itself evidence the fix failed.

## Acceptance boundary — what fixtures cannot reach

Mechanical checks and the review chain prove the code does what the taxonomy says, against fixture
contacts and unit-level `decide()` calls. **None of it flies the aircraft.** Specifically out of
reach from this terminal:

- Whether the twelve-o'clock marker (§4) lands early enough, or late enough, to actually prevent the
  overshoot it exists to prevent — that is a timing judgment only a turning pilot can make.
- Whether the four-state losing/regaining-sight register (§10/§11) reads as natural crew speech or
  as a noticeably different register switching at the `too_far` boundary.
- Whether `", obstructed"` firing (or, per BL-B76, *not* firing) reads as correct to a pilot who can
  see the terrain on screen.
- §9's tripwire is a logging instrument with no live sortie's data run through it yet — its own
  presence/skew numbers are unverified until a flight produces a log to read.

This is the exact class of gap the 2026-09-16 F10-vocabulary worked example names: a fixture pass
proves the code did what it says, never that it said the right thing at the controls.

## Required: user acceptance

**Nothing above substitutes for flying it.** The user flies `feature/attack-run-fixes` — this
branch is not merged to `main` and will not be until acceptance passes. Checkout:

```sh
git fetch origin feature/attack-run-fixes   # if working off a remote clone
git checkout feature/attack-run-fixes
```

(No separate build step beyond the normal body-layer run — this is a pure-Python change to
`belief/attack_run.py`/`belief/speech.py`, no DCS Hook/export change, no schema migration.)

### Acceptance Testing Plan: BL-B70 attack-run guidance fixes

**Goal:** confirm the five fixed behaviours (§1/§2/§4/§8/§9's tripwire) and the §10/§11 register
sound right in a live attack run, not merely render correctly against fixture data.

**Prerequisites**
- [ ] `cd body-layer && .venv/bin/mypy src` clean (confirmed above, re-check if you've pulled
      further commits)
- [ ] A mission with a single ground unit on open terrain, as close to the 2026-10-15 sortie's own
      scenario as practical, so the comparison to that sortie's log is direct

**Test Cases**
1. Engage a target and hold alignment steady without the geometry changing — expect the callout to
   stop repeating (§1). Compare against the old behaviour's 38% dead-repeat rate; expect near zero.
2. Fly past the target or turn the aircraft so it goes behind the airframe — expect silence, and the
   run should remain engaged rather than cancelling (§2).
3. Turn through the 1 or 11 o'clock position into 12 o'clock — expect to hear "twelve o'clock"
   before the left/right guidance resumes (§4).
4. Find a target genuinely masked by terrain (a ridge, a building) at close range where it would
   otherwise be resolvable — expect `", obstructed"` only in this case, not when the target is
   merely far away or behind the airframe (§8). If this case cannot be made to fire at all, that is
   itself informative — see the BL-B76 note above.
5. Approach a target from beyond naked-eye presence range and close the distance — expect a
   "last seen... ago" remembered-sighting line once on first losing resolution, bare guidance while
   still too far, then "Eyes on, ..." once on regaining resolution (§10/§11) — not re-announced on
   every tick, and not re-announced merely because the target was briefly masked mid-approach.

**Edge Cases to Probe**
- A target that oscillates near the 12 o'clock boundary — should it chatter "twelve o'clock"
  repeatedly, or only once per entry? (The code claims once per entry; this is where to feel for
  thrashing.)
- A target that goes from too-far to masked to too-far again without ever resolving — should not
  speak "eyes on" or re-announce the loss at the masked step (§11's explicit scenario).
- Whether `", obstructed"` is heard at all this sortie — per BL-B76, it may not be reachable against
  live DCS LOS data regardless of correctness; absence here is not necessarily a defect.

**Pass Criteria**
The feature passes if test cases 1-5 produce the expected spoken behaviour and nothing above sounds
wrong, confusing, or mistimed at the controls. Case 4's possible non-occurrence (BL-B76) is a known,
separately-tracked gap and does not itself fail acceptance.

**Does the feature pass acceptance testing? (yes / no + details)**
