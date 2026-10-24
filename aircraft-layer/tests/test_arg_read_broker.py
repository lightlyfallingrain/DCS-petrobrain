"""`collector.arg_read_broker.ArgReadBroker` -- the one-shot read path's
collector-side correlation point (`plans/effector-sequences/plan.md`
Stage 4, S4.2). Against a fake `CommandSender` that "replies" on a
background thread, since `ArgReadBroker.read` blocks the calling thread
for real."""

from __future__ import annotations

import threading
import time

import pytest

from collector.arg_read_broker import (
    MAX_OUTSTANDING_READS,
    ArgReadBroker,
    ArgReadBrokerBusy,
    ArgReadTimeout,
)
from collector.command_sender import CommandSender, CommandSendError


class _FakeCommandSender(CommandSender):
    """Records every `send_read_args` call; a test drives replies itself
    by calling `broker.handle_reply_line` on a background thread, so
    neither this double nor `ArgReadBroker` needs a real socket."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_read_ids: list[tuple[str, list[int]]] = []
        self.raise_on_send = False

    def send_read_args(  # type: ignore[override]
        self, read_id: str, args: list[int]
    ) -> None:
        if self.raise_on_send:
            raise CommandSendError("simulated send failure")
        self.sent_read_ids.append((read_id, list(args)))


def _reply_after(
    broker: ArgReadBroker,
    sender: _FakeCommandSender,
    delay_s: float,
    values: dict[str, float],
    t: float = 5.0,
) -> None:
    """Waits for `sender.sent_read_ids` to have an entry, then replies to
    the *latest* one after `delay_s` -- mirrors Export.lua answering on
    its own frame, from a background thread so the test's own call to
    `broker.read` can block for real."""

    baseline = len(sender.sent_read_ids)

    def _worker() -> None:
        deadline = time.monotonic() + 2.0
        while len(sender.sent_read_ids) <= baseline and time.monotonic() < deadline:
            time.sleep(0.005)
        assert len(sender.sent_read_ids) > baseline, "no new read_args was ever sent"
        read_id = sender.sent_read_ids[-1][0]
        time.sleep(delay_s)
        broker.handle_reply_line({"t": t, "read_id": read_id, "values": values})

    threading.Thread(target=_worker, daemon=True).start()


class TestArgReadBrokerSuccess:
    def test_read_returns_validated_values(self) -> None:
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)
        _reply_after(broker, sender, 0.01, {"773": 1.0, "761": 0.0})

        result = broker.read([773, 761])

        assert result.dcs_model_time_s == pytest.approx(5.0)
        assert result.values == {773: 1.0, 761: 0.0}
        assert sender.sent_read_ids[0][1] == [773, 761]


class TestArgReadBrokerTimeout:
    def test_no_reply_times_out(self) -> None:
        """*Mutation*: no timeout -- this test bounds its own wall time,
        so a version that blocks forever (no `ARG_READ_TIMEOUT_S` wait)
        would hang the test suite rather than merely failing."""
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)

        started = time.monotonic()
        with pytest.raises(ArgReadTimeout):
            broker.read([886])
        elapsed = time.monotonic() - started
        assert elapsed < 2.0  # bounded, not hung

    def test_a_late_reply_after_timeout_is_dropped(self) -> None:
        """A reply arriving after the broker already gave up must not
        raise or corrupt a later, unrelated read."""
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)

        with pytest.raises(ArgReadTimeout):
            broker.read([886])

        # The slot is already gone; a stale reply for it is a no-op.
        broker.handle_reply_line({"t": 1.0, "read_id": "doesnotexist", "values": {}})

        # A subsequent, independent read still works normally.
        _reply_after(broker, sender, 0.01, {"886": 1.0})
        result = broker.read([886])
        assert result.values == {886: 1.0}


class TestArgReadBrokerBusyLimit:
    def test_ninth_concurrent_request_is_refused(self) -> None:
        """At most `MAX_OUTSTANDING_READS` reads outstanding at once; a
        request beyond that raises `ArgReadBrokerBusy` immediately
        rather than queueing."""
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)

        threads: list[threading.Thread] = []
        errors: list[BaseException] = []

        def _hold_a_slot() -> None:
            try:
                broker.read([886])
            except ArgReadTimeout:
                pass
            except BaseException as exc:  # noqa: BLE001 - recorded, not swallowed
                errors.append(exc)

        for _ in range(MAX_OUTSTANDING_READS):
            thread = threading.Thread(target=_hold_a_slot, daemon=True)
            threads.append(thread)
            thread.start()

        # Give the `MAX_OUTSTANDING_READS` threads a moment to register
        # their slots before the next one checks capacity.
        deadline = time.monotonic() + 2.0
        while (
            len(sender.sent_read_ids) < MAX_OUTSTANDING_READS
            and time.monotonic() < deadline
        ):
            time.sleep(0.005)
        assert len(sender.sent_read_ids) == MAX_OUTSTANDING_READS

        with pytest.raises(ArgReadBrokerBusy):
            broker.read([886])

        for thread in threads:
            thread.join(timeout=2.0)
        assert errors == []


class TestArgReadBrokerSendFailure:
    def test_send_failure_leaves_no_slot_behind(self) -> None:
        """No datagram was ever sent, so the slot must not leak --
        verified by confirming a full `MAX_OUTSTANDING_READS` worth of
        later reads can still proceed (each times out on its own, rather
        than being refused as busy from a leaked slot)."""
        sender = _FakeCommandSender()
        sender.raise_on_send = True
        broker = ArgReadBroker(sender)

        with pytest.raises(CommandSendError):
            broker.read([886])

        sender.raise_on_send = False
        # If the failed attempt had leaked a slot, this would eventually
        # raise ArgReadBrokerBusy instead of ArgReadTimeout.
        with pytest.raises(ArgReadTimeout):
            broker.read([886])


class TestArgReadBrokerReplyValidation:
    """Security plan review required change 1, mirrored at the collector
    (A10): the same cases A9/E9 cover for the HTTP body are validated
    here on the `"read_id"` line itself."""

    @pytest.mark.parametrize(
        "values",
        [
            {"886": float("nan")},
            {"886": float("inf")},
            {"886": True},
            {"abc": 1.0},
            {"-1": 1.0},
            {"4096": 1.0},
        ],
    )
    def test_malformed_values_are_dropped_request_times_out(
        self, values: dict[str, object]
    ) -> None:
        """*Mutation*: drop `math.isfinite` inside `parse_arg_values` --
        a NaN value would then reach `result.values` rather than being
        dropped, and the request would succeed instead of timing out."""
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)
        _reply_after(broker, sender, 0.01, values)  # type: ignore[arg-type]

        with pytest.raises(ArgReadTimeout):
            broker.read([886])

    def test_65_keys_is_dropped(self) -> None:
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)
        values = {str(n): 0.0 for n in range(65)}
        _reply_after(broker, sender, 0.01, values)

        with pytest.raises(ArgReadTimeout):
            broker.read([886])

    def test_values_not_an_object_is_dropped(self) -> None:
        sender = _FakeCommandSender()
        broker = ArgReadBroker(sender)

        def _worker() -> None:
            deadline = time.monotonic() + 2.0
            while not sender.sent_read_ids and time.monotonic() < deadline:
                time.sleep(0.005)
            read_id = sender.sent_read_ids[-1][0]
            broker.handle_reply_line({"t": 1.0, "read_id": read_id, "values": [1, 2]})

        threading.Thread(target=_worker, daemon=True).start()
        with pytest.raises(ArgReadTimeout):
            broker.read([886])
