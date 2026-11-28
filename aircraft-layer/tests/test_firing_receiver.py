"""Tests for `collector.firing_receiver.EmitterTracker`/`FiringEventsReceiver`
-- `plans/emitter-visibility/plan.md` Stage B, `AC-B8`."""

from __future__ import annotations

import json
import socket
import threading
import time

from collector.firing_receiver import (
    EMITTER_KIND_FIRING,
    EMITTER_KIND_LAUNCH_FLASH,
    FIRING_MIN_VISIBLE_S,
    FIRING_WATCHDOG_S,
    LAUNCH_FLASH_DURATION_S,
    OWN_WEAPON_LEDGER_CAP,
    OWN_WEAPON_RETENTION_S,
    EmitterTracker,
    FiringEventsReceiver,
    OwnWeaponLedger,
)
from schema.firing import FiringEventBatch, FiringRawEvent, OwnWeaponRawEvent


def _batch(t_sim: float, *events: FiringRawEvent) -> FiringEventBatch:
    return FiringEventBatch(
        dcs_model_time_s=t_sim,
        received_wall_clock_s=0.0,
        bridge_call_ms=0.0,
        events=tuple(events),
    )


def _start(
    initiator: str, t_sim: float, targets_ownship: bool = False
) -> FiringRawEvent:
    return FiringRawEvent(
        kind="S_EVENT_SHOOTING_START",
        t_sim=t_sim,
        initiator=initiator,
        targets_ownship=targets_ownship,
        x=None,
        z=None,
    )


def _end(initiator: str, t_sim: float) -> FiringRawEvent:
    return FiringRawEvent(
        kind="S_EVENT_SHOOTING_END",
        t_sim=t_sim,
        initiator=initiator,
        targets_ownship=False,
        x=None,
        z=None,
    )


def _dead(initiator: str, t_sim: float) -> FiringRawEvent:
    return FiringRawEvent(
        kind="S_EVENT_DEAD",
        t_sim=t_sim,
        initiator=initiator,
        targets_ownship=False,
        x=None,
        z=None,
    )


def test_a_start_opens_an_entry() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))

    snapshot = tracker.snapshot()
    assert snapshot["dcs_model_time_s"] == 100.0
    active = snapshot["active"]
    assert isinstance(active, dict)
    assert active["Unit_1"]["kind"] == EMITTER_KIND_FIRING
    assert active["Unit_1"]["targets_ownship"] is False


def test_targets_ownship_is_carried_through() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0, targets_ownship=True)))

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert active["Unit_1"]["targets_ownship"] is True


def test_a_sub_poll_burst_start_and_end_in_the_same_batch_survives_one_poll() -> None:
    """The plan's own latch requirement: `START`/`END` landing in the same
    drained batch must not be discarded as already-over."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.2), _end("Unit_1", 100.3)))

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active

    # Still visible at the very next poll (one second later, under
    # FIRING_MIN_VISIBLE_S's own margin).
    tracker.ingest(_batch(101.0))
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active


def test_end_after_a_long_burst_closes_on_the_next_poll_at_the_latest() -> None:
    """`expires_at_sim = max(now, since_sim + FIRING_MIN_VISIBLE_S)` sets
    the expiry to exactly `now` when the burst already ran long -- which
    survives *this* poll (pruning is strict: `now > expires_at_sim`, not
    `>=`) but is gone on the very next one, matching the plan's own
    "gone on the next poll at the latest.\""""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))
    # The unit has been firing well beyond FIRING_MIN_VISIBLE_S by the
    # time END arrives.
    long_after = 100.0 + FIRING_MIN_VISIBLE_S + 5.0
    tracker.ingest(_batch(long_after, _end("Unit_1", long_after)))

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active

    tracker.ingest(_batch(long_after + 0.1))
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" not in active


def test_a_start_with_no_end_is_bounded_by_the_watchdog() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))

    # Just before the watchdog expires, still present.
    tracker.ingest(_batch(100.0 + FIRING_WATCHDOG_S - 0.1))
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active

    # Past the watchdog, gone -- no END, no DEAD, nothing but time.
    tracker.ingest(_batch(100.0 + FIRING_WATCHDOG_S + 0.1))
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" not in active


def test_dead_removes_the_entry_immediately_regardless_of_watchdog() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))
    tracker.ingest(_batch(100.5, _dead("Unit_1", 100.5)))

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" not in active


def test_a_unit_still_firing_past_the_former_ten_second_floor_stays_visible() -> None:
    """Pins the fix for the review's required finding (`AC-B8`/`BL-B73` Stage
    B review): the watchdog must not end a sighting while the unit is still
    genuinely firing. `10.0` was the old `FIRING_WATCHDOG_S` -- a sustained
    burst with no further event at all (no `END`, no `DEAD`/`CRASH`) must
    still be visible well past that old floor, because "no further event"
    does not mean "nothing is happening"; it can mean the unit is mid-burst
    and `S_EVENT_SHOOTING_START` never retriggers."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))

    tracker.ingest(_batch(100.0 + 10.0 + 0.1))  # past the old watchdog floor
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active


def test_dead_during_a_sustained_burst_removes_the_entry_immediately() -> None:
    """The other half of the distinction the review's finding draws: a unit
    destroyed mid-burst is removed by the death path, not by the watchdog,
    at any point in the burst -- including well past the old 10s floor,
    where the watchdog alone would have left it visible for a while yet."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))
    tracker.ingest(_batch(100.0 + 10.0 + 0.1))  # still firing, past old floor
    assert "Unit_1" in tracker.snapshot()["active"]  # type: ignore[operator]

    tracker.ingest(_batch(100.0 + 10.0 + 0.2, _dead("Unit_1", 100.0 + 10.0 + 0.2)))
    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" not in active


def test_dead_for_an_untracked_unit_is_a_no_op() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _dead("Unit_never_fired", 100.0)))

    active = tracker.snapshot()["active"]
    assert active == {}


def test_two_units_track_independently() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0), _start("Unit_2", 100.0)))
    tracker.ingest(_batch(100.5, _dead("Unit_1", 100.5)))

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" not in active
    assert "Unit_2" in active


def test_a_mission_restart_clears_every_tracked_entry() -> None:
    """`dcs_model_time_s` regressing by more than the tolerance band is
    treated as a mission boundary -- "no entry survives a mission
    boundary" (plan)."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(500.0, _start("Unit_1", 500.0)))
    assert "Unit_1" in tracker.snapshot()["active"]  # type: ignore[operator]

    tracker.ingest(_batch(0.5))  # new mission, timer.getTime() reset

    active = tracker.snapshot()["active"]
    assert active == {}


def test_harmless_jitter_within_tolerance_does_not_clear_state() -> None:
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("Unit_1", 100.0)))
    tracker.ingest(_batch(99.9))  # 0.1s regression, well under tolerance

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active


def _shot(initiator: str, t_sim: float) -> FiringRawEvent:
    return FiringRawEvent(
        kind="S_EVENT_SHOT",
        t_sim=t_sim,
        initiator=initiator,
        targets_ownship=False,
        x=1.0,
        z=2.0,
    )


def test_shot_event_creates_a_launch_flash_entry() -> None:
    """`[[BL-B124]]` Stage 5 -- `S_EVENT_SHOT` (missile/rocket launch,
    treated the same for both per the user's own words) now creates a
    `LAUNCH_FLASH` entry at the launcher's own name, superseding the
    `[[BL-B74]]`-seam no-op this test used to assert."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _shot("SAM-1", 100.0)))

    active = tracker.snapshot()["active"]
    assert active == {
        "SAM-1": {
            "kind": EMITTER_KIND_LAUNCH_FLASH,
            "since_sim": 100.0,
            "targets_ownship": False,
        }
    }


def test_launch_flash_expires_after_its_own_fixed_window() -> None:
    """Unlike `FIRING`, `LAUNCH_FLASH` is never watchdog-extended by
    further events -- a fixed `LAUNCH_FLASH_DURATION_S` window from the
    shot's own `t_sim`."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _shot("SAM-1", 100.0)))
    assert "SAM-1" in tracker.snapshot()["active"]  # type: ignore[operator]

    tracker.ingest(_batch(100.0 + LAUNCH_FLASH_DURATION_S + 0.1))
    assert tracker.snapshot()["active"] == {}


def test_shot_event_does_not_overwrite_an_existing_firing_entry() -> None:
    """A unit already tracked as gun-firing (`S_EVENT_SHOOTING_START`)
    that then launches a missile/rocket stays `FIRING` -- its own
    watchdog is the longer-lived, more informative visibility state, and
    overwriting it with a short `LAUNCH_FLASH` window would make a
    sustained engagement go dark early."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _start("SAM-1", 100.0)))
    tracker.ingest(_batch(100.1, _shot("SAM-1", 100.1)))

    active = tracker.snapshot()["active"]
    assert active["SAM-1"]["kind"] == EMITTER_KIND_FIRING  # type: ignore[index]


def test_death_removes_a_launch_flash_entry_like_firing() -> None:
    """`S_EVENT_DEAD`/`S_EVENT_CRASH` remove a `LAUNCH_FLASH` entry
    outright too, independent of its own watchdog -- same reasoning as
    the existing `FIRING` removal."""
    tracker = EmitterTracker()
    tracker.ingest(_batch(100.0, _shot("SAM-1", 100.0)))
    tracker.ingest(
        _batch(
            100.1,
            FiringRawEvent(
                kind="S_EVENT_DEAD",
                t_sim=100.1,
                initiator="SAM-1",
                targets_ownship=False,
                x=None,
                z=None,
            ),
        )
    )
    assert tracker.snapshot()["active"] == {}


def test_empty_batch_before_anything_ingested_has_no_model_time() -> None:
    tracker = EmitterTracker()
    snapshot = tracker.snapshot()
    assert snapshot["dcs_model_time_s"] is None
    assert snapshot["active"] == {}
    assert snapshot["mission_clock"] is None


def test_snapshot_carries_the_most_recent_batchs_mission_clock() -> None:
    tracker = EmitterTracker()
    tracker.ingest(
        FiringEventBatch.from_wire(
            "0|100.0|",
            bridge_call_ms=0.0,
            received_wall_clock_s=0.0,
            mission_clock_raw="18300.5|2020|6|1",
        )
    )

    mission_clock = tracker.snapshot()["mission_clock"]
    assert mission_clock == {"abs_time_s": 18300.5, "year": 2020, "month": 6, "day": 1}


def test_snapshot_mission_clock_goes_back_to_none_when_a_later_batch_cannot_read_it() -> (
    None
):
    """The tracker reports exactly what the most recent batch said --
    it does not hold onto a stale "last known good" reading (module
    docstring's `_last_mission_clock` note)."""
    tracker = EmitterTracker()
    tracker.ingest(
        FiringEventBatch.from_wire(
            "0|100.0|",
            bridge_call_ms=0.0,
            received_wall_clock_s=0.0,
            mission_clock_raw="18300.5|2020|6|1",
        )
    )
    tracker.ingest(
        FiringEventBatch.from_wire(
            "0|101.0|",
            bridge_call_ms=0.0,
            received_wall_clock_s=0.0,
            mission_clock_raw="unavailable",
        )
    )

    assert tracker.snapshot()["mission_clock"] is None


def _send(port: int, payload: object) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode("utf-8"), ("127.0.0.1", port))
    finally:
        sock.close()


def _run_receiver_briefly(receiver: FiringEventsReceiver) -> None:
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    receiver.close()
    thread.join(timeout=5)


def test_well_formed_envelope_is_ingested() -> None:
    tracker = EmitterTracker()
    receiver = FiringEventsReceiver(tracker, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(
        port,
        {
            "payload": "1|60.0|S_EVENT_SHOOTING_START:60.0:Unit_1:1:nil:nil",
            "bridge_call_ms": 0.5,
        },
    )
    _run_receiver_briefly(receiver)

    active = tracker.snapshot()["active"]
    assert isinstance(active, dict)
    assert active["Unit_1"]["targets_ownship"] is True


def test_malformed_payload_is_dropped_not_ingested() -> None:
    tracker = EmitterTracker()
    receiver = FiringEventsReceiver(tracker, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(port, {"payload": "garbage", "bridge_call_ms": 0.5})
    _run_receiver_briefly(receiver)

    assert tracker.snapshot()["active"] == {}


def test_mission_clock_envelope_key_reaches_the_snapshot() -> None:
    tracker = EmitterTracker()
    receiver = FiringEventsReceiver(tracker, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(
        port,
        {
            "payload": "0|60.0|",
            "bridge_call_ms": 0.5,
            "mission_clock": "18300.5|2020|6|1",
        },
    )
    _run_receiver_briefly(receiver)

    mission_clock = tracker.snapshot()["mission_clock"]
    assert mission_clock == {"abs_time_s": 18300.5, "year": 2020, "month": 6, "day": 1}


def test_mission_clock_envelope_key_absent_is_fine() -> None:
    """Pre-amendment envelope shape (no `mission_clock` key at all) --
    the firing events themselves still ingest normally."""
    tracker = EmitterTracker()
    receiver = FiringEventsReceiver(tracker, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    _send(
        port,
        {
            "payload": "1|60.0|S_EVENT_SHOOTING_START:60.0:Unit_1:1:nil:nil",
            "bridge_call_ms": 0.5,
        },
    )
    _run_receiver_briefly(receiver)

    snapshot = tracker.snapshot()
    assert snapshot["mission_clock"] is None
    active = snapshot["active"]
    assert isinstance(active, dict)
    assert "Unit_1" in active


def test_non_json_datagram_is_dropped() -> None:
    tracker = EmitterTracker()
    receiver = FiringEventsReceiver(tracker, host="127.0.0.1", port=0)
    receiver.open()
    port = receiver.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"not json", ("127.0.0.1", port))
    finally:
        sock.close()
    _run_receiver_briefly(receiver)

    assert tracker.snapshot()["active"] == {}


# --- `[[BL-B67]]` Stage 5: `OwnWeaponLedger` -----------------------------


def _own_shot(
    seq: int,
    t_sim: float,
    *,
    type_name: str | None = "Ataka_9M120",
    category: int | None = 1,
    guidance: int | None = 8,
    exists_at_shot: bool | None = True,
) -> OwnWeaponRawEvent:
    return OwnWeaponRawEvent(
        kind="OWN_SHOT",
        t_sim=t_sim,
        seq=seq,
        type_name=type_name,
        category=category,
        guidance=guidance,
        exists_at_shot=exists_at_shot,
    )


def _own_gone(seq: int, t_sim: float) -> OwnWeaponRawEvent:
    return OwnWeaponRawEvent(kind="OWN_GONE", t_sim=t_sim, seq=seq)


def test_own_weapon_ledger_shot_then_gone_across_batches() -> None:
    ledger = OwnWeaponLedger()
    ledger.ingest((_own_shot(1, 10.0),), now=10.0)
    snapshot = ledger.snapshot()
    assert snapshot["1"] == {
        "type_name": "Ataka_9M120",
        "category": 1,
        "guidance": 8,
        "exists_at_shot": True,
        "shot_t": 10.0,
        "gone_t": None,
    }

    ledger.ingest((_own_gone(1, 20.0),), now=20.0)
    entry = ledger.snapshot()["1"]
    assert isinstance(entry, dict)
    assert entry["gone_t"] == 20.0


def test_own_weapon_ledger_gone_for_unknown_seq_is_a_no_op() -> None:
    ledger = OwnWeaponLedger()
    ledger.ingest((_own_gone(99, 5.0),), now=5.0)
    assert ledger.snapshot() == {}


def test_own_weapon_ledger_retention_prunes_after_gone_plus_window() -> None:
    ledger = OwnWeaponLedger()
    ledger.ingest((_own_shot(1, 0.0),), now=0.0)
    ledger.ingest((_own_gone(1, 1.0),), now=1.0)
    assert "1" in ledger.snapshot()

    ledger.ingest((), now=1.0 + OWN_WEAPON_RETENTION_S - 1.0)
    assert "1" in ledger.snapshot()

    ledger.ingest((), now=1.0 + OWN_WEAPON_RETENTION_S + 1.0)
    assert ledger.snapshot() == {}


def test_own_weapon_ledger_cap_drops_the_oldest_by_shot_t() -> None:
    ledger = OwnWeaponLedger()
    for seq in range(1, OWN_WEAPON_LEDGER_CAP + 2):
        ledger.ingest((_own_shot(seq, float(seq)),), now=float(seq))
    snapshot = ledger.snapshot()
    assert len(snapshot) == OWN_WEAPON_LEDGER_CAP
    assert "1" not in snapshot
    assert str(OWN_WEAPON_LEDGER_CAP + 1) in snapshot


def test_own_weapon_ledger_clear() -> None:
    ledger = OwnWeaponLedger()
    ledger.ingest((_own_shot(1, 0.0),), now=0.0)
    ledger.clear()
    assert ledger.snapshot() == {}


def test_emitter_tracker_snapshot_carries_own_weapons() -> None:
    tracker = EmitterTracker()
    batch = FiringEventBatch(
        dcs_model_time_s=5.0,
        received_wall_clock_s=0.0,
        bridge_call_ms=0.0,
        events=(),
        own_events=(_own_shot(1, 5.0),),
    )
    tracker.ingest(batch)
    own_weapons = tracker.snapshot()["own_weapons"]
    assert isinstance(own_weapons, dict)
    assert "1" in own_weapons


def test_emitter_tracker_mission_restart_clears_own_weapons_too() -> None:
    tracker = EmitterTracker()
    tracker.ingest(
        FiringEventBatch(
            dcs_model_time_s=100.0,
            received_wall_clock_s=0.0,
            bridge_call_ms=0.0,
            events=(),
            own_events=(_own_shot(1, 100.0),),
        )
    )
    assert "1" in tracker.snapshot()["own_weapons"]  # type: ignore[operator]

    tracker.ingest(
        FiringEventBatch(
            dcs_model_time_s=0.0,
            received_wall_clock_s=0.0,
            bridge_call_ms=0.0,
            events=(),
            own_events=(),
        )
    )
    assert tracker.snapshot()["own_weapons"] == {}
