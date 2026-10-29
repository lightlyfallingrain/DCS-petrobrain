"""Run the collector process: Export.lua listener + Mac-facing LAN API.

Both `CollectorServer` (loopback push from Export.lua) and `TelemetryAPIServer`
(LAN-reachable poll API, plan stage 4) run in this one process, sharing a
single `TelemetryCache` instance. Before stage 4, this only dumped the latest
sample to stdout for manual verification (plan stage 2); that dump is kept
(`--dump-interval`) since it's still useful for watching the pipeline without
a separate HTTP client.

A `CommandSender` (BL-6, `plans/bl6-commands-inspect-adapt/plan.md`) is
constructed here and handed to `TelemetryAPIServer` for `POST /command/
petrovich_search`, this pipeline's first inbound/write path (`BL-B96`
removed the original first, `TextOverlaySender`/`POST /text/push`).

An `AudioPlaybackSender` (BL-10 first slice, `plans/tts-voice-output/
plan.md`) is constructed the same way as `command_sender`
for `POST /audio/play`, this pipeline's second inbound/write path -- unlike
that one, it has no host/port (it plays audio directly on this box via
`winsound`, no loopback UDP peer involved).

A `UnitVelocityReceiver` (`plans/movement-detection/plan.md` Stage 1) is
opened and run on its own background thread the same way, feeding a
`UnitVelocityCache` that `GET /unit_velocity/latest` reads -- the first
channel running the opposite direction (Hook script -> collector, not
collector -> Hook/Export.lua).

A `LineOfSightReceiver` (`plans/dcs-driven-los/plan.md`, X-B29) is opened and
run on its own background thread the same way as `unit_velocity_receiver`,
feeding a `LineOfSightCache` that `GET /line_of_sight/latest` reads -- the
second channel running the Hook-to-collector direction. A `LookDirectionSender`
is constructed the same way as `command_sender` for `POST /command/
look_direction`, this pipeline's fifth inbound/write path -- unlike
`command_sender` (which targets `Export.lua`'s inbound listener), this one
targets the LOS Hook script's own inbound listener (`land.*`/`world.*` are
only reachable from the mission-scripting state, not Export's).

A `FiringEventsReceiver`/`EmitterTracker` pair (`plans/emitter-visibility/
plan.md` Stage B, `AC-B8`) is opened and run on its own background thread
the same way as `line_of_sight_receiver` -- the third channel running the
Hook-to-collector direction. Unlike every other feed above, the thing fed
by the receiver is not a `*Cache` but a small stateful machine
(`collector.firing_receiver.EmitterTracker`) that latches/watchdogs raw
`S_EVENT_SHOOTING_START`/`_END` events into "who is currently firing" --
see that module's own docstring. `GET /firing/latest` reads its
`snapshot()`.

A `Spu8Cache` (`plans/spu8-intercom/plan.md`) is constructed the same way
as `ptt_cache` -- fed by `CollectorServer` from Export.lua's "net1" lines,
served by `GET /spu8/state`, and consumed by `_handle_ptt_state` to gate
`/ptt/state`'s own `"intercom"` field (Stage 2). Its `gate_state` method is
also handed to `AudioPlaybackSender` as the gate/volume provider consulted
before each queued line plays (Stage 3).

A `MissionStartReceiver` (`plans/bl15-mission-start/plan.md`, BL-15 Stage 1)
is opened and run on its own background thread the same way as
`unit_velocity_receiver` -- the fourth channel running the Hook-to-collector
direction, feeding a `MissionStartCache` that `GET /mission_start/latest`
reads.

A `PayloadCache` (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md` Stage 4) is
constructed the same way as `sight_servo_cache` -- fed by `CollectorServer`
from Export.lua's "stations" lines, served by `GET /payload/latest`.

A `WatchedArgsCache` + `ArgReadBroker` pair (`plans/effector-sequences/
plan.md` Stage 4) replaces the former `CockpitSwitchCache` (decided,
"remove"). `WatchedArgsCache` is constructed the same way as `spu8_cache`
-- fed by `CollectorServer` from Export.lua's "watch_id" lines, served by
`GET /watched_args/latest`; its install side (`POST /command/watch_args`)
reuses `command_sender` (above). `ArgReadBroker` is different in kind from
every cache here: it is not fed by `CollectorServer` passively, it *drives*
a UDP send (also via `command_sender`) and then blocks the calling
`POST /query/read_args` HTTP handler thread until `CollectorServer`'s own
connection thread calls `handle_reply_line` on the matching "read_id" TCP
reply -- so both halves of this request/reply pair, and the single
`ArgReadBroker` instance connecting them, are shared between the collector
and API server exactly as `WatchedArgsCache` is.

Usage: python -m collector [--host HOST] [--port PORT] [--api-host HOST]
       [--api-port PORT]
       [--command-host HOST] [--command-port PORT]
       [--unit-velocity-host HOST] [--unit-velocity-port PORT]
       [--mission-start-host HOST] [--mission-start-port PORT]
       [--dump-interval SECONDS] [--debug]
"""

from __future__ import annotations

import argparse
import logging
import threading
import time

from api.server import DEFAULT_HOST as API_DEFAULT_HOST
from api.server import DEFAULT_PORT as API_DEFAULT_PORT
from api.server import TelemetryAPIServer
from collector.arg_read_broker import ArgReadBroker
from collector.audio_sender import AudioPlaybackSender
from collector.cache import (
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
from collector.command_sender import DEFAULT_HOST as COMMAND_DEFAULT_HOST
from collector.command_sender import DEFAULT_PORT as COMMAND_DEFAULT_PORT
from collector.command_sender import (
    LOOK_DIRECTION_DEFAULT_HOST,
    LOOK_DIRECTION_DEFAULT_PORT,
    CommandSender,
    LookDirectionSender,
)
from collector.firing_receiver import DEFAULT_HOST as FIRING_DEFAULT_HOST
from collector.firing_receiver import DEFAULT_PORT as FIRING_DEFAULT_PORT
from collector.firing_receiver import EmitterTracker, FiringEventsReceiver
from collector.line_of_sight_receiver import DEFAULT_HOST as LOS_DEFAULT_HOST
from collector.line_of_sight_receiver import DEFAULT_PORT as LOS_DEFAULT_PORT
from collector.line_of_sight_receiver import LineOfSightReceiver
from collector.mission_start_receiver import (
    DEFAULT_HOST as MISSION_START_DEFAULT_HOST,
)
from collector.mission_start_receiver import (
    DEFAULT_PORT as MISSION_START_DEFAULT_PORT,
)
from collector.mission_start_receiver import MissionStartReceiver
from collector.server import DEFAULT_HOST, DEFAULT_PORT, CollectorServer
from collector.unit_velocity_receiver import DEFAULT_HOST as UNIT_VELOCITY_DEFAULT_HOST
from collector.unit_velocity_receiver import DEFAULT_PORT as UNIT_VELOCITY_DEFAULT_PORT
from collector.unit_velocity_receiver import UnitVelocityReceiver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help="Export.lua listener host (loopback)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Export.lua listener port"
    )
    parser.add_argument(
        "--api-host", default=API_DEFAULT_HOST, help="Mac-facing LAN API host"
    )
    parser.add_argument(
        "--api-port", type=int, default=API_DEFAULT_PORT, help="Mac-facing LAN API port"
    )
    parser.add_argument(
        "--command-host",
        default=COMMAND_DEFAULT_HOST,
        help="Export.lua's inbound command listener host (loopback)",
    )
    parser.add_argument(
        "--command-port",
        type=int,
        default=COMMAND_DEFAULT_PORT,
        help="Export.lua's inbound command listener port",
    )
    parser.add_argument(
        "--unit-velocity-host",
        default=UNIT_VELOCITY_DEFAULT_HOST,
        help="mission-telemetry Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--unit-velocity-port",
        type=int,
        default=UNIT_VELOCITY_DEFAULT_PORT,
        help="mission-telemetry Hook script's UDP sender port",
    )
    parser.add_argument(
        "--line-of-sight-host",
        default=LOS_DEFAULT_HOST,
        help="line-of-sight Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--line-of-sight-port",
        type=int,
        default=LOS_DEFAULT_PORT,
        help="line-of-sight Hook script's UDP sender port",
    )
    parser.add_argument(
        "--look-direction-host",
        default=LOOK_DIRECTION_DEFAULT_HOST,
        help="line-of-sight Hook script's inbound command listener host (loopback)",
    )
    parser.add_argument(
        "--look-direction-port",
        type=int,
        default=LOOK_DIRECTION_DEFAULT_PORT,
        help="line-of-sight Hook script's inbound command listener port",
    )
    parser.add_argument(
        "--mission-start-host",
        default=MISSION_START_DEFAULT_HOST,
        help="mission-start Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--mission-start-port",
        type=int,
        default=MISSION_START_DEFAULT_PORT,
        help="mission-start Hook script's UDP sender port",
    )
    parser.add_argument(
        "--firing-host",
        default=FIRING_DEFAULT_HOST,
        help="firing-events Hook script's UDP sender host (loopback)",
    )
    parser.add_argument(
        "--firing-port",
        type=int,
        default=FIRING_DEFAULT_PORT,
        help="firing-events Hook script's UDP sender port",
    )
    parser.add_argument(
        "--dump-interval",
        type=float,
        default=1.0,
        help="seconds between stdout dumps of the latest sample",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="log every received line and parse result (DEBUG level)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    cache = TelemetryCache()
    world_objects_cache = WorldObjectsCache()
    petrovich_indication_cache = PetrovichIndicationCache()
    petrovich_wheel_cache = PetrovichWheelCache()
    command_sender = CommandSender(host=args.command_host, port=args.command_port)
    command_sender.open()
    unit_velocity_cache = UnitVelocityCache()
    unit_velocity_receiver = UnitVelocityReceiver(
        unit_velocity_cache, host=args.unit_velocity_host, port=args.unit_velocity_port
    )
    unit_velocity_receiver.open()
    unit_velocity_receiver_thread = threading.Thread(
        target=unit_velocity_receiver.serve_forever, daemon=True
    )
    unit_velocity_receiver_thread.start()
    line_of_sight_cache = LineOfSightCache()
    line_of_sight_receiver = LineOfSightReceiver(
        line_of_sight_cache,
        host=args.line_of_sight_host,
        port=args.line_of_sight_port,
    )
    line_of_sight_receiver.open()
    line_of_sight_receiver_thread = threading.Thread(
        target=line_of_sight_receiver.serve_forever, daemon=True
    )
    line_of_sight_receiver_thread.start()
    mission_start_cache = MissionStartCache()
    mission_start_receiver = MissionStartReceiver(
        mission_start_cache,
        host=args.mission_start_host,
        port=args.mission_start_port,
    )
    mission_start_receiver.open()
    mission_start_receiver_thread = threading.Thread(
        target=mission_start_receiver.serve_forever, daemon=True
    )
    mission_start_receiver_thread.start()
    look_direction_sender = LookDirectionSender(
        host=args.look_direction_host, port=args.look_direction_port
    )
    look_direction_sender.open()
    emitter_tracker = EmitterTracker()
    firing_events_receiver = FiringEventsReceiver(
        emitter_tracker, host=args.firing_host, port=args.firing_port
    )
    firing_events_receiver.open()
    firing_events_receiver_thread = threading.Thread(
        target=firing_events_receiver.serve_forever, daemon=True
    )
    firing_events_receiver_thread.start()

    # One cache, handed to both halves: the collector fills it from
    # Export.lua's ptt lines and the API serves it to the capture process.
    ptt_cache = PttCache()

    # Same shape as ptt_cache above, plus `AudioPlaybackSender`'s gate/
    # volume provider (`plans/spu8-intercom/plan.md` Stage 3) -- real
    # wiring passes `spu8_cache.gate_state` (fail-safe-closed when no SPU-8
    # sample has arrived yet, matching Stage 2's capture-gating default),
    # unlike `AudioPlaybackSender`'s own constructor default (`_always_open`)
    # which exists only for pre-existing call sites/tests.
    spu8_cache = Spu8Cache()
    audio_sender = AudioPlaybackSender(gate_state=spu8_cache.gate_state)
    audio_sender.open()

    # `plans/effector-sequences/plan.md` Stage 4 -- replaces the former
    # cockpit_switch_cache. Reuses command_sender (above) for the install
    # side (POST /command/watch_args); the one-shot read side
    # (POST /query/read_args) is arg_read_broker below, which also drives
    # command_sender directly (its own send_read_args).
    watched_args_cache = WatchedArgsCache()
    arg_read_broker = ArgReadBroker(command_sender)
    # `[[BL-B80]]` v2 -- the DCS-slave servo's own status feed, a second
    # cache from watched_args_cache above (see `schema.sight_servo`'s
    # own "Departure, stated").
    sight_servo_cache = SightServoCache()
    # `[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md` Stage 4 -- the ownship
    # loadout feed, same "latest of one, fed on change" shape as every
    # cache above.
    payload_cache = PayloadCache()

    collector = CollectorServer(
        cache,
        world_objects_cache,
        petrovich_indication_cache,
        petrovich_wheel_cache,
        ptt_cache=ptt_cache,
        spu8_cache=spu8_cache,
        sight_servo_cache=sight_servo_cache,
        watched_args_cache=watched_args_cache,
        arg_read_broker=arg_read_broker,
        payload_cache=payload_cache,
        host=args.host,
        port=args.port,
    )
    collector.open()
    collector_thread = threading.Thread(target=collector.serve_forever, daemon=True)
    collector_thread.start()

    api = TelemetryAPIServer(
        cache,
        world_objects_cache,
        host=args.api_host,
        port=args.api_port,
        petrovich_indication_cache=petrovich_indication_cache,
        petrovich_wheel_cache=petrovich_wheel_cache,
        command_sender=command_sender,
        audio_sender=audio_sender,
        unit_velocity_cache=unit_velocity_cache,
        ptt_cache=ptt_cache,
        spu8_cache=spu8_cache,
        line_of_sight_cache=line_of_sight_cache,
        look_direction_sender=look_direction_sender,
        emitter_tracker=emitter_tracker,
        mission_start_cache=mission_start_cache,
        watched_args_cache=watched_args_cache,
        sight_servo_cache=sight_servo_cache,
        arg_read_broker=arg_read_broker,
        payload_cache=payload_cache,
    )
    api.open()
    api_thread = threading.Thread(target=api.serve_forever, daemon=True)
    api_thread.start()

    try:
        while True:
            time.sleep(args.dump_interval)
            sample = cache.latest()
            logger.debug(sample if sample is not None else "(no sample received yet)")
    except KeyboardInterrupt:
        pass
    finally:
        api.close()
        collector.close()
        command_sender.close()
        audio_sender.close()
        unit_velocity_receiver.close()
        line_of_sight_receiver.close()
        look_direction_sender.close()
        firing_events_receiver.close()
        mission_start_receiver.close()


if __name__ == "__main__":
    main()
