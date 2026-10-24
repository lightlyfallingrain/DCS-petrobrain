"""Collector-side sender for the Petrovich-search command channel (BL-6,
`plans/bl6-commands-inspect-adapt/plan.md`).

The collector fires a small JSON command at `Export.lua`'s new inbound
UDP listener over loopback, the "collector -> Export.lua" direction.

**`send_command` raises on failure, deliberately:** it drives a real
effector (Petrovich's AI Wheel), and a dropped command is a real
behavioral gap the caller needs to know about, not a state to silently
swallow -- unlike a display-only write, where losing one line is
cosmetic. `send_command` therefore raises `CommandSendError` on a
clearly-failed send (an `OSError` from the underlying socket). Note this
still cannot promise the command *worked* -- UDP is fire-and-forget, so a
`send_command` call that does not raise means only "the datagram was
handed to the OS," never "Petrovich actually searched." Live confirmation
of that is `GET /petrovich_wheel/latest`'s job, not this sender's."""

from __future__ import annotations

import json
import logging
import socket
from types import TracebackType
from typing import Literal, Self

logger = logging.getLogger(__name__)


def _format_fixed_point(value: float) -> str:
    """Render `value` as fixed-point decimal, never exponent notation --
    `json.dumps` emits exponent form for small magnitudes
    (`json.dumps({'x': 0.00001})` -> `'{"x": 1e-05}'`), which
    `Export.lua`'s `extract_json_number_field` pattern-matched straight
    past the "e" and silently truncated (`"1e-05"` parsed as `1`,
    `"-3.3e-07"` as `-3.3` -- a 60deg-equivalent sight-slew command from
    a near-zero intent). BL-B80 exponent-float fix, 2026-10-22. 9 decimal
    places is ample precision for every value on this channel (raw
    `-1.5..1.5` sight/cockpit-switch commands); trailing zeros are
    trimmed but at least one digit after the point is kept so the result
    is still a valid JSON number token (`"0.0"`, never `"0."`)."""
    text = f"{value:.9f}"
    if "." in text:
        text = text.rstrip("0")
        if text.endswith("."):
            text += "0"
    return text


#: Loopback only -- `Export.lua`'s new inbound command listener runs inside
#: the same DCS process tree as the collector's UDP peer. A distinct port
#: from `collector.server.DEFAULT_PORT` (Export.lua -> collector, TCP) and
#: 7792 (formerly `collector.text_sender.TextOverlaySender`'s
#: collector -> overlay Hook script UDP channel, retired by `BL-B96`) --
#: this is a third, separate loopback channel.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7793

#: Petrovich search mode -- `"forward"` (`SRCH FWD`, a long wheel-button
#: hold) or `"boresight"` (`SRCH BRST`, a short press). Matches
#: `aircraft_client.AircraftLayerClient.trigger_petrovich_search`'s own
#: `Literal` exactly, the type flowing unchanged from body-layer's tool call
#: through this sender to Export.lua's JSON command.
SearchMode = Literal["forward", "boresight"]


class CommandSendError(RuntimeError):
    """Raised when `CommandSender.send_command` cannot hand its datagram to
    the OS -- see the module docstring for why this sender does not
    swallow that failure."""


class CommandSender:
    """Sends short JSON command datagrams to `Export.lua`'s inbound command
    listener over UDP. Open-once/close-on-shutdown lifecycle, even though
    UDP is connectionless."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None

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

    def open(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def send_command(self, mode: SearchMode) -> None:
        """Send `{"op": "petrovich_search", "mode": mode}` to `Export.lua`'s
        command listener. Raises `CommandSendError` if the underlying socket
        send fails (see the module docstring for why this call does not
        swallow that failure)."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        payload = json.dumps({"op": "petrovich_search", "mode": mode}).encode("utf-8")
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "petrovich-search command send failed: mode=%r", mode, exc_info=True
            )
            raise CommandSendError(f"failed to send command {mode!r}: {exc}") from exc

    def send_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        """Send `{"op": "cockpit_switch", "device": device, "cmd": cmd,
        "value": value}` to `Export.lua`'s command listener -- the generic
        cockpit-write channel (`plans/9k113-effectors/plan.md`, BL-B66
        Stage 1). Structurally identical to `send_command` above, same
        `CommandSendError` posture (see the module docstring): a dropped
        9K113 switch write is a real behavioral gap, not an opaque display
        string to swallow.

        **No validation happens here** -- same division of labour as
        `LookDirectionSender.send_look_direction`'s own docstring:
        `api.server`'s `POST /command/cockpit_switch` handler validates
        shape (device/cmd integers, value finite) before this method is
        ever called, and `Export.lua`'s own dispatch
        (`handle_cockpit_switch_command`) validates a third time. There is
        **no allow-list of which `(device, cmd)` pairs are accepted** at
        any of those three layers -- user direction 2026-10-21, overriding
        the security plan review's required fix; see `aircraft-layer/
        CLAUDE.md`'s "What this is" section for the quote.

        `value` is hand-formatted via `_format_fixed_point`, not
        `json.dumps`, so it never reaches `Export.lua` in exponent
        notation (see that helper's docstring -- BL-B80 exponent-float
        fix, 2026-10-22)."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        payload = (
            f'{{"op": "cockpit_switch", "device": {device}, "cmd": {cmd}, '
            f'"value": {_format_fixed_point(value)}}}'
        ).encode()
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "cockpit-switch command send failed: device=%r cmd=%r value=%r",
                device,
                cmd,
                value,
                exc_info=True,
            )
            raise CommandSendError(
                f"failed to send cockpit switch device={device!r} cmd={cmd!r} "
                f"value={value!r}: {exc}"
            ) from exc

    def send_sight_target(
        self,
        goal_az_deg: float,
        goal_el_deg: float,
        goal_rate_az_deg_s: float,
        goal_rate_el_deg_s: float,
        t_sim: float,
    ) -> None:
        """Send `{"op": "sight_target", "goal_az_deg": ..., "goal_el_deg":
        ..., "goal_rate_az_deg_s": ..., "goal_rate_el_deg_s": ...,
        "t_sim": ...}` to `Export.lua`'s command listener -- the 9K113
        pointing channel (`plans/9k113-sight-pointing/plan.md`, BL-B80
        v2). A **persistent** world goal, unlike `send_cockpit_switch`'s
        one-shot write: `Export.lua` caches it and its own per-frame
        servo rate-limits a setpoint toward it while OBSERV reads on
        (that plan's "Architecture" section on why this is a third,
        narrow op rather than reusing `cockpit_switch`'s "write once now"
        semantics). Same `CommandSendError` posture as `send_cockpit_
        switch`: a dropped goal update is a real behavioral gap, not an
        opaque display string to swallow.

        **No validation happens here** -- same division of labour as
        `send_cockpit_switch`'s own docstring: `api.server`'s `POST
        /command/sight_target` handler validates shape (every value
        finite, in range, including `t_sim`'s own bound -- the security
        plan review's required change) before this method is ever
        called.

        Every field is hand-formatted via `_format_fixed_point`, not
        `json.dumps`, so none ever reaches `Export.lua` in exponent
        notation (see that helper's docstring -- BL-B80 exponent-float
        fix, 2026-10-22): body-layer float arithmetic near sight centre
        readily produces values below `1e-4`, exactly the magnitude
        `json.dumps` switches to exponent form for."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        payload = (
            f'{{"op": "sight_target", "goal_az_deg": {_format_fixed_point(goal_az_deg)}, '
            f'"goal_el_deg": {_format_fixed_point(goal_el_deg)}, '
            f'"goal_rate_az_deg_s": {_format_fixed_point(goal_rate_az_deg_s)}, '
            f'"goal_rate_el_deg_s": {_format_fixed_point(goal_rate_el_deg_s)}, '
            f'"t_sim": {_format_fixed_point(t_sim)}}}'
        ).encode()
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "sight-target command send failed: goal_az_deg=%r goal_el_deg=%r "
                "goal_rate_az_deg_s=%r goal_rate_el_deg_s=%r t_sim=%r",
                goal_az_deg,
                goal_el_deg,
                goal_rate_az_deg_s,
                goal_rate_el_deg_s,
                t_sim,
                exc_info=True,
            )
            raise CommandSendError(
                f"failed to send sight target goal_az_deg={goal_az_deg!r} "
                f"goal_el_deg={goal_el_deg!r} t_sim={t_sim!r}: {exc}"
            ) from exc

    def send_watch_args(self, watch_id: str, args: list[int]) -> None:
        """Send `{"op": "watch_args", "watch_id": watch_id, "args": args}`
        to `Export.lua`'s command listener -- the continuous watched-args
        channel (`plans/effector-sequences/plan.md` Stage 4). Installs a
        replacement watched set whole, never a merge -- see `Export.lua`'s
        own `handle_watch_args_command`. Same `CommandSendError` posture
        as `send_cockpit_switch`/`send_sight_target`.

        **No validation happens here** -- same division of labour as
        `send_cockpit_switch`'s own docstring: `api.server`'s `POST
        /command/watch_args` handler validates shape (watch_id pattern,
        args non-bool ints in 0..4095, deduped, <= 64) before this method
        is ever called, and `Export.lua`'s own `parse_arg_list` validates
        a third time."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        args_text = ",".join(str(int(a)) for a in args)
        payload = (
            f'{{"op": "watch_args", "watch_id": "{watch_id}", "args": [{args_text}]}}'
        ).encode()
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "watch_args command send failed: watch_id=%r args=%r",
                watch_id,
                args,
                exc_info=True,
            )
            raise CommandSendError(
                f"failed to send watch_args watch_id={watch_id!r}: {exc}"
            ) from exc

    def send_read_args(self, read_id: str, args: list[int]) -> None:
        """Send `{"op": "read_args", "read_id": read_id, "args": args}` to
        `Export.lua`'s command listener -- the one-shot read channel
        (`plans/effector-sequences/plan.md` Stage 4, S4.2). The reply does
        not come back on this UDP socket -- it arrives on the existing
        Export.lua<->collector TCP connection
        (`collector.arg_read_broker.ArgReadBroker` is the one caller of
        this method, and is also the one piece of code that waits for that
        reply). Same `CommandSendError` posture as `send_watch_args`."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        args_text = ",".join(str(int(a)) for a in args)
        payload = (
            f'{{"op": "read_args", "read_id": "{read_id}", "args": [{args_text}]}}'
        ).encode()
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "read_args command send failed: read_id=%r args=%r",
                read_id,
                args,
                exc_info=True,
            )
            raise CommandSendError(
                f"failed to send read_args read_id={read_id!r}: {exc}"
            ) from exc


#: Loopback only -- `petrobrain-line-of-sight-hook.lua`'s own inbound
#: listener runs inside the same DCS process tree as the collector's UDP
#: peer, same reasoning as `DEFAULT_HOST`/`DEFAULT_PORT` above. **Not**
#: `Export.lua`'s command listener (`DEFAULT_PORT` above) -- this directive
#: has to land in the mission-scripting state (`land.*`/`world.*` live
#: there, not in the Export state Export.lua runs in), so it is a
#: Hook-script-owned socket, structurally like the retired overlay Hook
#: script's inbound listener was, not Export.lua's (`plans/dcs-driven-los/
#: plan.md` SS9a). A distinct loopback port: `collector.server.
#: DEFAULT_PORT` (7790), 7792 (formerly `text_sender.TextOverlaySender`,
#: retired by `BL-B96`), this module's
#: own `DEFAULT_PORT` (7793), 7794 (formerly the F10 command channel,
#: retired by `BL-B96`), `unit_velocity_receiver.DEFAULT_PORT` (7795),
#: `line_of_sight_receiver.DEFAULT_PORT` (7796), and this one (7797).
LOOK_DIRECTION_DEFAULT_HOST = "127.0.0.1"
LOOK_DIRECTION_DEFAULT_PORT = 7797


class LookDirectionSender:
    """Sends short JSON look-direction command datagrams to the LOS Hook
    script's inbound listener over UDP (`plans/dcs-driven-los/plan.md`
    SS9b). Structurally mirrors `CommandSender`'s open-once/
    close-on-shutdown lifecycle and its raise-on-failure posture -- a
    dropped look-direction push is a real coverage gap (the cone can go
    stale, plan SS9c), not an opaque display string to swallow silently.

    **No validation happens here** -- `api.server`'s `POST /command/
    look_direction` handler validates `hour`/`fov_half_deg` before this
    method is ever called, and the Hook script itself validates and clamps
    a third time (defense in depth, the Security plan review's Finding 4).
    This sender's only job is putting already-validated integers on the
    wire."""

    def __init__(
        self,
        host: str = LOOK_DIRECTION_DEFAULT_HOST,
        port: int = LOOK_DIRECTION_DEFAULT_PORT,
    ) -> None:
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None

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

    def open(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def send_look_direction(self, hour: int, fov_half_deg: int) -> None:
        """Send `{"op": "look_direction", "hour": hour, "fov_half_deg":
        fov_half_deg}` to the LOS Hook script's inbound listener. Raises
        `CommandSendError` if the underlying socket send fails -- see this
        class's own docstring for why this does not swallow that
        failure."""
        if self._socket is None:
            self.open()
        sock = self._socket
        assert sock is not None  # `open()` above always sets it

        payload = json.dumps(
            {"op": "look_direction", "hour": hour, "fov_half_deg": fov_half_deg}
        ).encode("utf-8")
        try:
            sock.sendto(payload, (self._host, self._port))
        except OSError as exc:
            logger.warning(
                "look-direction command send failed: hour=%r fov_half_deg=%r",
                hour,
                fov_half_deg,
                exc_info=True,
            )
            raise CommandSendError(
                f"failed to send look direction hour={hour!r} "
                f"fov_half_deg={fov_half_deg!r}: {exc}"
            ) from exc
