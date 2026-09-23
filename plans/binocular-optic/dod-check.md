### DoD Check: binocular-optic + voice-command-completeness (flown together)

Scope: `feature/binocular-optic` (carries both milestones), merged into this DoD worktree from
`main`. Log range `be6e048`..`7b1b4b6` (binocular Stage 1-3b + review-fix round, voice-command-
completeness Stages 1-5, the acceptance card, and two out-of-scope commits noted below).

Two milestones checked together because their reviews already scoped them that way and the
acceptance card flies them as one loop.

---

## 1 — Checks (real numbers, run fresh in this worktree)

No `.venv` existed in this worktree (worktrees don't carry gitignored dirs). Built one per
subproject matching the main checkout's pinned tool versions (`ruff`, `mypy==2.3.1`,
`pytest==9.1.1`).

**body-layer/** (touched — `src/belief/`, `src/perception/`, `tests/`)
- `ruff format --check src tests` — pass, 97 files already formatted
- `ruff check src tests` — pass, all checks passed
- `mypy --strict src` (`PYTHONPATH=src:../world-model/src`, run from `body-layer/`) — pass, 45
  source files
- `pytest tests -q` (`PYTHONPATH=src:../world-model/src`) — **1080 passed, 4 xfailed**. Matches
  expected.

**audio-adapter/** (touched — `src/vocabulary.py`, `src/transcript_queue.py`, `src/server.py`,
tests)
- `ruff format --check src tests` — pass, 28 files
- `ruff check src tests` — pass
- `mypy --strict src` (`PYTHONPATH=src`) — pass, 15 source files
- `pytest tests -q` — **179 passed, 1 skipped**. Matches expected.

**aircraft-layer/** (not touched by this branch's diff — no Windows-side change, confirmed by
`git diff main...HEAD --name-only`; run anyway as a regression baseline)
- `ruff format --check src tests` — pass, 45 files
- `ruff check src tests` — pass
- `mypy --strict src` — pass, 18 source files
- `pytest tests -q` — **175 passed**. Matches expected.

**Lua** (`aircraft-layer/dcs-export/*.lua`, `luac5.1 -p`, spot-checked `Export.lua`,
`petrobrain-f10-commands-hook.lua`, `petrobrain-overlay-hook.lua`) — all pass. None of these files
are touched by this branch's diff.

## 2 — Working tree / staging

`git status --porcelain` on the merge — clean. `git diff --name-only main...HEAD` confirms scope:
`body-layer/`, `audio-adapter/src|tests`, `docs/acceptance/`, `docs/concept/STATE_TRANSITIONS.md`,
`plans/binocular-optic/`, `plans/voice-command-completeness/`, `todo/todo.md`, `run-scripts/`, and
three subprojects' `.claude/agent-memory/` — no `aircraft-layer/` or `world-model/` source touched.

## 3 — Debug output / suppressed errors / TODOs

`git diff main...HEAD -- body-layer/src audio-adapter/src` grepped for `print(`, `pdb`, `TODO`,
`FIXME`, `XXX`, `breakpoint(`, bare `except:`, `except Exception` — one hit:
`CrewConsole._maybe_log_transcript`'s `except Exception:  # noqa: BLE001 -- a debug sink, never
load-bearing`, guarding a write to an optional transcript-log sink so a logging failure never costs
the player the command they just spoke. Explicitly labeled, consistent with this module's other
optional-sink try/excepts (`overlay_client`, `speech_client`). Not a concern.

## 4 — Reviewer required fixes, verified against code (not just the review's own claim)

**binocular-optic** (`APPROVED WITH MINOR FIXES`, 3 required fixes) — all three landed in the
review-fix commit (`fdec1b5`/`a427df6`):
- D4 wiring gap — `grep -n "_note_player_command" body-layer/src/belief/crew_console.py` shows two
  call sites (`handle_f10_command`'s existing one, plus a new one added to `_handle_utterance`, the
  single point both the typed and voice-fallthrough paths pass through). Confirmed present, not
  just claimed.
- `plans/binocular-optic/plan.md` Stage 3b entry — no longer says "NOT BUILT."
- `body-layer/ROADMAP.md` milestone entry — present (`grep -n "Binocular optic" body-layer/
  ROADMAP.md` → line 775, "DONE, merged 2026-09-23").

**voice-command-completeness** (`APPROVED`, no required fixes) — four optional refinements were
closed anyway per the implementation log's "Closing the review's Optional Refinements" section;
not re-verified line-by-line here since none were required for DoD.

## 5 — Roadmap / doc currency

- `body-layer/ROADMAP.md` — both milestones have full entries (binocular-optic Stages 1-3b,
  voice-command-completeness Stages 1-5), both explicitly marked unflown pending the sortie. **Gap
  found and fixed** (one-line-class staleness correction, done directly per this role's mandate):
  the "Live acceptance debt" list at the top of the file had no entry for this merge — added one
  pointing to `docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`, per that list's own stated
  purpose (a milestone whose live acceptance is *deferred, not waived*, tracked until a real sortie
  clears it).
- `audio-adapter/ROADMAP.md` — **stale, not fixed.** No entry anywhere for the Stage 3 wire fix this
  branch carries (`MatchResult.bearing_degrees` was computed but dropped before reaching
  `TranscriptEvent`; `vocabulary.py`/`transcript_queue.py`/`server.py` all changed). This is more
  than a one-line correction — it needs a real Status entry describing what changed and why,
  written by whoever next touches that file with the wire-fix context in hand. Flagging, not
  fixing, per this role's scope for non-one-line gaps.
- Root `ROADMAP.md` — **stale, not fixed.** The Body Layer status row makes no mention of either
  milestone; the Audio Adapter row is stale further back too (predates the already-merged inbound-
  speech Stages 4/5, `7b1b4b6`, which landed on this same branch before the two milestones this
  check covers). Both rows need a real rewrite, not a line edit — flagging for the next session
  that touches root `ROADMAP.md`, not fixed here.

Neither gap blocks merge — both subprojects' own `ROADMAP.md` files (the actual source of truth
per root `CLAUDE.md`) are current for the milestones under review here; root `ROADMAP.md` and
audio-adapter's are summary/pointer documents that were already behind before this branch, on
unrelated prior work.

## 6 — Milestone-completion question (root `CLAUDE.md` "Milestone Completion")

**binocular-optic:** Does completion change what's next, or invalidate a downstream assumption?
Yes, directly — it defines the next milestone (Stage 4: the live sortie against real dwell/lockout/
sweep constants) and every constant it ships (dwell, lockout length, bearing-uncertainty default,
search-band) is provisional pending that flight; nothing downstream should read these as validated.

**voice-command-completeness:** Same question. No architectural invalidation — Stage 5's nine new
o'clock tokens are unbenched (no corpus recording), which changes what the *next* voice-vocabulary
work should be (a corpus recording pass covering them, same class as `cancel_scan`/`cancel_watch`
before 2026-09-23) but doesn't invalidate anything already built.

## 7 — Acceptance testing: DEFERRED, not run

Per instruction, this session does not run or ask for acceptance testing. Both milestones ship with
**no live-DCS acceptance** — every constant, both binocular timings and the voice-vocabulary
recognition of the nine new `scan <clock>` tokens, is fixture/console-verified only. The card
already exists (`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`), written to specifically
name what fixtures cannot reach (see next section). Recorded as live-acceptance debt in
`body-layer/ROADMAP.md` (§5 above), not as a merge blocker.

## 8 — Acceptance boundary (what these fixtures structurally cannot reach)

Stated explicitly, per this role's mandate — not more testing, an honest line:

- **Whether binoculars "feel like a crewman."** Fixtures can prove the phase-cycle state machine is
  correct and the lockout is structural, not that raising binoculars every ~16s (or however a
  commanded sector's shorter cycle plays out live) reads as natural crew behaviour rather than a tic.
  No fixture has an opinion on cadence.
- **Whether the uncalibrated constants (dwell, lockout length, bearing-uncertainty sweep default,
  search band) are anywhere near right.** They are internally consistent and tested for their own
  logic, not validated against a real cockpit's geometry or a real crewman's timing.
- **The nine `scan <clock>` tokens' recognition accuracy.** No corpus recording exists for them at
  all — unmeasured in the benched sense the other 32 tokens have, and unmeasured live. A fixture
  test proves the dispatch table is wired; it cannot prove Whisper hears "scan three o'clock"
  reliably against this user's voice.
- **The seam between binoculars and voice, specifically.** Both milestones were reviewed
  individually and pass on their own fixtures; nothing in either test suite exercises them
  together (e.g., a spoken command landing exactly while binoculars are mid-sweep). The acceptance
  card's own framing — "the interesting failures are likely to be where they touch" — names this
  gap directly rather than assuming fixture coverage transfers.
- **Report wording read aloud, not just rendered as text.** `render_report`'s truncation and the
  clear/no-view distinction are unit-tested as strings; whether they read naturally at cockpit
  cadence, or run too long to sit through for a multi-contact report, is a live-ear question the
  card asks the user to judge (§1's "does a multi-contact report run too long to sit through").

## 9 — Recurring-fix pattern flagged (process signal, not a blocker)

**Plans naming test files/expectations incorrectly, three occurrences now**, none previously
tracked as a pattern in architect/dod memory:
1. An earlier design named an `xfail` test it expected to flip; the test had been folded into
   another by an unrelated commit (`NOTES.md`, "A design written against a stale test list produces
   phantom expectations").
2. A file omitted from a plan's list entirely (referenced in `plans/voice-command-completeness/
   implementation.md`'s Notable Discoveries as the second prior incident).
3. This branch: the plan named `audio-adapter/tests/test_transcript_queue.py`/`test_server.py` for
   the `TranscriptEvent`/`POST /transcribe` wire changes; the real coverage is in
   `test_transcribe_api.py` — a real file, just named wrong (`plans/voice-command-completeness/
   implementation.md` Notable Discoveries).

All three were caught by the implementer grepping before writing, at zero cost to this branch — but
three variants of the same failure mode (doesn't exist / omitted / wrong name) suggests the
generating step is Architect's plan-writing, not Implementer's execution. Added a pattern memory to
this role's own `MEMORY.md` (see below); recommend Architect verify named test files exist via grep
before finalizing a plan, rather than relying on Implementer to catch it every time.

## 10 — What blocks merge

**Nothing.** All checks pass with real, freshly-run numbers matching expected counts; both
milestones' reviewer-required fixes are verified present in code, not just claimed; the working
tree is clean; both subprojects' own roadmaps (the actual source of truth) are current; live
acceptance is deliberately deferred and now tracked as debt rather than silently dropped. The two
stale summary documents (root `ROADMAP.md`, `audio-adapter/ROADMAP.md`) and the recurring plan-
naming pattern are real but neither is a merge blocker — both are flagged for follow-up.

---

### Verdict: DoD PASSED. Acceptance testing DEFERRED (tracked as live-acceptance debt, not waived).
