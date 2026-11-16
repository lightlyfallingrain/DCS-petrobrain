# Definition of Done: BL-16 Stage P2 (voice goals + HVRT translate)

**Branch:** `feature/bl16-p2-voice-goals`. **Tip tested:** `e5f65452b162d1be314d5728b6eed5430ffe27a8`
(fast-forwarded cleanly from `370f37c0`, which this worktree started at — `git merge --ff-only`,
clean tree). **This verdict is scoped to that exact sha.** If the branch moves before merge, this
report is stale and must be re-run against the new tip.

Subprojects touched, derived from `git diff --name-only 370f37c0 e5f65452` (never from memory):
**aircraft-layer**, **audio-adapter**, **body-layer**.

## Code Quality

- [x] **Full suite, foreground, per touched subproject** (`.claude/scripts/fast-tests.sh --full
  <subproject>`, fresh `.venv`s built in this worktree, Python 3.12, `ruff`/`mypy`/`pytest`/
  `pytest-xdist` installed into each):
  - **aircraft-layer**: 881 passed (10.17s, parallel).
  - **audio-adapter**: 438 passed, 2 skipped (4.88s, parallel — the 2 skips are the pre-existing
    live-Piper/whisper-binary env-var gates).
  - **body-layer**: 3428 passed, 4 xfailed (149.16s, parallel — the 4 xfailed are pre-existing).
- [x] `ruff format --check` / `ruff check` clean on all three (`src`+`tests`): aircraft-layer 81
  files, audio-adapter 32 files, body-layer 208 files.
- [x] `mypy src --strict` clean on all three, run from inside each subproject (CWD-only config
  discovery): aircraft-layer 27 files, audio-adapter 16 files, body-layer 84 files.
- [x] `luac5.1 -p` clean on `aircraft-layer/dcs-export/Export.lua` and all 8
  `dcs-export/Petrobrain/*.lua` files.
- [x] **Use-before-`local` check** (`luac5.1 -l -p | grep GETGLOBAL`, this project's own
  mechanical check beyond what `-p` alone catches): run on `Export.lua`, `ai_pilot_wheel.lua`,
  `commands.lua`. Every name in the output is Lua stdlib, a genuine DCS API, or a name this
  codebase deliberately exports as a cross-module global via `_G.<name> = <name>` in `core.lua`
  (`client`, `WHEEL_CENTER_BUTTON`/`WHEEL_MENU_BUTTON`, `debug_log`, `safe_call`,
  `json_escape_string`, `extract_json_*_field`, `fmt_num_or_null`, `GetDevice`) — confirmed by
  reading `core.lua`'s own `_G.x = x` lines and diffing against the fork point: all pre-existing,
  none introduced by this feature.
- [x] No unhandled errors/panics in data paths — `aircraft_client.py`'s writes raise
  `AircraftLayerError`, caught at both `_apply_ai_pilot_wheel_goal` call sites in `body.py`,
  logged and the poll loop continues (see the Security open item below for the one correctness
  gap in that same catch block).
- [x] No debug output / no leftover TODOs introduced by this feature — checked the diff (not the
  whole file) against `370f37c0`: the only new `print(...)`/`self._print(...)` call in the
  touched `body.py`/`crew_console.py`/`belief/*.py` files is `self._print(lines, now_sim)`, the
  existing speech mechanism, not a debug print. `test_ai_pilot_wheel_lua.py`'s many `print(...)`
  calls are Lua `print()` inside an embedded-interpreter test harness (pre-existing pattern,
  reads captured stdout as the test's own assertion channel), not debug droppings. No
  `TODO`/`FIXME`/`XXX` added by the diff (`grep` against the full touched-file list).
- [x] No bare `except:`/swallowed exceptions introduced (`grep` on the diff for
  `except:|except Exception:|# noqa|# type: ignore` — none).

**Tested tree's sha**: `e5f65452b162d1be314d5728b6eed5430ffe27a8`. A merge whose tree matches this
sha exactly may skip its own full run, per root `CLAUDE.md` "Verification".

## Scope & Correctness

- [x] Implementation matches `plans/flight-control/plan.md`'s "Stage P2 ready to build" revision —
  read in full (goal channel wire shape, `AiPilotWheelGoal`/rotation rule, the 700 m radar cap
  rule, Readbacks table, Co-moving Fields table, the two sub-stages P2a/P2b) and cross-checked
  against `implementation.md`'s own "Files Changed"/"Notable Discoveries" sections and
  `review-p2.md`'s full-read verdict (APPROVED after one fix round).
- [x] No unplanned scope added silently — every departure from the plan's literal wording is
  flagged in `implementation.md`'s own Notable Discoveries as a named, local, reversible judgement
  call (the enumerated-per-word HVRT tokens instead of one shared token; gating HVRT on `HVR`
  instead of only `HVRT`; `hvrt_step` as a field on the existing message rather than a new op;
  `level_off`'s readback shape) — none silent.
- [x] No invariants from CLAUDE.md violated — no new dependency, no write path outside the
  existing closed command vocabulary (`POST /command/ai_pilot_goal` follows the exact
  `sight_target`/`cockpit_switch` precedent), no DCS-authoritative-state override, single-player
  scope preserved, behaviour-affecting constants (`AI_PILOT_GOAL_SLICE_S`,
  `AI_PILOT_HEADING_TOLERANCE_DEG`, `AI_PILOT_SPEED_STEPS_KMH`, `AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M`)
  all declared through `tuning.py` with `lo`/`hi` bounds — checked against the **rendered**
  `config/defaults.toml`, not just the source comment (no truncation, arithmetic checks out
  against `Export.lua`'s own `AI_PILOT_QUICK_PATH_MAX_AGL_M = 700.0`).
- [x] All new files staged — this merge's own commits are already landed on the branch; nothing
  from the feature itself is unstaged. (This DoD pass's own new files — the backlog entry, notes,
  card, this report — are staged in the final commit below.)

## Testing

- [x] Core logic covered: the rotation mechanism's promote/demote/preempt/settle/takeover-gate
  sequences (pure-function tests), the Lua hold-and-poll loops against a real Lua interpreter
  (mode-cycle-then-press, the `mode_blocked` bound and retry, HVRT hold/redirect/timeout), the new
  slot parsers, the HTTP boundary's validation/bounds/503 paths, `_apply_ai_pilot_wheel_goal`'s own
  composition (transition application, settle/rotate/send, the unpark reset).
- [x] Tests are meaningful, not decorative — `review-p2.md`'s re-review specifically checked this
  for the fix round: the bound test drives 5 explicit tick times and asserts press counts at each
  (not just a final state), the arbitration test traces the real send gate end-to-end through
  `_apply_ai_pilot_wheel_goal` rather than only the unit-level `goal_seq` bump, and the Fix 3 test
  is a rewrite of a test that had previously encoded the bug as the contract (caught by the first
  review pass, verified fixed by the second).
- [x] No existing tests broken — full suites pass clean on all three subprojects (counts above);
  the merge with the seat-gate fix (`a55f7e97`) added a direct covering test
  (`test_goal_hold_releases_without_new_press_on_switch_to_pilot_seat`), verified red-then-green
  against a deliberate revert.

## Documentation

- [x] **Reviewer findings addressed**: `review-p2.md` went NEEDS REVISION → three required fixes
  (HVRT mode-cycle bound; goal/HVRT arbitration; `mode_blocked` must retry) → re-reviewed and
  VERIFIED individually → **APPROVED**, full-read confidence stated both passes.
- [x] **Every accepted plan decision accounted for** — `accepted-items-ledger.sh plans/flight-control`
  reports "U1 U2 U3 not yet answered (no **Answered line)" because it matches only the *first*
  "Decisions Requiring User Input" heading in `plan.md` (a known, already-documented script
  limitation — `review-p2.md`'s own "Optional Refinements" flags it). That first section is
  **Stage P3's own** (CBTM align/break), not this stage's:
  - **U1/U2** (CBTM-align refusal posture) — Stage P3's own open questions, correctly out of
    scope for this DoD; Stage P3 is not built yet.
  - **U3** (player-driven mode change reasserted at once) — answered 2026-11-15, **built**:
    `MODE_CYCLE_MAX_ATTEMPTS`/the mode-cycle-then-press loops always reassert, not deferred to a
    window.
  - **U4** (the goal-slice rotation mechanism, `AI_PILOT_GOAL_SLICE_S = 3.0`) — the live decision
    for *this* stage, in "Decisions Requiring User Input (Stage P2) — answered 2026-11-16." **Built**:
    `decide_ai_pilot_wheel`'s promote/demote-after-slice logic, confirmed by
    `TestDecideAiPilotWheel`'s rotation-after-slice tests and `review-p2.md`'s own verification.
  - **Plan-aligner Q1** (HVRT reachable from hover, auto-cycle-then-press) — **built**:
    `_ai_pilot_hvrt_ready` accepts `HVR`, confirmed by `TestHvrtHold` tests.
  - **Plan-aligner Q2** (`mode_blocked` → "unable, not ready" for the goal channel, superseding the
    plan's original "no spoken line") — **built**: `drain_ai_pilot_wheel_speech`, confirmed by the
    re-review's Fix 3 verification (the retry now actually reaches the re-announce path).
- [x] Non-obvious behaviour explained via code structure/docstrings and this stage's own
  `notes/` additions (below) — `goal_param_for_wire`'s docstring states the "a translate nulls the
  wire `param`" rule explicitly; `set_hvrt_direction`/`clear_hvrt_direction`'s docstrings now note
  the `goal_seq`-bump-on-change requirement the fix round added.

## Security

- [x] `plans/flight-control/security-p2.md` exists, **APPROVED**. Scope: LAN/code-execution
  surface (not player-experience correctness, which is Reviewer's territory). Findings:
  - `[[AC-B14]]` filed (not blocking) — the Lua-side `ai_pilot_goal` dispatch skips the
    enum/bound check its siblings (`sight_target`, `petrovich_search`) have. Low probability
    (loopback-only command socket, same already-accepted local-actor trust boundary as
    `cockpit_switch`), low impact (fixed tiny button set, no crash risk, every hold has a fixed
    safety-ceiling timeout regardless of input validity).
  - **One correctness item passed to Reviewer, decided by DoD below** (see "Open item from
    Security").

### Open item from Security — decided, not blocking

`body.py`'s `_apply_ai_pilot_wheel_goal` advances `ai_pilot_goal_last_sent_seq` unconditionally,
even when `write_ai_pilot_goal` raised `AircraftLayerError` and was caught — so a goal rejected or
lost to a transient LAN/collector hiccup is marked "sent" and not retried until a new or repeated
command for the same parameter. **Confirmed directly in code** (`body.py:3365-3377`,
`:3388-3409` — both call sites bump the sent-cursor outside the `try`).

**Judged: does not make P2 unflyable.** The failure window is a transient network condition, not a
normal-flight path (every full/fast-test run above exercises the non-failing write path). It is
not silent in the deceptive sense — the readback already said what was *heard*, never what was
*achieved*, matching this project's own E-P3/E-P4 "no settlement narration" posture. Recovery
exists without restarting anything: repeating the command, or speaking a different value for the
same parameter, both bump `goal_seq` and resend; a multi-goal session self-heals sooner still,
since every rotation re-promotion sends a fresh message regardless of prior send state. A
single-outstanding goal during an isolated LAN hiccup is the one case with no automatic retry,
and it is the case this DoD's own test card asks the pilot to watch for.

**Filed `[[BL-B122]]`** (`body-layer/ROADMAP/BL-B122.md`, minted via `mint-id.sh BL-B`, added to
`body-layer/ROADMAP/body-layer-backlog.md`'s index) rather than left in this report's prose. The
fix needs a design choice (retry on a transient failure; answer "unable" once and stop on what
reads as a permanent rejection) before implementation, not a one-line patch — correctly deferred
rather than rushed into this merge.

## Verdict

**PASSED.**

---

## Acceptance boundary — stated up front, before the card

This feature's fixtures are a real Lua interpreter, a loopback HTTP server, and synthetic
belief-state construction. **What they structurally cannot reach:**

- Whether the AI wheel's real press-release timing in a live DCS process actually converges
  within the stated tolerances (5° heading, the altitude/speed figures) — every hold-and-poll
  loop is proven against the *takeover* correction's harder, already-flown case (a 742 m
  correction), not against *these* goals' own smaller targets in a live cockpit.
- Whether the 700 m radar cap's refusal behaviour is real DCS physics or an assumption — Stage
  P0-rad (the dedicated probe) was not flown this round; the "alt ... radar" row ships
  provisional until a live altitude-above-cap-while-on-radar attempt confirms it (carried in the
  test card, block 5).
- Whether a human voice, recognised by whisper through the real audio-adapter pipeline, actually
  reaches these new tokens — the vocabulary/slot-parser tests exercise `match_transcript`/the
  parsers directly against pre-transcribed text, never a recognised utterance.
- Whether the HVRT arbitration rule (a main-loop judgement call, not a pilot-specified
  requirement) is the behaviour the pilot actually wants when a translate and a goal collide —
  this is explicitly a confirm-or-overrule item on the card, not a settled requirement being
  verified.

None of this is a defect in the work done; it is the line fixtures draw by construction, stated so
a fixture PASS is never mistaken for a flight PASS.

## Acceptance testing

**PENDING (live).** Card published:
https://claude.ai/artifact/K2vYdNY8d4kVaf2Eom56V8 (source:
`docs/acceptance/2026-11-17-bl16-p2-voice-goals-sortie.md`,
`docs/acceptance/2026-11-17-bl16-p2-voice-goals-card.html`). **Branch to fly: `main`, after this
DoD pass's merge.**

Every command on the card was checked against the real code before being written down — the
exact spoken phrases are pulled from `crew_console.py`'s handler return values and
`vocabulary.py`'s `PHRASES` table, not reconstructed from the plan's prose; `_digit_readback`'s
actual output format ("3 1 5", space-separated) was read, not assumed. The one thing on the card
that is a mechanical certainty rather than a live-only question — whether the deployed vocabulary
is stale — was verified directly:

```
$ python3 .claude/scripts/command-map-check.py
not on the map: level_flight, turn_heading, turn_heading_relative, set_speed, speed_step,
set_altitude, altitude_step, hold_altitude, level_off, hvrt_translate_left,
hvrt_translate_right, hvrt_translate_forward, hvrt_translate_back, hvrt_hold,
hvrt_step_up, hvrt_step_down
command map STALE -- run /command-map
EXIT=1
```

This confirms the plan's own claim ("the `/command-map` redraw ... fires automatically on
whichever merge lands these vocabulary.py changes, per the merge skill's own stale-check") is a
real, working mechanism, not an unverified assertion — `/merge`'s own step 6 will catch this at
merge time and redraw the map. **Noted for the main loop**: expect `command-map-check.py` to exit
1 during this merge; that is this check working as designed, not a DoD regression.

`[[BL-16]]`'s own Stage P1 revision entry already flagged that this stage inherits a
hold-and-poll mechanism proven at a harder scale than its own goals need — re-confirmed true by
this DoD's own reading of `review-p2.md`.

Does Stage P2's completion change what the next stage should be? **No new information** — Stage
P3 (align/launch, break turns) was already next in sequence per the plan's own stage ordering,
and nothing built here invalidates an assumption P3 relies on; P3's own U1/U2 remain open, as
they were before this stage.
