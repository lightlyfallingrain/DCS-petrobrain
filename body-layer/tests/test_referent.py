"""Tests for `belief.referent` -- `[[BL-B102]]`, `plans/that-it-referent/
plan.md` Stage 1. Pure unit tests over `ReferentMemory`/`resolve_referent`:
window pruning, bare-last, qualified-filter, target-priority tie-break,
group->lead-member reduction (including the `group_membership_state is
None` fallback), nearest-wins tie-break, and expired/empty -> "unable".

`CrewConsole`-level integration (mention recording via `_print`, the
unseen/lost-contact case end to end) lives in `test_crew_console.py`."""

from __future__ import annotations

import math

from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S, certainty_of
from belief.referent import REFERENT_WINDOW_S, Mention, ReferentMemory, resolve_referent
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _no_qualifier_scope(ids: object) -> list[dict[str, object]]:
    """A `qualifier_scope` that must never be called -- the bare-referent
    path resolves from `memory.last` alone, before any qualifier filter
    runs."""
    raise AssertionError("qualifier_scope must not be called with no qualifier")


# --- ReferentMemory ---------------------------------------------------


def test_referent_memory_last_is_the_most_recently_recorded_mention() -> None:
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    memory.record([Mention(kind="contact", id="C2", t_sim=5.0)], now_sim=5.0)
    assert memory.last(now_sim=5.0) == Mention(kind="contact", id="C2", t_sim=5.0)


def test_referent_memory_last_line_wins_within_one_batch() -> None:
    """Two mentions recorded in the same `record` call (one `_print`
    call naming two groups) share one `t_sim` -- append order, not
    `t_sim`, decides which is "last" (module docstring)."""
    memory = ReferentMemory()
    memory.record(
        [
            Mention(kind="group", id="G3", t_sim=10.0),
            Mention(kind="group", id="G5", t_sim=10.0),
        ],
        now_sim=10.0,
    )
    assert memory.last(now_sim=10.0) == Mention(kind="group", id="G5", t_sim=10.0)


def test_referent_memory_prunes_mentions_outside_the_window() -> None:
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    just_inside = REFERENT_WINDOW_S - 1.0
    just_outside = REFERENT_WINDOW_S + 1.0
    assert memory.last(now_sim=just_inside) is not None
    assert memory.last(now_sim=just_outside) is None


def test_referent_memory_record_of_empty_mentions_does_not_disturb_last() -> None:
    """A line with no subject must not blank out what was last
    mentioned (module docstring)."""
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    memory.record([], now_sim=1.0)
    assert memory.last(now_sim=1.0) == Mention(kind="contact", id="C1", t_sim=0.0)


# --- resolve_referent: window / bare-last / unable ---------------------


def test_resolve_referent_with_nothing_mentioned_is_unable() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )
    assert contact_id is None
    assert lines == ["Unable, I don't know what you mean."]


def test_resolve_referent_bare_referent_picks_the_last_mention() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    memory.record([Mention(kind="contact", id="C2", t_sim=5.0)], now_sim=5.0)
    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=5.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )
    assert contact_id == "C2"
    assert lines == []


def test_resolve_referent_expired_mention_is_unable() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=REFERENT_WINDOW_S + 1.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )
    assert contact_id is None
    assert lines == ["Unable, I don't know what you mean."]


# --- resolve_referent: qualified filter ---------------------------------


def test_resolve_referent_qualified_filter_picks_the_surviving_mention() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record(
        [
            Mention(kind="contact", id="C1", t_sim=0.0),
            Mention(kind="contact", id="C2", t_sim=0.0),
        ],
        now_sim=0.0,
    )

    def _scope(ids: object) -> list[dict[str, object]]:
        assert ids == {"C1", "C2"}
        return [{"id": "C2"}]

    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=True,
        qualifier_scope=_scope,
        active_attack_target_id=None,
    )
    assert contact_id == "C2"
    assert lines == []


def test_resolve_referent_qualified_filter_with_no_survivors_is_unable() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record([Mention(kind="contact", id="C1", t_sim=0.0)], now_sim=0.0)
    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=True,
        qualifier_scope=lambda ids: [],
        active_attack_target_id=None,
    )
    assert contact_id is None
    assert lines == ["Unable, I don't know what you mean."]


def test_resolve_referent_target_priority_wins_over_a_qualified_match() -> None:
    """Decision 2's own worked example: "if attack target is AAA, which
    would take priority" -- the attack target wins even when it is not
    the nearest qualified match."""
    store = ContactStore()
    memory = ReferentMemory()
    memory.record(
        [
            Mention(kind="contact", id="TARGET", t_sim=0.0),
            Mention(kind="contact", id="OTHER", t_sim=0.0),
        ],
        now_sim=0.0,
    )

    def _scope(ids: object) -> list[dict[str, object]]:
        return [
            {"id": "TARGET", "relative_now": {"range_m": 9000.0}},
            {"id": "OTHER", "relative_now": {"range_m": 100.0}},
        ]

    contact_id, _lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=True,
        qualifier_scope=_scope,
        active_attack_target_id="TARGET",
    )
    assert contact_id == "TARGET"


def test_resolve_referent_nearest_wins_the_qualified_tie() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record(
        [
            Mention(kind="contact", id="NEAR", t_sim=0.0),
            Mention(kind="contact", id="FAR", t_sim=0.0),
        ],
        now_sim=0.0,
    )

    def _scope(ids: object) -> list[dict[str, object]]:
        return [
            {"id": "NEAR", "relative_now": {"range_m": 500.0}},
            {"id": "FAR", "relative_now": {"range_m": 5000.0}},
        ]

    contact_id, _lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=True,
        qualifier_scope=_scope,
        active_attack_target_id=None,
    )
    assert contact_id == "NEAR"


# --- resolve_referent: group reduction -----------------------------------


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _xz_for_clock(clock: int, range_m: float) -> tuple[float, float]:
    bearing = math.radians((clock % 12) * 30.0)
    return range_m * math.cos(bearing), range_m * math.sin(bearing)


def _grouped_observation(
    *, obs_id: str, classification_raw: str, clock: int, range_m: float
) -> Observation:
    x, z = _xz_for_clock(clock, range_m)
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=x, z=z),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=2,
    )


def _store_with_one_real_group() -> tuple[ContactStore, str]:
    """Two observations at the identical clock/range cohere into one real
    `belief.groups.Group` via `ContactStore.tick`'s reconcile -- the same
    pattern `test_crew_console.py`'s own group-tagging tests use. Returns
    the store and the group's id."""
    store = ContactStore()
    store.ingest(
        [
            _grouped_observation(
                obs_id="OBS_A", classification_raw="OP_ARMORED", clock=2, range_m=3000.0
            ),
            _grouped_observation(
                obs_id="OBS_B", classification_raw="OP_TRUCK", clock=2, range_m=3000.0
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    group = store.groups[0]
    return store, group.id


def test_resolve_referent_group_mention_reduces_to_a_leading_member() -> None:
    store, group_id = _store_with_one_real_group()
    memory = ReferentMemory()
    memory.record([Mention(kind="group", id=group_id, t_sim=0.0)], now_sim=0.0)

    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )

    assert lines == []
    assert contact_id is not None
    group = next(g for g in store.groups if g.id == group_id)
    assert contact_id in group.member_contact_ids


def test_resolve_referent_group_mention_falls_back_to_one_surviving_member() -> None:
    """`group_membership_state`'s own "fewer than two members still
    resolve" guard -- one member retired, the group itself still exists
    with a stale membership set. The fallback picks the one id that
    still resolves to a live `Contact` (Facts section / Design step 6)."""
    store, group_id = _store_with_one_real_group()
    group = next(g for g in store.groups if g.id == group_id)
    survivor_id, retired_id = sorted(group.member_contact_ids)
    store._contacts = {  # type: ignore[attr-defined]
        contact_id: contact
        for contact_id, contact in store._contacts.items()  # type: ignore[attr-defined]
        if contact_id != retired_id
    }
    memory = ReferentMemory()
    memory.record([Mention(kind="group", id=group_id, t_sim=0.0)], now_sim=0.0)

    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )

    assert lines == []
    assert contact_id == survivor_id


def test_resolve_referent_group_mention_with_no_resolvable_group_is_unable() -> None:
    store = ContactStore()
    memory = ReferentMemory()
    memory.record([Mention(kind="group", id="GROUP_GONE", t_sim=0.0)], now_sim=0.0)

    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=0.0,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )

    assert contact_id is None
    assert lines == ["Unable, I don't know what you mean."]


# --- Decision 4: an unseen/"lost" contact still resolves ----------------


def test_resolve_referent_bare_referent_resolves_a_contact_even_after_it_is_lost() -> (
    None
):
    """Decision 4 (explore-notes, user: "time ok, but use belief if not
    visible") -- `resolve_referent` itself never reads `certainty` at
    all, so a mentioned contact that has since gone `"lost"` is still the
    bare-referent winner. The certainty-aware filtering this decision
    actually guards against lives in `CrewConsole._report_scope`'s
    `restrict_to_ids` mode (tested in `test_crew_console.py`), not here --
    this test pins that `resolve_referent`'s own bare-last path never
    needed that fix in the first place."""
    store = ContactStore()
    store.ingest(
        [
            _grouped_observation(
                obs_id="OBS_AAA", classification_raw="OP_AAA", clock=2, range_m=3000.0
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]

    # The mention is recorded well *after* the contact's last real
    # observation -- past `LOST_THRESHOLD_S` since it was last seen (so
    # `certainty_of` reads "lost" by then), but still within
    # `REFERENT_WINDOW_S` of the mention itself (a report/callout at this
    # later tick, describing the contact from belief). This is the
    # realistic shape of the case Decision 4 covers: the window is
    # measured from when Petrovich last *spoke* about it, not from when
    # it was last *seen*.
    mention_t_sim = LOST_THRESHOLD_S + 1.0
    assert certainty_of(contact, mention_t_sim) == "lost"
    memory = ReferentMemory()
    memory.record(
        [Mention(kind="contact", id=contact.id, t_sim=mention_t_sim)],
        now_sim=mention_t_sim,
    )

    now_sim = mention_t_sim + 1.0
    contact_id, lines = resolve_referent(
        store,
        memory,
        now_sim=now_sim,
        has_qualifier=False,
        qualifier_scope=_no_qualifier_scope,
        active_attack_target_id=None,
    )
    assert contact_id == contact.id
    assert lines == []
