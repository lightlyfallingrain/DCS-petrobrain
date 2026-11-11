"""Ad hoc timing probe for the BL-B111 expected-area-look hot path --
performance-review scratch script, not part of the shipped test suite.
Mirrors `body-layer/tests/test_expected_area.py`'s own `_contact`
construction. Run from `body-layer/` with:

    PYTHONPATH=src:../world-model/src .venv/bin/python \\
        ../plans/expected-area-look/perf_probe_b111.py
"""
import sys
import time

sys.path.insert(0, "src")
sys.path.insert(0, "../world-model/src")

from belief.contacts import Contact
from belief.expected_area import (
    ExpectedAreaCheck,
    LookEvidence,
    a_out_of_view,
    area_fits_one_look,
    area_visibility,
    eligible_trigger_target,
    probe_points_for,
    resolve_checks,
)
from belief.percept import percept_of
from perception.geometry import GeoPosition
from perception.source import Observation, OwnshipState, PositionUncertainty


def _ownship(x=0.0, z=0.0):
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _contact(contact_id, t_sim=0.0, bearing_deg=0.0, range_m=3000.0, position_uncertainty=None):
    observation = Observation(
        id=f"{contact_id}-obs",
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source="test_fixture",
        classification_raw="s-125",
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=_ownship(),
        derived_world_position=None,
        provenance="test_fixture",
        classification_level=2,
        position_uncertainty=position_uncertainty,
        count_bucket=None,
    )
    percept = percept_of(observation)
    return Contact.from_percept(contact_id, percept)


OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)


def assert_can_fail():
    """Can-this-fail probe, per performance-reviewer memory: a trivially
    wrong call must make this script fail before any timing is trusted."""
    wide = _contact(
        "Z",
        range_m=500.0,
        position_uncertainty=PositionUncertainty(sigma_cross_m=2000.0, sigma_down_m=2000.0),
    )
    assert area_fits_one_look(wide, now_sim=0.0, observer=OBSERVER) is False, (
        "sanity check failed: a close contact with a huge cross-range "
        "sigma must not fit one look -- harness cannot distinguish pass "
        "from fail"
    )
    assert area_fits_one_look(_contact("Y", range_m=3000.0), now_sim=0.0, observer=OBSERVER) is True


def time_it(label, fn, n=200_000):
    start = time.perf_counter()
    for _ in range(n):
        fn()
    elapsed = time.perf_counter() - start
    per_call_us = (elapsed / n) * 1e6
    print(f"{label}: {per_call_us:.3f} us/call  ({n} calls, {elapsed:.3f}s)")
    return per_call_us


def main():
    assert_can_fail()
    print("can-this-fail probe: OK\n")

    a = _contact("A", range_m=3000.0)

    t1 = time_it("probe_points_for", lambda: probe_points_for(a, now_sim=1.0, observer=OBSERVER))
    t2 = time_it("area_fits_one_look", lambda: area_fits_one_look(a, now_sim=1.0, observer=OBSERVER))
    t3 = time_it("a_out_of_view", lambda: a_out_of_view(a, now_sim=1.0))

    evidence = LookEvidence(
        area_fits_one_look_now=True,
        look_completed_naturally=True,
        inside_cockpit_mask=True,
        within_binocular_presence_range=True,
        occluded=False,
        probe_seq_matches=True,
        probe_time_in_window=True,
        probe_clear=(True, True, True),
    )
    t4 = time_it("area_visibility", lambda: area_visibility(
        area_fits_one_look_now=evidence.area_fits_one_look_now,
        look_completed_naturally=evidence.look_completed_naturally,
        inside_cockpit_mask=evidence.inside_cockpit_mask,
        within_binocular_presence_range=evidence.within_binocular_presence_range,
        occluded=evidence.occluded,
        probe_seq_matches=evidence.probe_seq_matches,
        probe_time_in_window=evidence.probe_time_in_window,
        probe_clear=evidence.probe_clear,
    ))

    class FakeStore:
        def contact(self, contact_id):
            return a if contact_id in ("A",) else b

        def close_check(self, b_id):
            pass

        def release_check(self, b_id, now_sim):
            pass

        def record_believed_distinct(self, a_id, b_id):
            pass

        def merge_contact(self, *, into, source):
            pass

        def mark_lost_now(self, contact_id, now_sim):
            pass

        def record_relocation(self, contact_id, now_sim):
            pass

        def record_absence(self, contact_id, now_sim):
            pass

    b = _contact("B", range_m=3000.0)
    check = ExpectedAreaCheck(
        b_id="B",
        a_id="A",
        kind="fold",
        opened_sim=0.0,
        a_snapshot=a,
        released=False,
    )
    store = FakeStore()

    def _resolve_one():
        resolve_checks(
            store,
            [check],
            now_sim=1.0,
            deadline_s=20.0,
            look_evidence={"B": evidence},
            a_observed={"A": False},
            relocation_warranted_by_b={"B": False},
            a_was_announced={"A": False},
            paused=False,
        )

    t5 = time_it("resolve_checks (1 check, cannot_look->still_open path? exercised below)", _resolve_one, n=50_000)

    total_per_check = t1 + t2 + t3 + t4
    print(f"\nSum of the four new per-check pure functions: {total_per_check:.3f} us/check")
    print(f"At MAX_OPEN_CHECKS=2: {total_per_check * 2:.3f} us/poll")
    print(f"resolve_checks itself (1 check): {t5:.3f} us; at 2 checks (linear): {t5*2:.3f} us/poll")
    print(f"Combined (per-check evidence assembly + resolve_checks), 2 checks: "
          f"{(total_per_check + t5) * 2:.3f} us/poll")
    print(f"As a fraction of the 1.0 Hz (1,000,000 us) poll budget: "
          f"{((total_per_check + t5) * 2) / 1_000_000 * 100:.5f}%")


if __name__ == "__main__":
    main()
