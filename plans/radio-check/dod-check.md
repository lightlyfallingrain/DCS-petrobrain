### Definition of Done: `feature/radio-check` (BL-B82, BL-B81)

Scoped to merge commit `92ae5b3cbee63548fa49344d171296ff3aca40b8` (`Performance review:
feature/radio-check batch`), fast-forwarded from `main`@`d1126570612b29379b50c5c7bda32b123fa250a3`.
This verdict is scoped to that tip — if the branch moves, re-verify.

#### Gate status going in

- Reviewer: APPROVED (initial `192c1b0f`) → review fixes (`2f1c8d8c`) → Fix review: APPROVED. Full
  read both passes (`plans/radio-check/review.md`).
- Performance Reviewer: APPROVED, no action items (`plans/radio-check/performance-review.md`).
- Security (deep analysis): APPROVED, no findings above "none" (`plans/radio-check/security-deep-analysis.md`).

#### Mechanical checks

| Check | body-layer | audio-adapter |
|---|---|---|
| `ruff format --check src tests` | PASS (155 files) | PASS (29 files) |
| `ruff check src tests` | PASS | PASS |
| `mypy --strict src` (run `cd <subproject> && .venv/bin/mypy src`) | PASS (68 files) | PASS (15 files) |
| `pytest tests -q` | PASS (2237 passed, 4 xfailed) | PASS (300 passed, 1 pre-existing skip) |

Run directly in this worktree, not taken from any report.

- **`body-layer/config/defaults.toml`'s `ON_GROUND_AGL_THRESHOLD_M` entry reads correctly**,
  checked against the **rendered** file (not the source `#:` comment):
  ```
  [belief.crew_console]
  # Below this altitude AGL in metres, Petrovich is treated as on the ground: perception stops and
  # a look command is refused rather than dispatched -- too high false-grounds him during genuine
  # low-level/NOE flight, too low lets him scan while the aircraft is still sitting on the ramp.
  # status: uncalibrated | range: 0.5 .. 50.0
  # source: belief/crew_console.py:ON_GROUND_AGL_THRESHOLD_M
  ON_GROUND_AGL_THRESHOLD_M = 10.0
  ```
  Full warning survives rendering (it's written as a single sentence with no internal period, so
  the generator's one-sentence-only rendering rule doesn't truncate it) — confirms the review's own
  finding on this point.
- **No debug output / TODO/FIXME left by this feature.** `git diff` over the touched files in both
  subprojects, grepped for `TODO`/`FIXME`/`pdb`/stray `print(` — the only `print(`-shaped hits are
  pre-existing `self._print(...)` call sites (the crew-console's designed output funnel), not
  leftover debug prints.
- **`maybe_apply_on_ground_default`/`_on_ground_default_applied` fully removed**, cross-checked
  independently (not just taken from the Reviewer's grep): only historical plan docs
  (`plans/spu8-intercom/*`) and "marked, not deleted" supersession comments remain; no live call
  site, test, or docstring.
- **Staging / tree state:** `git status --porcelain` clean at merge time; all files from the
  fast-forward are committed (19 files, see merge log below).

#### Scope & correctness

- Implementation matches `plans/radio-check/plan.md` exactly, per Reviewer's full read — build
  order (BL-B82 before BL-B81), on-ground gate placement (both poll loops, perception only, belief
  decay untouched), `_LOOK_COMMAND_TOKENS` scope (scan family + `watch_nearest`/
  `watch_nearest_air_defence`/`follow`), refusal-mode precedence, silence-ends-on-any-command
  ordering, and the F10/voice-wiring scope decisions (F10 correctly not added; voice wiring done in
  `audio-adapter` as a necessary but originally out-of-plan cross-subproject follow-up, stated
  explicitly in `implementation.md` rather than added silently).
- No invariants violated: no-omniscience boundary untouched (new code reads only
  `ownship.alt_agl_m` and fixed slot values, never a DCS object id); mechanism/calibration not
  mixed in one commit (the on-ground gate and the `tuning.py` wiring landed as separate review-fix
  work, not folded together); world-model/DCS authority untouched.

#### Testing

- Core logic covered: on-ground gate (both poll loops, resumes above threshold, existing belief
  decays but is not wiped), look-command refusal (6 dedicated tests + refusal-mode precedence),
  radio-check/greeting dispatch (ground/air/refusal/silence-ending), typed crew-text dispatch, the
  now-closed cross-subproject `time_of_day` drift guard (one test per side, each naming the other
  by function name). Reviewer mutation-tested two of the new guards directly (neutralized the
  on-ground branch and the `ConsolePerceptionRunner` gate, confirmed red for the stated reason, not
  just that something failed).
- No regressions: full suites green on both subprojects, including the pre-existing xfails/skip
  unchanged in count.

#### Documentation

- Reviewer's one required fix (asymmetric drift guard) addressed and confirmed in the fix review.
  All three optional refinements either applied (`on_ground` defaults `True`; `tuning.py` wiring)
  or correctly left alone (the `DISPATCHED_COMMAND_TOKENS` note, already verified with no fix
  needed).
- Non-obvious behaviour: `ON_GROUND_AGL_THRESHOLD_M`'s doing double duty (perception gate +
  look-command refusal, on top of its removed-and-superseded original one-shot-silence use) is
  recorded in its own tuning comment and in the plan/implementation docs; no separate NOTES.md
  entry needed (checked against existing NOTES.md — the relevant general lessons, cross-subproject
  voice-token wiring and rendered-artifact verification, are already there from earlier features;
  nothing new and non-obvious surfaced this time that isn't already covered by this feature's own
  plan docs or an existing entry).

#### Security

- `plans/radio-check/security-deep-analysis.md`: APPROVED, no required fixes. No separate plan
  review ran for this small batch (stated and accepted in the security doc itself, matching the
  current once-per-batch cadence root `CLAUDE.md` sets).

### Verdict: PASS

---

### Acceptance boundary — what these fixtures structurally cannot reach

Every test above runs against synthetic `OwnshipState`/fixture telemetry and a fake/loopback
aircraft-layer. None of it can tell us:

- **Whether the intercom/voice pipeline actually carries "radio check" and the four greetings at
  all**, end to end, through a real microphone, real whisper transcription, and the real `/speak`
  TTS path. The command-matcher's near-miss behaviour is measured against known transcript strings,
  not against what whisper actually outputs for this pilot's voice and intercom audio quality. This
  is the single most load-bearing untested path in this feature — it is also the feature's whole
  stated purpose (confirming the intercom is alive).
- **Whether `ON_GROUND_AGL_THRESHOLD_M = 10.0 m` is the right number for a real Mi-24P on a real
  ramp/taxi profile.** It is marked `status: uncalibrated` in `defaults.toml` on purpose — the
  fixtures only prove the gate fires at the threshold it's given, not that the threshold is
  correct for genuine low-level/NOE flight vs. sitting on the ramp.
- **Whether the look-command refusal ("Unable, on the ground.") reads naturally in the cockpit**,
  spoken over the intercom in context, rather than just being the correct string in a test
  assertion.

Both backlog entries carry `#needs-flight` below for exactly this reason — the code is correct and
merged; whether it is *right* in the cockpit is not yet known.

---

### Acceptance Testing Plan: Radio Check / No-Scan-on-Ground (`feature/radio-check`)

**Goal:** confirm the intercom/voice pipeline is actually alive for two new phrases, and that
Petrovich stops scanning (but keeps answering) while on the ground.

**Branch:** `feature/radio-check` (merge pending your approval below) — or, once merged, `main`.

**Prerequisites**
- [ ] Type-checked and importable: `cd body-layer && .venv/bin/mypy src` and
      `cd audio-adapter && .venv/bin/mypy src` — both already confirmed PASS above.
- [ ] Restart `body-layer`'s `logger.py` (`--crew-text --speech-input --speech-audio
      --audio-adapter-url ...`) and `audio-adapter`'s server — both touched by this feature.
- [ ] New tuning key: `belief.crew_console.ON_GROUND_AGL_THRESHOLD_M` (default `10.0` m,
      `status: uncalibrated`) — override via `config/tuning.toml` + `PETROBRAIN_TUNING` if the
      10 m threshold feels wrong on the ramp/during taxi.

**Test Cases**
1. On the ramp, engines off, say "radio check" → hear "Loud and clear." over the intercom.
2. Say "good evening Petrovich" (or morning/day/night, matching actual sim time) → hear
   "Good evening, commander." echoing your own word.
3. On the ground, issue a look command (e.g. "watch nearest" or "scan ahead") →
   "Unable, on the ground."
4. While taxiing/sitting on the ground, confirm no unprompted contact callouts occur (perception
   gated off) even if real contacts are in view.
5. Take off, climb above ~10 m AGL → scanning resumes; contact callouts return to normal.
6. Land (e.g. at a FARP) → scanning stops again (every ground period, not just before first
   takeoff).
7. Say "silence" to go quiet, then say "radio check" → silence ends, "Loud and clear." is heard.

**Edge Cases to Probe**
- Say "good job" or other "good"-starting ordinary chatter → should NOT be misheard as a greeting
  (degrades to no match / normal fallthrough, not a false "Good ..., commander.").
- Say "radio check" immediately after a mission (re)start, before the first telemetry poll lands —
  should still answer normally (refusal mode only applies if the world model fails to load).
- A look command issued in refusal mode (world model not loaded) on the ground — should get the
  fixed refusal line, not "Unable, on the ground." (refusal wins).

**Pass Criteria**
The feature passes if all seven test cases produce the expected result, the two edge cases around
greeting false-triggering do not fire, and no regression is visible in ordinary scan/watch/report
command behaviour while airborne.

**Does the feature pass acceptance testing? (yes / no + details)**
