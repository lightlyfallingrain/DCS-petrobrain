### Review Summary

**Branch:** `fix/callout-observability-gate` · **Reviewed:** `61edc58` (= `31d5733` + cherry-pick
of `76c3550`, `-x` recorded) · **Base:** current `main` `81c4374` · **Date:** 2026-10-06

**Branch-contract note.** The sha named at dispatch, `9d02ad1`, **is not a valid object in this
repository** (`git rev-parse` fatal). The worktree landed on the branch's real tip and the branch is
two commits atop current `main`, so nothing was reviewed at the wrong commit — but the named sha was
wrong, not merely stale, and that is worth knowing given AGENTS.md rule 4's recent history. The
follow-up `76c3550` applied clean with no conflict; `dce2534` in the Debugger's own report is an
older `main`, so the reviewable scope is `main..HEAD`, not `dce2534..HEAD`.

Scope reviewed (`main...HEAD`, 8 files, +704/−2): `belief/callouts.py`, `belief/contacts.py`,
`perception/motion.py`, `tests/test_callouts.py`, `plans/callout-observability-gate/debug.md`, three
`.claude/agent-memory/debugger/` files.

**The fix is correct, well-placed, and the hard claims hold up under re-derivation.** Everything the
task flagged for scrutiny was checked by running code rather than by reading:

| claim | how verified | result |
|---|---|---|
| gate reads bookkeeping that is current for every contact | read `ContactStore.tick` 1146→1489: `observable_or_grace` is computed unconditionally per contact; **no `continue`/`break` anywhere in the loop** | holds |
| ordering is current by construction | `run_once`: `ingest` → `store.tick(ownship)` → … → `drain_events(last_t_sim)`, same `t_sim` | holds |
| a permanently-astern event retires | probe: astern from t=1 to t=60 → `_consumed` flips **True at t=12** (age 11 > `CALLOUT_MAX_AGE_S` 10); brought back into view at t=61, stays silent | holds |
| reverse order would leak | same probe with the gate moved above the age check → `_consumed` **never** becomes True through t=60 | holds; ordering justified |
| three tests fail pre-fix | `callout_observable` neutralised to `return True` → **exactly** `…masked_bearing`, `…deferred_not_lost`, `…every_member_is_masked` fail, 4 guards pass | holds |
| grace test pins the grace | removing the grace branch makes it fail (stamp at t=0, masked at t=5, speaks); it is a guard, so it also passes with the gate absent — as documented | holds |
| `motion.py` is comment-only | `git diff` filtered to non-`#` lines → **empty**; `MOTION_VELOCITY_MAX_SKEW_S` still `2.0` | holds |
| both rates are producer rates | `Export.lua:143` `EXPORT_INTERVAL_S = 0.2`; `petrobrain-mission-telemetry-hook.lua:91` `POLL_INTERVAL_S = 1.0` — both exactly at the named lines | holds |
| grace == max age | `decay.py:143` `10.0`, `callouts.py:282` `10.0` | holds |
| 17/3 split | matches `explore-notes.md` §9 (17 unprompted / 3 within 0.0–4.4 s, seven report-family commands). The three `t_sim` values 1601.0/1734.3/2966.2 appear only in `debug.md`; §9 does not list them, so they are unverifiable here but **not contradicted** | consistent |

**The pull-path independence is structural, not merely observed.** Mechanically scoped
`_handle_report` (lines 1519–1662) and extracted every attribute it touches: `self.enrichment` and
`self.store`, nothing else. Zero occurrences of `scheduler`, `callout_observable`, `tick(` or
`drain_events` in its body. `callout_observable` has **exactly two call sites in the whole tree**,
both inside `CalloutScheduler.tick`, whose **only** caller is `CrewConsole.drain_events`, which is
called from exactly one place (`logger.py:1484`) and never from `_handle_report`. So the crew query
path (`plans/crew-query-path/plan.md`) cannot be reached by this gate without someone adding a new
call site — which is the property that matters, and the `callouts.py` docstring now names it.

**No invariant at risk.** No DCS writes, nothing under `world-model/data/`, no `.gitignore` change,
type hints complete, `mypy --strict` clean, no leftover debug code or TODOs in the three touched
source files.

### Required Fixes

- **`CONTACT_ENGAGEMENT_CHANGED` is also newly gated, and nothing says so — the breadth question put
  to the user understates itself.** `debug.md`'s "For the user" item 1, the `callouts.py` inline
  comment and the `callouts.py` module docstring all describe the widening as
  `CONTACT_DETECTED`/`CONTACT_REACQUIRED`. It is three kinds, not two. Verified: `observable_or_grace`
  appears at only **two** emission sites (`contacts.py:1237` motion, `:1349` range-crossed) — the
  seventh block that mints `CONTACT_ENGAGEMENT_CHANGED` (`:1456`) was **never** gated at emission,
  and `CONTACT_ENGAGEMENT_CHANGED` is in `_TEMPLATED_KINDS` (`callouts.py:236`), so the new gate —
  which discriminates on the contact and not at all on the kind — now applies to it.

  This is the one of the three where the trade-off is not identification chatter but a **threat
  warning about a contact the pilot already asked to watch**: a SAM or ZSU astern whose engagement
  envelope just started covering the aircraft now produces silence, and because the grace window
  equals `CALLOUT_MAX_AGE_S`, a watched threat masked for more than 10 s loses that callout
  permanently rather than late. That reads directly against *"Petrovich helps the pilot evade
  dangerous units"* (root `CLAUDE.md`).

  **Concrete change, documentation only — no behaviour change is required by this review, because
  the breadth itself is a defensible reading of the invariant and is the user's call:** add
  `CONTACT_ENGAGEMENT_CHANGED` to the enumeration in all three places (the `callouts.py` module
  docstring, the inline comment at the event-loop gate, and `debug.md`'s "For the user" item 1), and
  state in item 1 that it is the kind where the cost of gating is a missed threat cue rather than a
  missed identification. The user is being asked to approve a two-kind widening and would in fact be
  approving a three-kind one, with the third being the only safety-relevant member — that is exactly
  the kind of silent breadth this fix's own reasoning (*"a per-kind list the next kind silently fails
  to join"*) exists to prevent, arriving from the other direction.

### Optional Refinements

- **No test pins the bounded-deferral property the ordering exists for** (optional). The deferral
  test proves "not consumed, speaks when the bearing returns"; nothing asserts that a *permanently*
  astern event is eventually consumed. I verified it by probe, and the reverse-order counterfactual
  only differs in that the candidate is rescanned forever rather than retired — so this is a
  maintenance guard, not a live gap. A test that ticks astern past `CALLOUT_MAX_AGE_S` and asserts
  silence-after-return would pin the one property the comment argues the ordering from.
- **The "90° is narrower than 130°" argument compares two different frames** (optional).
  `perception/association.py:122`'s `FORWARD_HEMISPHERE_HALF_WIDTH_DEG = 90.0` is measured against
  ownship's **true heading** (yaw only), while `_CO_PILOT_MASK.rear_cutoff_deg = 130.0` is a
  **body-relative** azimuth that includes pitch and bank. Dead astern is 180° in both frames, so the
  load-bearing conclusion ("a contact cannot be founded dead astern") is sound; but in a hard bank a
  hybrid-founded contact within ±90° of heading can sit past 130° body azimuth, so the gating of
  `CONTACT_DETECTED`/`CONTACT_REACQUIRED` is not quite the no-op the comment claims. Behaviour is
  still defensible (he genuinely cannot see it); one clause noting the frame difference would stop
  the next reader taking "90 < 130" as frame-matched.
- **`test_group_disclosure_speaks_when_any_one_member_is_observable` stamps `last_observable_sim`
  directly** rather than reaching the state geometrically (optional). The docstring is honest about
  why — a cohering group's members share one body azimuth at test range — and the stamp is exactly
  what `_callout_may_speak` would leave. Worth keeping in mind that the `any`-vs-`all` choice is
  therefore only distinguishable at close range, where a group genuinely can straddle the cutoff.
  `any` is the right default regardless (it is the less-suppressing one).
- **`debug.md` still leads with "20 of 357"** before correcting to 17 four lines later (optional).
  The correction is present and clear; a reader skimming the table alone still takes away 20. The
  source files were all corrected properly.

### Verdict

**APPROVED WITH REQUIRED FIXES** — the one required fix is documentation plus the user-facing
question's framing, not code. The gate itself, its placement, its ordering, its no-op escape and its
tests are all sound and independently re-verified.

### Verification run (worktree had no `.venv`; used `body-layer/.venv` tooling from the main
checkout, with cwd inside the worktree's `body-layer/`)

Confirmed first that imports resolve to the **worktree's** `src` (`belief.contacts.__file__` under
`.claude/worktrees/agent-a1a663030835d9e16/`, `callout_observable` present) — the rule-4 trap does
not apply here.

| check | result |
|---|---|
| `ruff format --check src tests` | 115 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` (cwd `body-layer/`) | Success: no issues found in 53 source files |
| `pytest tests -q` | **1473 passed, 4 xfailed** — matches the expected count exactly |

All probe edits reverted; `git status --porcelain` empty before commit.

### Review Confidence

**Full read**, with four independent re-derivations by running code (gate neutralisation, the
reversed-order counterfactual, the astern-retirement probe, and a mechanical attribute extraction
over `_handle_report`). The only item not independently verifiable from this tree is the three
pull-path `t_sim` values, which exist in `debug.md` but not in `explore-notes.md` §9; they are
consistent with §9 and are not load-bearing for the fix.
