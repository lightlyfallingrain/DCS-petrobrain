# Definition of Done — Stage 2 (inbound-speech)

**Branch:** `feature/stt-command-matcher` · **Commits:** `62690ad..aef7f90`  
**Date:** 2026-09-19  
**Reviewer Approval:** ✓ APPROVED (2026-09-19, `aef7f90`)

---

## DoD Checklist — ALL PASS

### Code Quality
- ✅ **Format/Lint/Type/Test for both subprojects:** Verified by direct execution
  - `srs-adapter`: `ruff format --check` ✓ | `ruff check` ✓ | `mypy --strict src tools/stt_bench.py` ✓ | `pytest -q` → **81 passed, 1 skipped**
  - `body-layer`: `ruff format --check` ✓ | `ruff check` ✓ | `mypy --strict src` (from body-layer/) ✓ | `pytest -q` → **705 passed**
- ✅ **No unhandled errors or panics:** Reviewed error handling in matcher and band classifier; all cases caught
- ✅ **No debug output in committed code:** Confirmed by review
- ✅ **No leftover TODO comments introduced by this feature:** None found

### Scope & Correctness
- ✅ **Implementation matches plan:** Reviewed against Decision 4 REVISED, Decisions 5-6, Stage 1 result section
- ✅ **No unplanned scope added:** Module split (adapter owns matching, body owns behaviour) matches Decision 4 REVISED exactly
- ✅ **No invariants violated:** Module independence preserved — `body-layer` imports nothing from `srs-adapter` (verified by grep)
- ✅ **All new files staged and committed:** Code changes in commits on branch; only agent memory/review files staged

### Testing
- ✅ **Core logic covered:**
  - `srs-adapter/tests/test_command_matcher.py`: exact hits, verb-anchor rejection, bearing parsing, separation check, regression guards
  - `body-layer/tests/test_voice_commands.py`: all four dispositions, ambiguous-always-confirms, cancel-task higher floor
  - `body-layer/tests/test_crew_console.py`: `handle_transcript` routing, pending-confirmation lifecycle, `!voice` harness
- ✅ **Tests are meaningful:** Tested against real false-positive fixtures (15 cases from reviewer's own run) and real-corpus mishearings
- ✅ **No existing tests broken:** All pre-existing tests continue to pass

### Documentation
- ✅ **Reviewer findings addressed:** Two required fixes (verb-anchor leak + ACT_FLOOR citation) verified genuine via direct execution; optional items folded into plan
- ✅ **Non-obvious behavior explained:** Asymmetry between `VERB_FLOOR` (0.5) and `MATCH_FLOOR` (0.6) documented as deliberate pair; phrase-match rewrite documented in module docstring

### Security
- ✅ **Security plan review:** Not required (root `CLAUDE.md` exempts Security phase for this project)
- ✅ **No untrusted input surfaces:** All matcher parameters are constants or closed-set booleans from `command_matcher.MatchResult`

### Staging & Mergeability
- ✅ **Clean working tree:** Only `body-layer/run-crew-text.sh` has uncommitted changes (user's own local wiring; left alone per instructions)
- ✅ **No audio/binaries/gitignored files committed:** Verified; untracked world-model files are gitignored
- ✅ **Acceptance testing possible without Windows/DCS:** Stage 2 entirely text-driven via `!voice` REPL command

---

## Acceptance Boundary (Structural Limits)

**Stage 2 fixtures cannot reach:**
1. **Live audio or real transcripts** — the `!voice` command takes pre-matched results as typed arguments, not audio clips
2. **Windows audio capture or real PTT events** — capture and PTT gating are Stage 4-5 work
3. **Voice-only token dispatch** — tokens like `report_all`, `report_bearing_*`, `report_clock_*`, `scan_bearing_deg`, `stop_talking` match but dispatch is deferred (graceful no-op); only 15-token legacy vocabulary produces real effects
4. **Brain-layer escalation behavior** — non-matching speech routes to escalation, but stand-in `DebugPrintBrainClient` produces no output
5. **Live acceptance at sortie scale** — fixture pass certifies mechanism; real usage requires human judgment in cockpit (Stage 6 work)

---

## Acceptance Testing Plan: Stage 2 Voice Command Matcher

**Goal:** Verify that the `!voice` REPL harness correctly drives the text-matcher pipeline through all four band dispositions (act, confirm, say-again, fallthrough) and that pending-confirmation state transitions work correctly.

**Prerequisites**
- [ ] Body-layer repo checkable (`cd body-layer && .venv/bin/python -m logger --console` starts with no crashes)
- [ ] Stage 1's threshold constants known: `ACT_FLOOR=0.60`, `CONFIRM_FLOOR=0.35` (documented in `body-layer/src/belief/voice_commands.py`)

**Test Cases**

1. **Happy path — clean `scan_left` match above `ACT_FLOOR`**
   ```
   !voice scan_left 0.95 0.85 1 0 scan to the left
   ```
   Expected: Reads back `"Scanning to the left."` (via `render_scan_readback`), no confirm prompt

2. **Confirm band — `watch_nearest` above `CONFIRM_FLOOR` but below `ACT_FLOOR`**
   ```
   !voice watch_nearest 0.72 0.40 1 0 watch the nearest
   ```
   Expected: Reads back `"Watch nearest, confirm?"` (via `render_confirm_request`), holds pending

3. **Confirm-then-affirm — answer the confirm band prompt**
   ```
   (immediately after case 2)
   !voice - 0.0 1.0 0 0 affirm
   ```
   Expected: Executes `watch_nearest`, reads back `"Watching <contact report>."`, clears pending

4. **Confirm-then-negative — discard the pending confirmation**
   ```
   (repeat case 2, then)
   !voice - 0.0 1.0 0 0 negative
   ```
   Expected: Returns empty (silent discard), clears pending confirmation

5. **Confirm-then-unrelated — discard stale question, process new utterance**
   ```
   (repeat case 2, then)
   !voice - 0.0 0.50 0 0 where is contact one
   ```
   Expected: Discards pending silently, routes new utterance through escalation path

6. **Say-again — below `CONFIRM_FLOOR`**
   ```
   !voice - 0.0 0.20 0 0 garbled nonsense text
   ```
   Expected: Reads back `"Say again?"` (via `render_say_again`), no execution

7. **Fallthrough — no match (`token=None`), verb not anchored**
   ```
   !voice - 0.0 0.90 0 0 the weather is quite nice
   ```
   Expected: Routes to escalation path (no band decision)

8. **Ambiguous always-confirms — two candidates tied**
   ```
   !voice scan_east 0.50 0.85 1 1 scan east
   ```
   Expected: Despite high confidence, `ambiguous=1` forces confirm band, reads back `"Scan east, confirm?"`

9. **Cancel-task higher floor — `cancel_task` requires `ACT_FLOOR_CANCEL` (0.80)**
   ```
   !voice cancel_task 0.95 0.75 1 0 cancel the task
   ```
   Expected: Combined confidence = 0.95 * 0.95 = 0.9025 > 0.80, executes directly

10. **Confirm-window expiry — hold pending longer than `CONFIRM_WINDOW_S` (8.0 s)**
    ```
    !voice watch_nearest 0.72 0.40 1 0 watch the nearest
    (manually step sim time forward by 9 seconds)
    !voice - 0.0 1.0 0 0 affirm
    ```
    Expected: Affirm treats expired confirmation as new input, routes to escalation (no command)

**Pass Criteria**

All 10 test cases produce expected output (readbacks, confirms, silent discards, escalations) with no crashes or exceptions. Confirm-band state transitions work across sequential commands. Fallthrough utterances correctly route without partial matches. No regressions in surrounding text commands.

---

## Milestone Completion Question

**Does Stage 2's completion change what Stage 3 should be, or invalidate an assumption a later stage relies on?**

**Answer:** Yes — one clarification, already documented. Stage 2's implementation revealed that Decision 4 REVISED's seam payload was incomplete. Two additional fields (`verb_anchored` and `ambiguous`) are **required**, not optional, to distinguish three behaviourally distinct `token=None` outcomes (not-a-command / verb-anchored-but-unresolved / ambiguous).

**Stage 3 impact:** `GET /transcripts/poll` must return these two fields alongside `token` and `match_ratio` in its JSON payload. The seam table in the plan (`plans/inbound-speech/plan.md` Decision 6) has been updated inline (2026-09-19 note added) to show the real 7-argument shape. This is a clarification of what Stage 3's payload shape must be, not a change to architecture or interpretation bands.

---

## Known Gaps and Deferral Record

**Real dispatch for voice-only tokens (deferred to later milestone):**
- `report_all`, `report_bearing_*`, `report_clock_*`, `scan_bearing_deg`, `stop_talking`
- These tokens match and reach the band classifier. Acting on them is a graceful no-op (`handle_f10_command`'s defensive `else`).
- Why deferred: Report tokens need query capabilities that don't exist; dispatch mechanism is documented as missing, not silent.

**Confidence band constants are unmeasured placeholders (pending live sortie data):**
- `ACT_FLOOR_CANCEL` (0.80), `CONFIRM_FLOOR` (0.35), `CONFIRM_WINDOW_S` (8.0)
- `ACT_FLOOR` (0.60) is grounded in Stage 1 measurement; the rest are placeholders.
- Will be re-tuned after Stage 6's live sorties.

**Phrase-match on short words is loose by design:**
- `VERB_FLOOR` (0.5) < `MATCH_FLOOR` (0.6) intentionally
- A false verb anchor triggers an extra phrase-scoring pass that almost always rejects it; a false verb rejection is irreversible
- This asymmetry was verified against 15 real false-positive fixtures and an 80-case adversarial sweep; behavior is documented

---

## Live Acceptance Status

**What is verified in fixtures:** ✅ Text-to-token matching under all band thresholds, confirm-question lifecycle, fallthrough, separation check, voice-only token matching

**What is deferred to live sorties (Stage 6):** Latency, false-fire rate under cockpit noise, confirm-band frequency, pilot subjective experience

---

## Recommendation

**READY TO MERGE** pending:
1. User accepts the acceptance testing card above
2. User confirms Stage 2's test cases pass (or confirms already confident based on fixtures)
3. Optionally: knowledge harvest into NOTES.md (asymmetric verb-floor pattern, short-word matching challenges)

**Do not merge without:** User's explicit approval (root `CLAUDE.md` policy)

---

**Stage 2 is complete and ready for Stage 3 planning.**### Acceptance Testing Card: Stage 2 — CORRECTED AND VERIFIED

**An earlier version of this card was wrong in four ways and is replaced.** It named
`python -m logger --console`, which does not host `!voice` (that is the *crew* console, `--crew-text`)
and requires `--aircraft-layer-url`/`--theatre`/`--world-model-db`, all three mandatory — so it
needed the Windows box for a stage with no hardware in it. It also inverted `!voice`'s argument
order, used a token name that does not exist (`scan_east`; the token is `scan_bearing_e`), and gave
at least one case whose arithmetic lands in a different band than its description claims. Every
case below was executed against the real `CrewConsole` on this branch, and the outputs are
transcribed from that run rather than predicted.

**Run it:**

```sh
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python tools/voice_repl.py
```

Both path entries and this subproject's interpreter are required (`belief.tasks` reaches the
world-model seam, which pulls in `pyproj`). No aircraft layer, no world-model database, no theatre,
no DCS, no audio.

**Argument order** — note ratio comes *before* confidence:

```
!voice <token|-> <match_ratio> <confidence> <verb_anchored:0|1> <ambiguous:0|1> <transcript...>
!time <seconds>          advance simulated time, for confirm expiry
```

The band decision is on `combined = confidence × match_ratio`, against `ACT_FLOOR` 0.60,
`ACT_FLOOR_CANCEL` 0.80, `CONFIRM_FLOOR` 0.35, `CONFIRM_WINDOW_S` 8.0.

| # | type this | combined | expected |
| --- | --- | --- | --- |
| A | `!voice scan_left 0.90 0.95 1 0 scan left` | 0.855 | acts — reaches dispatch |
| B | `!voice scan_ahead 0.80 0.55 1 0 scan ahead` | 0.440 | `Scan ahead, confirm?` |
| C | `!voice scan_ahead 0.60 0.40 1 0 scan ahead` | 0.240 | `Say again?` |
| D | `!voice - 0.0 0.90 0 0 the tanks are on the ridge` | — | silence; escalates to the brain path |
| E | `!voice scan_bearing_e 0.95 0.95 1 1 scan east` | 0.903 | `Scan east, confirm?` — **ambiguous overrides a high score** |
| F | B, then `!voice - 0.0 1.0 0 0 affirm` | — | executes the held command |
| G | B, then `!voice - 0.0 1.0 0 0 negative` | — | silent discard |
| H | B, then `!time 9`, then `affirm` as in F | — | silence — the window expired, nothing runs |
| I | `!voice - 0.0 1.0 0 0 affirm` with nothing pending | — | silence — a stray "yes" must never act |
| J | `!voice cancel_task 0.90 0.95 1 0 cancel task` | 0.855 | acts (`nothing to stop` on an empty store) |
| K | `!voice cancel_task 0.90 0.85 1 0 cancel task` | 0.765 | `Cancel the task, confirm?` — **under cancel's higher floor** |

**What to actually look at.** A and J prove the act path; C proves a mishearing asks rather than
guesses; D proves free speech is not pulled into the command matcher; E and K are the two cases
worth dwelling on, because they are where the design refuses to take an easy answer — E declines a
0.903 score purely because two candidates were too close, and K holds `cancel` to a higher bar than
every other command.

H and I are the ones that would be easy to get wrong and hard to notice: a confirmation must expire
rather than linger, and an affirmative outside a pending confirmation must do nothing at all.

**On A, F and J:** with an empty contact store and no world-model connection, these print
`no world-model connection configured` or `nothing to stop` rather than a readback. That is the
dispatch being reached, which is what the band test is proving. Full readback text needs a live
session and belongs to Stage 6.

**Known gap you will notice:** `report`, `stop`, `say again` and the bearing tokens match and
confirm correctly but have no dispatch yet — they no-op. Deliberate, recorded, and Stage 3 work.


