# Definition of Done: audio-adapter Slice 2 (SPU-8 intercom)

**Branch:** `feature/spu8-intercom`, verified tip `bc10f14bfed2719f77e9607e0d7a6dc758fa4e93` (matches
expected). This worktree's own HEAD landed on `main`/scaffolding as predicted — the branch is
checked out in the main checkout — so it was **not** used for verification. Snapshotted instead via
`git archive feature/spu8-intercom | tar -x -C <scratch>` and ran every check with cwd inside
`<scratch>/aircraft-layer` or `<scratch>/body-layer`, using the main checkout's own
`<subproject>/.venv/bin/{ruff,mypy,pytest}`.

## Provenance note

Architect and Implementer ran on another machine, in a different Claude session, and the branch
was handed over with **no gate having run on it at all**. The first gate run here (mechanical fix
`d3444ff`) found the implementer had never run the suite — a shadowed test helper was breaking 80
pre-existing tests. Worth recording: a cross-machine handoff skipped the step that would have
caught it before it reached Reviewer.

## Mechanical checks (re-run independently from the snapshot)

**aircraft-layer**
- `ruff format --check src tests` — pass (48 files already formatted)
- `ruff check src tests` — pass (all checks passed)
- `mypy src` (`--strict`) — pass (19 source files, no issues)
- `pytest tests -q` — **210 passed** (matches expectation exactly)

**body-layer**
- `ruff format --check src tests` — pass (114 files already formatted)
- `ruff check src tests` — pass (all checks passed)
- `mypy src` (`--strict`) — pass (53 source files, no issues)
- `pytest tests -q` — **1440 passed, 4 xfailed** (matches expectation exactly; `main`'s own
  baseline is 1434/4, so this branch adds 6 net passing tests)

**audio-adapter** — confirmed **zero diff** against the merge base
(`git diff --stat main...feature/spu8-intercom -- audio-adapter` returns nothing), as both the
plan and the implementation log claim. The module-boundary design constraint ("gating capture in
the collector, not downstream") holds literally, not just in spirit.

## Clean tree / staging

Main checkout confirmed clean at session start (`git status` reported clean on
`feature/spu8-intercom`). No further action needed.

## Scope & correctness

- Implementation matches `plans/spu8-intercom/plan.md`'s five stages exactly — confirmed via
  Reviewer round 1's full read (all 5 stages + amendment, every changed file read in full) and
  independently cross-checked against the diff stat here.
- No unplanned scope: `git diff --stat main...feature/spu8-intercom` touches exactly the files the
  plan's "Affected Modules / Files" section names, plus agent-memory/research/plan artifacts.
- No invariants violated: `audio-adapter` untouched (module independence held), no DCS-write path
  added outside the one the plan names (`Export.lua`'s cockpit write, same mechanism BL-6 already
  ships), no omniscience violation (Security's deep analysis confirmed `maybe_apply_on_ground_default`
  reads only the player's own `ownship.alt_agl_m`, nothing it couldn't perceive).

## Testing

- Core logic covered: `test_schema_spu8.py`, `test_audio_sender.py` (gate/volume cases),
  `test_ptt.py` (updated for the new fail-safe-closed default), `test_crew_console.py` (on-ground
  default cases).
- Reviewer empirically disabled four mechanisms (gate check in `_run`, `scale_wav_volume` call,
  on-ground-silent branch, `spu8_gate_open` conjunction) and confirmed each breaks its own test and
  only its own test — not decorative.
- No existing tests broken (both suites pass clean at the counts above; the one existing test whose
  expected payload changed, `test_ptt.py`'s raw-value test, was updated per plan Decision 3's
  documented fail-safe-closed default, not silently left broken).

## Documentation / Reviewer findings

`plans/spu8-intercom/review.md`: **Required Fixes: None** (round 1 and round 2). Three optional
refinements noted (double-encoded gate-open logic, two uncalibrated constants, Stage 5 not wired
into `--console`) — all explicitly non-blocking and tracked, not defects.

## Security

- `plans/spu8-intercom/security-deep-analysis.md`: initial verdict **NEEDS FIXES** — unguarded
  `ValueError` in `scale_wav_volume` could permanently kill the audio playback worker thread while
  the LAN API kept reporting success. Fixed in `f1d39b9` (widened except clause + defense-in-depth
  wrap in `_run`). Reviewer round 2 (`bc10f14`) independently reproduced both guards by reverting
  each and confirming the specific test failure, and re-ran the full three-file-scoped diff clean.
  **Verdict after fix: APPROVED.**
- No `security-plan-review.md` exists for this feature — expected under the current one-pass
  cadence (root `CLAUDE.md` "Agents": Security runs once per whole feature, immediately before
  DoD, not a separate plan-review pass for every feature).

## Performance

`plans/spu8-intercom/performance.md`: **APPROVED — MONITOR.** `scale_wav_volume` measured at
4–8ms for realistic clip lengths, negligible against playback's own multi-second block. The one
un-measurable item — three extra per-frame cockpit reads in `Export.lua` — is reasoned as the same
cost class as the existing, unremarkable PTT read, but explicitly flagged as needing a live sortie
to confirm; carried onto the acceptance card (test 7) rather than blocking the gate.

## Milestone Completion question

Does this change what the next milestone should be, or invalidate a downstream assumption?
**No.** `audio-adapter/ROADMAP.md`'s Slice 3 (inbound speech, "Next priority") already consumes
the collector's served `"intercom"` field verbatim via `DcsPTT.is_down()` — this slice changed only
what that field *means* at the collector (now gated by the real cockpit switches), not how Slice 3
reads it. Slice 3's own live testing will now implicitly respect the SPU-8 gate too, which is a
desirable side effect, not a scope change.

## Verdict

**DoD: PASSED.** Proceeding to acceptance testing — see the acceptance card published below. Not
merging yet per DoD process (merge happens only after the user accepts acceptance testing).

## Acceptance boundary — what fixtures structurally cannot reach

This DoD pass is entirely fixture/snapshot verification: unit tests, a reproduced mechanical check,
and two independent reviewer reconstructions of the exploit/fix. **None of it can observe the real
cockpit.** Specifically out of reach without a flight:

- Whether arg 377/664/457 actually behave as the 2026-10-05 probe recorded, on a sortie that isn't
  the one-time probe itself.
- Whether the ~0.1s animation through intermediate switch values produces an audible glitch/click
  rather than clean silence when a switch is flipped mid-utterance.
- Whether `ON_GROUND_AGL_THRESHOLD_M = 10.0` and `MISSION_START_ICS_DELAY_S = 5.0` read as correct
  in the actual cockpit — both are uncalibrated guesses, not measurements.
- Whether the three added per-frame cockpit reads produce any felt stutter — no in-DCS profiler
  exists; Performance's own verdict says only a pilot can answer this.
- Whether the cross-seat cockpit write (co-pilot ICS) still works reliably when fired automatically
  and unattended, rather than via the one manual probe script that demonstrated it once.

A fixture pass here is not a flight pass. The acceptance card below is the live-acceptance debt
this gate cannot retire on its own, and per CLAUDE.md's live-acceptance-debt convention it is
tracked in `audio-adapter/ROADMAP.md` until a real sortie clears it — named explicitly, not folded
into a generic "tested" checkbox.
