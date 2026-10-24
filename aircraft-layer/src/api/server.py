"""Mac-facing LAN API for querying the collector's cached telemetry +
world-objects + Petrovich-indication state.

Plan stage 4. Unlike `collector.server.CollectorServer` (loopback-only, the
Export.lua push hop), this server is LAN-reachable by design — it's the hop
the body/brain process, on either Windows or Mac (compute topology note in
`plans/aircraft-layer/plan.md`), polls over the network. Read-only.

- `GET /telemetry/latest` -> the most recent sample as JSON, or JSON `null`
  if the cache is still empty (not an error — Export.lua may not have
  connected/sent anything yet).
- `GET /world_objects/latest` -> the most recent `LoGetWorldObjects` snapshot
  as JSON, or JSON `null` on the same "not an error" basis. Added by
  `plans/pb1-perception-logger/plan.md` stage 3 as body-layer's Tier 3
  fallback data source; same shape/lifecycle as `/telemetry/latest`.
- `GET /petrovich_indication/latest` -> the most recent
  `list_indication(HELPERAI_DEVICE_ID)` sample as JSON (parsed
  `{leaf_name: text}` fields + timestamps), or JSON `null` on the same
  "not an error" basis. Added by `plans/pb1-perception-logger/plan.md`
  stage 4 as `HybridPerceptionSource`'s real detection-existence gate; same
  shape/lifecycle as the other two `/latest` endpoints. Raw parsed text
  only -- no detection/interpretation/association logic here, that is
  body-layer's job (`body-layer/src/perception/association.py`).
- `POST /text/push` -> the aircraft layer's first inbound/write path
  (`plans/dcs-text-panel-output/plan.md`, BL-2.5). Body `{"text": "<string>"}`;
  a non-empty (after `.strip()`) string forwards to
  `collector.text_sender.TextOverlaySender.send_line`, which fires the line at
  the in-cockpit overlay Hook script over loopback UDP, and responds
  `200 {"ok": true}`. `400 {"error": ...}` on a missing/invalid/empty `text`
  field or non-JSON body; `503 {"error": "text push not configured"}` if this
  server was built without a `text_sender` (matching the
  optional-cache-defaults-to-empty pattern below, rather than crashing). This
  endpoint carries opaque display strings only -- no aircraft state, no
  commands, no code -- everything else on this API remains read-only.
- `GET /petrovich_wheel/latest` -> the most recent `list_indication(10)`
  (Petrovich's AI-Wheel state) sample as JSON, or JSON `null` on the same
  "not an error" basis. Added by `plans/bl6-commands-inspect-adapt/plan.md`
  (BL-6) as a live diagnostic for `scan_area`'s `task-status` console
  command; same shape/lifecycle as the other `/latest` endpoints.
- `POST /command/petrovich_search` -> the aircraft layer's second
  inbound/write path (BL-6). Body `{"mode": "forward"|"boresight"}`; a valid
  mode forwards to `collector.command_sender.CommandSender.send_command`,
  which fires the JSON command at `Export.lua`'s new inbound UDP listener
  (driving Petrovich's AI Wheel), and responds `200 {"ok": true}` --
  matching `/text/push`'s "attempted the call" contract exactly: a `200`
  here means the datagram was hand off to the OS, never that Petrovich
  actually searched (that confirmation is `/petrovich_wheel/latest`'s job).
  `400 {"error": ...}` on a missing/invalid `mode` or non-JSON body;
  `503 {"error": "command channel not configured"}` if this server was
  built without a `command_sender`. Unlike `/text/push`, a send failure here
  propagates as `500 {"error": ...}` rather than being swallowed --
  `collector.command_sender.CommandSender.send_command` raises
  `CommandSendError` on a clearly-failed send (see that module's docstring
  for why this write path does not share `/text/push`'s
  never-raises posture).
- `POST /audio/play` -> the aircraft layer's third inbound/write path
  (BL-10 first slice, `plans/tts-voice-output/plan.md`). Body
  `{"audio_b64": "<base64 WAV bytes>", "urgent": bool}`; forwards the
  decoded bytes to `collector.audio_sender.AudioPlaybackSender.play_audio`,
  which plays them through `winsound` on this (Windows) box, and responds
  `200 {"ok": true}` -- same "attempted the call" contract as `/text/push`
  and `/command/petrovich_search`: a `200` means the audio was handed to
  the playback queue, never that it was actually heard. `400 {"error": ...}`
  on a missing/invalid `audio_b64`/`urgent` or non-JSON body; `503
  {"error": "audio playback not configured"}` if this server was built
  without an `audio_sender`. Like `/text/push` (and unlike
  `/command/petrovich_search`), this never propagates a `500` for a
  playback failure -- `AudioPlaybackSender.play_audio` never raises (plan
  Decision 5: audio is best-effort display-equivalent output, not a
  verifiable command).
- `POST /audio/stop` -> the aircraft layer's fourth inbound/write path
  (`plans/inbound-speech/plan.md` Stage 3 follow-up, "stop_talking"'s
  interrupt-only path). No request body is read or required -- forwards
  directly to `collector.audio_sender.AudioPlaybackSender.interrupt`,
  which clears the routine queue and stops in-flight playback without
  enqueueing anything, and responds `200 {"ok": true}`. `503
  {"error": "audio playback not configured"}` if this server was built
  without an `audio_sender`, same as `/audio/play`. Like `/audio/play`,
  this never propagates a `500` -- `AudioPlaybackSender.interrupt` never
  raises (it is `_clear_queue`/`_interrupt_playback`, the same two calls
  `/audio/play`'s own `urgent=True` path already uses, with the enqueue
  dropped). This is a debug/utility tool rather than a crew feature (user
  direction, 2026-09-20): it exists so a stop request can be silent --
  interrupting playback with no new audio to acknowledge it -- rather than
  needing to push an audio line just to reach the interrupt mechanism.

- `GET /f10_commands/poll` -> drains the collector's `F10CommandQueue`
  (`plans/f10-crew-commands/plan.md`) and returns every pending F10
  radio-menu selection as a JSON list, oldest first (`[]` if none pending,
  never `null` -- unlike every `/latest` endpoint above, this response is
  always a list). **Documented exception to every other endpoint's
  idempotent-read contract**: this one mutates collector-local queue state
  on every call, so it assumes exactly one poller (body-layer's
  `--crew-text --f10-commands`) -- a second concurrent poller would
  silently steal commands from the first. The queue defaults to a fresh,
  never-populated one (same optional-cache-defaults-to-empty pattern as
  `world_objects_cache`/`petrovich_indication_cache`/`petrovich_wheel_cache`
  above), so this endpoint always answers `200 []` rather than `503` when
  unconfigured -- there is no live effector here to be "not configured,"
  only an always-valid, possibly-empty queue.

- `GET /ptt/state` -> the pilot's push-to-talk trigger, or `null` before it
  has moved at all (`plans/inbound-speech/plan.md` Stage 5). A pure,
  idempotent read of a *state*, not a queue: the capture process polls it
  tens of times a second and must never consume anything by asking.
  **Since `plans/spu8-intercom/plan.md` Stage 2, the served `"intercom"`
  field is already gated by the SPU-8 switches** (`_handle_ptt_state`
  combines this with `Spu8Cache`) -- see that function's own docstring.
  `"radio"` is untouched.
- `GET /spu8/state` -> the SPU-8 intercom panel (pilot NET-1, co-pilot ICS
  power, volume), or `null` before the first line arrives
  (`plans/spu8-intercom/plan.md` Stage 1). Same shape/lifecycle as
  `/ptt/state`.
- `GET /unit_velocity/latest` -> the most recent `UnitVelocitySnapshot`
  (`plans/movement-detection/plan.md` Stage 1) as JSON, or JSON `null` on
  the same "not an error" basis as every other `/latest` endpoint. A
  **separate endpoint from `/world_objects/latest`, not merged into it**
  (that plan's Decision 2): merging would mean either holding a world-objects
  snapshot back until a matching velocity snapshot arrives, or emitting one
  timestamp for two feeds whose sim-clock stamps genuinely differ (5 Hz vs.
  1 Hz polls) -- silently destroying the provenance the dual-clock schema
  exists to preserve. The join (by `unit_name`, within a skew bound) is
  `perception.motion`'s job on the body-layer side, not this layer's.

- `GET /line_of_sight/latest` -> the most recent `LineOfSightSnapshot`
  (`plans/dcs-driven-los/plan.md`, X-B29) as JSON, or JSON `null` on the
  same "not an error" basis as every other `/latest` endpoint. A separate
  endpoint from `/world_objects/latest`/`/unit_velocity/latest`, same
  "separate feed, separate clock, joined client-side by `unit_name`"
  reasoning as `/unit_velocity/latest`'s own docstring.
- `GET /mission_start/latest` -> the most recent `MissionStartEvent`
  (`plans/bl15-mission-start/plan.md`, BL-15 Stage 1) as JSON, or JSON
  `null` on the same "not an error" basis as every other `/latest`
  endpoint -- no `onSimulationStart` has fired yet this collector
  process's lifetime is the ordinary state at startup, not an error. Body-
  layer polls this and compares `sequence` against the last value it saw
  to detect a genuine mission (re)start; this endpoint does no comparison
  or state of its own, same "this layer only serves, interpretation is
  body-layer's job" split as `/petrovich_indication/latest`.
- `GET /firing/latest` -> `collector.firing_receiver.EmitterTracker.
  snapshot()` as JSON (`plans/emitter-visibility/plan.md` Stage B,
  `AC-B8`) -- `{"dcs_model_time_s", "received_wall_clock_s", "active":
  {unit_name: {"kind", "since_sim", "targets_ownship"}}}`. Unlike every
  `/latest` endpoint above, this is never JSON `null`: an `EmitterTracker`
  with nothing currently firing answers `{"dcs_model_time_s": null,
  "received_wall_clock_s": <float>, "active": {}}` -- there is no
  "cache empty" state distinct from "nothing is firing right now", so the
  response is always a well-formed object. Joined client-side by
  `unit_name`, same convention as `/unit_velocity/latest`/
  `/line_of_sight/latest`.
- `POST /command/look_direction` -> the aircraft layer's fifth
  inbound/write path (`plans/dcs-driven-los/plan.md` SS9). Body
  `{"hour": <int 0..11>, "fov_half_deg": <int 5..180>}`; forwards to
  `collector.command_sender.LookDirectionSender.send_look_direction`,
  which fires the JSON command at the LOS Hook script's own inbound UDP
  listener (not Export.lua's -- see that sender's own docstring for why),
  and responds `200 {"ok": true}` on the same "attempted the call" contract
  as `/command/petrovich_search`. `400 {"error": ...}` on a missing/
  out-of-range `hour`/`fov_half_deg` or non-JSON body; `503
  {"error": "look direction not configured"}` if this server was built
  without a `look_direction_sender`; a send failure propagates as
  `500 {"error": ...}`, same posture as `/command/petrovich_search`
  (a dropped look-direction push is a real coverage gap, not an opaque
  display string to swallow).

- `POST /command/cockpit_switch` -> the aircraft layer's sixth
  inbound/write path (`plans/9k113-effectors/plan.md`, BL-B66 Stage 1),
  **unchanged by Stage 4** (only this endpoint's own *readback* sibling,
  `GET /cockpit_switch/latest`, is removed below). Body `{"device": int,
  "cmd": int, "value": number}`; forwards to `collector.command_sender.
  CommandSender.send_cockpit_switch`, which fires the JSON command at
  `Export.lua`'s inbound UDP listener (writing *any* clickable cockpit
  control -- **no allow-list**, user direction 2026-10-21, see
  `aircraft-layer/CLAUDE.md`'s "What this is" section), and responds
  `200 {"ok": true}` on the same "attempted the call" contract as
  `/command/petrovich_search`. `400 {"error": ...}` on a missing/
  non-integer `device`/`cmd` or a missing/non-finite `value`, or a
  non-JSON body -- shape validation only, never a value/vocabulary check,
  same posture `Export.lua`'s own dispatch takes. `503
  {"error": "cockpit switch channel not configured"}` if this server was
  built without a `command_sender`; a send failure propagates as
  `500 {"error": ...}`, same posture as `/command/petrovich_search` (a
  dropped switch write is a real behavioral gap, not an opaque display
  string to swallow).

- `GET /watched_args/latest` -> the most recent `WatchedArgsState`
  (`plans/effector-sequences/plan.md` Stage 4, replacing the old
  `GET /cockpit_switch/latest`) as JSON, or JSON `null` on the same
  "not an error" basis as every other `/latest` endpoint. The continuous
  cockpit-arg readback -- a small, `polled.toml`-driven set of args
  `Export.lua` polls at its own 5 Hz export tick and sends only on change.
- `POST /command/watch_args` -> installs the set of args the continuous
  feed above should watch (`plans/effector-sequences/plan.md` Stage 4).
  Body `{"watch_id": "<1-16 char [A-Za-z0-9_] string>", "args": [int,
  ...]}`; forwards to `collector.command_sender.CommandSender.
  send_watch_args`, which fires the JSON command at `Export.lua`'s inbound
  UDP listener (replacing the previously-installed set whole, never
  merging), and responds `200 {"ok": true}` on the same "attempted the
  call" contract as `/command/petrovich_search`. `400 {"error": ...}` on
  a missing/malformed `watch_id`, or a missing/non-integer/out-of-range/
  oversized `args` list, or a non-JSON body. `503
  {"error": "watch_args channel not configured"}` if this server was
  built without a `command_sender`; a send failure propagates as
  `500 {"error": ...}`, same posture as `/command/petrovich_search`.
- `POST /query/read_args` -> the aircraft layer's sixth inbound/write path,
  and its first **synchronous** one (`plans/effector-sequences/plan.md`
  Stage 4, S4.2, "readback by need" option B). Body `{"args": [int, ...]}`;
  forwards to `collector.arg_read_broker.ArgReadBroker.read`, which fires
  a one-shot `read_args` command at `Export.lua`'s inbound UDP listener
  and **blocks this HTTP worker thread** waiting for `Export.lua`'s TCP
  reply, up to `collector.arg_read_broker.ARG_READ_TIMEOUT_S` (about one
  DCS frame plus the LAN round trip in the common case) -- unlike every
  other endpoint on this API, a `200` here means the values were actually
  read this call, not merely that a command was handed off. `400
  {"error": ...}` on a missing/invalid `args` list (same shape rules as
  `/command/watch_args`'s own `args`), or a non-JSON body. `503
  {"error": "read_args channel not configured"}` if this server was built
  without an `arg_read_broker`, or `{"error": "too many reads outstanding"}`
  if `collector.arg_read_broker.MAX_OUTSTANDING_READS` concurrent reads are
  already in flight. `504 {"error": ...}` if no reply arrives within the
  timeout (no Export.lua peer connected, or a stalled frame).

- `POST /command/sight_target` -> the aircraft layer's seventh
  inbound/write path (`plans/9k113-sight-pointing/plan.md`, BL-B80 v2).
  Body `{"goal_az_deg": number, "goal_el_deg": number, "goal_rate_az_
  deg_s": number, "goal_rate_el_deg_s": number, "t_sim": number}`;
  forwards to `collector.command_sender.CommandSender.send_sight_target`,
  which fires the JSON command at `Export.lua`'s inbound UDP listener
  (the same listener `/command/cockpit_switch` already targets) -- a
  **persistent** world goal `Export.lua`'s own per-frame servo
  rate-limits toward, not a one-shot write, responding `200 {"ok":
  true}` on the same "attempted the call" contract as `/command/
  cockpit_switch`. `400 {"error": ...}` on a missing/non-finite field or
  a non-JSON body -- shape validation only, every field clamped-checked
  against a generous sane range: `az`/`el` as before (Security plan
  review's non-blocking recommendation), plus `t_sim` itself (**the same
  review's required change**, re-plan v2) -- a non-finite or wildly
  out-of-range `t_sim` would feed `Export.lua`'s own `clamp(t - t_sim, 0,
  cap)` directly, so it is bounded exactly like `az`/`el`/`rate`, never
  left unchecked on the assumption that only `az`/`el` could misbehave.
  `503 {"error": "sight target channel not configured"}` if this server
  was built without a `command_sender`; a send failure propagates as
  `500 {"error": ...}`, same posture as `/command/cockpit_switch`.

- `GET /sight_servo/latest` -> the most recent `SightServoState`
  (`plans/9k113-sight-pointing/plan.md`, BL-B80 v2) as JSON, or JSON
  `null` on the same "not an error" basis as every other `/latest`
  endpoint. `Export.lua`'s own per-frame DCS-slave servo status -- mode,
  setpoint, the mark-derived body direction (or `null` when invalid),
  error, and the stall flag. A **second** feed from `/cockpit_switch/
  latest` (see `schema.sight_servo`'s own "Departure, stated").

A `GET /telemetry/since/{timestamp}` delta-query endpoint was implemented
and then dropped (stage 5): its cursor filtered on receipt time, not
content, so during a paused mission it returned every motionless sample as
"new" -- not a useful "changed" signal, and the body/brain consumer's
polling model doesn't need gap-free history anyway (it can just poll
`/latest` as often as it needs). See `plans/aircraft-layer/plan.md`. The
same reasoning applies to `/world_objects/latest` and
`/petrovich_indication/latest` -- no delta variant for either.

Runs `http.server.ThreadingHTTPServer` (stdlib only, per plan decision 4) in
the same process as `CollectorServer`, sharing one `TelemetryCache`, one
`WorldObjectsCache`, and one `PetrovichIndicationCache` instance — see
`collector.__main__`.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

from collector.arg_read_broker import (
    ArgReadBroker,
    ArgReadBrokerBusy,
    ArgReadTimeout,
)
from collector.audio_sender import AudioPlaybackSender
from collector.cache import (
    F10CommandQueue,
    LineOfSightCache,
    MissionStartCache,
    PetrovichIndicationCache,
    PetrovichWheelCache,
    PttCache,
    SightServoCache,
    Spu8Cache,
    TelemetryCache,
    UnitVelocityCache,
    WatchedArgsCache,
    WorldObjectsCache,
)
from collector.command_sender import (
    CommandSender,
    CommandSendError,
    LookDirectionSender,
    SearchMode,
)
from collector.firing_receiver import EmitterTracker
from collector.text_sender import TextOverlaySender
from schema import MAX_WATCHED_ARG_NUMBER, MAX_WATCHED_ARGS

logger = logging.getLogger(__name__)

#: LAN-facing by design, unlike `collector.server.DEFAULT_HOST`.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7791

_TELEMETRY_LATEST_PATH = "/telemetry/latest"
_WORLD_OBJECTS_LATEST_PATH = "/world_objects/latest"
_UNIT_VELOCITY_LATEST_PATH = "/unit_velocity/latest"
_LINE_OF_SIGHT_LATEST_PATH = "/line_of_sight/latest"
_MISSION_START_LATEST_PATH = "/mission_start/latest"
_FIRING_LATEST_PATH = "/firing/latest"
_PTT_STATE_PATH = "/ptt/state"
_SPU8_STATE_PATH = "/spu8/state"
_WATCHED_ARGS_LATEST_PATH = "/watched_args/latest"
_SIGHT_SERVO_LATEST_PATH = "/sight_servo/latest"
_PETROVICH_INDICATION_LATEST_PATH = "/petrovich_indication/latest"
_PETROVICH_WHEEL_LATEST_PATH = "/petrovich_wheel/latest"
_TEXT_PUSH_PATH = "/text/push"
_COMMAND_PETROVICH_SEARCH_PATH = "/command/petrovich_search"
_COMMAND_LOOK_DIRECTION_PATH = "/command/look_direction"
_COMMAND_COCKPIT_SWITCH_PATH = "/command/cockpit_switch"
_COMMAND_WATCH_ARGS_PATH = "/command/watch_args"
_QUERY_READ_ARGS_PATH = "/query/read_args"
_COMMAND_SIGHT_TARGET_PATH = "/command/sight_target"
_F10_COMMANDS_POLL_PATH = "/f10_commands/poll"
_AUDIO_PLAY_PATH = "/audio/play"
_AUDIO_STOP_PATH = "/audio/stop"

#: `SearchMode`'s two valid wire values -- checked against the request
#: body's `mode` field before forwarding to `CommandSender.send_command`.
_VALID_SEARCH_MODES: tuple[SearchMode, ...] = ("forward", "boresight")

#: `POST /command/look_direction`'s own range validation (`plans/
#: dcs-driven-los/plan.md` SS9b) -- the collector-side layer of the
#: three-deep defense (body-layer -> collector -> Hook) the Security plan
#: review's Finding 4 confirmed sound. `0..11` is an o'clock hour
#: (`perception.gaze`'s own granularity on the body-layer side);
#: `5..180` degrees half-angle is the Hook's own accepted range (SS9b),
#: 180 being the honest full-circle ceiling, never a fallback.
_LOOK_DIRECTION_HOUR_MIN = 0
_LOOK_DIRECTION_HOUR_MAX = 11
_LOOK_DIRECTION_FOV_MIN_DEG = 5
_LOOK_DIRECTION_FOV_MAX_DEG = 180

#: `/audio/play`'s optional `correlation_id` field (`plans/
#: voice-latency-instrumentation/plan.md` Stage 4) -- the capture side
#: mints a fixed ~12-char id, so a generous cap costs nothing and forecloses
#: an attacker-controlled LAN peer growing this process's own playback log
#: without bound (same reasoning, same value, as audio-adapter's own copy
#: of this constant in `server.py` -- duplicated rather than imported,
#: module independence).
_MAX_CORRELATION_ID_LEN = 128

#: `/command/sight_target`'s own clamps (`plans/9k113-sight-pointing/
#: plan.md`, BL-B80 v2) -- `az`/`el`/`rate` are the Security plan
#: review's non-blocking recommendation, generous bounds well past the
#: sight's own physical envelope (±60 deg az, +20/-15 deg el) and a sane
#: slew rate, costing nothing real since Export.lua's own setpoint only
#: ever *approaches* an out-of-range goal, never jumps to it, and DCS's
#: own mechanical stops bound the head's real position regardless.
#: `_SIGHT_TARGET_TSIM_BOUND` is the **required** change from that same
#: review: `t_sim` feeds `Export.lua`'s own `clamp(t - t_sim, 0, cap)`
#: directly, so an unbounded value there is as dangerous as an unbounded
#: angle -- a day's worth of seconds is generous headroom past any real
#: `LoGetModelTime()` value a sortie will ever produce.
_SIGHT_TARGET_AZ_BOUND = 360.0
_SIGHT_TARGET_EL_BOUND = 90.0
_SIGHT_TARGET_RATE_BOUND = 30.0
_SIGHT_TARGET_TSIM_BOUND = 86400.0

#: `/command/watch_args`'s own `watch_id` validation -- matches
#: `Export.lua`'s own `[%w_]{1,16}` bound on the wire (`plans/
#: effector-sequences/plan.md` Stage 4, S4.5).
_WATCH_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def _handle_telemetry_latest(cache: TelemetryCache) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_world_objects_latest(
    cache: WorldObjectsCache,
) -> dict[str, Any] | None:
    snapshot = cache.latest()
    return None if snapshot is None else snapshot.to_dict()


def _handle_unit_velocity_latest(
    cache: UnitVelocityCache,
) -> dict[str, Any] | None:
    snapshot = cache.latest()
    return None if snapshot is None else snapshot.to_dict()


def _handle_line_of_sight_latest(
    cache: LineOfSightCache,
) -> dict[str, Any] | None:
    snapshot = cache.latest()
    return None if snapshot is None else snapshot.to_dict()


def _handle_mission_start_latest(
    cache: MissionStartCache,
) -> dict[str, Any] | None:
    event = cache.latest()
    return None if event is None else event.to_dict()


def _handle_firing_latest(tracker: EmitterTracker) -> dict[str, Any]:
    """Never `null` -- see this endpoint's own docstring in the module
    docstring for why there is no "cache empty" state to distinguish from
    "nothing is firing"."""
    return tracker.snapshot()


def _handle_ptt_state(cache: PttCache, spu8_cache: Spu8Cache) -> dict[str, Any] | None:
    """`null` until the trigger first moves. That is the ordinary startup
    state, not an error -- `Export.lua` sends a line only on change, so an
    untouched trigger produces nothing. A consumer reads `null` as "not
    pressed", which is also what it means.

    **The served `"intercom"` field is already gated by the SPU-8 switches**
    (`plans/spu8-intercom/plan.md` Stage 2, plan Decision 1): `"intercom"`
    is `sample.intercom and spu8_gate_open`, where `spu8_gate_open` is
    `False` whenever `spu8_cache.latest() is None` -- fail-safe-closed, an
    unknown intercom state must not let capture through (plan Decision 3).
    `"radio"` is untouched -- a full press is talking to ATC/another
    player, independent of the SPU-8 gate. This is the entire capture-
    gating mechanism: `audio-adapter`'s `DcsPTT` already reads `"intercom"`
    verbatim off the wire, so no audio-adapter change is needed."""
    sample = cache.latest()
    if sample is None:
        return None
    spu8_sample = spu8_cache.latest()
    spu8_gate_open = spu8_sample is not None and spu8_sample.gate_open
    payload = sample.to_api_dict()
    payload["intercom"] = sample.intercom and spu8_gate_open
    return payload


def _handle_spu8_state(cache: Spu8Cache) -> dict[str, Any] | None:
    """`null` before the first SPU-8 line arrives -- same "not an error"
    posture as `/ptt/state`."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_watched_args_latest(
    cache: WatchedArgsCache,
) -> dict[str, Any] | None:
    """`null` before the first watched-args line arrives -- same "not an
    error" posture as `/spu8/state`."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _validate_arg_list(raw: Any) -> list[int] | None:
    """Shared shape validation for an `"args"` field, used by both
    `/command/watch_args` and `/query/read_args` (`plans/
    effector-sequences/plan.md` Stage 4) -- a list of non-bool ints in
    `[0, MAX_WATCHED_ARG_NUMBER]`, deduped, at most `MAX_WATCHED_ARGS`
    entries. Returns the deduped, sorted list, or `None` if `raw` fails
    any of those checks (the caller responds `400`)."""
    if not isinstance(raw, list):
        return None
    seen: set[int] = set()
    for item in raw:
        if (
            isinstance(item, bool)
            or not isinstance(item, int)
            or not (0 <= item <= MAX_WATCHED_ARG_NUMBER)
        ):
            return None
        seen.add(item)
    if len(seen) > MAX_WATCHED_ARGS:
        return None
    return sorted(seen)


def _handle_sight_servo_latest(
    cache: SightServoCache,
) -> dict[str, Any] | None:
    """`null` before the first sight-servo line arrives -- same "not an
    error" posture as `/watched_args/latest`."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_petrovich_indication_latest(
    cache: PetrovichIndicationCache,
) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_petrovich_wheel_latest(
    cache: PetrovichWheelCache,
) -> dict[str, Any] | None:
    sample = cache.latest()
    return None if sample is None else sample.to_dict()


def _handle_f10_commands_poll(queue: F10CommandQueue) -> list[dict[str, Any]]:
    return [event.to_dict() for event in queue.drain_all()]


def _make_handler(
    cache: TelemetryCache,
    world_objects_cache: WorldObjectsCache,
    petrovich_indication_cache: PetrovichIndicationCache,
    petrovich_wheel_cache: PetrovichWheelCache,
    f10_command_queue: F10CommandQueue,
    text_sender: TextOverlaySender | None,
    command_sender: CommandSender | None,
    audio_sender: AudioPlaybackSender | None,
    unit_velocity_cache: UnitVelocityCache,
    ptt_cache: PttCache,
    spu8_cache: Spu8Cache,
    line_of_sight_cache: LineOfSightCache,
    look_direction_sender: LookDirectionSender | None,
    emitter_tracker: EmitterTracker,
    mission_start_cache: MissionStartCache,
    watched_args_cache: WatchedArgsCache,
    sight_servo_cache: SightServoCache,
    arg_read_broker: ArgReadBroker | None,
) -> type[BaseHTTPRequestHandler]:
    class TelemetryRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == _TELEMETRY_LATEST_PATH:
                self._respond_json(200, _handle_telemetry_latest(cache))
                return
            if path == _WORLD_OBJECTS_LATEST_PATH:
                self._respond_json(
                    200, _handle_world_objects_latest(world_objects_cache)
                )
                return
            if path == _UNIT_VELOCITY_LATEST_PATH:
                self._respond_json(
                    200, _handle_unit_velocity_latest(unit_velocity_cache)
                )
                return
            if path == _LINE_OF_SIGHT_LATEST_PATH:
                self._respond_json(
                    200, _handle_line_of_sight_latest(line_of_sight_cache)
                )
                return
            if path == _MISSION_START_LATEST_PATH:
                self._respond_json(
                    200, _handle_mission_start_latest(mission_start_cache)
                )
                return
            if path == _FIRING_LATEST_PATH:
                self._respond_json(200, _handle_firing_latest(emitter_tracker))
                return
            if path == _PTT_STATE_PATH:
                self._respond_json(200, _handle_ptt_state(ptt_cache, spu8_cache))
                return
            if path == _SPU8_STATE_PATH:
                self._respond_json(200, _handle_spu8_state(spu8_cache))
                return
            if path == _WATCHED_ARGS_LATEST_PATH:
                self._respond_json(200, _handle_watched_args_latest(watched_args_cache))
                return
            if path == _SIGHT_SERVO_LATEST_PATH:
                self._respond_json(200, _handle_sight_servo_latest(sight_servo_cache))
                return
            if path == _PETROVICH_INDICATION_LATEST_PATH:
                self._respond_json(
                    200,
                    _handle_petrovich_indication_latest(petrovich_indication_cache),
                )
                return
            if path == _PETROVICH_WHEEL_LATEST_PATH:
                self._respond_json(
                    200, _handle_petrovich_wheel_latest(petrovich_wheel_cache)
                )
                return
            if path == _F10_COMMANDS_POLL_PATH:
                self._respond_json(200, _handle_f10_commands_poll(f10_command_queue))
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _TEXT_PUSH_PATH:
                self._handle_text_push()
                return
            if path == _COMMAND_PETROVICH_SEARCH_PATH:
                self._handle_command_petrovich_search()
                return
            if path == _COMMAND_LOOK_DIRECTION_PATH:
                self._handle_command_look_direction()
                return
            if path == _AUDIO_PLAY_PATH:
                self._handle_audio_play()
                return
            if path == _AUDIO_STOP_PATH:
                self._handle_audio_stop()
                return
            if path == _COMMAND_COCKPIT_SWITCH_PATH:
                self._handle_command_cockpit_switch()
                return
            if path == _COMMAND_WATCH_ARGS_PATH:
                self._handle_command_watch_args()
                return
            if path == _QUERY_READ_ARGS_PATH:
                self._handle_query_read_args()
                return
            if path == _COMMAND_SIGHT_TARGET_PATH:
                self._handle_command_sight_target()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

        def _handle_text_push(self) -> None:
            if text_sender is None:
                self._respond_json(503, {"error": "text push not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            text = data.get("text")
            if not isinstance(text, str) or not text.strip():
                self._respond_json(400, {"error": "'text' must be a non-empty string"})
                return

            text_sender.send_line(text)
            self._respond_json(200, {"ok": True})

        def _handle_command_petrovich_search(self) -> None:
            if command_sender is None:
                self._respond_json(503, {"error": "command channel not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            mode = data.get("mode")
            if mode not in _VALID_SEARCH_MODES:
                self._respond_json(
                    400,
                    {
                        "error": (
                            f"'mode' must be one of {_VALID_SEARCH_MODES}, got {mode!r}"
                        )
                    },
                )
                return

            try:
                command_sender.send_command(mode)
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_look_direction(self) -> None:
            if look_direction_sender is None:
                self._respond_json(503, {"error": "look direction not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            hour = data.get("hour")
            if (
                isinstance(hour, bool)
                or not isinstance(hour, int)
                or not (_LOOK_DIRECTION_HOUR_MIN <= hour <= _LOOK_DIRECTION_HOUR_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'hour' must be an integer in "
                            f"[{_LOOK_DIRECTION_HOUR_MIN}, "
                            f"{_LOOK_DIRECTION_HOUR_MAX}], got {hour!r}"
                        )
                    },
                )
                return

            fov_half_deg = data.get("fov_half_deg")
            if (
                isinstance(fov_half_deg, bool)
                or not isinstance(fov_half_deg, int)
                or not (
                    _LOOK_DIRECTION_FOV_MIN_DEG
                    <= fov_half_deg
                    <= _LOOK_DIRECTION_FOV_MAX_DEG
                )
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'fov_half_deg' must be an integer in "
                            f"[{_LOOK_DIRECTION_FOV_MIN_DEG}, "
                            f"{_LOOK_DIRECTION_FOV_MAX_DEG}], got {fov_half_deg!r}"
                        )
                    },
                )
                return

            try:
                look_direction_sender.send_look_direction(hour, fov_half_deg)
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_cockpit_switch(self) -> None:
            """`POST /command/cockpit_switch` -- shape validation only
            (device/cmd integers, value finite), **no allow-list of which
            (device, cmd) pairs are accepted** (user direction 2026-10-21,
            see the module docstring's own entry for this endpoint and
            `aircraft-layer/CLAUDE.md`'s "What this is" section for the
            quote). Reuses `command_sender` -- the same `CommandSender`
            instance `/command/petrovich_search` already forwards
            through, since both target `Export.lua`'s one inbound command
            listener."""
            if command_sender is None:
                self._respond_json(
                    503, {"error": "cockpit switch channel not configured"}
                )
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            device = data.get("device")
            if isinstance(device, bool) or not isinstance(device, int):
                self._respond_json(
                    400, {"error": f"'device' must be an integer, got {device!r}"}
                )
                return

            cmd = data.get("cmd")
            if isinstance(cmd, bool) or not isinstance(cmd, int):
                self._respond_json(
                    400, {"error": f"'cmd' must be an integer, got {cmd!r}"}
                )
                return

            value = data.get("value")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                self._respond_json(
                    400,
                    {"error": f"'value' must be a finite number, got {value!r}"},
                )
                return

            try:
                command_sender.send_cockpit_switch(device, cmd, float(value))
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_watch_args(self) -> None:
            """`POST /command/watch_args` -- shape validation only
            (`watch_id` pattern, `args` list bounds -- see the module
            docstring's own entry for this endpoint). Reuses
            `command_sender`, the same `CommandSender` instance every
            other `Export.lua`-targeted write already forwards through."""
            if command_sender is None:
                self._respond_json(503, {"error": "watch_args channel not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            watch_id = data.get("watch_id")
            if not isinstance(watch_id, str) or not _WATCH_ID_RE.fullmatch(watch_id):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'watch_id' must be a 1-16 char [A-Za-z0-9_] "
                            f"string, got {watch_id!r}"
                        )
                    },
                )
                return

            args = _validate_arg_list(data.get("args"))
            if args is None:
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'args' must be a list of at most "
                            f"{MAX_WATCHED_ARGS} integers in "
                            f"[0, {MAX_WATCHED_ARG_NUMBER}]"
                        )
                    },
                )
                return

            try:
                command_sender.send_watch_args(watch_id, args)
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_query_read_args(self) -> None:
            """`POST /query/read_args` -- the one *synchronous* write path
            on this API (`plans/effector-sequences/plan.md` Stage 4, S4.2).
            Shape validation only (same `args` bounds as `/command/
            watch_args`), then blocks this handler thread inside
            `ArgReadBroker.read` until Export.lua answers or the broker's
            own timeout elapses -- see the module docstring's own entry
            for this endpoint."""
            if arg_read_broker is None:
                self._respond_json(503, {"error": "read_args channel not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            args = _validate_arg_list(data.get("args"))
            if args is None:
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'args' must be a list of at most "
                            f"{MAX_WATCHED_ARGS} integers in "
                            f"[0, {MAX_WATCHED_ARG_NUMBER}]"
                        )
                    },
                )
                return

            try:
                result = arg_read_broker.read(args)
            except ArgReadBrokerBusy as exc:
                self._respond_json(503, {"error": str(exc)})
                return
            except ArgReadTimeout as exc:
                self._respond_json(504, {"error": str(exc)})
                return
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(
                200,
                {
                    "t": result.dcs_model_time_s,
                    "values": {str(arg): value for arg, value in result.values.items()},
                },
            )

        def _handle_command_sight_target(self) -> None:
            """`POST /command/sight_target` -- shape validation only
            (every field finite, each clamped to its own generous bound
            -- see the module docstring's own entry for this endpoint,
            including `t_sim`'s own bound, the security plan review's
            required change). Reuses `command_sender`, the same
            `CommandSender` instance `/command/cockpit_switch` already
            forwards through, since both target `Export.lua`'s one
            inbound command listener."""
            if command_sender is None:
                self._respond_json(
                    503, {"error": "sight target channel not configured"}
                )
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            def _bounded_field(field: str, bound: float) -> float | None:
                value = data.get(field)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or abs(value) > bound
                ):
                    self._respond_json(
                        400,
                        {
                            "error": (
                                f"{field!r} must be a finite number in "
                                f"[-{bound}, {bound}], got {value!r}"
                            )
                        },
                    )
                    return None
                return float(value)

            goal_az_deg = _bounded_field("goal_az_deg", _SIGHT_TARGET_AZ_BOUND)
            if goal_az_deg is None:
                return
            goal_el_deg = _bounded_field("goal_el_deg", _SIGHT_TARGET_EL_BOUND)
            if goal_el_deg is None:
                return
            goal_rate_az_deg_s = _bounded_field(
                "goal_rate_az_deg_s", _SIGHT_TARGET_RATE_BOUND
            )
            if goal_rate_az_deg_s is None:
                return
            goal_rate_el_deg_s = _bounded_field(
                "goal_rate_el_deg_s", _SIGHT_TARGET_RATE_BOUND
            )
            if goal_rate_el_deg_s is None:
                return
            # `t_sim` has no sign (DCS model time is never negative) --
            # bounded to `[0, _SIGHT_TARGET_TSIM_BOUND]`, not `+-`, the
            # security plan review's required change.
            t_sim_raw = data.get("t_sim")
            if (
                isinstance(t_sim_raw, bool)
                or not isinstance(t_sim_raw, (int, float))
                or not math.isfinite(t_sim_raw)
                or t_sim_raw < 0
                or t_sim_raw > _SIGHT_TARGET_TSIM_BOUND
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'t_sim' must be a finite number in "
                            f"[0, {_SIGHT_TARGET_TSIM_BOUND}], got {t_sim_raw!r}"
                        )
                    },
                )
                return
            t_sim = float(t_sim_raw)

            try:
                command_sender.send_sight_target(
                    goal_az_deg,
                    goal_el_deg,
                    goal_rate_az_deg_s,
                    goal_rate_el_deg_s,
                    t_sim,
                )
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_audio_play(self) -> None:
            if audio_sender is None:
                self._respond_json(503, {"error": "audio playback not configured"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b""
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._respond_json(400, {"error": "body must be valid JSON"})
                return
            if not isinstance(data, dict):
                self._respond_json(400, {"error": "body must be a JSON object"})
                return

            audio_b64 = data.get("audio_b64")
            if not isinstance(audio_b64, str) or not audio_b64:
                self._respond_json(
                    400, {"error": "'audio_b64' must be a non-empty string"}
                )
                return
            try:
                audio = base64.b64decode(audio_b64, validate=True)
            except (binascii.Error, ValueError) as exc:
                self._respond_json(
                    400, {"error": f"'audio_b64' is not valid base64: {exc}"}
                )
                return
            if not audio:
                self._respond_json(400, {"error": "'audio_b64' decoded to no bytes"})
                return

            urgent = data.get("urgent", False)
            if not isinstance(urgent, bool):
                self._respond_json(400, {"error": "'urgent' must be a boolean"})
                return

            correlation_id = data.get("correlation_id")
            if correlation_id is not None and (
                not isinstance(correlation_id, str)
                or len(correlation_id) > _MAX_CORRELATION_ID_LEN
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'correlation_id' must be a string of at most "
                            f"{_MAX_CORRELATION_ID_LEN} characters"
                        )
                    },
                )
                return

            # Never raises -- see AudioPlaybackSender.play_audio's own
            # docstring and plan Decision 5 (this is /text/push's
            # never-raises posture, not /command/petrovich_search's
            # propagate-500 one).
            audio_sender.play_audio(audio, urgent, correlation_id)
            self._respond_json(200, {"ok": True})

        def _handle_audio_stop(self) -> None:
            """No request body is read -- `AudioPlaybackSender.interrupt`
            takes no arguments, so there is nothing to validate here
            (unlike every other `POST` handler above). Never raises --
            see `AudioPlaybackSender.interrupt`'s own docstring."""
            if audio_sender is None:
                self._respond_json(503, {"error": "audio playback not configured"})
                return
            audio_sender.interrupt()
            self._respond_json(200, {"ok": True})

        def _respond_json(self, status: int, body: Any) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            logger.debug("%s - %s", self.address_string(), format % args)

    return TelemetryRequestHandler


class TelemetryAPIServer:
    """Owns the LAN-facing HTTP server; mirrors `CollectorServer`'s shape."""

    def __init__(
        self,
        cache: TelemetryCache,
        world_objects_cache: WorldObjectsCache | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        petrovich_indication_cache: PetrovichIndicationCache | None = None,
        text_sender: TextOverlaySender | None = None,
        petrovich_wheel_cache: PetrovichWheelCache | None = None,
        command_sender: CommandSender | None = None,
        f10_command_queue: F10CommandQueue | None = None,
        audio_sender: AudioPlaybackSender | None = None,
        unit_velocity_cache: UnitVelocityCache | None = None,
        ptt_cache: PttCache | None = None,
        spu8_cache: Spu8Cache | None = None,
        line_of_sight_cache: LineOfSightCache | None = None,
        look_direction_sender: LookDirectionSender | None = None,
        emitter_tracker: EmitterTracker | None = None,
        mission_start_cache: MissionStartCache | None = None,
        watched_args_cache: WatchedArgsCache | None = None,
        sight_servo_cache: SightServoCache | None = None,
        arg_read_broker: ArgReadBroker | None = None,
    ) -> None:
        # `world_objects_cache`/`petrovich_indication_cache`/
        # `petrovich_wheel_cache`/`f10_command_queue`/`unit_velocity_cache`/
        # `spu8_cache` default to a fresh, never-populated cache/queue
        # rather than being required -- keeps every existing
        # `TelemetryAPIServer(cache, host=..., port=...)` call site (tests
        # included) working unchanged; the corresponding `/latest` (or
        # `/f10_commands/poll`) endpoint on such a server just always
        # answers `null` (or `[]`), same as an empty cache would -- and
        # `/ptt/state`'s served `"intercom"` correctly reads as fail-safe-
        # closed (plan Decision 3) against a never-populated `Spu8Cache`.
        # `text_sender`/`command_sender`/`audio_sender` default to `None`
        # rather than a real sender for the same reason --
        # `/text/push`/`/command/petrovich_search`/`/audio/play` answer
        # `503` rather than crashing when they aren't configured.
        self._cache = cache
        self._world_objects_cache = (
            world_objects_cache
            if world_objects_cache is not None
            else WorldObjectsCache()
        )
        self._petrovich_indication_cache = (
            petrovich_indication_cache
            if petrovich_indication_cache is not None
            else PetrovichIndicationCache()
        )
        self._petrovich_wheel_cache = (
            petrovich_wheel_cache
            if petrovich_wheel_cache is not None
            else PetrovichWheelCache()
        )
        self._f10_command_queue = (
            f10_command_queue if f10_command_queue is not None else F10CommandQueue()
        )
        self._unit_velocity_cache = (
            unit_velocity_cache
            if unit_velocity_cache is not None
            else UnitVelocityCache()
        )
        self._ptt_cache = ptt_cache if ptt_cache is not None else PttCache()
        self._spu8_cache = spu8_cache if spu8_cache is not None else Spu8Cache()
        self._line_of_sight_cache = (
            line_of_sight_cache
            if line_of_sight_cache is not None
            else LineOfSightCache()
        )
        self._mission_start_cache = (
            mission_start_cache
            if mission_start_cache is not None
            else MissionStartCache()
        )
        self._watched_args_cache = (
            watched_args_cache if watched_args_cache is not None else WatchedArgsCache()
        )
        self._sight_servo_cache = (
            sight_servo_cache if sight_servo_cache is not None else SightServoCache()
        )
        # `arg_read_broker` defaults to `None`, same posture as
        # `command_sender`/`text_sender`/`audio_sender` above --
        # `/query/read_args` answers `503` rather than crashing when it
        # isn't configured.
        self._arg_read_broker = arg_read_broker
        # `EmitterTracker` defaults to a fresh, never-fed instance -- same
        # "unconfigured answers the empty/default state, never crashes"
        # posture as every other optional cache above, just with no
        # "configured at all" distinction for this one (see `/firing/
        # latest`'s own docstring).
        self._emitter_tracker = (
            emitter_tracker if emitter_tracker is not None else EmitterTracker()
        )
        self._text_sender = text_sender
        self._command_sender = command_sender
        self._audio_sender = audio_sender
        self._look_direction_sender = look_direction_sender
        self._host = host
        self._port = port
        self._httpd: ThreadingHTTPServer | None = None

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    @property
    def port(self) -> int:
        """Bound port. Useful when constructed with `port=0` (OS-assigned)."""
        if self._httpd is None:
            raise RuntimeError("call open() before reading port")
        return int(self._httpd.server_address[1])

    def open(self) -> None:
        """Bind and start listening. Does not block."""
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port),
            _make_handler(
                self._cache,
                self._world_objects_cache,
                self._petrovich_indication_cache,
                self._petrovich_wheel_cache,
                self._f10_command_queue,
                self._text_sender,
                self._command_sender,
                self._audio_sender,
                self._unit_velocity_cache,
                self._ptt_cache,
                self._spu8_cache,
                self._line_of_sight_cache,
                self._look_direction_sender,
                self._emitter_tracker,
                self._mission_start_cache,
                self._watched_args_cache,
                self._sight_servo_cache,
                self._arg_read_broker,
            ),
        )
        logger.info("telemetry API listening on %s:%d", self._host, self.port)

    def close(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

    def serve_forever(self) -> None:
        """Serve requests until `close()` is called from another thread."""
        if self._httpd is None:
            raise RuntimeError("call open() before serve_forever()")
        self._httpd.serve_forever()
