# BL-15 Stage 1 acceptance — mission start: clean slate + theatre

**Branch:** `feature/bl15-mission-start` (merging to `main` once this card passes).
**Checkout:** `git checkout feature/bl15-mission-start` — in your own repo root, not a worktree.

## What this tests

A genuine DCS mission (re)start now gives Petrovich a clean slate (no stale contacts, tasks, or
mission memory from the previous mission) and points world-model queries at the theatre the
*running* mission actually is. On failure to resolve the new theatre's store, body-layer refuses
every player command with a fixed line rather than silently running against the wrong terrain
model.

## What this does NOT test (deferred, not a gap)

- **The Mission Interpreter briefing ("briefing ready").** Explored with you 2026-10-19 and
  explicitly deferred as a whole (`plans/bl15-mission-start/explore-notes-stage2.md`) — not part of
  this card.
- **Whether `DCS.getCurrentMission()`/`getMissionName()`/`getMissionFilename()` exist as callable
  Hook-state functions in your DCS build.** The shipped Hook script does not use them — it uses the
  already-proven `net.dostring_in("scripting", "return env.mission.theatre")` bridge instead, the
  same mechanism the F10-commands Hook already uses. Those three functions are a *possible future
  cheaper path*, not something this feature needs; an optional probe for them is at the bottom of
  this card if you want to settle it while you're in there, but it does not gate anything above.

## Setup

**1. Deploy the new Hook script** (once per change — `aircraft-layer/WORKFLOW.md`'s new "Deploy the
mission-start Hook script" section has the full detail):

```
aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua
  -> Saved Games\DCS\Scripts\Hooks\petrobrain-mission-start-hook.lua
```

Restart DCS (not just the mission) after copying — Hook scripts load once at application startup.
No new `autoexec.cfg` line needed if the F10-commands Hook's `net.allow_dostring_in = { "scripting"
}` is already there (it already is on your machine per `stage1-decisions.md`'s security
acceptance).

**2. Start the collector** on the Windows box as usual (`aircraft-layer/WORKFLOW.md`, "Run the
collector").

**3. Start body-layer with `--world-model-dir` added**, pointing at the directory holding your
built theatre stores (`world-model/data/world-model/`, which today holds only `syria-full.sqlite`).
Your existing `run-scripts/run-crew-text.sh` already passes everything else through `$@`, so from
`run-scripts/`:

```sh
./run-crew-text.sh --world-model-dir ../world-model/data/world-model
```

This is new and load-bearing for tests 3 and 4 below — without it, a theatre change always refuses
(there is nowhere to resolve a new store from at all), which would make test 4 pass for the wrong
reason.

## Verified without DCS (run by me, not you — included so you can see the mechanism is real)

```sh
$ cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
    --theatre Syria --world-model-db /tmp/does-not-exist.sqlite \
    --world-model-dir /tmp/does-not-exist-dir --crew-text --print-tuning
tuning: no override file (PETROBRAIN_TUNING unset)
at default (29): ...
```

Confirms `--world-model-dir` is now accepted alongside an explicit `--theatre`/`--world-model-db`
pair with no `parser.error` — the CLI widening this feature needed works. (`--print-tuning` exits
before any world-model file is actually opened, which is why a nonexistent path doesn't error
here — this only proves the flag combination is accepted, not that a real switch works; tests 3/4
below prove that.)

## Tests — do these in the cockpit

### Test 1 — Hook fires once per mission start, and only then

**Do:** start a mission. In `Saved Games\DCS\Logs\dcs.log`, grep for `PetrobrainMissionStart`.
**Expect:** one line reading `onSimulationStart sequence=1 theatre=Syria` (or whatever theatre the
mission is in) at mission start, and nothing else from this Hook until the mission restarts.
**Record:** did `theatre=` show the real theatre name, or `theatre=nil`?

**Do:** pause the mission, then resume it. Grep `dcs.log` again.
**Expect:** no new `PetrobrainMissionStart` line — pause/resume must not look like a restart.
**Record:** confirm no new line appeared. If one did, that's the mid-flight-false-positive risk the
plan named as residual and unverified — tell me immediately, don't wait for the debrief.

**Do:** restart the mission (DCS's own in-sim "Restart Mission"). Grep `dcs.log` again.
**Expect:** a second line, `onSimulationStart sequence=2 theatre=...`.
**Record:** did the sequence number increment? This settles the plan's own open question —
whether single-player restart re-fires `onSimulationStart` at all — which no fixture could answer.

### Test 2 — reset on same-theatre restart

**Do:** fly the Syria mission far enough to get Petrovich to call out at least one contact
(`show`/listen for a callout). Note the contact. Then restart the mission (same mission, so same
theatre).
**Expect:** after the restart, the previously-called-out contact is gone — the next thing Petrovich
reports should be freshly detected, not a stale carry-over. No startup announcement (silence at
reset was your own decision, `stage1-decisions.md` #3).
**Record:** did anything from before the restart survive — an old contact mentioned, a stale "watch"
task still active, an attack-run state referencing a target that no longer exists?

### Test 3 — refusal on an unresolvable theatre

**Do:** from the same running process (don't restart body-layer), switch to a mission in a theatre
with no built store on your Mac (anything other than Syria — Caucasus, Nevada, whatever you have
to hand that isn't Syria). Restart into it (or just start that mission if DCS allows switching
missions without a full relaunch — either way, a fresh `onSimulationStart` with a different
`theatre` is what matters).
**Expect:** *"system error, world model not loaded"* — spoken/printed/overlaid identically on
whatever surface you're using — in response to **every** command you give afterward (F10, voice,
crew-text), not just the first one. Perception should visibly stop (no new contacts called out).
**Record:** did the refusal line match exactly? Did it answer every command, or did some slip
through?

### Test 4 — recovery

**Do:** from the refused state in Test 3, restart back into the Syria mission.
**Expect:** refusal clears, perception resumes, commands work normally again.
**Record:** confirm the recovery, and note how long after the restart it took before commands
stopped being refused.

## Optional — settles a question for later, not required for this merge

If you have a spare few minutes in the same session: deploy the throwaway probe script from
`aircraft-layer/research/2026-10-19-theatre-detection-at-mission-start.md` ("Reproducible Test"
section) instead of (or alongside) the production Hook, start a mission, and send me the
`PetrobrainTheatreProbe` lines from `dcs.log`. This settles whether `DCS.getCurrentMission()` is a
real, callable Hook-state function in your build — useful if we ever want a cheaper theatre read
than the bridge call, but nothing above depends on the answer. Delete the probe script afterward
(it's throwaway, same discipline as every other probe in this codebase).

## Bring back

- Test 1: did the sequence number behave as described above (fires once per genuine start/restart,
  never on pause/resume)?
- Test 2: anything that survived a same-theatre restart that shouldn't have?
- Test 3: exact wording you heard/saw for the refusal, and whether it covered every command.
- Test 4: how long recovery took.
- **Anything that surprises you is worth more than anything on this list.**
