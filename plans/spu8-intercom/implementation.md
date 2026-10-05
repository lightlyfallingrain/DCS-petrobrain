### Implementation Summary

All five stages of `plans/spu8-intercom/plan.md` implemented (code + tests + Export.lua). **Checks
(ruff format/check, mypy --strict, pytest) have NOT been run yet** — the user interrupted before a
fresh `.venv` could be created in either subproject to run them (this worktree had no venv for
either `aircraft-layer` or `body-layer`). The Lua side was syntax-checked (`luac5.1 -p`, passes)
and exercised under a throwaway stub harness (see below); Python code has not been executed at
all, only written against the existing patterns in each file it mirrors. **This must be finished
before the feature is considered done**: create venvs, run format/lint/type/test for both
`aircraft-layer/` and `body-layer/`, and fix whatever those checks surface.

### Files Changed

**aircraft-layer** (Stages 1-4):
- `src/schema/spu8.py` (new) — `Spu8Sample`: raw `net1`/`ics_power`/`vol` plus `net1_on`/
  `ics_power_on`/`gate_open` properties, mirroring `schema/ptt.py`'s raw-plus-decided shape and
  0.5 threshold-not-equality reasoning.
- `src/schema/__init__.py` — re-exports `Spu8Sample`/`Spu8ParseError`.
- `src/collector/cache.py` — `Spu8Cache` (latest-of-one, mirrors `PttCache`) plus `Spu8GateState`
  (a `NamedTuple(gate_open, volume)`) and `Spu8Cache.gate_state()`, fail-safe-closed
  (`gate_open=False, volume=1.0`) when no sample has arrived (plan Decision 3).
- `src/collector/server.py` — `_handle_line` gains a `"net1"`-keyed branch pushing to `Spu8Cache`;
  `CollectorServer` gains an optional `spu8_cache` param (same optional-cache pattern as
  `ptt_cache`); `EXPECTED_EXPORT_VERSION` bumped to `"2026-10-05"`.
- `src/collector/audio_sender.py` — `AudioPlaybackSender` gains an injected
  `gate_state: Callable[[], Spu8GateState] = _always_open` provider, consulted once per queued
  item in `_run`, immediately before `self._player.play(path)`: closed drops silently (no
  special-casing for urgent); open calls `scale_wav_volume(path, state.volume)` first. New module
  function `scale_wav_volume` scales 16-bit PCM in place via stdlib `wave` + `array` (not
  `audioop` — removed in Python 3.13, per the plan's main-loop amendment); a no-op at
  `volume == 1.0`; a non-16-bit-PCM or unreadable file is logged and left unscaled.
- `src/api/server.py` — new `GET /spu8/state` endpoint; `_handle_ptt_state` now takes
  `spu8_cache` too and serves `"intercom": sample.intercom and spu8_gate_open` (fail-safe-closed
  when `spu8_cache.latest() is None`); `"radio"` untouched. `TelemetryAPIServer` gains
  `spu8_cache: Spu8Cache | None = None` (defaults to a fresh empty cache, same pattern as every
  other optional cache here).
- `src/collector/__main__.py` — constructs one `Spu8Cache`, wires it into `CollectorServer`,
  `TelemetryAPIServer`, and `AudioPlaybackSender(gate_state=spu8_cache.gate_state)` (moved the
  `AudioPlaybackSender()` construction down to where the real gate provider is available, removing
  the earlier bare construction).
- `dcs-export/Export.lua` — `push_spu8_state(t)` (args 377/664/457, every-frame-read/send-on-change,
  mirrors `push_ptt_state`), `set_copilot_ics_on()` + a 5s mission-start timer
  (`mission_start_model_t`/`copilot_ics_set`, captured/checked right where `DUMPED_SELF_DATA`'s
  one-shot dump already fires, i.e. the first frame `LoGetSelfData()` succeeds), both reset in
  `LuaExportStop`. `EXPORT_SCRIPT_VERSION` bumped to `"2026-10-05"`.
- Tests: `tests/test_schema_spu8.py` (new — schema, `Spu8Cache`/`gate_state()`, collector routing,
  `/spu8/state` endpoint, mirrors `test_ptt.py`'s structure). `tests/test_ptt.py` updated per the
  plan's flagged risk: the pre-existing `test_serves_the_raw_value_and_both_predicates` now pushes
  an open `Spu8Sample` first (the gate must be open for the old assertion to still hold); added
  `test_intercom_is_gated_closed_with_no_spu8_data`, `test_intercom_is_gated_closed_when_either_
  spu8_switch_is_off`, `test_radio_is_not_gated_by_spu8`. `tests/test_audio_sender.py` — new gate/
  volume test section: gate closed drops (incl. urgent), gate open plays, default-provider
  backward compatibility, `scale_wav_volume` unit tests (scales, clamps, no-op at full volume,
  non-16-bit-PCM left alone, malformed file left alone), and one end-to-end test through `_run`.

**audio-adapter**: no changes, as the plan specifies (`DcsPTT.is_down()` already reads the served
`"intercom"` field verbatim).

**body-layer** (Stage 5):
- `src/belief/crew_console.py` — `ON_GROUND_AGL_THRESHOLD_M: Final[float] = 10.0` (module-level
  constant, flagged uncalibrated, same debt class as `mission_phase.WAYPOINT_CAPTURE_RADIUS_M`);
  `CrewConsole._on_ground_default_applied: bool` (new one-shot field, same `field(default=...,
  repr=False)` pattern as `silenced`); `CrewConsole.maybe_apply_on_ground_default(ownship:
  OwnshipState) -> None` — sets `self.silenced = True` directly (not through `_handle_silence`,
  so no acknowledgement is spoken) when `ownship.alt_agl_m <= ON_GROUND_AGL_THRESHOLD_M` on its
  first-ever call; the latch is set on that first call regardless of outcome. Imports
  `perception.source.OwnshipState`.
- `src/logger.py` — `_run_crew_text_poll_loop` calls `crew_console.maybe_apply_on_ground_default
  (runner.last_ownship_state)` (guarded on `is not None`) right after `runner.run_once()`
  succeeds, inside the existing `if runner.last_t_sim is not None:` block, and before
  `crew_console.drain_events(...)` — per the plan's ordering requirement.
- Tests: `tests/test_crew_console.py` — new section (`_ownship` helper plus six tests): on-ground
  applies, airborne does not, no acknowledgement is spoken, one-shot (does not re-silence after a
  command un-silences it), one-shot latches on an airborne first call too (no retroactive apply
  once grounded later), and the locked end-condition (a command ends it; a drained callout stays
  suppressed in the meantime — reusing the existing `silenced` suppression path, no new logic).

### Tests Added

See the per-file lists above. Summary of new/changed test functions:

- `test_schema_spu8.py`: `TestSpu8Sample` (parse, gate conjunction, threshold-not-equality, parse
  errors, `to_api_dict`), `TestSpu8Cache` (empty, latest-of-one, `gate_state()` fail-safe-closed
  and reflecting-latest), `TestCollectorRouting` (net1 line reaches cache, routed ahead of
  telemetry fallthrough, dropped cleanly with no cache wired, malformed line dropped),
  `TestSpu8Endpoint` (`null` before first line, serves raw+decided fields).
- `test_ptt.py`: `test_intercom_is_gated_closed_with_no_spu8_data`,
  `test_serves_the_raw_value_and_both_predicates` (updated to push an open `Spu8Sample` first),
  `test_intercom_is_gated_closed_when_either_spu8_switch_is_off`, `test_radio_is_not_gated_by_spu8`.
- `test_audio_sender.py`: `test_gate_closed_drops_the_queued_line_without_playing`,
  `test_gate_open_plays_the_queued_line`, `test_gate_closed_drops_the_line_even_when_urgent`,
  `test_default_gate_state_is_always_open_full_volume`,
  `test_scale_wav_volume_scales_16bit_pcm_samples`, `test_scale_wav_volume_clamps_to_int16_range`,
  `test_scale_wav_volume_is_a_no_op_at_full_volume`,
  `test_scale_wav_volume_plays_unscaled_for_non_16bit_pcm`,
  `test_scale_wav_volume_handles_a_malformed_file`, `test_run_applies_volume_scaling_before_
  playback`.
- `test_crew_console.py`: `test_on_ground_at_mission_start_applies_silent_mode`,
  `test_airborne_at_mission_start_does_not_apply_silent_mode`,
  `test_on_ground_default_does_not_speak_an_acknowledgement`,
  `test_on_ground_default_is_evaluated_only_once`,
  `test_airborne_first_call_latches_even_though_later_on_ground`,
  `test_on_ground_default_ends_only_via_a_command_not_by_leaving_the_ground`.

### Checks

**NOT RUN — task was interrupted before a venv existed in either subproject in this worktree.**
Next step before this can be called done:

```sh
cd aircraft-layer && python3 -m venv .venv && .venv/bin/python -m pip install -e . \
  && .venv/bin/python -m pip install pytest ruff mypy \
  && .venv/bin/python -m ruff format --check src tests \
  && .venv/bin/python -m ruff check src tests \
  && .venv/bin/python -m mypy src \
  && .venv/bin/python -m pytest tests -q

cd ../body-layer && python3 -m venv .venv && .venv/bin/python -m pip install -e . \
  && .venv/bin/python -m pip install pytest ruff mypy \
  && .venv/bin/python -m ruff format --check src tests \
  && .venv/bin/python -m ruff check src tests \
  && (cd . && PYTHONPATH=src:../world-model/src .venv/bin/python -m mypy src) \
  && .venv/bin/python -m pytest tests -q
```

(body-layer needs `numpy`/`pyproj` transitively via the world-model seam — declared in its own
`pyproject.toml`; mypy must run with `cd body-layer` per that subproject's own CLAUDE.md note on
CWD-only config discovery.)

- `ruff format --check`: not run
- `ruff check`: not run
- `mypy --strict`: not run
- `pytest -q`: not run

### Notable Discoveries

- **Pre-existing latent bug in `Export.lua`, found and fixed while building/stub-testing Stage
  4's restart-reset behaviour.** `last_export_t` (the 5 Hz export throttle's own state) was never
  reset in `LuaExportStop`. DCS's model clock resets on a mission restart, but `last_export_t`
  didn't, so immediately after a restart `t - last_export_t < EXPORT_INTERVAL_S` compared a
  near-zero `t` against the *previous* sortie's last export time and stayed true — suspending the
  entire `self_data` branch (telemetry, world-objects, indication/wheel polls, **and** this
  stage's own `mission_start_model_t` capture) for as long as the previous sortie had run. This
  directly broke the plan's own stated Stage 4 guarantee ("a mission restart re-triggers the
  5-second wait"), and is strictly broader than this feature — it would have delayed telemetry
  resumption after *any* mission restart, pre-dating this plan entirely. Fixed with a one-line
  `last_export_t = -1` reset in `LuaExportStop`, mirroring `pending_release_t`'s existing reset.
  Caught by writing a throwaway stub Lua 5.1 harness (fake `GetDevice`/`LoGetModelTime`/
  `socket.core`, not DCS — not committed, lived at
  `/tmp/.../scratchpad/spu8_harness.lua` this session) that drove `LuaExportStart` →
  `LuaExportAfterNextFrame` × N → `LuaExportStop` → `LuaExportStart` again and asserted the 5s
  ICS-ON write re-fires after a simulated restart; it failed before the fix (`ICS-ON clicks
  recorded = 1`, expected 2) and passed after. `luac5.1 -p` alone could not have caught this (it's
  a control-flow/state bug, not a syntax error) — same class of gap the file's own comment on the
  `push_ptt_state`-defined-above-`safe_call` incident already documents.
- The stub harness also exercised Stage 1's on-change SPU-8 telemetry push (one line on the
  initial read, none while unchanged across several 0.2s frames, exactly one new line on a NET-1
  flip, carrying the new value) — all passed without needing further changes.
- `schema/__init__.py`'s `__all__` list omits `PttSample`/`PttParseError` even though they're
  imported into the module namespace (pre-existing, unrelated to this feature) — `Spu8Sample`/
  `Spu8ParseError` were added to `__all__` per the plan's explicit "re-export" instruction, so
  `from schema import *` now differs slightly between the two in behavior (ptt not exported via
  star-import, spu8 is). Not fixed — out of scope, flagging only.

## Follow-up: Security change request fix (2026-10-05)

Security deep analysis (`plans/spu8-intercom/security-deep-analysis.md`, commit `5767168`) found
`scale_wav_volume` could raise an uncaught `ValueError` from a truncated/malformed WAV, killing the
`AudioPlaybackSender` worker thread permanently and silently — `POST /audio/play` keeps answering
`200 {"ok": true}` forever after, with no signal anywhere that audio is dead for the rest of the
sortie. Only reachable when `volume != 1.0`, i.e. the normal case this slice exists to create.

### Root cause

`reader.readframes(params.nframes)` does not raise when a WAV's declared `nframes` exceeds the
actual file size — it silently returns however many bytes are actually present. If that count is
odd (a truncated `data` chunk), the following `array("h").frombytes(raw_frames)` call raises
`ValueError: bytes length not a multiple of item size`. That call sat **outside**
`scale_wav_volume`'s existing `except (wave.Error, OSError, EOFError)` block, and `_run()`'s worker
loop wrapped only `self._player.play(path)`, not the `scale_wav_volume(...)` call two lines above
— so nothing caught it.

### Files Changed
- `aircraft-layer/src/collector/audio_sender.py`:
  - `scale_wav_volume` — widened the existing `try` block to also cover the `array("h")`
    construction/`frombytes` step, and added `ValueError` to the caught exception tuple. Same
    posture the function already uses for its other malformed-input cases: log and return,
    playing the file unscaled rather than guessing. No other change to the function's shape
    (Performance's ~1.8ms/s-of-audio measurement stands).
  - `_run()` — wrapped the `scale_wav_volume(...)` call in its own `try`/`except Exception`,
    logging and falling through to play the file unscaled, the same defensive posture
    `self._player.play` already has two lines below. This is independent defense-in-depth: a
    future unguarded parse path inside `scale_wav_volume` must not be able to kill the worker
    thread again.
- `aircraft-layer/tests/test_audio_sender.py` — two new tests (see below).

### Tests Added
- `test_scale_wav_volume_handles_truncated_odd_length_pcm` — builds a WAV via the stdlib `wave`
  writer (10 int16 samples = 20 bytes of PCM data), then truncates the file to keep only 15
  (odd) bytes of that data chunk while leaving the header's declared `nframes` unchanged —
  reproducing Security's crafted-WAV shape exactly (`wave.open` parses cleanly, `readframes`
  returns the truncated bytes without raising, `array("h").frombytes()` raises on the odd byte
  count). Asserts `scale_wav_volume` does not raise and leaves the file unchanged (played
  unscaled). Covers the parse-fix half of the required fix — the existing
  `test_scale_wav_volume_handles_a_malformed_file` only exercises a file that fails at
  `wave.open` itself and never reaches this line.
- `test_run_survives_scale_wav_volume_raising` — monkeypatches the module-level
  `scale_wav_volume` to raise `ValueError` on its first call only (falling through to the real
  implementation on the second), then confirms the worker thread processes *both* queued items
  rather than dying on the first. Covers the call-site guard's own claim, independent of the
  parse fix above.

**Verified non-decorative by reverting each guard in turn** (per dispatch instructions):
- Reverting only the `ValueError` addition to `scale_wav_volume`'s `except` tuple (leaving the
  `_run()` call-site wrap in place) made `test_scale_wav_volume_handles_truncated_odd_length_pcm`
  fail with an uncaught `ValueError` at the `frombytes` line; `test_run_survives_scale_wav_volume_
  raising` still passed (the call-site guard catches it independently).
- Reverting only the `_run()` call-site `try`/`except` around `scale_wav_volume(...)` (leaving the
  parse fix in place) made `test_run_survives_scale_wav_volume_raising` fail — the worker thread
  died on the first raise, the second queued item was never played, with the raised `ValueError`
  visible in the thread-exception traceback; `test_scale_wav_volume_handles_truncated_odd_length_
  pcm` still passed.

Both guards restored after verification; full suite re-run clean.

### Checks
(aircraft-layer only — body-layer, audio-adapter, and the Export.lua work were untouched by this
fix and already approved by Reviewer/Performance)
- `ruff format --check src tests`: pass (48 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (`--strict`): pass (19 source files, no issues)
- `pytest tests -q`: pass — **210 passed** (baseline 208 + 2 new)

### Verification environment note
This fix was implemented from an isolated snapshot per `AGENTS.md` rule 4: the worktree's own
branch (`worktree-agent-a90159e47edafa8cd`) was unrelated (terrain/X-B29 work), so a new local
branch `fix/spu8-wav-decode-guard` was created directly at the expected tip
`5767168` inside this worktree (`git checkout -b fix/spu8-wav-decode-guard 5767168`), confirmed
byte-identical to a `git archive` snapshot of `feature/spu8-intercom` before any edits, then
committed. Checks were run against the main checkout's `aircraft-layer/.venv` (`ruff`/`mypy`/
`pytest` binaries), executed with `cwd` inside this worktree's own `aircraft-layer/`.
