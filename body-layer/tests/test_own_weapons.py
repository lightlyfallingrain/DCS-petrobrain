"""Tests for `perception.own_weapons.OwnWeaponTracker` -- `[[BL-B67]]`
Stage 5, `plans/bl-b67-atgm-run/plan.md`. Synthetic `GET /firing/latest`
dicts only, no aircraft-layer, mirroring `test_atgm_run.py`'s own
table-driven-against-synthetic-inputs posture. Per the plan's own test
list: a new guided `seq` gives a launch; `exists=0` gives a failed
launch; an unguided `seq` gives nothing; a baseline `seq` gives nothing;
a gone report on the tracked `seq` gives `missile_gone`; a gone report
on an older `seq` gives nothing; a stale snapshot gives
`own_feed_fresh=False`, never an impact."""

from __future__ import annotations

from typing import Any

from perception.own_weapons import OwnWeaponTracker


def _firing_latest(
    dcs_model_time_s: float, own_weapons: dict[str, Any]
) -> dict[str, Any]:
    return {
        "dcs_model_time_s": dcs_model_time_s,
        "received_wall_clock_s": 0.0,
        "active": {},
        "mission_clock": None,
        "own_weapons": own_weapons,
    }


def _own_weapon(
    *,
    type_name: str | None = "Ataka_9M120",
    category: int | None = 1,
    guidance: int | None = 8,
    exists_at_shot: bool | None = True,
    shot_t: float = 0.0,
    gone_t: float | None = None,
) -> dict[str, Any]:
    return {
        "type_name": type_name,
        "category": category,
        "guidance": guidance,
        "exists_at_shot": exists_at_shot,
        "shot_t": shot_t,
        "gone_t": gone_t,
    }


def test_no_feed_is_not_fresh_and_produces_no_events() -> None:
    tracker = OwnWeaponTracker()
    events = tracker.poll(None, now_sim=10.0, max_age_s=3.0)
    assert events.own_feed_fresh is False
    assert events.launch is None
    assert events.failed_launch is None
    assert events.missile_gone is False


def test_stale_feed_is_not_fresh() -> None:
    tracker = OwnWeaponTracker()
    stale = _firing_latest(0.0, {})
    events = tracker.poll(stale, now_sim=10.0, max_age_s=3.0)
    assert events.own_feed_fresh is False


def test_first_poll_is_a_baseline_never_a_launch() -> None:
    """A `seq` already present the first poll this tracker ever reads is
    a baseline -- the ledger retains an entry for a while after `gone_t`,
    so a tracker that started mid-sortie must not misreport it."""
    tracker = OwnWeaponTracker()
    feed = _firing_latest(10.0, {"1": _own_weapon()})
    events = tracker.poll(feed, now_sim=10.0, max_age_s=3.0)
    assert events.launch is None
    assert events.failed_launch is None
    assert events.own_feed_fresh is True

    # The same seq, still present, is not a launch on the *next* poll
    # either -- it was already seen.
    events2 = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events2.launch is None


def test_new_guided_existing_seq_is_a_launch() -> None:
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    feed = _firing_latest(
        11.0, {"1": _own_weapon(type_name="Ataka_9M120", shot_t=11.0)}
    )
    events = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events.launch is not None
    assert events.launch.t_sim == 11.0
    assert events.launch.type_name == "Ataka_9M120"
    assert events.failed_launch is None


def test_new_guided_seq_not_existing_is_a_failed_launch() -> None:
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    feed = _firing_latest(11.0, {"1": _own_weapon(exists_at_shot=False, shot_t=11.0)})
    events = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events.launch is None
    assert events.failed_launch is not None
    assert events.failed_launch.t_sim == 11.0


def test_new_unguided_seq_produces_nothing() -> None:
    """S-8 rockets also raise `S_EVENT_SHOT` -- category/guidance differ
    from the ATGM filter."""
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    feed = _firing_latest(
        11.0, {"1": _own_weapon(type_name="C_8", category=2, guidance=None)}
    )
    events = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events.launch is None
    assert events.failed_launch is None


def test_gone_report_on_tracked_seq_gives_missile_gone() -> None:
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    launch_feed = _firing_latest(11.0, {"1": _own_weapon(shot_t=11.0)})
    tracker.poll(launch_feed, now_sim=11.0, max_age_s=3.0)

    gone_feed = _firing_latest(12.0, {"1": _own_weapon(shot_t=11.0, gone_t=12.0)})
    events = tracker.poll(gone_feed, now_sim=12.0, max_age_s=3.0)
    assert events.missile_gone is True


def test_gone_report_on_an_older_seq_gives_nothing() -> None:
    """Only the *tracked* seq's own `gone_t` counts -- a baseline seq
    (never launched through this tracker) turning `gone_t` is not this
    run's missile."""
    tracker = OwnWeaponTracker()
    tracker.poll(
        _firing_latest(10.0, {"5": _own_weapon(shot_t=5.0)}),
        now_sim=10.0,
        max_age_s=3.0,
    )
    gone_feed = _firing_latest(11.0, {"5": _own_weapon(shot_t=5.0, gone_t=11.0)})
    events = tracker.poll(gone_feed, now_sim=11.0, max_age_s=3.0)
    assert events.missile_gone is False


def test_launch_and_gone_in_the_same_poll() -> None:
    """A very short flight -- both reported in one poll's own `OwnWeaponEvents`."""
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    feed = _firing_latest(11.0, {"1": _own_weapon(shot_t=11.0, gone_t=11.0)})
    events = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events.launch is not None
    assert events.missile_gone is True


def test_newest_new_guided_seq_is_tracked_when_two_launch_same_poll() -> None:
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    feed = _firing_latest(
        11.0,
        {
            "1": _own_weapon(type_name="first", shot_t=11.0),
            "2": _own_weapon(type_name="second", shot_t=11.0),
        },
    )
    events = tracker.poll(feed, now_sim=11.0, max_age_s=3.0)
    assert events.launch is not None
    # `new_seqs` is sorted ascending, so seq 2 (the higher/newest) wins.
    assert events.launch.type_name == "second"


def test_reset_for_new_mission_drops_baseline_and_re_baselines() -> None:
    tracker = OwnWeaponTracker()
    tracker.poll(
        _firing_latest(10.0, {"1": _own_weapon()}), now_sim=10.0, max_age_s=3.0
    )
    tracker.reset_for_new_mission()

    # The same seq, if still present after a (re)start, is a fresh
    # baseline again, not a launch -- a genuine mission restart means
    # this is "before this tracker started watching" all over again.
    feed = _firing_latest(0.0, {"1": _own_weapon()})
    events = tracker.poll(feed, now_sim=0.0, max_age_s=3.0)
    assert events.launch is None


def test_malformed_own_weapons_value_degrades_to_no_events() -> None:
    tracker = OwnWeaponTracker()
    feed = _firing_latest(10.0, {})
    feed["own_weapons"] = "not a dict"
    events = tracker.poll(feed, now_sim=10.0, max_age_s=3.0)
    assert events.launch is None
    assert events.failed_launch is None
    assert events.own_feed_fresh is True


def test_tracked_seq_pruned_from_ledger_without_gone_report_is_treated_as_gone() -> (
    None
):
    """A fail-safe, not an expected path: if the ledger's own retention
    window somehow prunes the tracked `seq` before this tracker ever saw
    its `gone_t`, stop tracking rather than wait forever."""
    tracker = OwnWeaponTracker()
    tracker.poll(_firing_latest(10.0, {}), now_sim=10.0, max_age_s=3.0)
    tracker.poll(
        _firing_latest(11.0, {"1": _own_weapon(shot_t=11.0)}),
        now_sim=11.0,
        max_age_s=3.0,
    )
    events = tracker.poll(_firing_latest(200.0, {}), now_sim=200.0, max_age_s=3.0)
    assert events.missile_gone is True
