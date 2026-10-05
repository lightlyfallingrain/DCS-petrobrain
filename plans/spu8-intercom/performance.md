### Performance Review

Reviewed at `feature/spu8-intercom` tip `20b555bccd888c16db4c8536da5df81535f297a2` (verified via
`git archive feature/spu8-intercom | tar -x` into an isolated snapshot — the worktree itself landed
on `main` as expected since the branch is checked out in the main checkout). All commands below ran
with cwd inside the snapshot's `aircraft-layer/` or `body-layer/`, using the main checkout's own
`<subproject>/.venv/bin/python3` (Python 3.14.7).

Baseline (Reviewer, same snapshot): aircraft-layer 208 passed; body-layer 1440 passed / 4 xfailed;
ruff + `mypy --strict` clean in both.

### Findings

#### Export.lua: `push_spu8_state` reads 3 cockpit args every frame, unthrottled
- **Location:** `aircraft-layer/dcs-export/Export.lua`, `push_spu8_state` (args 377/664/457),
  called from `LuaExportAfterNextFrame` ahead of the 5 Hz export throttle — same position as the
  pre-existing `push_ptt_state` (arg 738).
- **Risk:** This runs on DCS's own render/sim thread, every frame (confirmed by this file's own
  `LuaExportActivityNextEvent`/`LuaExportAfterNextFrame` instrumentation: the latter fires every
  ~8ms regardless of the 5 Hz throttle). Adding 3 more `GetDevice(0):get_argument_value()` +
  `safe_call`/`pcall` pairs per frame on top of the 1 that `push_ptt_state` already does is the
  right place to worry, given this project's own measured finding that a 24–26ms bridge call
  (`land.getHeight`) was felt by the pilot as a stutter.
- **Assessment (estimated, not measured):** `get_argument_value` is a direct mainpanel-device
  argument read — a cheap table/field lookup, not a raycast or terrain query — and is the exact
  same call `push_ptt_state` already makes every frame today without a reported stutter. Going
  from 1 to 4 such calls plus `pcall` overhead per frame is the same cost *class*, not a new one,
  and `pcall` itself is cheap in LuaJIT/Lua 5.1-class interpreters for the non-error path. I cannot
  bound this in milliseconds without an in-DCS probe (no Lua profiler available in this
  environment), but there is no credible mechanism here for anything near the
  land.getHeight finding's cost.
- **Action:** MONITOR. If a future flight test reports any stutter after this change, this is the
  first place to instrument with the same frame-time logging `Export.lua` already uses elsewhere
  (`debug_log`/`ACTIVITY_LOG_LIMIT`-style bounded sampling) — not something to gate this merge on.
  Worth naming on the acceptance card: "confirm no added stutter in a live sortie", since only a
  flight can give that number.

#### Export.lua: mission-start co-pilot ICS write
- **Location:** `set_copilot_ics_on`, gated by `copilot_ics_set` one-shot latch, reset in
  `LuaExportStop`.
- **Risk:** None credible — fires at most once per sortie (5 s after the first successful
  `LoGetSelfData()` frame), and the latch is reset correctly on mission restart so it cannot
  double-fire within a session or silently skip a restart.
- **Action:** NONE.

#### `scale_wav_volume` (audio-adapter collector worker)
- **Location:** `aircraft-layer/src/collector/audio_sender.py::scale_wav_volume`, called once per
  queued utterance from `AudioPlaybackSender._run` (the dedicated worker thread, not the HTTP
  request thread — already off the main/request path).
- **Risk:** Per-sample pure-Python `array('h')` arithmetic over a WAV is the shape that gets
  expensive; this project's prompt specifically flagged it because urgent lines interrupt and
  re-queue, so latency here is felt as added silence before audio starts.
- **Measured** (synthesized 22050 Hz, 16-bit mono WAVs, `aircraft-layer/.venv/bin/python3`,
  Python 3.14.7, `scale_wav_volume(path, 0.5)`):

  | clip length | samples | measured time |
  |---|---|---|
  | 2 s | 44,100 | 4.08 ms |
  | 4 s | 88,200 | 7.68 ms |
  | 8 s | 176,400 | 14.94 ms |

  Scales linearly at ~1.8 ms per second of audio. A realistic Petrovich callout (a few seconds)
  adds **4–8 ms** to time-to-first-audio. `volume == 1.0` (gate open, knob at full — the common
  case) short-circuits before touching the file at all, so this cost is only paid when the knob is
  actually turned down. This runs after the gate/volume check and before `self._player.play(path)`,
  which itself blocks for the clip's own multi-second duration — a single-digit millisecond scaling
  cost is not perceptible against that, and is paid once per utterance on a background thread, not
  per sample-tick or per HTTP request.
- **Action:** NONE. Clean, measured, no credible risk at any realistic clip length. (It would take
  a multi-minute WAV, which this project never produces, before this approached anything felt as a
  delay.)

#### body-layer: `maybe_apply_on_ground_default`
- **Location:** `body-layer/src/belief/crew_console.py::CrewConsole.maybe_apply_on_ground_default`,
  called every poll of the crew-text loop.
- **Risk:** None — read and confirmed O(1): a boolean-latch check (`_on_ground_default_applied`),
  then at most one float comparison against `ON_GROUND_AGL_THRESHOLD_M`. Evaluates and latches on
  its first call ever, regardless of outcome, so every subsequent poll for the rest of the sortie
  is a single `if self._on_ground_default_applied: return` — cheaper than the AGL comparison it
  guards.
- **Action:** NONE.

#### `Spu8Cache` / `GET /spu8/state`
- **Location:** `aircraft-layer/src/collector/cache.py::Spu8Cache`,
  `aircraft-layer/src/api/server.py::_handle_spu8_state`.
- **Risk:** None — identical "latest of one" shape to the pre-existing `PttCache`/
  `TelemetryCache`/etc.: `push`/`latest` on a single `Spu8Sample | None` slot, no allocation beyond
  the sample itself, no iteration. `gate_state()` adds one more attribute read and a `NamedTuple`
  construction on the fail-safe path — negligible, and only called once per queued audio item (the
  worker thread's own per-item rate), not per frame or per request.
- **Action:** NONE.

### Verdict
APPROVED — MONITOR

One item carries forward: whether `push_spu8_state`'s added per-frame cockpit reads are
perceptible in DCS's own frame — reasoned here as the same cost class as the existing, unremarkable
`push_ptt_state`, but not something this review can put a millisecond number on without a live
in-DCS probe. Recommend adding "confirm no added stutter in a live sortie, same test as the PTT
trigger" to the acceptance card rather than blocking on it — everything else in this feature is
either measured clean (`scale_wav_volume`) or trivially O(1) and confirmed by reading the code
(`maybe_apply_on_ground_default`, `Spu8Cache`, the mission-start write's one-shot latch).
