# Acceptance card source: `feature/radio-check` (BL-B82 + BL-B81)

Published card: https://claude.ai/artifact/QxCKq1kgUVKZnG1bfxzd8t

DoD passed on `feature/radio-check` at merge commit `92ae5b3cbee63548fa49344d171296ff3aca40b8`
(`main`@`d1126570612b29379b50c5c7bda32b123fa250a3` + this branch). Mechanical checks, Reviewer,
Performance Reviewer, and Security all APPROVED — see `plans/radio-check/{review,
performance-review,security-deep-analysis,dod-check}.md`.

**Not yet verified: anything requiring a live DCS session or real speech over the intercom.** Both
backlog entries (`BL-B81`, `BL-B82`) are tagged `#needs-flight` for this reason — merge is not
blocked on it (project policy: live acceptance happens in bursts and does not gate the branch).

Every command/utterance below was actually run against this branch's code before being written
here (not reasoned from reading the source):

- `match_transcript("radio check")` → `token='radio_check', match_ratio=1.0`
- `match_transcript("good morning petrovich")` → `token='greeting', slots={'time_of_day':
  'morning'}` (same for day/evening/night)
- `match_transcript("good job keeping that altitude")` → `token=None` — does **not** false-fire as
  a greeting
- Fresh `CrewConsole(store=ContactStore())`: `on_ground == True` by default;
  `handle_command("radio_check", ...)` → `["Loud and clear."]`;
  `handle_command("watch_nearest", ...)` → `["Unable, on the ground."]`;
  `handle_command("greeting", slots={"time_of_day": "evening"})` → `["Good evening, commander."]`
- Setting `silenced = True` then dispatching `radio_check` clears `silenced` and still answers
  `["Loud and clear."]`
- Switching `on_ground = False`, `watch_nearest` on an empty store answers `["no contact to
  watch"]` (not the refusal line) — confirms the gate is specifically the on-ground branch, not a
  general breakage

## What needs restarting

- `body-layer`'s `logger.py` (poll-loop gating + new dispatch tokens)
- `audio-adapter`'s server (new vocabulary entries + matcher branch)

## Branch

`feature/radio-check` — not yet merged to `main` as of this card (merge is not blocked on the
sortie below; your checkout is yours to park). Checkout:

```sh
git checkout feature/radio-check
```

## Run commands (body-layer, from `body-layer/`)

```sh
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
  --aircraft-layer-url http://<aircraft-layer-host>:7791 \
  --theatre <TheatreName> --world-model-db <path-to-region.sqlite> \
  --crew-text --speech-input --speech-audio --audio-adapter-url http://<mac-ip>:7795
```

## Run commands (audio-adapter, from `audio-adapter/`)

```sh
PYTHONPATH=src .venv/bin/python -m audio_adapter --host 0.0.0.0 --whisper-model /path/to/ggml-small.en.bin
```

Both command skeletons are this project's own documented run commands (`body-layer/CLAUDE.md`,
`audio-adapter/CLAUDE.md`) with the feature's required flags added; the placeholders
(`<aircraft-layer-host>`, `<TheatreName>`, `<path-to-region.sqlite>`, `<mac-ip>`,
`/path/to/ggml-small.en.bin`) are this user's own setup values, not newly invented — **UNVERIFIED
end-to-end** (needs the Windows box + DCS + a real intercom).

## New tuning key

`belief.crew_console.ON_GROUND_AGL_THRESHOLD_M` — default `10.0` m, `status: uncalibrated`. If the
no-scan-on-ground trigger feels early or late relative to actual ground effect/rotor downwash,
this is the value to adjust (`config/tuning.toml` + `PETROBRAIN_TUNING=config/tuning.toml`).

## Test cases (see the published card for the cockpit-facing version)

1. Ramp, engines off: "radio check" → "Loud and clear."
2. "good evening Petrovich" (or morning/day/night matching sim time) → "Good evening, commander."
3. On the ground, a look command ("watch nearest", "scan ahead") → "Unable, on the ground."
4. No unprompted contact callouts while on the ground/taxiing, even with real contacts in view.
5. Climb above ~10 m AGL → scanning resumes.
6. Land (e.g. FARP) → scanning stops again.
7. "silence" then "radio check" → silence ends, "Loud and clear." is heard.

## Edge cases

- "good job" (or similar "good"-leading chatter) must NOT be misheard as a greeting.
- Radio check immediately after a mission (re)start, before first telemetry — should still answer
  normally.
- A look command on the ground while in refusal mode (world model not loaded) — should get the
  fixed refusal line, not "Unable, on the ground."
