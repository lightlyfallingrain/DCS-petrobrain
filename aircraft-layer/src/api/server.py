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
- `GET /petrovich_wheel/latest` -> the most recent `list_indication(10)`
  (Petrovich's AI-Wheel state) sample as JSON, or JSON `null` on the same
  "not an error" basis. Added by `plans/bl6-commands-inspect-adapt/plan.md`
  (BL-6) as a live diagnostic for `scan_area`'s `task-status` console
  command; same shape/lifecycle as the other `/latest` endpoints.
- `POST /command/petrovich_search` -> the aircraft layer's first
  inbound/write path (BL-6; `/text/push`, the original first write path,
  was removed by `plans/default-crew-pipeline/plan.md`, BL-B96). Body
  `{"mode": "forward"|"boresight"}`; a valid
  mode forwards to `collector.command_sender.CommandSender.send_command`,
  which fires the JSON command at `Export.lua`'s new inbound UDP listener
  (driving Petrovich's AI Wheel), and responds `200 {"ok": true}` --
  an "attempted the call" contract: a `200`
  here means the datagram was hand off to the OS, never that Petrovich
  actually searched (that confirmation is `/petrovich_wheel/latest`'s job).
  `400 {"error": ...}` on a missing/invalid `mode` or non-JSON body;
  `503 {"error": "command channel not configured"}` if this server was
  built without a `command_sender`. Unlike `/audio/play` below, a send failure here
  propagates as `500 {"error": ...}` rather than being swallowed --
  `collector.command_sender.CommandSender.send_command` raises
  `CommandSendError` on a clearly-failed send (see that module's docstring
  for why this write path does not share the never-raises posture the
  audio/display paths use).
- `POST /audio/play` -> the aircraft layer's second inbound/write path
  (BL-10 first slice, `plans/tts-voice-output/plan.md`). Body
  `{"audio_b64": "<base64 WAV bytes>", "urgent": bool}`; forwards the
  decoded bytes to `collector.audio_sender.AudioPlaybackSender.play_audio`,
  which plays them through `winsound` on this (Windows) box, and responds
  `200 {"ok": true}` -- same "attempted the call" contract as
  `/command/petrovich_search`: a `200` means the audio was handed to
  the playback queue, never that it was actually heard. `400 {"error": ...}`
  on a missing/invalid `audio_b64`/`urgent` or non-JSON body; `503
  {"error": "audio playback not configured"}` if this server was built
  without an `audio_sender`. Unlike
  `/command/petrovich_search`, this never propagates a `500` for a
  playback failure -- `AudioPlaybackSender.play_audio` never raises (plan
  Decision 5: audio is best-effort display-equivalent output, not a
  verifiable command).
- `POST /audio/stop` -> the aircraft layer's third inbound/write path
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
- `POST /command/look_direction` -> the aircraft layer's fourth
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

- `POST /command/cockpit_switch` -> the aircraft layer's fifth
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
- `POST /query/read_args` -> the aircraft layer's fifth inbound/write path,
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

- `POST /command/sight_target` -> the aircraft layer's sixth
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
- `GET /payload/latest` -> the most recent `PayloadSample` (`[[BL-B67]]`,
  `plans/bl-b67-atgm-run/plan.md` Stage 4) as JSON, or JSON `null` on the
  same "not an error" basis as every other `/latest` endpoint. The
  ownship loadout (`LoGetPayloadInfo()` + `LoGetNameByType()`, read at
  the same 5 Hz export tick, sent only on change) -- which stations hold
  what and how many, and the currently-selected station. Read-only, no
  write side: this layer carries the raw values and decides nothing (see
  `schema.payload`'s own module docstring).
- `GET /ai_pilot_wheel/latest` -> the most recent `AiPilotWheelState`
  (`plans/flight-control/plan.md`, BL-16 mode 2, Stage P1, extended Stage
  P2a/P2b with `goal_progress`/`goal_seq`) as JSON, or JSON `null` on the
  same "not an error" basis as every other `/latest` endpoint.
  `Export.lua`'s own per-frame `run_ai_pilot_wheel` status -- whether the
  stick is parked, the flattened AI-pilot overlay readback (mode/course/
  altitude/speed text), the last press issued, and (Stage P2) which goal
  the per-frame loop is pursuing and how it is going.
- `POST /command/ai_pilot_goal` -> the aircraft layer's seventh
  inbound/write path (`plans/flight-control/plan.md`, "Stage P2 ready to
  build", BL-16 mode 2's goal channel). Body `{"goal_seq": int, "param":
  "heading"|"altitude"|"speed"|null, "heading_target_deg": number|null,
  "altitude_target_m": number|null, "altitude_target_ref":
  "radar"|"barometric"|null, "speed_target_kmh": number|null,
  "hvrt_direction": "left"|"right"|"forward"|"back"|null, "hvrt_step":
  "up"|"down"|null, "cbtm_action": "align"|"align_for_launch"|
  "break_left"|"break_right"|"break_away"|null, "cbtm_seq": int|null,
  "wake": bool}`
  (`cbtm_action`/`cbtm_seq` are Stage P3+P4's own sibling one-shot
  fields, "Revised 2026-11-18" -- same closed-vocabulary/
  act-once-per-distinct-seq contract as `hvrt_step`, see `CommandSender.
  send_ai_pilot_goal`'s own docstring; `wake`, `[[BL-B139]]`, is optional
  and defaults `False`, marking a recovery-from-align-for-launch goal so
  `Export.lua`'s own ticks force a one-step kick instead of settling
  when the displayed value already matches the target); forwards to `collector.
  command_sender.CommandSender.send_ai_pilot_goal`, which fires the
  JSON command at
  `Export.lua`'s inbound UDP listener (the same listener
  `/command/cockpit_switch`/`/command/sight_target` already target), and
  responds `200 {"ok": true}` on the same "attempted the call" contract
  as those two. `hvrt_step` is a one-shot trigger (not named in the
  plan's own "wire shape" section, added for Stage P2b's own task list --
  see `send_ai_pilot_goal`'s docstring), acted on by `Export.lua` once
  per distinct `goal_seq`, same as every other field on this message.
  `400 {"error": ...}` on a missing/ out-of-range `goal_seq`, an invalid
  `param`/`altitude_target_ref`/`hvrt_direction`/`hvrt_step`, an
  out-of-range optional numeric field, or a non-JSON body -- shape
  validation only, same division of labour as
  `/command/sight_target`. `503 {"error": "ai_pilot_goal channel not
  configured"}` if this server was built without a `command_sender`; a
  send failure propagates as `500 {"error": ...}`, same posture as
  `/command/cockpit_switch` (a dropped goal update is a real behavioral
  gap, not an opaque display string to swallow).
- `GET /flight_control/latest` -> the most recent `FlightControlState`
  (`plans/flight-control/plan.md`, "Revised 2026-11-18", BL-16 mode 1,
  Stage M1) as JSON, or JSON `null` on the same "not an error" basis as
  every other `/latest` endpoint. `Export.lua`'s own per-frame `flight_
  control` module status -- mode (`off`/`taking`/`active`/`armed`),
  measured telemetry, the handover-diagnostics fields, and the A9 bands.
  **No goal/take-seq fields any more** (BL-16 Stage 3, `plans/
  flight-desired-state/plan.md`) -- the commanded heading/altitude/
  speed is `GET /flight_desired/latest`'s own job now.
- `POST /command/flight` -> BL-16 Stage 3's one numbered channel,
  replacing `/command/flight_control` entirely. Body `{"epoch": int,
  "seq": int, "until": float, "kind": "set"|"take"|"release"|
  "align"|"align_for_launch"|"recover"|"translate"|"hover_hold"|
  "hover_step", ...fields}`; forwards to `collector.command_sender.
  CommandSender.send_flight`, which fires the JSON command at `Export.
  lua`'s inbound UDP listener (the same listener every other
  `/command/*` endpoint already targets), and responds `200 {"ok":
  true}` on the same "attempted the call" contract as those -- **this
  is "sent", never "accepted"**: whether `Export.lua` actually applied
  it rides the next `GET /flight_desired/latest` poll's own `fd_acks`
  ring (plan, section 3a), not this response. `400 {"error": ...}` on a
  missing/out-of-range `epoch`/`seq`/`until`, an invalid `kind`, or an
  out-of-range field -- shape validation only, same division of labour
  as `/command/ai_pilot_goal`: `Export.lua`'s own `flight_desired.
  handle_flight_command` checks every bound again and refuses the whole
  request on any violation (the plan's own `[[AC-B14]]` lesson, read as
  an ack reason rather than a dropped message). `503 {"error": "flight
  channel not configured"}` if this server was built without a
  `command_sender`; a send failure propagates as `500 {"error": ...}`.
- `POST /command/reset` -> body-layer's own process-start reset (BL-16
  sortie 2026-11-20, `docs/acceptance/2026-11-20-sortie-feedback.md`,
  `plans/flight-control/debug.md`). Body `{"epoch": int}`; forwards to
  `collector.command_sender.CommandSender.send_reset`, which fires
  `{"op": "reset", "epoch": epoch}` at `Export.lua`'s inbound UDP
  listener, the same one every other `/command/*` endpoint already
  targets. `commands.lua`'s own `handle_reset_command` dispatches it to
  every seq-carrying channel's own `reset(epoch)` (today: `flight_
  control`/`ai_pilot_wheel`), each of which echoes the epoch back on its
  own status line (`fc_reset_epoch`/`apw_reset_epoch`) so body-layer can
  confirm it landed before sending anything that carries a `seq`.
  `400 {"error": ...}` on a missing/out-of-range `epoch` or a non-JSON
  body. `503 {"error": "reset channel not configured"}` if this server
  was built without a `command_sender`; a send failure propagates as
  `500 {"error": ...}` -- same posture as every other write here, since
  a dropped reset is exactly the "keep retrying" signal body-layer's own
  bounded resend loop needs.

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
    AiPilotWheelCache,
    FlightControlCache,
    FlightDesiredCache,
    LineOfSightCache,
    MissionStartCache,
    PayloadCache,
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
from schema import MAX_WATCHED_ARG_NUMBER, MAX_WATCHED_ARGS
from schema.line_of_sight import MAX_PROBE_POINTS

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
_PAYLOAD_LATEST_PATH = "/payload/latest"
_AI_PILOT_WHEEL_LATEST_PATH = "/ai_pilot_wheel/latest"
_FLIGHT_CONTROL_LATEST_PATH = "/flight_control/latest"
_FLIGHT_DESIRED_LATEST_PATH = "/flight_desired/latest"
_COMMAND_FLIGHT_PATH = "/command/flight"
_COMMAND_FLIGHT_LEASE_PATH = "/command/flight_lease"
_PETROVICH_INDICATION_LATEST_PATH = "/petrovich_indication/latest"
_PETROVICH_WHEEL_LATEST_PATH = "/petrovich_wheel/latest"
_COMMAND_PETROVICH_SEARCH_PATH = "/command/petrovich_search"
_COMMAND_LOOK_DIRECTION_PATH = "/command/look_direction"
_COMMAND_PROBE_POINTS_PATH = "/command/probe_points"
_COMMAND_COCKPIT_SWITCH_PATH = "/command/cockpit_switch"
_COMMAND_WATCH_ARGS_PATH = "/command/watch_args"
_QUERY_READ_ARGS_PATH = "/query/read_args"
_COMMAND_SIGHT_TARGET_PATH = "/command/sight_target"
_COMMAND_AI_PILOT_GOAL_PATH = "/command/ai_pilot_goal"
_COMMAND_RESET_PATH = "/command/reset"
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

#: `POST /command/probe_points`'s own validation (`plans/
#: expected-area-look/plan.md` Stage 1) -- the collector-side layer of
#: the same three-deep defense `_LOOK_DIRECTION_*` above documents
#: (body-layer -> collector -> Hook). `MAX_PROBE_POINTS` ("two open
#: checks x three points") and the coordinate bound both match
#: `schema.line_of_sight`'s own declarations and the Hook's
#: `SET_PROBES_TEMPLATE`/`_safeClampInt` pair exactly -- a mismatch here
#: would validate a shape the Hook then silently reclamps differently.
_PROBE_POINTS_MAX_POINTS = MAX_PROBE_POINTS
_PROBE_POINTS_COORD_ABS_MAX = 2_000_000
_PROBE_POINTS_SEQ_MAX = 2**31 - 1

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

#: `/command/ai_pilot_goal`'s own bounds (`plans/flight-control/plan.md`,
#: "Stage P2 ready to build", BL-16 mode 2) -- shape validation only,
#: same division of labour as `/command/sight_target`'s own clamps: real
#: cockpit limits are enforced by `Export.lua`/DCS itself, these are
#: generous sanity bounds against a malformed or hostile body on the LAN.
_AI_PILOT_GOAL_SEQ_MAX = 2**31 - 1
_AI_PILOT_GOAL_HEADING_MIN_DEG = 0.0
_AI_PILOT_GOAL_HEADING_MAX_DEG = 360.0
#: Metres, either reference -- generous past any altitude this airframe
#: will ever fly (a few km AGL/MSL at most), well short of overflow.
_AI_PILOT_GOAL_ALTITUDE_MIN_M = -500.0
_AI_PILOT_GOAL_ALTITUDE_MAX_M = 20_000.0
#: km/h IAS -- generous headroom above body-layer's own `AI_PILOT_SPEED_
#: MAX_SENTINEL_KMH` (1,000,000, `belief/ai_pilot_wheel.py`), a protocol
#: sentinel duplicated across the seam like every other cross-subproject
#: constant in this codebase (module independence) -- this bound exists
#: only to reject a wildly malformed value, not to police body-layer's
#: own choice of sentinel.
_AI_PILOT_GOAL_SPEED_MIN_KMH = 0.0
_AI_PILOT_GOAL_SPEED_MAX_KMH = 2_000_000.0
_AI_PILOT_GOAL_VALID_PARAMS: tuple[str, ...] = ("heading", "altitude", "speed")
_AI_PILOT_GOAL_VALID_ALTITUDE_REFS: tuple[str, ...] = ("radar", "barometric")
_AI_PILOT_GOAL_VALID_HVRT_DIRECTIONS: tuple[str, ...] = (
    "left",
    "right",
    "forward",
    "back",
)
#: `hvrt_step`'s own closed vocabulary -- the one-shot altitude-tap
#: trigger (Stage P2b's own task list, not named in the plan's "wire
#: shape" section -- see `CommandSender.send_ai_pilot_goal`'s docstring).
_AI_PILOT_GOAL_VALID_HVRT_STEPS: tuple[str, ...] = ("up", "down")

#: `cbtm_action`'s own closed vocabulary -- Stage P3+P4's one-shot
#: align/break channel (`plans/flight-control/plan.md`, "Revised
#: 2026-11-18 -- Stages P3+P4 ready to build", "The CBTM one-shot wire
#: channel"), same sibling-field shape as `hvrt_step` above.
_AI_PILOT_GOAL_VALID_CBTM_ACTIONS: tuple[str, ...] = (
    "align",
    "align_for_launch",
    "break_left",
    "break_right",
    "break_away",
)

#: `/command/flight`'s own bounds (`plans/flight-desired-state/plan.md`,
#: BL-16 Stage 3, section 5) -- shape validation only, same division of
#: labour as `/command/ai_pilot_goal`'s own clamps: `Export.lua`'s own
#: `flight_desired.handle_flight_command` checks every bound again and
#: refuses the whole request (an ack reason, not a dropped message) if
#: any one is violated (the plan's own `[[AC-B14]]` lesson), rather than
#: trusting this layer's check alone. Replaces `_FLIGHT_CONTROL_SEQ_MAX`/
#: `_FLIGHT_CONTROL_VALID_CMDS`/`_FLIGHT_CONTROL_GOAL_BOUNDS` (the old
#: `flight_control` op, retired this stage).
_FLIGHT_SEQ_MAX = 2**31 - 1
#: Same ceiling as `_RESET_EPOCH_MAX` below: the epoch IS body-layer's
#: reset epoch (`ConsolePerceptionRunner.command_reset_epoch`, wall-clock
#: milliseconds, ~1.8e12), so a 2**31 bound rejected every real message
#: with a 400 (sortie 2026-11-23, "you have controls" -> "Unable, not
#: ready."). Lua encodes it with `%.0f`, so 2**53 is safe end to end.
_FLIGHT_EPOCH_MAX = 2**53 - 1
_FLIGHT_VALID_KINDS: tuple[str, ...] = (
    "set",
    "take",
    "release",
    "align",
    "align_for_launch",
    "recover",
    "translate",
    "hover_hold",
    "hover_step",
)
_FLIGHT_CONTROL_VALID_ALT_REFS: tuple[str, ...] = ("agl", "baro")
_FLIGHT_VALID_TURN_STYLES: tuple[str, ...] = ("normal", "break", "break_away")
#: `limits` fields -- generous sanity bounds, same posture as every other
#: `/command/*` endpoint's own clamps (real cockpit/behaviour limits are
#: body-layer's `tuning.py` job, not this layer's).
_FLIGHT_CONTROL_LIMITS_BOUNDS: dict[str, tuple[float, float]] = {
    "takeover_level_bank_deg": (0.0, 90.0),
    "floor_agl_m": (0.0, 2000.0),
    "min_ias_kmh": (0.0, 500.0),
    "max_ias_kmh": (0.0, 500.0),
    "on_ground_agl_threshold_m": (0.0, 100.0),
    # security-m1-m2.md Finding B, change-request round: `arm_lease_s`
    # is itself a safety margin (U10's park-then-unpark escape window),
    # not a flight-behaviour knob, so it gets a tight ceiling of its
    # own rather than the generous sanity bound every other limit here
    # shares -- must match `Export.lua`'s own `FC_LIMIT_BOUNDS.arm_
    # lease_s` and body-layer's `tuning.py` `ARM_LEASE_S` `hi` exactly.
    "arm_lease_s": (0.0, 10.0),
    # M2 additions (`Export.lua`'s own `FC_LIMIT_BOUNDS`, matched here
    # key-for-key -- a field this dict does not name is silently
    # dropped by the loop below, never forwarded at all, so adding a
    # new wire key to body-layer's `flight_control_limits()` without a
    # matching entry here would be a silent loss, not a rejection).
    # **No `max_bank_deg` entry any more** (mode-1 batch, F-M1: "remove
    # the 30 degree limit") -- removed key-for-key with `Export.lua`'s
    # own `FC_LIMIT_BOUNDS` and body-layer's `tuning.py`, not widened.
    "max_turn_bank_deg": (0.0, 60.0),
    "max_climb_vs_mps": (0.0, 20.0),
    "max_accel_mps2": (0.0, 10.0),
    "speed_band_frac": (0.0, 1.0),
    "alt_band_frac": (0.0, 1.0),
    "alt_band_min_m": (0.0, 100.0),
    "turn_rate_band_frac": (0.0, 1.0),
    "heading_band_deg": (0.0, 90.0),
    # Mode-1 batch additions (`Export.lua`'s own `FC_LIMIT_BOUNDS`,
    # same key-for-key matching requirement).
    "rotor_rpm_floor_pct": (0.0, 100.0),
    "retreating_blade_stall_ias_kmh": (0.0, 500.0),
    "break_max_height_loss_m": (0.0, 1000.0),
    "vrs_ias_threshold_kmh": (0.0, 200.0),
    "vrs_max_descent_mps": (0.0, 50.0),
}
#: `/command/flight`'s own numeric fields -- same generous-sanity-bound
#: posture as `_FLIGHT_CONTROL_LIMITS_BOUNDS` above.
_FLIGHT_FIELD_BOUNDS: dict[str, tuple[float, float]] = {
    "heading_deg": (0.0, 360.0),
    "alt_m": (-500.0, 20_000.0),
    "ias_kmh": (0.0, 2_000_000.0),
    # Mode-1 batch, Decision 27 -- the break's own signed rate override.
    # Generous sanity bound (same posture as every other field here);
    # `rules/actions.py`'s own `ActionParam(lo=1, hi=90)` is the tight,
    # domain-specific bound on the magnitude the rule can ever send.
    "turn_rate_deg_s": (-90.0, 90.0),
}

#: `/command/reset`'s own bound (BL-16 sortie 2026-11-20, `docs/
#: acceptance/2026-11-20-sortie-feedback.md`) -- shape validation only,
#: same posture as every other `/command/*` endpoint's own clamp.
#: Body-layer mints `epoch` from a wall-clock millisecond timestamp
#: (`int(time.time() * 1000)`), well under the JSON/JS safe-integer
#: ceiling; a non-negative whole number is all this layer needs to
#: check -- `Export.lua`'s own `handle_reset_command` does not interpret
#: the value at all, only echoes it back verbatim.
_RESET_EPOCH_MAX = 2**53 - 1


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


def _handle_payload_latest(
    cache: PayloadCache,
) -> dict[str, Any] | None:
    """`null` before the first payload line arrives -- same "not an
    error" posture as `/sight_servo/latest`."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_ai_pilot_wheel_latest(
    cache: AiPilotWheelCache,
) -> dict[str, Any] | None:
    """`null` before the first AI-pilot-wheel line arrives -- same "not an
    error" posture as `/sight_servo/latest` (`plans/flight-control/
    plan.md`, BL-16 mode 2, Stage P1)."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_flight_control_latest(
    cache: FlightControlCache,
) -> dict[str, Any] | None:
    """`null` before the first flight-control line arrives -- same "not an
    error" posture as `/ai_pilot_wheel/latest` (`plans/flight-control/
    plan.md`, "Revised 2026-11-18", BL-16 mode 1, Stage M1)."""
    sample = cache.latest()
    return None if sample is None else sample.to_api_dict()


def _handle_flight_desired_latest(
    cache: FlightDesiredCache,
) -> dict[str, Any] | None:
    """`null` before the first flight-desired line arrives -- same "not
    an error" posture as `/flight_control/latest` (`plans/
    flight-desired-state/plan.md`, BL-16 Stages 1-2)."""
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


def _make_handler(
    cache: TelemetryCache,
    world_objects_cache: WorldObjectsCache,
    petrovich_indication_cache: PetrovichIndicationCache,
    petrovich_wheel_cache: PetrovichWheelCache,
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
    payload_cache: PayloadCache,
    ai_pilot_wheel_cache: AiPilotWheelCache,
    flight_control_cache: FlightControlCache,
    flight_desired_cache: FlightDesiredCache,
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
            if path == _PAYLOAD_LATEST_PATH:
                self._respond_json(200, _handle_payload_latest(payload_cache))
                return
            if path == _AI_PILOT_WHEEL_LATEST_PATH:
                self._respond_json(
                    200, _handle_ai_pilot_wheel_latest(ai_pilot_wheel_cache)
                )
                return
            if path == _FLIGHT_CONTROL_LATEST_PATH:
                self._respond_json(
                    200, _handle_flight_control_latest(flight_control_cache)
                )
                return
            if path == _FLIGHT_DESIRED_LATEST_PATH:
                self._respond_json(
                    200, _handle_flight_desired_latest(flight_desired_cache)
                )
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
            self._respond_json(404, {"error": f"not found: {path}"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == _COMMAND_PETROVICH_SEARCH_PATH:
                self._handle_command_petrovich_search()
                return
            if path == _COMMAND_LOOK_DIRECTION_PATH:
                self._handle_command_look_direction()
                return
            if path == _COMMAND_PROBE_POINTS_PATH:
                self._handle_command_probe_points()
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
            if path == _COMMAND_AI_PILOT_GOAL_PATH:
                self._handle_command_ai_pilot_goal()
                return
            if path == _COMMAND_FLIGHT_PATH:
                self._handle_command_flight()
                return
            if path == _COMMAND_FLIGHT_LEASE_PATH:
                self._handle_command_flight_lease()
                return
            if path == _COMMAND_RESET_PATH:
                self._handle_command_reset()
                return
            self._respond_json(404, {"error": f"not found: {path}"})

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

        def _handle_command_probe_points(self) -> None:
            """`POST /command/probe_points` -- forwards to the same
            `LookDirectionSender` instance `/command/look_direction`
            already uses (`plans/expected-area-look/plan.md` Stage 1: one
            Hook listener, two ops). `{"seq": int, "points": [[x, z],
            ...]}`; at most `MAX_PROBE_POINTS` points, each an integer
            pair with `|x|, |z| <= _PROBE_POINTS_COORD_ABS_MAX`. An empty
            `points` list is valid -- it is how a caller clears an open
            check's probes (plan: "N = 0 clears")."""
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

            seq = data.get("seq")
            if (
                isinstance(seq, bool)
                or not isinstance(seq, int)
                or not (0 <= seq <= _PROBE_POINTS_SEQ_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            f"'seq' must be an integer in [0, {_PROBE_POINTS_SEQ_MAX}], "
                            f"got {seq!r}"
                        )
                    },
                )
                return

            points_raw = data.get("points")
            if not isinstance(points_raw, list) or len(points_raw) > (
                _PROBE_POINTS_MAX_POINTS
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'points' must be a list of at most "
                            f"{_PROBE_POINTS_MAX_POINTS} [x, z] pairs, got {points_raw!r}"
                        )
                    },
                )
                return

            points: list[tuple[int, int]] = []
            for point in points_raw:
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(isinstance(coord, bool) for coord in point)
                    or not all(isinstance(coord, int) for coord in point)
                    or not all(
                        -_PROBE_POINTS_COORD_ABS_MAX
                        <= coord
                        <= _PROBE_POINTS_COORD_ABS_MAX
                        for coord in point
                    )
                ):
                    self._respond_json(
                        400,
                        {
                            "error": (
                                "each point must be an [x, z] integer pair with "
                                f"|x|, |z| <= {_PROBE_POINTS_COORD_ABS_MAX}, got "
                                f"{point!r}"
                            )
                        },
                    )
                    return
                points.append((point[0], point[1]))

            try:
                look_direction_sender.send_probe_points(seq, points)
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

        def _handle_command_ai_pilot_goal(self) -> None:
            """`POST /command/ai_pilot_goal` -- BL-16 mode 2's goal
            channel (`plans/flight-control/plan.md`, "Stage P2 ready to
            build", "The goal channel -- wire shape"). Shape validation
            only, mirroring `/command/sight_target`'s own division of
            labour: every field finite/in-range where present, `param`/
            `altitude_target_ref`/`hvrt_direction` checked against their
            own closed vocabularies, `null` accepted for every optional
            field (the "only the fields matching `param` are meaningful"
            selector design). Reuses `command_sender`, the same instance
            every other `/command/*` endpoint on this listener forwards
            through."""
            if command_sender is None:
                self._respond_json(
                    503, {"error": "ai_pilot_goal channel not configured"}
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

            goal_seq_raw = data.get("goal_seq")
            if (
                isinstance(goal_seq_raw, bool)
                or not isinstance(goal_seq_raw, int)
                or not (0 <= goal_seq_raw <= _AI_PILOT_GOAL_SEQ_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'goal_seq' must be a whole number in "
                            f"[0, {_AI_PILOT_GOAL_SEQ_MAX}], got {goal_seq_raw!r}"
                        )
                    },
                )
                return

            param = data.get("param")
            if param is not None and param not in _AI_PILOT_GOAL_VALID_PARAMS:
                self._respond_json(
                    400,
                    {
                        "error": (
                            f"'param' must be one of {_AI_PILOT_GOAL_VALID_PARAMS} "
                            f"or null, got {param!r}"
                        )
                    },
                )
                return

            def _optional_bounded_field(
                field: str, lo: float, hi: float
            ) -> tuple[float | None, bool]:
                """`(value, ok)` -- `ok=False` means a 400 was already
                sent and the caller must return immediately. `None` is a
                legal value (the field was simply not supplied this
                message)."""
                value = data.get(field)
                if value is None:
                    return None, True
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < lo
                    or value > hi
                ):
                    self._respond_json(
                        400,
                        {
                            "error": (
                                f"{field!r} must be a finite number in "
                                f"[{lo}, {hi}] or null, got {value!r}"
                            )
                        },
                    )
                    return None, False
                return float(value), True

            heading_target_deg, ok = _optional_bounded_field(
                "heading_target_deg",
                _AI_PILOT_GOAL_HEADING_MIN_DEG,
                _AI_PILOT_GOAL_HEADING_MAX_DEG,
            )
            if not ok:
                return
            altitude_target_m, ok = _optional_bounded_field(
                "altitude_target_m",
                _AI_PILOT_GOAL_ALTITUDE_MIN_M,
                _AI_PILOT_GOAL_ALTITUDE_MAX_M,
            )
            if not ok:
                return
            speed_target_kmh, ok = _optional_bounded_field(
                "speed_target_kmh",
                _AI_PILOT_GOAL_SPEED_MIN_KMH,
                _AI_PILOT_GOAL_SPEED_MAX_KMH,
            )
            if not ok:
                return

            altitude_target_ref = data.get("altitude_target_ref")
            if (
                altitude_target_ref is not None
                and altitude_target_ref not in _AI_PILOT_GOAL_VALID_ALTITUDE_REFS
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'altitude_target_ref' must be one of "
                            f"{_AI_PILOT_GOAL_VALID_ALTITUDE_REFS} or null, got "
                            f"{altitude_target_ref!r}"
                        )
                    },
                )
                return

            hvrt_direction = data.get("hvrt_direction")
            if (
                hvrt_direction is not None
                and hvrt_direction not in _AI_PILOT_GOAL_VALID_HVRT_DIRECTIONS
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'hvrt_direction' must be one of "
                            f"{_AI_PILOT_GOAL_VALID_HVRT_DIRECTIONS} or null, got "
                            f"{hvrt_direction!r}"
                        )
                    },
                )
                return

            hvrt_step = data.get("hvrt_step")
            if (
                hvrt_step is not None
                and hvrt_step not in _AI_PILOT_GOAL_VALID_HVRT_STEPS
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'hvrt_step' must be one of "
                            f"{_AI_PILOT_GOAL_VALID_HVRT_STEPS} or null, got "
                            f"{hvrt_step!r}"
                        )
                    },
                )
                return

            cbtm_action = data.get("cbtm_action")
            if (
                cbtm_action is not None
                and cbtm_action not in _AI_PILOT_GOAL_VALID_CBTM_ACTIONS
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'cbtm_action' must be one of "
                            f"{_AI_PILOT_GOAL_VALID_CBTM_ACTIONS} or null, got "
                            f"{cbtm_action!r}"
                        )
                    },
                )
                return

            cbtm_seq_raw = data.get("cbtm_seq")
            cbtm_seq: int | None
            if cbtm_seq_raw is None:
                cbtm_seq = None
            elif (
                isinstance(cbtm_seq_raw, bool)
                or not isinstance(cbtm_seq_raw, int)
                or not (0 <= cbtm_seq_raw <= _AI_PILOT_GOAL_SEQ_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'cbtm_seq' must be a whole number in "
                            f"[0, {_AI_PILOT_GOAL_SEQ_MAX}] or null, got "
                            f"{cbtm_seq_raw!r}"
                        )
                    },
                )
                return
            else:
                cbtm_seq = cbtm_seq_raw

            # `[[BL-B139]]` -- the recovery-only wake flag. Optional,
            # defaults `False` (every pre-existing caller that never
            # sends it keeps the old no-op-when-already-there
            # behaviour); a strict bool, same posture every other
            # closed-vocabulary field on this endpoint already takes.
            wake_raw = data.get("wake", False)
            if not isinstance(wake_raw, bool):
                self._respond_json(
                    400,
                    {"error": f"'wake' must be a boolean, got {wake_raw!r}"},
                )
                return

            try:
                command_sender.send_ai_pilot_goal(
                    goal_seq_raw,
                    param,
                    heading_target_deg,
                    altitude_target_m,
                    altitude_target_ref,
                    speed_target_kmh,
                    hvrt_direction,
                    hvrt_step,
                    cbtm_action,
                    cbtm_seq,
                    wake_raw,
                )
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_flight(self) -> None:
            """`POST /command/flight` -- BL-16 Stage 3's one numbered
            channel (`plans/flight-desired-state/plan.md`, section 5),
            replacing `/command/flight_control` entirely. Shape
            validation only, mirroring `/command/ai_pilot_goal`'s own
            division of labour: `epoch`/`seq`/`until`/`kind` required,
            every other field optional and checked individually (every
            present field finite and in its own generous sanity bound; a
            field the message omits is `null` on the wire, "keep yours"
            to `Export.lua`, never rejected here). `turn` is a closed
            three-way int, `turn_style`/`alt_ref` closed vocabularies.
            Fields are flat on the body (never nested under a `"goal"`
            key) -- `Export.lua`'s own extraction helpers are nesting-
            blind, so there is no reason to nest them here either."""
            if command_sender is None:
                self._respond_json(503, {"error": "flight channel not configured"})
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

            epoch_raw = data.get("epoch")
            if (
                isinstance(epoch_raw, bool)
                or not isinstance(epoch_raw, int)
                or not (0 <= epoch_raw <= _FLIGHT_EPOCH_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'epoch' must be a whole number in "
                            f"[0, {_FLIGHT_EPOCH_MAX}], got {epoch_raw!r}"
                        )
                    },
                )
                return

            seq_raw = data.get("seq")
            if (
                isinstance(seq_raw, bool)
                or not isinstance(seq_raw, int)
                or not (0 <= seq_raw <= _FLIGHT_SEQ_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'seq' must be a whole number in "
                            f"[0, {_FLIGHT_SEQ_MAX}], got {seq_raw!r}"
                        )
                    },
                )
                return

            until_raw = data.get("until")
            if (
                isinstance(until_raw, bool)
                or not isinstance(until_raw, (int, float))
                or not math.isfinite(until_raw)
            ):
                self._respond_json(
                    400,
                    {"error": f"'until' must be a finite number, got {until_raw!r}"},
                )
                return

            kind = data.get("kind")
            if kind not in _FLIGHT_VALID_KINDS:
                self._respond_json(
                    400,
                    {
                        "error": (
                            f"'kind' must be one of {_FLIGHT_VALID_KINDS}, got {kind!r}"
                        )
                    },
                )
                return

            fields: dict[str, object] = {}
            for field, (lo, hi) in _FLIGHT_FIELD_BOUNDS.items():
                if field not in data or data[field] is None:
                    continue
                value = data[field]
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < lo
                    or value > hi
                ):
                    self._respond_json(
                        400,
                        {
                            "error": (
                                f"'{field}' must be a finite number in "
                                f"[{lo}, {hi}], got {value!r}"
                            )
                        },
                    )
                    return
                fields[field] = float(value)
            if "turn" in data and data["turn"] is not None:
                turn_value = data["turn"]
                if (
                    isinstance(turn_value, bool)
                    or not isinstance(turn_value, int)
                    or turn_value not in (-1, 0, 1)
                ):
                    self._respond_json(
                        400,
                        {
                            "error": (
                                "'turn' must be one of -1, 0, 1 or null, "
                                f"got {turn_value!r}"
                            )
                        },
                    )
                    return
                fields["turn"] = turn_value
            if "turn_style" in data and data["turn_style"] is not None:
                turn_style_value = data["turn_style"]
                if turn_style_value not in _FLIGHT_VALID_TURN_STYLES:
                    self._respond_json(
                        400,
                        {
                            "error": (
                                "'turn_style' must be one of "
                                f"{_FLIGHT_VALID_TURN_STYLES} or null, got "
                                f"{turn_style_value!r}"
                            )
                        },
                    )
                    return
                fields["turn_style"] = turn_style_value
            if "alt_ref" in data and data["alt_ref"] is not None:
                alt_ref_value = data["alt_ref"]
                if alt_ref_value not in _FLIGHT_CONTROL_VALID_ALT_REFS:
                    self._respond_json(
                        400,
                        {
                            "error": (
                                "'alt_ref' must be one of "
                                f"{_FLIGHT_CONTROL_VALID_ALT_REFS} or null, got "
                                f"{alt_ref_value!r}"
                            )
                        },
                    )
                    return
                fields["alt_ref"] = alt_ref_value

            try:
                command_sender.send_flight(
                    epoch_raw, seq_raw, float(until_raw), kind, fields
                )
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_flight_lease(self) -> None:
            """`POST /command/flight_lease` -- BL-16 Stage 2's own
            unnumbered lease (`plans/flight-desired-state/plan.md`,
            refinement 3), replacing the old `{"cmd": "arm"}` message on
            `/command/flight_control`. Shape validation only, same
            division of labour as `/command/flight_control`'s own
            `limits`: `epoch` a non-negative whole number (same bound as
            `/command/reset`), `limits` an optional object whose fields
            are each checked individually against `_FLIGHT_CONTROL_
            LIMITS_BOUNDS` (the same bounds the lease's sibling endpoint
            uses, since it carries the same `limits` bundle)."""
            if command_sender is None:
                self._respond_json(
                    503, {"error": "flight_lease channel not configured"}
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

            epoch_raw = data.get("epoch")
            if (
                isinstance(epoch_raw, bool)
                or not isinstance(epoch_raw, int)
                or not (0 <= epoch_raw <= _RESET_EPOCH_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'epoch' must be a whole number in "
                            f"[0, {_RESET_EPOCH_MAX}], got {epoch_raw!r}"
                        )
                    },
                )
                return

            limits_raw = data.get("limits")
            if limits_raw is not None and not isinstance(limits_raw, dict):
                self._respond_json(
                    400,
                    {
                        "error": f"'limits' must be an object or null, got {limits_raw!r}"
                    },
                )
                return
            limits: dict[str, float] = {}
            if limits_raw is not None:
                for field, (lo, hi) in _FLIGHT_CONTROL_LIMITS_BOUNDS.items():
                    if field not in limits_raw:
                        continue
                    value = limits_raw[field]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or value < lo
                        or value > hi
                    ):
                        self._respond_json(
                            400,
                            {
                                "error": (
                                    f"limits.{field} must be a finite number in "
                                    f"[{lo}, {hi}], got {value!r}"
                                )
                            },
                        )
                        return
                    limits[field] = float(value)

            try:
                command_sender.send_flight_lease(
                    epoch_raw, limits if limits_raw is not None else None
                )
            except CommandSendError as exc:
                self._respond_json(500, {"error": str(exc)})
                return
            self._respond_json(200, {"ok": True})

        def _handle_command_reset(self) -> None:
            """`POST /command/reset` -- body-layer's own process-start
            reset (BL-16 sortie 2026-11-20, `docs/acceptance/
            2026-11-20-sortie-feedback.md`). Shape validation only:
            `epoch` a non-negative whole number, same division of
            labour as every other `/command/*` endpoint -- `Export.
            lua`'s own `handle_reset_command` does not interpret the
            value, only dispatches and echoes it back."""
            if command_sender is None:
                self._respond_json(503, {"error": "reset channel not configured"})
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

            epoch_raw = data.get("epoch")
            if (
                isinstance(epoch_raw, bool)
                or not isinstance(epoch_raw, int)
                or not (0 <= epoch_raw <= _RESET_EPOCH_MAX)
            ):
                self._respond_json(
                    400,
                    {
                        "error": (
                            "'epoch' must be a whole number in "
                            f"[0, {_RESET_EPOCH_MAX}], got {epoch_raw!r}"
                        )
                    },
                )
                return

            try:
                command_sender.send_reset(epoch_raw)
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
            # docstring and plan Decision 5 (never-raises posture, not
            # /command/petrovich_search's propagate-500 one).
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
        petrovich_wheel_cache: PetrovichWheelCache | None = None,
        command_sender: CommandSender | None = None,
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
        payload_cache: PayloadCache | None = None,
        ai_pilot_wheel_cache: AiPilotWheelCache | None = None,
        flight_control_cache: FlightControlCache | None = None,
        flight_desired_cache: FlightDesiredCache | None = None,
    ) -> None:
        # `world_objects_cache`/`petrovich_indication_cache`/
        # `petrovich_wheel_cache`/`unit_velocity_cache`/
        # `spu8_cache` default to a fresh, never-populated cache
        # rather than being required -- keeps every existing
        # `TelemetryAPIServer(cache, host=..., port=...)` call site (tests
        # included) working unchanged; the corresponding `/latest`
        # endpoint on such a server just always
        # answers `null`, same as an empty cache would -- and
        # `/ptt/state`'s served `"intercom"` correctly reads as fail-safe-
        # closed (plan Decision 3) against a never-populated `Spu8Cache`.
        # `command_sender`/`audio_sender` default to `None`
        # rather than a real sender for the same reason --
        # `/command/petrovich_search`/`/audio/play` answer
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
        self._payload_cache = (
            payload_cache if payload_cache is not None else PayloadCache()
        )
        self._ai_pilot_wheel_cache = (
            ai_pilot_wheel_cache
            if ai_pilot_wheel_cache is not None
            else AiPilotWheelCache()
        )
        self._flight_control_cache = (
            flight_control_cache
            if flight_control_cache is not None
            else FlightControlCache()
        )
        self._flight_desired_cache = (
            flight_desired_cache
            if flight_desired_cache is not None
            else FlightDesiredCache()
        )
        # `arg_read_broker` defaults to `None`, same posture as
        # `command_sender`/`audio_sender` above --
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
                self._payload_cache,
                self._ai_pilot_wheel_cache,
                self._flight_control_cache,
                self._flight_desired_cache,
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
