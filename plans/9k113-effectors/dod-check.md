# Definition of Done: BL-B66 (9K113 effectors), Stages 1-4 + 4b

**Scoped to tip `510084a325f1454556e8a8d23fb3a0d8d66d056e`** on `feature/9k113-effectors`
(fast-forwarded cleanly from `origin/main` `b2583b84`, no stale-base handling needed — strict
ancestor, clean tree). This verdict describes that commit only; if the branch moves, re-run.

This is a DoD pass for the **built batch** (Stages 1-4 + review-fix + Stage 4b). Stage 5 — the
acceptance sortie — is the user's, has not flown, and is **not blocked on**: per root `CLAUDE.md`'s
"Live verification happens in bursts, and must not gate the work," this batch merges now and the
entry stays `#needs-flight` until a real flight clears it.

## Acceptance boundary — what fixtures structurally cannot reach

Everything below is verified against fakes, fixtures, and static analysis. None of it can tell us:

- **Whether 761 (`CPLR DISTR`) actually drives the coupler/distributor** rather than some other
  switch — it is built, shape-correct, and corroborated by two independent sources (physical
  layout, DCS-BIOS's device-16 mapping), but "corroborated" is not "confirmed." Only a real
  cockpit read while the pilot throws it by hand settles this.
- **Whether the four power-up switches actually animate as the ~3-frame model assumes**, on the
  installed DCS version, today. The 2026-10-17 probe measured this once; an ED patch could have
  moved the argument numbers since (they are positional).
- **Whether "Guidance unit ready" lands at a moment that makes sense to a pilot in the cockpit** —
  the zero-warm-up direction means it fires immediately after the fourth switch write, with no
  lamp or timer gating it. A fixture cannot judge whether that *feels* right against the real
  animation pacing; only a flight can.
- **Whether the voice commands are actually heard correctly against real microphone/radio audio.**
  The matcher-level checks below (run against `match_transcript` directly) confirm the vocabulary
  resolves correctly from clean text; they say nothing about STT accuracy on "weapons armed" vs.
  "weapons safe" spoken over a noisy cockpit audio path.
- **Whether the per-frame slew trace actually separates quantised/lagged/stepped readback** —
  Stage 4b's whole purpose is to answer `BL-B80`'s open question from real hand-slew data; no
  fixture contains that data, by construction.

None of this is a defect in what was built — it is the line past which only a sortie can see, and
the point of naming it is so a fixture-level PASS below is never mistaken for a flight-level one.

## Mechanical checks — all re-run directly, not taken on report

| Check | aircraft-layer | body-layer | audio-adapter |
|---|---|---|---|
| `ruff format --check` | PASS (69 files) | PASS (160 files) | PASS (31 files) |
| `ruff check` | PASS | PASS | PASS |
| `mypy --strict` (from inside subproject) | PASS (26 files) | PASS (70 files) | PASS (16 files) |
| `pytest` | PASS — 409 passed | PASS — 2401 passed, 4 xfailed | PASS — 346 passed, 2 skipped |

All four counts match `implementation.md`'s own claims and the Reviewer's re-review exactly.
`.venv`s were built fresh in this worktree (worktrees carry no gitignored content) and tools
(`ruff`/`mypy`/`pytest`) installed to match the main checkout's versions.

- `luac5.1 -p Export.lua`: syntax PASS.
- `luac5.1 -l -p Export.lua` GETGLOBAL scan: every global resolves to a real DCS/Lua API or
  stdlib name (`GetDevice`, `safe_call`, `pcall`, `io`, `lfs`, `math`, `string`, `table`,
  `tostring`, `type`, `LoGet*`, `require`, `os`, `pairs`, `tonumber`, plus the `DUMPED_*` debug
  flags) — none of the new Stage 1/4b helpers leak as a global. Confirmed independently, not taken
  on the Reviewer's report.
- `test_tuning_defaults_toml.py`: PASS — `config/defaults.toml` is not stale against `tuning.py`'s
  declarations.
- Rendered `GUIDANCE_UNIT_SWITCH_DELAY_S` entry in `config/defaults.toml`: checked directly (not
  the source `#:` comment) — first sentence intact, status/range/source lines correct.
- `grep -rn "TODO\|FIXME\|XXX"` across every touched `aircraft-layer/src`, `Export.lua`,
  `body-layer/src/belief/{sight_effector,crew_console}.py`, `body-layer/src/{logger,sight_trace_writer}.py`,
  `audio-adapter/src/vocabulary.py`: zero hits.
- `grep -n "print("` across the new modules: one hit, `sight_trace_writer.py:114`, inside `_fail` —
  a one-time stderr notice mirroring `DetectionTraceWriter._fail`'s precedent (disable-after-first-
  error, not a debug leftover).
- `git status --porcelain`: clean. All 51 files from the fast-forward are already committed; no
  untracked/unstaged content.

## Voice vocabulary — every spoken form run through the real matcher

Per this role's own standing lesson (`.claude/agent-memory/dod/feedback_run_the_card_utterances_through_the_matcher.md`),
ran the actual commands through `command_matcher.match_transcript` on this tip rather than trusting
the plan/review's account:

```
'observ on'                   -> observ_on        verb_anchored=True  ambiguous=False
'observ off'                  -> observ_off       verb_anchored=True  ambiguous=False
'weapons armed'                -> weapons_armed    verb_anchored=True  ambiguous=False
'weapons safe'                 -> weapons_safe     verb_anchored=True  ambiguous=False
'engage'                       -> engage           verb_anchored=True  ambiguous=False
'the tanks are on the ridge'   -> None             verb_anchored=True  ambiguous=False  (correctly rejected)
```

All resolve exactly as the plan/review claim, including the measured "weapons" false-anchor case
(`verb_anchored=True` on the adversarial sentence, but `token=None` — the phrase-sequence score
still rejects it). No wake-word prefix needed or used for any of these — confirmed directly, not
assumed (`feedback_voice_card_never_prefix_a_command_with_the_wake_word.md`).

## Scope & correctness

- Implementation matches `plans/9k113-effectors/plan.md`'s narrowed scope (text above the `---`
  divider) exactly: cockpit-action channel, four-switch power-up, OBSERV gating, weapons safety
  bar, Stage 4b slew telemetry. No unplanned scope found.
- `aircraft-layer/CLAUDE.md`'s "no general-purpose remote-exec surface" invariant is **knowingly
  overridden**, not silently violated: the override is named in the plan (Decision 4), in
  `aircraft-layer/CLAUDE.md`'s own "What this is" section, and in security memory
  (`project_cockpit_write_vocabulary_invariant.md`). The security plan review's REJECTED verdict on
  this point is correctly not re-litigated by the deep analysis or by this pass.
- `GuidanceUnitState` has exactly one construction site (checked by the construction-site grep
  tests, which this pass read rather than re-derived — mechanical regex check, low false-guard
  risk) — the plan's own named risk (a second construction site added under time pressure) did not
  materialize.
- All new files are committed (confirmed via the fast-forward diff and `git status --porcelain`
  above).

## Testing

- Core logic (the sequencer, readiness predicate, OBSERV/weapons writes, slew trace writer) is
  covered by unit tests against fakes.
- The poll-loop **wiring** — the gap the Reviewer's first pass found and required a fix for — is
  now covered and confirmed by mutation (both reviewer mutations re-run independently by this
  pass's predecessor the Reviewer, not re-mutated again here since the Reviewer's re-review already
  did so twice independently of the implementer's own claim).
- No existing test was broken: all four subprojects' full suites are green, matching pre-feature
  baselines in count where comparable (body-layer's own review re-ran the identical mutations and
  got identical results).

## Documentation

- Reviewer's one required fix (poll-loop wiring test coverage) is resolved and independently
  re-confirmed in the re-review — not merely claimed.
- Non-obvious behaviour is explained in-code (`sight_effector.py`'s docstrings naming calibration
  sources) and in `notes/` (see Knowledge Harvest below).

## Security

- `plans/9k113-effectors/security-plan-review.md`: **REJECTED** (missing allow-list on
  `cockpit_switch`) — **user explicitly overrode this**, recorded in the plan (Decision 4),
  `aircraft-layer/CLAUDE.md`, and security agent memory. Not an outstanding gap; a recorded
  decision.
- `plans/9k113-effectors/security-review.md` (deep analysis): **APPROVED**. One low/low finding
  (unbounded `Content-Length` read, pre-existing shape extended to a fifth endpoint) filed as
  `AC-B11`, not blocking.

## Performance

`plans/9k113-effectors/performance-review.md`: **APPROVED — MONITOR**. The one flagged item
(`push_cockpit_switch_state`'s 8 unconditional per-frame reads, tripling the existing
ptt+SPU-8 unconditional-read count to 12) is judged qualitatively safe at this scale and not a
regression of a new pattern — it extends a shape that has shipped twice before without incident.
No action required now; a mitigation (cache one `GetDevice(0)` handle per frame) is named for if
the pattern keeps growing.

## Milestone completion question

**Does this batch change what the next milestone should be, or invalidate a downstream
assumption?** Yes, in one specific way: `BL-B80` (the slew loop) now inherits Stage 4b's per-frame
logging and the ~2-minute hand-slew data as a head start on its own "one more probe run" hard
dependency — if that data cleanly separates quantised/lagged/stepped readback, `BL-B80`'s own
probe requirement is satisfied for free by this batch's sortie once it flies. `BL-B67` (the ATGM
run) now has the guidance-unit power-up, OBSERV, and safety bar as settled, built facilities
rather than open questions — its own remaining work narrows to the launch-station selector and the
ARMED check, both of which can now reuse the `cockpit_switch` channel this batch made general and
reusable, rather than inventing a new one.

## Recurring-fix pattern surfaced

The Reviewer's one required fix (poll-loop wiring with zero test coverage at the wiring point,
while the leaf module was thoroughly unit-tested) is the **3rd occurrence** of this exact defect
shape, tracked in `.claude/agent-memory/reviewer/project_terrain_callout_stage5_wiring_gap.md`.
All three occurrences were caught at Reviewer, before reaching DoD — the role sequence working as
intended. Recorded as a DoD-level memory
(`project_untested_wiring_pattern_caught_at_reviewer_not_dod.md`) so a 4th occurrence reaching DoD
undetected would itself be the signal to move this check earlier (e.g. an Architect-time note
naming which test will drive the wiring, not just the unit) rather than only at Reviewer. This is
process debt worth naming, not code debt — the code itself is clean on this entry.

## Verdict

**DoD: PASSED** for Stages 1-4 + 4b, at tip `510084a3`. Stage 5 (acceptance sortie) remains open
and is tracked `#needs-flight` on `body-layer/ROADMAP/BL-B66.md` — not a blocker to merge.

---

# Stage 5 Acceptance Testing Plan — the sortie card

**This section is the draft content for a published test card** (the `test-card` skill should turn
it into an artifact before the user flies it — this markdown is not the deliverable itself, per
root `CLAUDE.md`'s "When acceptance needs the user's own hands, publish a card").

**Goal:** confirm the guidance-unit power-up, OBSERV gating, weapons safety bar, and 9K113 slew
telemetry logging all work against a live DCS session, in one sortie.

**Branch:** `feature/9k113-effectors` — checkout with `git worktree add ../DCS-petrobrain-9k113 feature/9k113-effectors`
(or whatever branch this has merged to by the time the sortie flies — confirm before launching).

## Restarts needed before flying

1. **Deploy `Export.lua`** — copy `aircraft-layer/dcs-export/Export.lua` to
   `Saved Games\DCS\Scripts\Export.lua` on the Windows box (per `aircraft-layer/WORKFLOW.md`'s
   "Deploy Export.lua" section). The version string bumped to `"2026-10-21b"` in this batch —
   **DCS must be restarted** (Export.lua loads once at DCS launch, not per-mission) for the new
   script to take effect. Watch the collector's first log lines after DCS connects for an
   `EXPORT_SCRIPT_VERSION` match, not a mismatch warning.
2. **Restart the collector** (aircraft-layer process) so its own `EXPECTED_EXPORT_VERSION` check
   and the new `/command/cockpit_switch` / `/cockpit_switch/latest` endpoints are live.
3. **Create the slew-debug flag** before launching DCS, if the hand-slew segment (step 6 below)
   is being flown this sortie: `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` (any
   content, even empty) — checked once at Export.lua load, so it must exist before DCS starts.
4. **Restart `logger.py`** (body-layer) with `--crew-text` and, for the slew data,
   `--slew-trace logs/dcs-slew-trace.jsonl` added to the existing command line. `--slew-trace`
   requires `--crew-text` (confirmed in `logger.py`'s own argument validation) and is rejected with
   `--console`.
5. **Restart `audio-adapter`** so it picks up the new `weapons_armed`/`weapons_safe` vocabulary
   entries.

## Flight sequence

1. **Take off.** On the ground→airborne transition, the four power-up switches should move in the
   cockpit (watch the operator panel — devices `WEAP_SYS`/`I9K113`) and "Guidance unit ready."
   should be heard/read exactly once, a few seconds after takeoff (one write per ~1 s, four
   switches).
2. **Say "Observ on" before "Guidance unit ready" is heard.** Expected: "Unable, guidance unit not
   ready." — confirmed to resolve via the real matcher (`observ_on`, verb-anchored, unambiguous)
   above; what this step tests is the readiness *gate*, not recognition.
3. **Say "Observ on" after "Guidance unit ready."** Expected: accepted ("Observ on." spoken), and
   the OBSERV switch (arg 886) should move in the cockpit.
4. **Say "Observ off."** Expected: accepted unconditionally ("Observ off." spoken), one write, no
   gating.
5. **Say "weapons armed", then "engage", then "weapons safe."** Expected: "Weapons armed." /
   attack-run engages / "Weapons safe." — confirm the weapons safety bar (arg 673) actually moves
   in the cockpit both ways by watching the switch directly, not just listening for the callout.
   **Listen for a false "weapons" trigger** on unrelated speech during the flight — this
   vocabulary addition has a measured (not just theoretical) false-anchor collision with "tanks"
   at the matcher's verb-anchor floor (see Notable Discoveries in `implementation.md`); the
   phrase-sequence score should still reject anything that isn't the exact phrase, but this is the
   one thing worth listening for specifically.
6. **Confirm 761 (`CPLR DISTR`) by watching that switch move** during the power-up sequence — this
   argument is still UNVERIFIED (corroborated by two independent sources, not confirmed live). If
   it does *not* move, note which switch (if any) did move instead — that is the one-line fix the
   plan's Risks & Unknowns anticipates.
7. **~2 minutes of hand-slewing the sight in OBSERV** — full left/right, up/down, both slow and
   fast — with the slew-debug flag on (step 3 above) and `--slew-trace` running (step 4). This is
   the data `BL-B80`'s rate-loop needs; there is no pass/fail here beyond "did the log capture
   motion," which the triage step below answers.

## After landing — what to bring back and how to triage it

- Copy `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log` from the Windows box.
- Locate the stamped `--slew-trace` output file (the logger prints the actual resolved path to
  stderr at startup — that line is authoritative).
- Run:
  ```sh
  python3 .claude/skills/sortie-log-triage/scripts/triage.py --slew PATH --body-slew PATH
  ```
  This reports: rows with OBSERV on, the smallest observed non-zero step in args 874/876 (floors
  the deadband `BL-B80` will need), and the rate (deg/s) over the longest monotonic azimuth run.
  Readback lag is *not* computed by this entry (nothing commands the player axis yet) — that is
  expected, not a bug in the triage output.
- Also bring back whatever text/overlay output exists for the spoken lines (there is no dedicated
  speech log unless `--speech-log` was also passed) to confirm "Guidance unit ready."/"Observ
  on."/"Weapons armed." etc. were actually heard, not just logically dispatched.

## Pass criteria

The feature passes if: the four-switch power-up fires once per mission on the real takeoff edge
and ends in exactly one "Guidance unit ready"; "Observ on" is refused before that callout and
accepted after; "Observ off" always succeeds; the weapons safety bar moves in the cockpit on both
"weapons armed" and "weapons safe" with no false triggers heard; and the slew trace log captures
real motion during the hand-slew segment. 761's identity and any animation-timing surprises are
recorded as findings, not failures — this batch is built for them to be discoverable, not to have
them pre-solved.

**UNVERIFIED by this DoD pass** (needs Windows/live DCS, cannot be run from here): every step in
"Flight sequence" and "After landing" above. Everything in the mechanical-checks section above
*was* executed directly, with real output pasted.
