"""Tests for `belief.crew_console` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 4's typed-input/printed-output crew session.

Includes the plan's required acceptance test: a scripted session reproducing
`docs/concept/PETROBRAIN_RUNTIME.md`'s "First useful success criterion"
(detect -> watch -> readback -> lost -> reacquired -> "where was that BMP?"
-> memory-backed answer), plus one contact-report trigger and one injected
urgent call -- the four pieces the milestone's acceptance criterion names
explicitly."""

from __future__ import annotations

import math
import socket
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Self, cast

import pytest

from aircraft_client import AircraftLayerError
from belief import enrichment as enrichment_module
from belief.attack_run import AttackRunState
from belief.attention import RelativeSector, Sector
from belief.audio_client import AudioAdapterError
from belief.brain_client import BrainLayerClient
from belief.classification import AIR_DEFENSE_OP_CLASSES, PRESENCE_CLASS
from belief.contacts import Contact, ContactStore
from belief.crew_console import (
    _GREETING_TIMES_OF_DAY,
    _MAX_PENDING_POSITIONAL_REPLIES,
    _NOTHING_TO_STOP,
    DISPATCHED_COMMAND_TOKENS,
    NO_RETURN_VALUE_COMMAND_TOKENS,
    CrewConsole,
    _describe_token_for_confirm,
    _nearest_sector,
)
from belief.decay import LOST_THRESHOLD_S, OBSERVED_WINDOW_S
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainReply, EscalationPayload
from belief.groups import Group
from belief.percept import Percept
from belief.speech import (
    group_membership_state,
    render_group_disclosure,
    render_group_full_disclosure,
    render_no_contact,
)
from belief.tasks import PendingIntent, TaskStore
from belief.tools import attack_target_task, describe_contact
from belief.voice_commands import (
    ACT_FLOOR,
    CONFIRM_FLOOR,
    CONFIRM_LATE_ANSWER_GRACE_S,
    CONFIRM_WINDOW_S,
)
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    DerivedWorldPosition,
    Observation,
    OwnshipState,
    RelativeDirection,
)


class FakeOverlayClient:
    """A `push_text_line`-only double, mirroring `tests/test_logger.py`'s
    own `FakeOverlayClient` (BL-2.5) -- kept as a small local copy rather
    than a shared helper module, per this project's per-test-file fixture
    convention. `fail_on` names texts that raise `AircraftLayerError`
    instead of recording, used to exercise `CrewConsole._print`'s per-push
    isolation."""

    def __init__(self, fail_on: frozenset[str] = frozenset()) -> None:
        self.pushed: list[str] = []
        self._fail_on = fail_on

    def push_text_line(self, text: str) -> None:
        if text in self._fail_on:
            raise AircraftLayerError("simulated push failure")
        self.pushed.append(text)


class FakeSpeechClient:
    """A `push_speech`/`stop`-only double, mirroring `FakeOverlayClient`
    above -- used to exercise `CrewConsole.speech_client` (BL-10 first
    slice, `plans/tts-voice-output/plan.md`, `stop` added `plans/
    inbound-speech/plan.md` Stage 3 follow-up). Records `(text, urgent)`
    pairs so tests can assert `bypass_gate` was threaded through as
    `push_speech`'s `urgent` argument, and a separate `stop_calls` count
    for `stop()` -- a different call with no text/urgent argument at all.
    `fail_on` names texts that raise `AudioAdapterError` from `push_speech`
    instead of recording (used to exercise `CrewConsole._print`'s per-push
    isolation for this sink); `"Copy."` in `fail_on` also makes `stop()`
    raise, reusing the same set rather than adding a second constructor
    flag purely for one stop_talking test."""

    def __init__(self, fail_on: frozenset[str] = frozenset()) -> None:
        self.pushed: list[tuple[str, bool]] = []
        #: `correlation_id` for every `push_speech` call, in order -- kept
        #: separate from `pushed` so every existing assertion on that list
        #: (text/urgent only) keeps working unchanged.
        self.pushed_correlation_ids: list[str | None] = []
        self.stop_calls = 0
        self._fail_on = fail_on

    def push_speech(
        self, text: str, urgent: bool, correlation_id: str | None = None
    ) -> None:
        if text in self._fail_on:
            raise AudioAdapterError("simulated push failure")
        self.pushed.append((text, urgent))
        self.pushed_correlation_ids.append(correlation_id)

    def stop(self) -> None:
        if "Copy." in self._fail_on:
            raise AudioAdapterError("simulated stop failure")
        self.stop_calls += 1


class _CapturingBrainClient:
    """`plans/brain-layer/plan.md` extends `BrainReply` with
    `poll_replies()`; `replies_to_return` is test-controlled queue-less
    override -- each `poll_replies()` call returns it once, then reverts
    to `[]`, mirroring a real drain-on-poll client without needing an
    actual FIFO for these tests' scripted single-reply scenarios."""

    def __init__(self) -> None:
        self.payloads: list[EscalationPayload] = []
        self.replies_to_return: list[BrainReply] = []

    def handle(self, payload: EscalationPayload) -> None:
        self.payloads.append(payload)

    def awaiting_reply_id(self) -> str | None:
        return None

    def poll_replies(self) -> list[BrainReply]:
        replies, self.replies_to_return = self.replies_to_return, []
        return replies


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *, obs_id: str, t_sim: float, classification_raw: str = "BMP-2"
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=2,
    )


_FAKE_CONN = sqlite3.connect(":memory:")


@dataclass
class _FakeInfo:
    name: str | None = None
    subtype: str | None = None
    area_m2: float | None = None
    distance_m: float = 100.0
    provenance: str = "osm"
    confidence: str = "high"


@dataclass
class _FakeDescription:
    nearest_settlement: _FakeInfo | None = None
    inside_settlement: _FakeInfo | None = None
    nearest_road: _FakeInfo | None = None
    nearest_water: _FakeInfo | None = None
    nearby_ridges: _FakeInfo | None = None
    nearby_valleys: _FakeInfo | None = None
    inside_landcover: object | None = None
    nearest_coastline: object | None = None


def _enrichment_context(monkeypatch: pytest.MonkeyPatch) -> EnrichmentContext:
    """`plans/f10-crew-commands/plan.md`'s `_nearest_contact_id` needs a
    real `EnrichmentContext` to read `facts["relative_now"]["range_m"]`
    through -- mirrors `test_console.py`'s own `_enrichment_context` helper
    (kept as a local copy per this project's per-test-file fixture
    convention, same as `FakeOverlayClient` above): `describe_position` is
    stubbed to a fixed settlement, `project_terrain_aware` is a no-op
    passthrough of the observer position it is given, so a contact's
    projected world position is exactly its most recent observation's
    `ownship_at_observation` position -- what `_observation_with_ownship_x`
    below exploits to give two contacts distinct, predictable ranges from
    ownship."""
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(
            nearest_settlement=_FakeInfo(name="Jableh", distance_m=250.0)
        ),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    # `terrain_divide_qualifier` (`plans/terrain-feature-probing/plan.md`
    # Revision 3) queries `store.reader`'s R*Tree-backed `features_in_bbox`
    # directly rather than through `describe_position` -- the fixture's
    # `_FAKE_CONN` has no `feature_bbox` table at all, so a non-zero
    # ownship->target segment would hit a real `sqlite3.OperationalError`
    # without this stub. `0` means "no divides crossed", the same no-op
    # answer a flat/featureless store would give.
    monkeypatch.setattr(
        enrichment_module,
        "divides_between",
        lambda conn, theatre, observer, target: 0,
    )
    return EnrichmentContext(
        conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
    )


def _observation_with_ownship_x(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str,
    ownship_x: float,
    classification_level: int = 2,
) -> Observation:
    """Same shape as `_observation` above, but with a caller-controlled
    `ownship_at_observation.x` -- see `_enrichment_context`'s docstring for
    why that is what actually drives a contact's projected range here."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=ownship_x),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def _observation_at(
    *,
    obs_id: str,
    t_sim: float,
    ownship_x: float,
    ownship_z: float,
    classification_raw: str = "BMP-2",
    classification_level: int = 2,
) -> Observation:
    """Places a contact at a controlled world position for `plans/
    voice-command-completeness/plan.md`'s report-family tests, via
    `ownship_at_observation`'s x/z rather than `bearing_deg`/`range_m` --
    `_enrichment_context`'s monkeypatched `project_terrain_aware` returns
    its `observer` argument unchanged (identity, ignoring bearing/range
    entirely), and `_terrain_aware_world_position` calls it with
    `percept.ownship_at_observation` as that observer. So, under this
    fixture, a contact's *reported* world position is exactly the
    observing ownship's own position at the moment of its most recent
    contributing observation -- `bearing_deg=0.0`/`range_m=1000.0` below
    are therefore arbitrary placeholders, not the values that end up
    driving `relative_now`.

    **`classification_level` defaults to 2 (class), matching every
    existing caller's assumption** -- but a `classification_raw` default of
    `"BMP-2"` (a type-shaped reporting name) paired with level 2 is a state
    no real producer emits: `perception.naked_eye_source.
    _classification_for_tier`'s `hires`/`hybrid_source.py`'s only producers
    of a type-shaped string always pair it with level 3 (type); level 2 is
    only ever paired with an `op_class` bucket string. A caller that wants
    several same-type contacts to cohere into a group (`plans/
    group-collapse/plan.md` Stage 3's fixture-correction note) must pass
    `classification_level=3` explicitly -- see the two `_observation_at`
    call sites that do."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=ownship_x, z=ownship_z),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


class _RecordingAircraftClient:
    """Test double recording `trigger_petrovich_search` calls, never
    touching a real network socket -- a local copy of `test_console.py`'s
    own double of the same name, per this project's per-test-file fixture
    convention."""

    def __init__(self) -> None:
        self.triggered_modes: list[str] = []
        self.raise_on_trigger = False

    def trigger_petrovich_search(self, mode: str) -> None:
        if self.raise_on_trigger:
            raise AircraftLayerError("simulated failure")
        self.triggered_modes.append(mode)


def test_blank_line_produces_no_output() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_line("   ", now_sim=0.0) == []


def test_unresolvable_reference_escalates_and_speaks_nothing() -> None:
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    lines = console.handle_line("should we go north of the ridge?", now_sim=0.0)

    assert lines == []
    assert len(brain_client.payloads) == 1
    assert brain_client.payloads[0].transcript == "should we go north of the ridge?"


def _two_ambiguous_bmp_contacts() -> ContactStore:
    """Two contacts both classified "bmp" but spatially far enough apart
    that `ContactStore.ingest` keeps them distinct -- `belief.tools.
    find_contact("bmp")` returns both, mirroring `test_utterance.py`'s own
    `_store_with_two_far_apart_contacts` helper (kept as a local copy,
    per this file's fixture convention)."""
    store = ContactStore()
    store.ingest(
        [
            Observation(
                id="OBS_1",
                contact_id=None,
                t_sim=0.0,
                t_wall=0.0,
                source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
                classification_raw="BMP-1",
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=_ownship(),
                derived_world_position=DerivedWorldPosition(
                    x=1000.0, z=0.0, confidence=0.9, method="bearing_range_terrain"
                ),
                provenance="test_fixture",
                classification_level=2,
            ),
            Observation(
                id="OBS_2",
                contact_id=None,
                t_sim=0.0,
                t_wall=0.0,
                source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
                classification_raw="BMP-2",
                bearing_deg=180.0,
                range_m=5000.0,
                ownship_at_observation=_ownship(),
                derived_world_position=DerivedWorldPosition(
                    x=-5000.0, z=0.0, confidence=0.9, method="bearing_range_terrain"
                ),
                provenance="test_fixture",
                classification_level=2,
            ),
        ],
        now_sim=0.0,
    )
    assert len(store.contacts) == 2
    return store


def _make_because_valid_for_d10(
    console: CrewConsole, utterance_id: str, because: str
) -> None:
    """`belief.brain_reply.validate_brain_reply` (D10) requires a `PICK`
    reply's `BECAUSE` words to appear both in the escalated transcript
    and in the chosen candidate's own `why` text. "watch that bmp" (the
    deterministic grammar's own ambiguity trigger for
    `_two_ambiguous_bmp_contacts`) carries no word that discriminates
    `BMP-1` from `BMP-2` by construction -- `belief.utterance.
    _resolve_reference` matches the *entire* filler-stripped reference as
    one substring, so a reference specific enough to discriminate (e.g.
    "BMP-1") would resolve unambiguously and never escalate at all.
    Stands in for what a live pilot utterance naming the specific vehicle
    would have looked like, without re-running `parse_utterance` (which
    would collapse the ambiguity), by directly extending this console's
    own tracked transcript for the already-pending escalation."""
    started_sim, parse, _transcript = console._pending_escalations[utterance_id]
    console._pending_escalations[utterance_id] = (
        started_sim,
        parse,
        f"watch that bmp, the {because}",
    )


def test_drain_brain_speaks_stand_by_once_at_the_threshold() -> None:
    """`plans/brain-layer/plan.md` D8, and the plan's own Stage 1
    acceptance criterion: "stand by" is spoken once, not repeatedly, once
    an escalation has been outstanding for `STAND_BY_AFTER_S`."""
    from belief.crew_console import STAND_BY_AFTER_S

    store = ContactStore()
    brain_client = _CapturingBrainClient()
    overlay = FakeOverlayClient()
    console = CrewConsole(
        store=store, brain_client=brain_client, overlay_client=overlay
    )

    console.handle_line("should we go north of the ridge?", now_sim=0.0)

    console.drain_brain(now_sim=STAND_BY_AFTER_S - 0.1)
    assert "Stand by." not in overlay.pushed

    console.drain_brain(now_sim=STAND_BY_AFTER_S)
    assert overlay.pushed.count("Stand by.") == 1

    # Still outstanding on a later poll -- must not speak it again.
    console.drain_brain(now_sim=STAND_BY_AFTER_S + 5.0)
    assert overlay.pushed.count("Stand by.") == 1


def test_drain_brain_pick_contact_deleted_during_delay_yields_lost_him() -> None:
    """`plans/brain-layer/plan.md` D4 and the plan's own Stage 1
    acceptance criterion: "a contact deleted during the delay yields
    'lost him' rather than an action on a stale id." A brain-decided
    `PICK` naming a contact_id no longer present in the store must not
    act on it."""
    store = _two_ambiguous_bmp_contacts()
    contact_id = store.contacts[0].id
    brain_client = _CapturingBrainClient()
    overlay = FakeOverlayClient()
    console = CrewConsole(
        store=store, brain_client=brain_client, overlay_client=overlay
    )

    console.handle_line("watch that bmp", now_sim=0.0)
    assert len(brain_client.payloads) == 1
    utterance_id = brain_client.payloads[0].utterance_id

    _make_because_valid_for_d10(console, utterance_id, "BMP-1")

    # The contact is lost (object-permanence prune, or simply gone from a
    # fresh store in this test) before the brain's reply lands.
    del store._contacts[contact_id]

    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id,
            kind="pick",
            t_sim=0.0,
            contact_id=contact_id,
            because="BMP-1",
        )
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert lines == ["Lost him."]
    assert overlay.pushed == ["Lost him."]


def test_drain_brain_pick_contact_present_acts_and_reads_back() -> None:
    """D4: `PICK <id>`, contact still present -> act, and read back as
    today. `matched_intent == "set_attention"` (the escalating utterance
    was "watch that bmp") means the readback is `render_readback`'s
    "Watching <id>."."""
    store = _two_ambiguous_bmp_contacts()
    contact_id = store.contacts[0].id
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("watch that bmp", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id
    _make_because_valid_for_d10(console, utterance_id, "BMP-1")

    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id,
            kind="pick",
            t_sim=0.0,
            contact_id=contact_id,
            because="BMP-1",
        )
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert lines == [f"Watching {contact_id}."]
    assert store.contacts[0].attention == "watch"


def test_drain_brain_ask_two_survivors_speaks_disambiguation() -> None:
    """D4: `ASK`, >=2 candidates still present -> ask, using the
    survivors."""
    store = _two_ambiguous_bmp_contacts()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("watch that bmp", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id

    brain_client.replies_to_return = [
        BrainReply(utterance_id=utterance_id, kind="ask", t_sim=0.0)
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert len(lines) == 1
    assert lines[0].startswith("Which one -- ")


def test_drain_brain_ask_zero_survivors_yields_lost_him() -> None:
    """D4: `ASK`, 0 candidates still present -> "lost him"."""
    store = _two_ambiguous_bmp_contacts()
    ids = [contact.id for contact in store.contacts]
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("watch that bmp", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id

    for contact_id in ids:
        del store._contacts[contact_id]

    brain_client.replies_to_return = [
        BrainReply(utterance_id=utterance_id, kind="ask", t_sim=0.0)
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert lines == ["Lost him."]


def test_drain_brain_ask_one_survivor_confirms_rather_than_acts() -> None:
    """D4: `ASK`, exactly 1 candidate still present -> confirm the
    survivor rather than acting on it -- "only one left" is not the same
    as "the pilot meant this one"."""
    store = _two_ambiguous_bmp_contacts()
    survivor_id = store.contacts[0].id
    doomed_id = store.contacts[1].id
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("watch that bmp", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id

    del store._contacts[doomed_id]

    brain_client.replies_to_return = [
        BrainReply(utterance_id=utterance_id, kind="ask", t_sim=0.0)
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert len(lines) == 1
    assert lines[0].endswith(", confirm?")
    # Not yet acted on.
    assert store.contacts[0].attention != "watch"

    # Affirming now acts on the confirmed survivor.
    affirm_lines = console.handle_transcript(
        "affirm",
        confidence=0.9,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=2.0,
    )
    assert affirm_lines == [f"Watching {survivor_id}."]


def test_drain_brain_confirm_sets_pending_confirmation() -> None:
    """D9: a `CONFIRM <token>` reply sets `_pending_confirmation`, reusing
    the exact voice confirm-band mechanism."""
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("scan somethinggarbled", now_sim=0.0)
    assert len(brain_client.payloads) == 1
    utterance_id = brain_client.payloads[0].utterance_id

    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id, kind="confirm", t_sim=0.0, token="report_all"
        )
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert lines == ["Report, confirm?"]
    assert console._pending_confirmation is not None
    assert console._pending_confirmation.token == "report_all"


def test_drain_brain_unable_speaks_the_reason() -> None:
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("should we go north of the ridge?", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id

    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id,
            kind="unable",
            t_sim=0.0,
            reason="NO_SUCH_COMMAND",
        )
    ]
    lines = console.drain_brain(now_sim=1.0)

    assert lines == ["Unable, no such command."]


def test_drain_brain_discards_stale_reply() -> None:
    """D4: a reply older than `BRAIN_REPLY_MAX_AGE_S` is discarded
    silently."""
    from belief.crew_console import BRAIN_REPLY_MAX_AGE_S

    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    console.handle_line("should we go north of the ridge?", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id

    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id, kind="unable", t_sim=0.0, reason="NO_MATCH"
        )
    ]
    lines = console.drain_brain(now_sim=BRAIN_REPLY_MAX_AGE_S + 1.0)

    assert lines == []


def test_drain_brain_reply_for_untracked_utterance_is_discarded_silently() -> None:
    """A reply for an id this session never escalated (or already handled)
    must not raise or speak anything."""
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    brain_client.replies_to_return = [
        BrainReply(
            utterance_id="U_UNKNOWN", kind="unable", t_sim=0.0, reason="NO_MATCH"
        )
    ]

    lines = console.drain_brain(now_sim=1.0)

    assert lines == []


def test_drain_brain_poll_failure_is_logged_and_continues() -> None:
    class _RaisingBrainClient:
        def handle(self, payload: EscalationPayload) -> None:
            return None

        def awaiting_reply_id(self) -> str | None:
            return None

        def poll_replies(self) -> list[BrainReply]:
            raise RuntimeError("simulated transport failure")

    console = CrewConsole(store=ContactStore(), brain_client=_RaisingBrainClient())
    assert console.drain_brain(now_sim=1.0) == []


class _WedgedBrainServer:
    """A TCP listener that accepts every connection and never answers it
    -- the "up but wedged" brain process
    `plans/brain-layer/performance-review.md` measured (5015ms per
    `poll_replies()` call, every call, no backoff, ~83% tick-rate loss on
    the shared crew-text poll thread). Own copy of `test_brain_client.
    _WedgedServer` (test files in this project are self-contained, no
    shared `conftest.py` helper for this yet) -- raw `socket`, not
    `http.server`, so nothing can accidentally answer the request."""

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._accepted: list[socket.socket] = []

    def __enter__(self) -> Self:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self._sock.settimeout(0.2)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        return self

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (TimeoutError, OSError):
                continue
            self._accepted.append(conn)  # kept open, never read or written

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        assert self._thread is not None
        self._thread.join(timeout=2)
        for conn in self._accepted:
            conn.close()
        assert self._sock is not None
        self._sock.close()

    @property
    def base_url(self) -> str:
        assert self._sock is not None
        port = self._sock.getsockname()[1]
        return f"http://127.0.0.1:{port}"


def test_drain_brain_tick_rate_unaffected_by_a_wedged_brain() -> None:
    """User direction, 2026-09-25: "brain must not block any other
    functionality... if thinking takes time, other things happen
    meanwhile." Proves the actual acceptance criterion end to end through
    `CrewConsole.drain_brain` against a real (if fake) HTTP-level wedge --
    not just `BrainLayerClient.poll_replies()`'s own unit-level guarantee
    (`test_brain_client.py`) -- since `drain_brain` is what the shared
    crew-text poll thread actually calls once per tick alongside
    `drain_events`/`_poll_f10_commands`/`_poll_transcripts`. Before the
    fix, this exact scenario cost 5015ms per call, every call."""
    with _WedgedBrainServer() as server:
        brain_client = BrainLayerClient(base_url=server.base_url, poll_timeout_s=5.0)
        console = CrewConsole(store=ContactStore(), brain_client=brain_client)

        start = time.monotonic()
        for i in range(20):
            assert console.drain_brain(now_sim=float(i)) == []
        elapsed = time.monotonic() - start

        # 20 ticks against a wedged brain, well under one old-design
        # single-call timeout (5s) -- each `drain_brain` call only ever
        # drains a local buffer, it never itself waits on the network.
        assert elapsed < 1.0


def test_drain_events_not_gated_by_an_in_flight_escalation() -> None:
    """User direction, 2026-09-25: "while the model is thinking, everything
    else must keep running and keep being spoken -- contact reports, watch
    reporting, callouts. The brain being mid-decision must never gate
    speech." Proves it directly: with a real escalation outstanding
    (`_pending_escalations` non-empty, no reply has landed yet), a queued
    lifecycle event still speaks normally through `drain_events` -- nothing
    in `_print`/`CalloutScheduler` reads escalation state at all (confirmed
    by inspection), pinned here as a regression guard rather than left
    implicit."""
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    # An outstanding escalation the brain has not yet answered.
    console.handle_line("should we go north of the ridge?", now_sim=0.0)
    assert len(brain_client.payloads) == 1
    assert console._pending_escalations  # genuinely still outstanding

    # A contact is detected while that escalation is still pending.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    spoken = console.drain_events(now_sim=0.0)
    assert spoken == ["BMP-2."]


def test_scripted_crew_session_reproduces_the_first_useful_success_criterion() -> None:
    """`docs/concept/PETROBRAIN_RUNTIME.md`'s "First useful success
    criterion", plus a readback, a contact report, and an injected urgent
    call -- the plan's full acceptance criterion in one scripted session."""
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)

    # Petrovich detects a vehicle.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    detected_lines = console.drain_events(now_sim=0.0)
    assert detected_lines == ["BMP-2."]

    # Player: "watch <id>" -> a readback, no brain call.
    readback_lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)
    assert readback_lines == [f"Watching {contact_id}."]
    assert brain_client.payloads == []

    # Petrovich later loses it -- CONTACT_LOST has no template, nothing spoken.
    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)
    lost_lines = console.drain_events(now_sim=lost_at)
    assert lost_lines == []

    # Petrovich later detects it again, at the same believed classification
    # and position -- `plans/group-reporting/plan.md` Stage 1's disclosure
    # gate suppresses this `CONTACT_REACQUIRED`, since its rendered text
    # ("BMP-2.") is byte-identical to the "BMP-2." already spoken above.
    # (Behaviour change from this test's own pre-Stage-1 assertion, which
    # expected the identical line to be re-spoken -- exactly the repeat
    # Stage 1 exists to suppress.)
    reacquired_at = lost_at + 1.0
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=reacquired_at, classification_raw="BMP-2")],
        now_sim=reacquired_at,
    )
    store.tick(now_sim=reacquired_at)
    reacquired_lines = console.drain_events(now_sim=reacquired_at)
    assert reacquired_lines == []

    # Player: "Where was that BMP?" -> a memory-backed answer, not a guess.
    answer_lines = console.handle_line("where was that bmp?", now_sim=reacquired_at)
    assert len(answer_lines) == 1
    assert answer_lines[0].startswith("BMP-2")
    assert brain_client.payloads == []  # answered from structured memory, no escalation

    # A contact report, triggered the same way ("status <id>").
    report_lines = console.handle_line(f"status {contact_id}", now_sim=reacquired_at)
    assert len(report_lines) == 1
    assert report_lines[0].startswith("BMP-2")

    # An injected urgent call -- Stage 5's manual bypass_gate test harness.
    urgent_lines = console.handle_line(
        f"!inject-urgent {contact_id} Missile launch, 9 o'clock! Break right!",
        now_sim=reacquired_at,
    )
    assert urgent_lines == ["Missile launch, 9 o'clock! Break right!"]


def test_inject_urgent_usage_message_with_too_few_arguments() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_line("!inject-urgent CONTACT_1", now_sim=0.0)
    assert lines == ["usage: !inject-urgent <contact_id> <text>"]


def test_act_reports_no_such_contact_for_a_reference_that_has_since_vanished() -> None:
    """`belief.utterance.parse_utterance` only ever resolves a reference to
    a contact id that exists in the store at parse time, so `_act`'s
    "no such contact" branches are defensive rather than reachable through
    `handle_line` alone (mirrors `belief.console.format_event_for_overlay`'s
    own defensive fallback for a similarly-impossible-in-practice case) --
    exercised directly here so the defensive code itself stays correct."""
    from belief.utterance import PartialParse

    console = CrewConsole(store=ContactStore())
    watch_parse = PartialParse(
        matched_intent="set_attention",
        confidence=1.0,
        disposition="handled",
        attention_level="watch",
        referenced_contact_id="CONTACT_999",
    )
    assert console._act(watch_parse, now_sim=0.0) == ["no such contact: CONTACT_999"]

    describe_parse = PartialParse(
        matched_intent="describe_contact",
        confidence=1.0,
        disposition="handled",
        referenced_contact_id="CONTACT_999",
    )
    assert console._act(describe_parse, now_sim=0.0) == ["no such contact: CONTACT_999"]


def test_console_prints_to_its_configured_output() -> None:
    import io

    store = ContactStore()
    output = io.StringIO()
    console = CrewConsole(store=store, output=output)
    console.handle_line("!inject-urgent CONTACT_1 test call", now_sim=0.0)
    assert output.getvalue() == "test call\n"


def test_no_overlay_push_when_overlay_client_is_unset() -> None:
    # overlay_client defaults to None: a true no-op, no AttributeError, no
    # push attempted -- existing no-op default, asserted explicitly here.
    store = ContactStore()
    console = CrewConsole(store=store)
    lines = console.handle_line("!inject-urgent CONTACT_1 test call", now_sim=0.0)
    assert lines == ["test call"]


def test_readback_pushes_to_overlay() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=store, overlay_client=overlay_client)  # type: ignore[arg-type]

    lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)

    assert lines == [f"Watching {contact_id}."]
    assert overlay_client.pushed == [f"Watching {contact_id}."]


def test_contact_report_pushes_to_overlay() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=store, overlay_client=overlay_client)  # type: ignore[arg-type]

    lines = console.handle_line(f"status {contact_id}", now_sim=0.0)

    assert len(lines) == 1
    assert overlay_client.pushed == lines


def test_drained_lifecycle_event_pushes_to_overlay() -> None:
    store = ContactStore()
    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=store, overlay_client=overlay_client)  # type: ignore[arg-type]

    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    spoken = console.drain_events(now_sim=0.0)

    assert len(spoken) == 1
    assert overlay_client.pushed == spoken


def test_urgent_call_pushes_to_overlay_with_prefix_but_prints_unprefixed() -> None:
    import io

    store = ContactStore()
    overlay_client = FakeOverlayClient()
    output = io.StringIO()
    console = CrewConsole(
        store=store,
        output=output,
        overlay_client=overlay_client,  # type: ignore[arg-type]
    )

    lines = console.handle_line(
        "!inject-urgent CONTACT_1 Missile launch, 9 o'clock! Break right!",
        now_sim=0.0,
    )

    assert lines == ["Missile launch, 9 o'clock! Break right!"]
    assert output.getvalue() == "Missile launch, 9 o'clock! Break right!\n"
    assert overlay_client.pushed == ["!! Missile launch, 9 o'clock! Break right!"]


def test_inject_urgent_usage_message_is_not_prefixed_when_pushed() -> None:
    store = ContactStore()
    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=store, overlay_client=overlay_client)  # type: ignore[arg-type]

    lines = console.handle_line("!inject-urgent CONTACT_1", now_sim=0.0)

    assert lines == ["usage: !inject-urgent <contact_id> <text>"]
    assert overlay_client.pushed == ["usage: !inject-urgent <contact_id> <text>"]


def test_failed_overlay_push_degrades_without_raising_and_does_not_block_remaining_lines() -> (
    None
):
    store = ContactStore()
    store.ingest(
        [
            _observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2"),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    detected_line = "BMP-2."

    overlay_client = FakeOverlayClient(fail_on=frozenset({detected_line}))
    console = CrewConsole(store=store, overlay_client=overlay_client)  # type: ignore[arg-type]

    # drain_events would normally push one line for the CONTACT_DETECTED
    # event above; make that push fail and confirm it degrades silently.
    spoken = console.drain_events(now_sim=0.0)
    assert spoken == [detected_line]
    assert overlay_client.pushed == []  # the one push failed, nothing recorded

    # A second, unrelated push in a later call must still go through --
    # one failed push must not disable the sink for subsequent lines.
    lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)
    assert overlay_client.pushed == [f"Watching {contact_id}."]
    assert lines == [f"Watching {contact_id}."]


# -- speech_client (BL-10 first slice, plans/tts-voice-output/plan.md) ------


def test_no_speech_push_when_speech_client_is_unset() -> None:
    # speech_client defaults to None: a true no-op, no AttributeError, no
    # push attempted -- mirrors overlay_client's own no-op default.
    store = ContactStore()
    console = CrewConsole(store=store)
    lines = console.handle_line("!inject-urgent CONTACT_1 test call", now_sim=0.0)
    assert lines == ["test call"]


def test_readback_pushes_to_speech_client_as_routine() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    speech_client = FakeSpeechClient()
    console = CrewConsole(store=store, speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)

    assert lines == [f"Watching {contact_id}."]
    assert speech_client.pushed == [(f"Watching {contact_id}.", False)]


def test_drained_lifecycle_event_pushes_to_speech_client_as_routine() -> None:
    store = ContactStore()
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=store, speech_client=speech_client)  # type: ignore[arg-type]

    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    spoken = console.drain_events(now_sim=0.0)

    assert len(spoken) == 1
    assert speech_client.pushed == [(spoken[0], False)]


def test_urgent_call_pushes_to_speech_client_as_urgent() -> None:
    store = ContactStore()
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=store, speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_line(
        "!inject-urgent CONTACT_1 Missile launch, 9 o'clock! Break right!",
        now_sim=0.0,
    )

    assert lines == ["Missile launch, 9 o'clock! Break right!"]
    # Unlike the overlay sink (which gets a "!! " text prefix), the speech
    # sink gets the *unmodified* text with urgent=True -- bypass_gate is
    # threaded straight through as push_speech's urgent argument, not
    # encoded into the text (plan Decision 3).
    assert speech_client.pushed == [("Missile launch, 9 o'clock! Break right!", True)]


def test_failed_speech_push_degrades_without_raising_and_does_not_block_overlay() -> (
    None
):
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    detected_line = "BMP-2."

    overlay_client = FakeOverlayClient()
    speech_client = FakeSpeechClient(fail_on=frozenset({detected_line}))
    console = CrewConsole(
        store=store,
        overlay_client=overlay_client,  # type: ignore[arg-type]
        speech_client=speech_client,  # type: ignore[arg-type]
    )

    # The speech push fails, but the overlay push for the same line must
    # still succeed -- one sink's failure must not block another's.
    spoken = console.drain_events(now_sim=0.0)
    assert spoken == [detected_line]
    assert overlay_client.pushed == [detected_line]
    assert speech_client.pushed == []

    # A second, unrelated push in a later call must still go through --
    # one failed push must not disable the sink for subsequent lines.
    lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)
    assert speech_client.pushed == [(f"Watching {contact_id}.", False)]
    assert lines == [f"Watching {contact_id}."]


# -- handle_command (plans/f10-crew-commands/plan.md) -------------------


def test_handle_command_unrecognized_token_returns_empty_list() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_command("shut_down_dcs", now_sim=0.0) == []


# -- stop_talking (Stage 3, plans/inbound-speech/plan.md, revised by the ----
# Stage 3 follow-up, user direction 2026-09-20: "no readback or            --
# confirmation, just stop talking" -- an exception to the readback/confirm --
# rule, not the deferred-from-Stage-2 "Copy." acknowledgement this token   --
# originally shipped with) -----------------------------------------------


def test_stop_talking_speaks_nothing() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_command("stop_talking", now_sim=0.0)
    assert lines == []


def test_stop_talking_calls_speech_client_stop_not_push_speech() -> None:
    """The whole point of `stop_talking`: it must reach the interrupt-only
    `AudioAdapterClient.stop()` (`POST /stop`), never `push_speech` -- no
    audio is ever synthesized or delivered for this token."""
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_command("stop_talking", now_sim=0.0)

    assert lines == []
    assert speech_client.pushed == []
    assert speech_client.stop_calls == 1


def test_stop_talking_pushes_nothing_to_the_overlay() -> None:
    """No line, no overlay push, no `"!! "` prefix -- `_print` is never
    called for this token at all."""
    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=ContactStore(), overlay_client=overlay_client)  # type: ignore[arg-type]

    console.handle_command("stop_talking", now_sim=0.0)

    assert overlay_client.pushed == []


def test_stop_talking_interrupt_failure_does_not_raise() -> None:
    """A failed interrupt call degrades silently -- same per-sink isolation
    posture as every other `speech_client` use in `_print`, even though
    this call bypasses `_print` entirely."""
    speech_client = FakeSpeechClient(fail_on=frozenset({"Copy."}))
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_command("stop_talking", now_sim=0.0)

    assert lines == []


# -- silence (`plans/silence-command/plan.md`, user direction 2026-10-04: -----
# "make Petrovich not talk until my next command", absolute silence incl. -----
# urgent callouts, one spoken acknowledgement, any subsequent command ends ----
# it) -----------------------------------------------------------------------


def test_silence_speaks_one_word_acknowledgement_then_goes_quiet() -> None:
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_command("silence", now_sim=0.0)

    # Nothing comes back through handle_command's own return value (same
    # no-return shape as stop_talking) -- the ack already went out via
    # `_print`, inside `_handle_silence`, before this returns.
    assert lines == []
    assert speech_client.pushed == [("Quiet.", False)]
    assert console.silenced is True


def test_silence_pushes_nothing_to_the_overlay_differently_than_speech() -> None:
    """The acknowledgement is spoken *and* shown -- `silence` gates only
    the audio sink, never the overlay, even for its own ack."""
    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=ContactStore(), overlay_client=overlay_client)  # type: ignore[arg-type]

    console.handle_command("silence", now_sim=0.0)

    assert overlay_client.pushed == ["Quiet."]


def test_silence_does_not_call_speech_client_stop() -> None:
    """`silence` and `stop_talking` answer different questions -- silence
    must not reach for the interrupt-only call `stop_talking` owns."""
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    console.handle_command("silence", now_sim=0.0)

    assert speech_client.stop_calls == 0


def test_silence_suppresses_a_drained_callout_that_would_otherwise_be_spoken() -> None:
    store = ContactStore()
    speech_client = FakeSpeechClient()
    overlay_client = FakeOverlayClient()
    console = CrewConsole(
        store=store,
        speech_client=speech_client,  # type: ignore[arg-type]
        overlay_client=overlay_client,  # type: ignore[arg-type]
    )
    console.handle_command("silence", now_sim=0.0)
    speech_client.pushed.clear()
    overlay_client.pushed.clear()

    # Well clear of the ack's own `CalloutScheduler.busy_until_sim` budget
    # (`note_reply` still runs unconditionally -- see `_print`'s docstring
    # on why that bookkeeping is deliberately not gated on `silenced`).
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=10.0, classification_raw="BMP-2")],
        now_sim=10.0,
    )
    store.tick(now_sim=10.0)
    spoken = console.drain_events(now_sim=10.0)

    # The event is still chosen and rendered by the scheduler -- it is not
    # held back to be dumped later (suppressed, not deferred) -- it is
    # simply never voiced.
    assert len(spoken) == 1
    assert speech_client.pushed == []
    # The text/overlay surfaces are untouched by silence (decision:
    # the use case is audio, so crew-text/overlay keep working).
    assert overlay_client.pushed == [spoken[0]]


def test_silence_suppresses_an_injected_urgent_call_too() -> None:
    """The user's explicit choice: absolute silence, including urgent
    threat callouts -- shown the risk (silenced near a friendly airbase,
    a Shilka opens up and says nothing) and chose absolute anyway."""
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]
    console.handle_command("silence", now_sim=0.0)
    speech_client.pushed.clear()

    lines = console.handle_line(
        "!inject-urgent CONTACT_1 Missile launch, 9 o'clock! Break right!",
        now_sim=1.0,
    )

    # The line is still produced (the overlay/text path, and the return
    # value, are unaffected by silence) -- only the audio push is gated.
    assert lines == ["Missile launch, 9 o'clock! Break right!"]
    assert speech_client.pushed == []


def test_silence_twice_is_a_no_op_not_a_toggle() -> None:
    """A repeated `silence` must stay silent, not un-silence -- a toggle
    would make a repeated press ambiguous when the pilot has lost track
    of whether he is already silenced."""
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    first = console.handle_command("silence", now_sim=0.0)
    second = console.handle_command("silence", now_sim=1.0)

    assert first == []
    assert second == []
    assert console.silenced is True
    # The acknowledgement was spoken exactly once, not once per `silence`.
    assert speech_client.pushed == [("Quiet.", False)]


def test_a_subsequent_command_ends_silence_and_is_itself_heard() -> None:
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]
    console.handle_command("silence", now_sim=0.0)
    speech_client.pushed.clear()

    lines = console.handle_command("watch_nearest", now_sim=1.0)

    assert console.silenced is False
    assert lines  # watch_nearest without enrichment still speaks a line
    assert speech_client.pushed == [(lines[0], False)]


def test_silence_ends_and_the_next_drained_callout_is_heard() -> None:
    store = ContactStore()
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=store, speech_client=speech_client)  # type: ignore[arg-type]
    console.handle_command("silence", now_sim=0.0)
    console.handle_command("watch_nearest", now_sim=1.0)  # any command ends it
    speech_client.pushed.clear()

    # Well clear of both prior replies' `busy_until_sim` budgets.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=10.0, classification_raw="BMP-2")],
        now_sim=10.0,
    )
    store.tick(now_sim=10.0)
    spoken = console.drain_events(now_sim=10.0)

    assert len(spoken) == 1
    assert speech_client.pushed == [(spoken[0], False)]


def test_unrecognised_free_text_does_not_end_silence() -> None:
    """Stray speech recognised as nothing (the use case: radio traffic
    picked up while silenced) must not break silence -- only a real
    command does."""
    console = CrewConsole(store=ContactStore())
    console.handle_command("silence", now_sim=0.0)

    console.handle_line("should we go north of the ridge?", now_sim=1.0)

    assert console.silenced is True


def test_recognised_free_text_command_ends_silence() -> None:
    """Unlike stray speech, a typed/spoken sentence the grammar actually
    resolves to an intent (`belief.utterance.parse_utterance`) is a real
    command and ends silence, same as a token-level one."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    console = CrewConsole(store=store)
    console.handle_command("silence", now_sim=0.0)

    console.handle_line(f"watch {contact_id}", now_sim=1.0)

    assert console.silenced is False


# -- `[[BL-B81]]` radio check / greeting -- an ordinary command, like any ---
# other: it ends an explicit `silence`, is answered on the ground, and gets ---
# the refusal line in refusal mode (plans/radio-check/plan.md). ------------


def test_radio_check_token_answers_loud_and_clear() -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_command("radio_check", now_sim=0.0) == ["Loud and clear."]


def test_radio_check_works_on_the_ground() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = True

    assert console.handle_command("radio_check", now_sim=0.0) == ["Loud and clear."]


def test_radio_check_ends_an_explicit_silence() -> None:
    console = CrewConsole(store=ContactStore())
    console.handle_command("silence", now_sim=0.0)

    console.handle_command("radio_check", now_sim=1.0)

    assert console.silenced is False


def test_radio_check_in_refusal_mode_gets_the_refusal_line() -> None:
    from belief.crew_console import WORLD_MODEL_NOT_LOADED_REFUSAL

    console = CrewConsole(store=ContactStore())
    console.refused = True

    assert console.handle_command("radio_check", now_sim=0.0) == [
        WORLD_MODEL_NOT_LOADED_REFUSAL
    ]


@pytest.mark.parametrize(
    "time_of_day,expected",
    [
        ("morning", "Good morning, commander."),
        ("day", "Good day, commander."),
        ("evening", "Good evening, commander."),
        ("night", "Good night, commander."),
    ],
)
def test_greeting_token_echoes_the_pilots_own_word(
    time_of_day: str, expected: str
) -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_command(
        "greeting", now_sim=0.0, slots={"time_of_day": time_of_day}
    ) == [expected]


def test_greeting_times_of_day_are_exactly_the_four_greetings() -> None:
    """This side of the `_GREETING_TIMES_OF_DAY` <-> audio-adapter's own
    `vocabulary.TIME_OF_DAY_WORDS` hand-synced mirror --
    `test_time_of_day_words_are_exactly_the_four_greetings` in
    `audio-adapter/tests/test_vocabulary.py` asserts the same membership
    against its own set; a drift then fails a test on whichever side
    changed, rather than during a sortie."""
    assert _GREETING_TIMES_OF_DAY == frozenset({"morning", "day", "evening", "night"})


def test_greeting_with_missing_slot_degrades_to_say_again() -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_command("greeting", now_sim=0.0) == [
        "say again -- no greeting heard"
    ]


def test_typed_radio_check_dispatches_through_handle_line() -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_line("radio check", now_sim=0.0) == ["Loud and clear."]


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("good morning Petrovich", "Good morning, commander."),
        ("good evening petrovich", "Good evening, commander."),
        ("Good Night Petrovich.", "Good night, commander."),
    ],
)
def test_typed_greeting_dispatches_through_handle_line(
    phrase: str, expected: str
) -> None:
    console = CrewConsole(store=ContactStore())

    assert console.handle_line(phrase, now_sim=0.0) == [expected]


def test_typed_radio_check_in_refusal_mode_gets_the_refusal_line() -> None:
    from belief.crew_console import WORLD_MODEL_NOT_LOADED_REFUSAL

    console = CrewConsole(store=ContactStore())
    console.refused = True

    assert console.handle_line("radio check", now_sim=0.0) == [
        WORLD_MODEL_NOT_LOADED_REFUSAL
    ]


# -- BL-15 Stage 3: loud-refusal mode (plans/bl15-mission-start/plan.md, ----
# user direction 2026-10-19: "on error loud refusal is better") -- every ----
# player command gets the fixed line while CrewConsole.refused is set. ------


def test_refused_handle_command_returns_the_fixed_refusal_line() -> None:
    console = CrewConsole(store=ContactStore())
    console.refused = True

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert lines == ["system error, world model not loaded"]


def test_refused_handle_line_returns_the_fixed_refusal_line() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    console = CrewConsole(store=store)
    console.refused = True

    lines = console.handle_line(f"watch {contact_id}", now_sim=0.0)

    assert lines == ["system error, world model not loaded"]


def test_refused_handle_transcript_returns_the_fixed_refusal_line() -> None:
    console = CrewConsole(store=ContactStore())
    console.refused = True

    lines = console.handle_transcript(
        "watch nearest",
        confidence=0.9,
        token="watch_nearest",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["system error, world model not loaded"]


def test_refused_blocks_dispatch_entirely_not_just_the_readback() -> None:
    """The refused command must not run at all -- `watch_nearest` would
    otherwise register a `PendingIntent`; confirm none is created."""
    tasks = TaskStore()
    console = CrewConsole(store=ContactStore(), tasks=tasks)
    console.refused = True

    console.handle_command("watch_nearest", now_sim=0.0)

    assert tasks.tasks == []


def test_refused_does_not_end_silence_or_increment_commands_handled() -> None:
    """A refused command is not dispatch -- it must not reset any of the
    per-dispatch bookkeeping a real dispatch would (`commands_handled`,
    `silenced`'s "any command ends silence" rule). `silence` itself is
    issued *before* `refused` is set, since the whole point is to compare
    before/after: a real dispatch (this first `silence` call) does count
    and does set `silenced`; the refused call that follows must change
    neither."""
    console = CrewConsole(store=ContactStore())
    console.handle_command("silence", now_sim=0.0)
    commands_handled_before_refusal = console.commands_handled
    console.refused = True

    console.handle_command("watch_nearest", now_sim=1.0)

    assert console.commands_handled == commands_handled_before_refusal
    assert console.silenced is True


def test_not_refused_by_default_dispatches_normally() -> None:
    """`refused` defaults to `False` -- an ordinary `CrewConsole` built
    without touching it dispatches exactly as before this stage."""
    console = CrewConsole(store=ContactStore())

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert lines != ["system error, world model not loaded"]


# -- Batch 2 review required fix (`plans/bl15-mission-start/review.md`, ----
# "(a)"): `drain_events`/`drain_brain` must not speak proactively while ----
# `refused` either -- constructed directly against a non-empty store/ -----
# pending-escalation state, bypassing the reset-always-precedes-refusal ----
# call graph `logger.py` happens to give today, so these do not depend on ---
# that invariant holding. -----------------------------------------------


def test_refused_drain_events_speaks_nothing_against_a_non_empty_store() -> None:
    """A real, unacknowledged `CONTACT_DETECTED` event is present (built
    directly on the store, not via `logger.py`'s reset-then-refuse call
    graph) and `console.refused` is set directly -- proves the guard is a
    property of `CrewConsole` itself, not a consequence of the store
    always being empty by the time refusal is reached."""
    store = ContactStore()
    overlay = FakeOverlayClient()
    console = CrewConsole(store=store, overlay_client=overlay)
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console.refused = True

    spoken = console.drain_events(now_sim=0.0)

    assert spoken == []
    assert overlay.pushed == []


def test_refused_drain_events_consumes_rather_than_leaves_the_event_queued() -> None:
    """Drain and discard, not leave queued (the review's explicit
    either/or) -- once refusal clears, the event that was pending while
    refused must not surface then, spoken against belief computed before
    the refusal/switch rather than after it."""
    store = ContactStore()
    console = CrewConsole(store=store)
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console.refused = True
    assert console.drain_events(now_sim=0.0) == []

    console.refused = False

    assert console.drain_events(now_sim=0.0) == []


def test_refused_drain_brain_speaks_nothing_against_a_pending_escalation() -> None:
    """A real escalation is outstanding and a reply for it is queued
    (built directly, not via `logger.py`'s call graph) -- `console.refused`
    set directly must stop both D8's "stand by" and the reply's own
    readback/confirm/pick action, not merely suppress the returned lines
    while still running `_handle_brain_reply`'s side effects
    (`_print`/`_act`)."""
    from belief.crew_console import STAND_BY_AFTER_S

    store = ContactStore()
    brain_client = _CapturingBrainClient()
    overlay = FakeOverlayClient()
    tasks = TaskStore()
    console = CrewConsole(
        store=store, brain_client=brain_client, overlay_client=overlay, tasks=tasks
    )
    console.handle_line("scan somethinggarbled", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id
    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id, kind="confirm", t_sim=0.0, token="report_all"
        )
    ]
    console.refused = True

    lines = console.drain_brain(now_sim=STAND_BY_AFTER_S + 5.0)

    assert lines == []
    assert overlay.pushed == []
    assert console._pending_confirmation is None


def test_refused_drain_brain_consumes_rather_than_leaves_the_reply_queued() -> None:
    """Drain and discard, not leave queued: the reply drained while
    refused must not resurface once refusal clears -- `brain_client.
    poll_replies()` has already handed it over (a real queue-draining
    client would not return it twice), and `_pending_escalations` must no
    longer be tracking its `utterance_id` either."""
    store = ContactStore()
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.handle_line("should we go north of the ridge?", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id
    brain_client.replies_to_return = [
        BrainReply(
            utterance_id=utterance_id,
            kind="unable",
            t_sim=0.0,
            reason="NO_SUCH_COMMAND",
        )
    ]
    console.refused = True

    assert console.drain_brain(now_sim=1.0) == []
    assert utterance_id not in console._pending_escalations

    console.refused = False

    assert console.drain_brain(now_sim=2.0) == []


# -- on_ground / look-command refusal (`[[BL-B82]]`, replacing the former --
# `maybe_apply_on_ground_default` silence default -- plans/radio-check/ -----
# plan.md) -------------------------------------------------------------


def test_look_command_on_ground_answers_unable() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = True

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        "Unable, on the ground."
    ]


def test_look_command_airborne_dispatches_normally() -> None:
    """The same token, the same store contents, airborne instead of on the
    ground -- the only thing that changed is `on_ground`."""
    console = CrewConsole(store=ContactStore())
    console.on_ground = False

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        "no contact to watch"
    ]


def test_scan_command_on_ground_answers_unable() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = True

    assert console.handle_command("scan_ahead", now_sim=0.0) == [
        "Unable, on the ground."
    ]


def test_follow_on_ground_answers_unable() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = True

    assert console.handle_command(
        "follow", now_sim=0.0, slots={"descriptor": "armor"}
    ) == ["Unable, on the ground."]


def test_look_command_on_ground_still_ends_silence() -> None:
    """A refused-on-the-ground look command is still a real command --
    it was heard and understood, the "any command ends silence" rule
    (`plans/silence-command/plan.md`) applies to it exactly like every
    other command."""
    console = CrewConsole(store=ContactStore())
    console.silenced = True
    console.on_ground = True

    console.handle_command("watch_nearest", now_sim=0.0)

    assert console.silenced is False


def test_non_look_command_on_ground_dispatches_normally() -> None:
    """`mark_here`/`observ_on`/etc are not in `_LOOK_COMMAND_TOKENS` -- on
    the ground they dispatch exactly as if airborne (they only read
    existing belief or register a non-perception task). `sight_ready`
    set so this exercises the on-ground path, not `BL-B66` Stage 3's
    separate readiness gate (see `test_observ_on_signals_the_poll_loop_
    and_speaks` for that one)."""
    console = CrewConsole(store=ContactStore())
    console.on_ground = True
    console.sight_ready = True

    assert console.handle_command("observ_on", now_sim=0.0) == ["Observ on."]


def test_refusal_mode_wins_over_on_ground_for_a_look_command() -> None:
    """`[[BL-15]]`'s refusal mode takes precedence over everything else
    `handle_command` does, on-ground included."""
    from belief.crew_console import WORLD_MODEL_NOT_LOADED_REFUSAL

    console = CrewConsole(store=ContactStore())
    console.on_ground = True
    console.refused = True

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        WORLD_MODEL_NOT_LOADED_REFUSAL
    ]


def test_watch_nearest_without_enrichment_reports_no_contact_to_watch() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store)
    console.on_ground = False

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        "no contact to watch"
    ]


def test_watch_nearest_reports_no_contact_to_watch_when_store_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        "no contact to watch"
    ]


def test_watch_nearest_selects_the_nearest_contact_by_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_with_ownship_x(
                obs_id="OBS_FAR",
                t_sim=0.0,
                classification_raw="BMP-2",
                ownship_x=2000.0,
            ),
            _observation_with_ownship_x(
                obs_id="OBS_NEAR", t_sim=0.0, classification_raw="T-72", ownship_x=500.0
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    near_contact = next(c for c in store.contacts if c.classification.value == "T-72")

    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("watch_nearest", now_sim=0.0)

    # Contact-report wording (unit type, clock, range), no spoken id -- the
    # player named no contact, so the readback has to say which one it was.
    assert lines == ["Watching T-72, 12 o'clock, 0.5 kilometres near a village."]
    assert near_contact.id not in lines[0]
    assert near_contact.attention == "watch"


def test_watch_nearest_tags_every_group_member_watched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sortie 2026-10-05 debrief, Item 3: "follow/watch group <where>
    should tag all units in that group as watched." Two contacts at the
    same clock/range resolve into one real `belief.groups.Group`
    (`GroupStore`'s own proximity reconciliation); `watch_nearest` picking
    one of them must mark both watched, and register a cancellable task
    for both when a `TaskStore` is configured -- the group tag reuses the
    identical per-member mechanism the single-contact case already uses,
    not a special-cased bulk write."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_NEAR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_FAR",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert lines == ["Watching two."]
    assert all(c.attention == "watch" for c in store.contacts)
    assert len(store.contacts) == 2
    assert len(tasks.tasks) == 2
    assert {task.contact_id for task in tasks.tasks} == {c.id for c in store.contacts}
    assert all(task.kind == "watch_contact" for task in tasks.tasks)


def test_follow_tags_every_group_member_watched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same group-tagging rule (Item 3), reached through `follow`'s
    descriptor-matching path instead of `watch_nearest`'s nearest-by-range
    pick -- `_mark_watched_with_group` is shared between the two, so this
    is the same mechanism exercised through its other caller, not a
    second implementation to keep in sync."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False

    lines = console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})

    assert lines == ["Watching two."]
    assert all(c.attention == "watch" for c in store.contacts)


def test_watch_nearest_a_single_ungrouped_contact_is_unaffected_by_group_tagging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for Item 3: a single, ungrouped contact must keep
    behaving exactly as before -- the ordinary per-contact readback, not
    the group-count wording, and no extra task registered for anyone
    else."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert "watching two" not in lines[0].lower()
    assert contact.attention == "watch"
    assert len(tasks.tasks) == 1


def test_watch_nearest_group_readback_counts_only_members_actually_marked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Security review 2026-10-05, finding 1: `Group.member_contact_ids`
    is recomputed from the live `Contact` set by `GroupStore.reconcile`,
    so between a reconcile and the next command a member id can stop
    resolving to a live contact. Speaking `len(member_ids)` would then
    assert a count the code never verified -- and the pilot cannot
    observe the discrepancy, because the un-tagged member simply never
    reports. A two-member group that has lost one member must fall back
    to the single-contact readback rather than say "Watching two.", and
    must register exactly one task."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    stale_group = Group(
        id="GROUP_STALE",
        member_contact_ids=frozenset({contact.id, "CONTACT_NO_LONGER_LIVE"}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
    )
    monkeypatch.setattr(store, "group_for_contact", lambda _id: stale_group)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert lines != ["Watching two."]
    assert "watching two" not in lines[0].lower()
    assert "CONTACT_NO_LONGER_LIVE" not in lines[0]
    assert contact.attention == "watch"
    assert [task.contact_id for task in tasks.tasks] == [contact.id]


def test_a_unit_that_joins_the_group_later_is_not_retroactively_watched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user's own settled scope (Item 3): "Tag once, static." A third
    contact that is not part of the group at command time, and never
    joins it, must not be marked watched just because it exists in the
    same store -- this is the cheapest version of the "a late arrival
    goes unreported" property the static design accepts by design."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_NEAR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_FAR",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            # Far away, a different clock -- not part of the group.
            _observation_for_follow(
                obs_id="OBS_OTHER",
                t_sim=0.0,
                classification_raw="OP_SAM",
                classification_level=2,
                clock=8,
                range_m=9000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    other_contact = next(c for c in store.contacts if c.last_class_raw == "OP_SAM")

    console.handle_command("watch_nearest", now_sim=0.0)

    assert other_contact.attention == "normal"


def test_scan_ahead_without_enrichment_reports_not_configured() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = False
    assert console.handle_command("scan_ahead", now_sim=0.0) == [
        "no world-model connection configured"
    ]


def test_scan_ahead_without_tasks_reports_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    assert console.handle_command("scan_ahead", now_sim=0.0) == [
        "no task store configured"
    ]


def test_scan_ahead_registers_a_task_and_fires_no_dcs_effector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scan is this project's own naked-eye/binocular perception, not DCS
    Petrovich's 9K113 sight -- `docs/concept/state-transitions.jpg`'s
    glossary keeps *Scan* and *Observ* as separate verbs, and a live test
    on 2026-09-16 found Scan driving the 9K113. The task must still be
    registered; only the effector call is gone."""
    store = ContactStore()
    tasks = TaskStore()
    client = _RecordingAircraftClient()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
        aircraft_client=client,  # type: ignore[arg-type]
    )
    console.on_ground = False

    lines = console.handle_command("scan_ahead", now_sim=0.0)

    assert lines == ["Scanning ahead."]
    # Regression guard: re-wiring any DCS effector to Scan is the bug this
    # fix removed. `Observ`/`Track` are where the 9K113 belongs.
    assert client.triggered_modes == []
    # A real PendingIntent is still registered over an ownship-anchored area.
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.status == "pending"
    assert task.area.relative_sector == "ahead"


def test_scan_bearing_n_registers_a_task_with_the_absolute_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command("scan_bearing_n", now_sim=0.0)

    assert lines == ["Scanning north."]
    task = tasks.tasks[0]
    assert task.area.sector == "N"
    assert task.area.relative_sector is None


def test_scan_clock_1_registers_a_task_with_the_relative_clock_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 5's ownship-relative o'clock scan family (`plans/
    voice-command-completeness/plan.md` Decision 5) -- the fine-grained
    sibling of `scan_ahead`/`scan_bearing_n`, registering `AttentionArea.
    relative_clock_hour` instead of `relative_sector`/`sector`."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command("scan_clock_1", now_sim=0.0)

    assert lines == ["Scanning one o'clock."]
    task = tasks.tasks[0]
    assert task.area.relative_clock_hour == 1
    assert task.area.relative_sector is None
    assert task.area.sector is None


def test_scan_never_calls_the_aircraft_layer_even_if_it_would_fail() -> None:
    """Replaces a D5-era test that asserted a *failed* trigger still left
    the task registered. There is no trigger on this path any more, so that
    ordering guarantee has nothing to protect; what is worth pinning now is
    the stronger property that the aircraft layer is not called at all. The
    double is armed to raise, so any reintroduced call fails loudly here
    rather than silently driving the 9K113 in flight."""
    store = ContactStore()
    tasks = TaskStore()
    client = _RecordingAircraftClient()
    client.raise_on_trigger = True
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
        ),
        aircraft_client=client,  # type: ignore[arg-type]
    )
    console.on_ground = False

    lines = console.handle_command("scan_full", now_sim=0.0)

    assert lines == ["Scanning full arc."]
    assert client.triggered_modes == []
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].status == "pending"


def test_scan_then_cancel_task_actually_cancels_it() -> None:
    """The `cancel_task` docstring's own claim: before this milestone's D5
    fix, `--crew-text` mode had no command path that ever registered a
    task, so `cancel_task` was dead in practice. A `scan_*` token now
    registers one, and `cancel_task` finds it."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
        ),
    )
    console.on_ground = False

    console.handle_command("scan_ahead", now_sim=0.0)
    task_id = tasks.tasks[0].id

    lines = console.handle_command("cancel_task", now_sim=1.0)

    # Names what was stopped, never the task id (live-test finding
    # 2026-09-16: the player heard "cancelled task TASK_4").
    assert lines == ["Copy, stop scan ahead."]
    assert task_id not in lines[0]
    assert tasks.get(task_id) is not None
    resolved = tasks.get(task_id)
    assert resolved is not None and resolved.status == "cancelled"


def test_cancel_task_reaches_an_already_succeeded_scan() -> None:
    # Cones 2C sortie fix: a scan_area task can resolve to "succeeded"
    # within seconds of being issued (tick() the instant any contact
    # appears in its area) -- "Cancel Task" must still be able to end that
    # standing mode, not report "nothing to stop" the way it used to when
    # the task fell out of the old "status == pending" filter.
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
        ),
    )
    console.on_ground = False

    console.handle_command("scan_ahead", now_sim=0.0)
    task = tasks.tasks[0]
    task.status = "succeeded"

    lines = console.handle_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan ahead."]
    resolved = tasks.get(task.id)
    assert resolved is not None and resolved.status == "cancelled"


def test_cancel_task_without_tasks_configured_reports_nothing_to_stop() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_command("cancel_task", now_sim=0.0) == ["nothing to stop"]


def test_cancel_task_reports_nothing_to_stop_when_none_pending() -> None:
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(store=store, tasks=tasks)

    assert console.handle_command("cancel_task", now_sim=0.0) == ["nothing to stop"]


def test_cancel_task_cancels_the_most_recently_created_pending_task() -> None:
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(store=store, tasks=tasks)

    area1 = store.add_area(
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=500.0,
        level="watch",
        source="scan_area",
    )
    task1 = tasks.create(
        kind="scan_area", area=area1, created_sim=0.0, deadline_sim=60.0, reason="first"
    )
    area2 = store.add_area(
        center=GeoPosition(x=1000.0, z=0.0, alt_m=0.0),
        radius_m=500.0,
        level="watch",
        source="scan_area",
    )
    task2 = tasks.create(
        kind="scan_area",
        area=area2,
        created_sim=1.0,
        deadline_sim=60.0,
        reason="second",
    )

    lines = console.handle_command("cancel_task", now_sim=2.0)

    # This task was built directly with no sector on its area, so the
    # phrase falls back to the bare kind rather than naming a sector.
    assert lines == ["Copy, stop scan."]
    assert task2.id not in lines[0]
    # Both are cancelled, not only the newest (2026-09-25). The readback
    # still names only the governing one -- naming a superseded scan would
    # be noise about something that was already inert.
    resolved_task2 = tasks.get(task2.id)
    resolved_task1 = tasks.get(task1.id)
    assert resolved_task2 is not None and resolved_task2.status == "cancelled"
    assert resolved_task1 is not None and resolved_task1.status == "cancelled"


def test_handle_command_pushes_to_overlay_via_the_print_funnel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RecordingAircraftClient()
    overlay_client = FakeOverlayClient()
    console = CrewConsole(
        store=ContactStore(),
        tasks=TaskStore(),
        enrichment=_enrichment_context(monkeypatch),
        aircraft_client=client,  # type: ignore[arg-type]
        overlay_client=overlay_client,  # type: ignore[arg-type]
    )
    console.on_ground = False

    lines = console.handle_command("scan_ahead", now_sim=0.0)

    assert lines == ["Scanning ahead."]
    assert overlay_client.pushed == ["Scanning ahead."]


def test_watch_nearest_air_defence_skips_a_closer_non_air_defence_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The air-defence item must pick the nearest *matching* contact, not
    the nearest contact that happens to match -- a closer tank does not
    shadow a further SAM."""
    store = ContactStore()
    store.ingest(
        [
            _observation_with_ownship_x(
                obs_id="OBS_SAM",
                t_sim=0.0,
                classification_raw="Osa 9A33",
                ownship_x=2000.0,
            ),
            _observation_with_ownship_x(
                obs_id="OBS_TANK", t_sim=0.0, classification_raw="T-72", ownship_x=500.0
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    sam = next(c for c in store.contacts if "Osa" in c.classification.value)
    tank = next(c for c in store.contacts if c.classification.value == "T-72")

    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("watch_nearest_air_defence", now_sim=0.0)

    assert "Osa" in lines[0]
    assert sam.attention == "watch"
    # The nearer tank must be untouched -- it was never a candidate.
    assert tank.attention == "normal"


def test_watch_nearest_air_defence_selects_a_long_range_sam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression, 2026-09-24: `OP_LRSAM` was absent from the air-defence
    class set -- then `crew_console`'s own local `_AIR_DEFENCE_OP_CLASSES`,
    since `BL-B51` the shared `belief.classification.
    AIR_DEFENSE_OP_CLASSES` -- so an S-300, long-range SAM and
    unambiguously air defence, could never be selected by "watch nearest
    air defence".

    This is the worst contact to have missed. The vision calibration found
    the S-300's tracking-radar mast detectable out to 8.89 km, further than
    anything else in the profile table, so it is both the most dangerous
    thing the command can be asked about and the one most likely to be the
    only air-defence contact held at all."""
    store = ContactStore()
    store.ingest(
        [
            _observation_with_ownship_x(
                obs_id="OBS_S300",
                t_sim=0.0,
                classification_raw="S-300PS 40B6M tr",
                ownship_x=4000.0,
            ),
            _observation_with_ownship_x(
                obs_id="OBS_TANK", t_sim=0.0, classification_raw="T-72", ownship_x=500.0
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    s300 = next(c for c in store.contacts if "S-300" in c.classification.value)
    tank = next(c for c in store.contacts if c.classification.value == "T-72")

    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("watch_nearest_air_defence", now_sim=0.0)

    assert s300.attention == "watch"
    assert lines and "no air defence contact" not in lines[0]
    assert tank.attention == "normal"


def test_watch_nearest_air_defence_resolves_through_the_one_shared_set() -> None:
    """`BL-B51`: the `<=` drift guard that used to live here moved to
    `tests/test_classification.py::test_air_defence_classes_cover_every_
    air_defence_class_in_the_object_model` with the set itself, so it is
    not duplicated.

    What stays here is this command's own wiring, asserted as an
    equivalence rather than as a provenance claim: the predicate behind
    "watch nearest air defence" agrees with `AIR_DEFENSE_OP_CLASSES`
    across that set's own boundary in **both** directions -- a class in
    the set is air defence to this command, and a profiled class outside
    it is not. **It cannot distinguish reading the shared set from
    reading an identical local copy**, and does not claim to -- no test
    asserts that, only `BL-B51`'s grep over `src`/`tests`/`tools` did.
    What this one buys is that the command's verdict tracks the set's
    *contents*, which is what breaks first if either side drifts."""
    console_predicate = CrewConsole._believed_air_defence

    def verdict(value: str) -> bool:
        return console_predicate(
            cast(CrewConsole, None),
            {"classification": {"level": "class", "value": value}},
        )

    for op_class in sorted(AIR_DEFENSE_OP_CLASSES):
        assert verdict(op_class), op_class
    for op_class in ("OP_ARMORED", "OP_TRUCK", "OP_INFANTRY"):
        assert op_class not in AIR_DEFENSE_OP_CLASSES
        assert not verdict(op_class), op_class


def test_watch_nearest_air_defence_reports_none_when_no_contact_is_air_defence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_with_ownship_x(
                obs_id="OBS_TANK", t_sim=0.0, classification_raw="T-72", ownship_x=500.0
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False

    # Distinct from the plain "no contact to watch" -- there *is* a contact,
    # it just isn't air defence, and the crew must hear which.
    assert console.handle_command("watch_nearest_air_defence", now_sim=0.0) == [
        "no air defence contact to watch"
    ]


def test_believed_air_defence_rejects_an_air_defence_value_at_presence_level() -> None:
    """Isolates the level gate itself, which the end-to-end presence test
    below cannot: it feeds `_believed_air_defence` a facts dict whose value
    *would* resolve into an air-defence class but whose level is only
    `presence`, and asserts it is still rejected.

    That value/level pairing cannot arise from a real contact -- the
    classification lattice ties value shape to level, so a presence-level
    claim always holds `PRESENCE_CLASS`. Which is exactly why this test
    exists at the predicate rather than through the store: the level check
    is deliberate defensive redundancy, and without a test that can fail
    when it is deleted, nothing would notice its removal."""
    console = CrewConsole(store=ContactStore())

    assert console._believed_air_defence(
        {"classification": {"level": "class", "value": "OP_SRSAM"}}
    )
    assert not console._believed_air_defence(
        {"classification": {"level": "presence", "value": "OP_SRSAM"}}
    )


def test_watch_nearest_air_defence_ignores_a_presence_level_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No-omniscience boundary, end to end: a contact seen only as
    "something is there" must never be reported as air defence, even when
    the underlying object really is a SAM.

    Note this passes on the *value* check alone (`parent_class_of
    (PRESENCE_CLASS)` is `None`) and so would survive deleting the level
    gate -- the test above is the one that pins the gate itself."""
    store = ContactStore()
    store.ingest(
        [
            _observation_with_ownship_x(
                obs_id="OBS_BLOB",
                t_sim=0.0,
                classification_raw=PRESENCE_CLASS,
                ownship_x=500.0,
                classification_level=1,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    blob = next(iter(store.contacts))
    assert blob.classification.level.name.lower() == "presence"

    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False

    assert console.handle_command("watch_nearest_air_defence", now_sim=0.0) == [
        "no air defence contact to watch"
    ]
    assert blob.attention == "normal"


def test_cancel_task_names_a_bearing_scan_by_its_compass_word() -> None:
    """The absolute-sector half of the cancel readback. `_describe_task_for_
    speech` reads a different field for these (`area.sector`, not
    `area.relative_sector`), so a relative-scan test alone would not cover
    it."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
        ),
    )
    console.on_ground = False

    console.handle_command("scan_bearing_se", now_sim=0.0)
    lines = console.handle_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan southeast."]


def test_cancel_task_names_a_clock_hour_scan_by_its_number_word() -> None:
    """The o'clock half of the cancel readback (Stage 5) -- `_describe_
    task_for_speech` reads a third field for these (`area.
    relative_clock_hour`), so neither the relative- nor the compass-scan
    test alone covers it."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
        ),
    )
    console.on_ground = False

    console.handle_command("scan_clock_1", now_sim=0.0)
    lines = console.handle_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan one o'clock."]


# --- plans/watch-as-standing-mode/plan.md: watch as a cancellable mode -----


def test_watch_nearest_registers_a_cancellable_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 2026-09-21 sortie's root cause: `_handle_watch_nearest` used to
    call `belief.tools.set_attention` directly, registering nothing
    `cancel_task` could ever find. With a `TaskStore` configured, watching
    the nearest contact must now also register a `"watch_contact"`
    `PendingIntent` for it."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    console.handle_command("watch_nearest", now_sim=0.0)

    assert contact.attention == "watch"
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.kind == "watch_contact"
    assert task.contact_id == contact.id
    assert task.status == "pending"
    assert task.area is None


def test_watch_then_cancel_task_stops_the_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sortie's own scripted sequence, fixed: "watch closest" ->
    "cancel task" must now stop the watch, not report "nothing to stop"."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    console.handle_command("watch_nearest", now_sim=0.0)
    assert contact.attention == "watch"

    lines = console.handle_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop watch."]
    assert contact.attention == "normal"
    assert tasks.tasks[0].status == "cancelled"


def test_watch_nearest_without_tasks_still_falls_back_to_a_bare_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a `TaskStore` configured, `watch_nearest` degrades to the
    old direct `set_attention` behaviour -- watching still works, it just
    is not cancellable (the same graceful-degradation shape `_handle_scan`
    already follows for a missing `enrichment`). Regression guard for
    `test_watch_nearest_selects_the_nearest_contact_by_range`'s existing
    no-tasks scenario."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False

    lines = console.handle_command("watch_nearest", now_sim=0.0)

    assert contact.attention == "watch"
    assert lines != ["no such contact: " + contact.id]


def test_scan_and_watch_coexist_and_cancel_task_stops_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The finding's full scripted sequence: "scan ahead" then "watch
    closest" must leave *both* standing modes active at once (a single
    "current task" field could not express this), and `cancel_task` -- now
    the explicit all-modes form rather than the only vocabulary available --
    ends both, naming each in the readback rather than silently dropping
    one. The narrow forms are covered below."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    console.handle_command("scan_ahead", now_sim=0.0)
    console.handle_command("watch_nearest", now_sim=0.0)
    assert len(tasks.tasks) == 2
    assert contact.attention == "watch"

    lines = console.handle_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan ahead and watch."]
    assert contact.attention == "normal"
    assert all(task.status == "cancelled" for task in tasks.tasks)


def test_cancel_task_cancels_superseded_tasks_too_so_none_resurrect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel everything must really cancel everything (user, 2026-09-25,
    after flying it).

    **This test previously asserted the opposite**, under the name
    `test_cancel_task_only_cancels_the_newest_task_per_kind`, on the
    reasoning that a superseded scan is not "currently governing" and so
    should not be swept up. That reasoning had the consequence backwards.
    A superseded `scan_area` is inert *precisely because* a newer one
    outranks it in `logger._active_gaze`'s most-recent-wins tie-break --
    so cancelling only the newest **promotes the older one straight back
    into steering the gaze**.

    The user hit exactly the sequence below: he said "cancel", confirmed
    "cancel everything", heard both current modes named back, and an
    earlier "scan south" was still steering afterwards.

    The readback is unchanged and still names only the governing tasks --
    naming every stale scan would be noise about things that were not
    doing anything anyway."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    console.handle_command("scan_ahead", now_sim=0.0)
    console.handle_command("scan_left", now_sim=1.0)
    first_scan, second_scan = tasks.tasks
    console.handle_command("watch_nearest", now_sim=1.0)

    lines = console.handle_command("cancel_task", now_sim=2.0)

    assert lines == ["Copy, stop scan left and watch."]
    # The superseded scan goes too -- otherwise cancelling the newest scan
    # hands the gaze straight back to this one.
    assert first_scan.status == "cancelled"
    assert second_scan.status == "cancelled"


# --- Stage 2 of plans/inbound-speech/plan.md: handle_transcript ------------


def test_handle_transcript_fallthrough_uses_handle_line_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Behaviour #4: `verb_anchored=False` falls through to the exact same
    path a typed line takes -- proven here by checking the stand-in brain
    client actually received the escalation, not just that the returned
    lines happen to match. This is also Decision 4 REVISED AGAIN's 'second
    route in' (`plans/inbound-speech/plan.md`, user 2026-09-20): a high
    `confidence` (0.95, well above `ACT_FLOOR`) that matches no command at
    all reaches the brain layer, not 'say again' -- the user's own words,
    well-transcribed audio that does not match command patterns is
    exactly what needs to be passed to the brain layer."""
    brain_client = _CapturingBrainClient()
    console = CrewConsole(store=ContactStore(), brain_client=brain_client)  # type: ignore[arg-type]

    lines = console.handle_transcript(
        "completely unrelated free speech",
        confidence=0.95,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == []
    assert len(brain_client.payloads) == 1
    assert brain_client.payloads[0].transcript == "completely unrelated free speech"


def test_handle_transcript_acts_above_act_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False

    lines = console.handle_transcript(
        "scan ahead",
        confidence=1.0,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["Scanning ahead."]
    assert len(tasks.tasks) == 1


def test_handle_transcript_confirm_band_asks_and_holds_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2

    lines = console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["Scan ahead, confirm?"]
    # Nothing actually executed yet.
    assert tasks.tasks == []


def test_handle_transcript_ambiguous_always_confirms() -> None:
    console = CrewConsole(store=ContactStore())

    lines = console.handle_transcript(
        "scan est",
        confidence=1.0,
        token="scan_bearing_e",
        match_ratio=0.99,
        verb_anchored=True,
        ambiguous=True,
        now_sim=0.0,
    )

    assert lines == ["Scan east, confirm?"]


def test_handle_transcript_says_again_below_confirm_floor() -> None:
    console = CrewConsole(store=ContactStore())

    lines = console.handle_transcript(
        "garbled",
        confidence=1.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["Say again?"]


def test_handle_transcript_unresolved_verb_says_again_even_when_heard_clearly() -> None:
    """The subtle half of Decision 4 REVISED AGAIN's table (`plans/
    inbound-speech/plan.md`, user 2026-09-20): "Scan somethinggarbled",
    heard clearly (high confidence) but unresolved (no token), is *not*
    free speech -- the player plainly tried to issue a command, so this
    must say again, never fall through to the brain. `verb_anchored`
    decides between the two right-hand table cells, not confidence."""
    console = CrewConsole(store=ContactStore())

    lines = console.handle_transcript(
        "scan somethinggarbled",
        confidence=0.95,  # heard clearly -- would clear ACT_FLOOR if matched
        token=None,
        match_ratio=0.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["Say again?"]


def test_handle_transcript_confirm_then_affirm_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    # The affirm answer's own match fields are irrelevant -- the pending
    # check runs before any of them are consulted.
    lines = console.handle_transcript(
        "roger",
        confidence=0.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=1.0,
    )

    assert lines == ["Scanning ahead."]
    assert len(tasks.tasks) == 1


def test_handle_transcript_confirm_then_negative_discards_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    lines = console.handle_transcript(
        "negative",
        confidence=0.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=1.0,
    )

    assert lines == []
    assert tasks.tasks == []


def test_handle_transcript_confirm_then_unrelated_answer_discards_and_processes_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ "Anything else... discards silently" (Decision 4 Layer 3) discards
    the *stale question*, not the player's new utterance -- the second
    transcript here is a fresh, fully-matched command and must still be
    acted on."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    lines = console.handle_transcript(
        "watch nearest",
        confidence=1.0,
        token="watch_nearest",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=1.0,
    )

    # Only the fresh command's own effect fired -- the stale "scan ahead"
    # confirm never silently executed.
    assert lines == ["no contact to watch"]
    assert tasks.tasks == []


def test_handle_transcript_confirm_expires_after_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    lines = console.handle_transcript(
        "roger",
        confidence=0.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=CONFIRM_WINDOW_S + 1.0,
    )

    # The window elapsed -- "roger" no longer commits anything. It is still
    # inside `CONFIRM_LATE_ANSWER_GRACE_S`, so it is recognised as a late
    # *answer* and draws a "Say again?" rather than being escalated as free
    # speech (which is what produced "Unable, no such command." on the
    # 2026-09-26 sortie). The command itself must still not have fired.
    assert lines == ["Say again?"]
    assert tasks.tasks == []


def test_handle_transcript_late_answer_beyond_the_grace_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past the grace window a yes/no word is ordinary speech again -- the
    late-answer branch is a short courtesy after a question, not a
    permanent reinterpretation of the word."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    lines = console.handle_transcript(
        "roger",
        confidence=0.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=CONFIRM_WINDOW_S + CONFIRM_LATE_ANSWER_GRACE_S + 1.0,
    )

    assert lines == []
    assert tasks.tasks == []


def test_handle_transcript_grace_window_does_not_swallow_a_real_utterance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Found in review: the late-answer grace runs over *every* transcript
    for 20 s after a question expires, so a first-word answer check turned
    an ordinary instruction that happens to open with "okay" into a
    swallowed "Say again?". A sentence is not an answer."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    # Inside the grace window, but a real command -- it must act, not be
    # read as a late answer.
    lines = console.handle_transcript(
        "okay scan left",
        confidence=1.0,
        token="scan_left",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=CONFIRM_WINDOW_S + 5.0,
    )

    assert lines != ["Say again?"]
    assert [task.kind for task in tasks.tasks] == ["scan_area"]


def test_handle_transcript_confirm_commits_on_the_questions_own_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 2026-09-26 sortie's exact sequence: a command lands in the
    confirm band, Petrovich asks "<X>, confirm?", and the pilot answers
    with the word the question asked for. That used to fall through to the
    brain layer and come back "Unable, no such command."."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False
    confidence_mid = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    asked = console.handle_transcript(
        "scan ahead",
        confidence=confidence_mid,
        token="scan_ahead",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )
    assert asked == ["Scan ahead, confirm?"]

    console.handle_transcript(
        "confirm",
        confidence=0.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=2.0,
    )

    assert [task.kind for task in tasks.tasks] == ["scan_area"]


def test_handle_transcript_cancel_task_needs_the_higher_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False
    console.handle_command("scan_ahead", now_sim=0.0)
    assert len(tasks.tasks) == 1

    confidence_mid = (
        ACT_FLOOR + CONFIRM_FLOOR
    ) / 2  # clears ACT_FLOOR, not ACT_FLOOR_CANCEL
    lines = console.handle_transcript(
        "cancel",
        confidence=confidence_mid,
        token="cancel_task",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=1.0,
    )

    assert lines == ["Cancel everything, confirm?"]
    # Not actually cancelled yet.
    assert tasks.tasks[0].status == "pending"


def test_voice_repl_harness_drives_the_same_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.on_ground = False

    lines = console.handle_line("!voice scan_ahead 1.0 1.0 1 0 scan ahead", now_sim=0.0)

    assert lines == ["Scanning ahead."]
    assert len(tasks.tasks) == 1


def test_voice_repl_harness_no_match_token() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_line("!voice - 0.0 1.0 1 0 garbled nonsense", now_sim=0.0)
    assert lines == ["Say again?"]


def test_voice_repl_harness_reports_usage_on_bad_input() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_line("!voice not enough args", now_sim=0.0)
    assert lines[0].startswith("usage: !voice")


def test_cancel_scan_leaves_the_watch_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User direction 2026-09-23, reversing this console's own earlier
    decision: *"One cancel does not automatically cancel other ongoing
    tasks."* Stopping the scan while continuing to watch a contact is an
    ordinary thing to want, and the cancel-everything reading made it
    impossible to express."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    console.handle_command("scan_ahead", now_sim=0.0)
    console.handle_command("watch_nearest", now_sim=0.0)

    lines = console.handle_command("cancel_scan", now_sim=1.0)

    assert lines == ["Copy, stop scan ahead."]
    assert contact.attention == "watch"
    scans = [task for task in tasks.tasks if task.kind == "scan_area"]
    watches = [task for task in tasks.tasks if task.kind == "watch_contact"]
    assert all(task.status == "cancelled" for task in scans)
    assert all(task.status != "cancelled" for task in watches)


def test_cancel_watch_leaves_the_scan_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of the above, and the one the sortie transcript actually
    wanted: the pilot watched a contact while scanning, and stopping the
    watch should not blind the scan."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    console.handle_command("scan_ahead", now_sim=0.0)
    console.handle_command("watch_nearest", now_sim=0.0)

    lines = console.handle_command("cancel_watch", now_sim=1.0)

    assert lines == ["Copy, stop watch."]
    assert contact.attention == "normal"
    scans = [task for task in tasks.tasks if task.kind == "scan_area"]
    assert all(task.status != "cancelled" for task in scans)


def test_cancel_scan_with_nothing_scanning_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A narrow cancel that matches nothing must not claim to have stopped
    something -- and must not fall through to cancelling the watch, which
    is the exact failure the narrow forms exist to prevent."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    console.handle_command("watch_nearest", now_sim=0.0)

    lines = console.handle_command("cancel_scan", now_sim=1.0)

    assert lines == ["nothing to stop"]
    assert contact.attention == "watch"


def test_every_transcript_is_logged_with_what_was_done_about_it() -> None:
    """`--speech-log`. The gap this closes: an utterance matching no
    command reached only the brain-layer stand-in, which does nothing, so
    the most useful case for debugging recognition left no trace at all."""
    rows: list[dict[str, object]] = []
    console = CrewConsole(store=ContactStore(), transcript_log=rows.append)

    console.handle_transcript(
        transcript="scan left",
        confidence=0.9,
        token="scan_left",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=10.0,
    )

    assert len(rows) == 1
    assert rows[0]["transcript"] == "scan left"
    assert rows[0]["disposition"] == "act"
    assert rows[0]["acted_token"] == "scan_left"


def test_an_unmatched_transcript_is_logged_too() -> None:
    """The case the log exists for -- well-heard speech that matched
    nothing is exactly what a recognition debrief needs to see."""
    rows: list[dict[str, object]] = []
    console = CrewConsole(store=ContactStore(), transcript_log=rows.append)

    console.handle_transcript(
        transcript="lovely weather today",
        confidence=0.88,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=10.0,
    )

    assert len(rows) == 1
    assert rows[0]["transcript"] == "lovely weather today"
    assert rows[0]["disposition"] == "fallthrough"
    assert rows[0]["acted_token"] is None


def test_a_failing_log_sink_never_costs_the_player_a_command() -> None:
    """A debug artifact must never be load-bearing."""

    def explode(_row: dict[str, object]) -> None:
        raise OSError("disk full")

    console = CrewConsole(store=ContactStore(), transcript_log=explode)

    lines = console.handle_transcript(
        transcript="scan left",
        confidence=0.9,
        token="scan_left",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=10.0,
    )

    assert lines  # the command still ran and still spoke


# -- plans/voice-command-completeness/plan.md ---------------------------


def test_dispatched_command_tokens_all_return_something(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression guard for the whole milestone: every token this
    project claims to have wired must either speak something or be one of
    `NO_RETURN_VALUE_COMMAND_TOKENS`' documented, deliberate no-readback-
    via-return-value no-ops (`stop_talking`, `silence`) -- never the
    silent `[]` that sent 20 of 41 recognised voice tokens nowhere.

    **Each token gets its own, well-separated `now_sim`** (`plans/
    voice-latency-instrumentation/plan.md` Stage 6): a positional readback
    now defers to `[]` when the channel is modeled busy, and a prior
    token's own `note_reply` claims the channel for its estimated speech
    duration -- calling every token at the same `now_sim` would make this
    loop's own dispatch order, not a wiring gap, the reason a later token
    returns `[]`. 100s apart is far longer than any line this class speaks
    takes, so every call here sees a clear channel, exactly as a real
    sortie's well-spaced commands would."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    for index, token in enumerate(sorted(DISPATCHED_COMMAND_TOKENS)):
        lines = console.handle_command(token, now_sim=index * 100.0)
        if token in NO_RETURN_VALUE_COMMAND_TOKENS:
            assert lines == [], token
        else:
            assert lines, token


def test_unknown_token_returns_nothing_and_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The failure mode this milestone exists to fix was *silence* -- an
    unrecognised token reaching `handle_command` and doing nothing,
    indistinguishable from not having been heard at all. Post-fix, the
    empty result is unchanged (there is genuinely nothing to say for a
    token nobody defined), but it must no longer be silent in the logs."""
    console = CrewConsole(store=ContactStore())
    with caplog.at_level("WARNING"):
        lines = console.handle_command("not_a_real_token", now_sim=0.0)
    assert lines == []
    assert any("not_a_real_token" in record.message for record in caplog.records)


def test_report_all_with_no_contacts_says_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report_all", now_sim=0.0) == ["Clear."]


def test_report_all_without_enrichment_reports_not_configured() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_command("report_all", now_sim=0.0) == [
        "no world-model connection configured"
    ]


def test_report_all_speaks_a_known_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test that would fail if `report_all`'s dispatch were removed --
    and pins the spoken output, not just that something was said.

    **The expected text changed with BL-13 Stage 3** (`plans/
    crew-query-path/plan.md` Decision C, user decision 13): the answer is
    a summary, not a per-contact enumeration. It used to read
    `"BMP-2, 3 o'clock, 1 kilometre near Jableh (about 200 metres)."` -- note
    what the summary drops and why. The type name goes because the summary
    speaks the *class* bucket (`parent_class_of`), the enrichment
    parenthetical goes because a pointer does not need a landmark to aim
    a look, and the exact range becomes a band. What survives is count,
    direction and band, which is the pointer."""
    store = ContactStore()
    store.ingest(
        [_observation_at(obs_id="OBS_1", t_sim=0.0, ownship_x=0.0, ownship_z=1000.0)],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    assert lines == ["One armor, at 3 o'clock, inside 2 kilometres."]


def test_report_all_drops_a_lost_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Decision 1 step 1: contacts are never pruned, so a report must drop
    `certainty == "lost"` itself or it would grow monotonically over a
    sortie -- a contact past `LOST_THRESHOLD_S` must not be reported."""
    store = ContactStore()
    store.ingest(
        [_observation_at(obs_id="OBS_1", t_sim=0.0, ownship_x=0.0, ownship_z=1000.0)],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=LOST_THRESHOLD_S + 1.0)

    assert lines == ["Clear."]


def test_report_clock_3_with_no_contact_says_clock_position_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report_clock_3", now_sim=0.0) == [
        "Three o'clock, clear."
    ]


def test_report_clock_3_finds_the_matching_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_at(obs_id="OBS_E", t_sim=0.0, ownship_x=0.0, ownship_z=1000.0),
            _observation_at(
                obs_id="OBS_N",
                t_sim=0.0,
                ownship_x=1000.0,
                ownship_z=0.0,
                classification_raw="T-72",
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    # No workaround needed here: OBS_E/OBS_N are BMP-2/T-72 (both 7 m,
    # `belief.groups.GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * 7.0 = 140`
    # m backstop), ~1.4 km apart -- well past it, the fix for the
    # two-contact cohesion tautology that used to group any two contacts
    # regardless of distance (`belief.groups`'s own module docstring).
    # They do not cohere, so this test is naturally about clock-scoping
    # alone -- group formation itself is covered by `tests/test_groups.py`
    # and `test_report_speaks_a_persisted_group_through_render_group_full_
    # disclosure`, below.
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    # OBS_E is east of ownship (3 o'clock); OBS_N is dead ahead (12 o'clock)
    # -- only the 3 o'clock contact must be named.
    lines = console.handle_command("report_clock_3", now_sim=0.0)

    # Summary wording since BL-13 Stage 3; the clock-scoping claim this
    # test exists for is unchanged -- only one of the two contacts is in
    # the answer, and the count says so.
    assert lines == ["One armor, at 3 o'clock, inside 2 kilometres."]


def test_report_bearing_n_with_no_contact_and_forward_heading_says_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ownship heads north (`_ownship`'s default heading); north is dead
    ahead, well inside the cockpit mask's forward envelope -- `render_
    clear`, not `render_no_view`."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report_bearing_n", now_sim=0.0) == ["North, clear."]


def test_report_bearing_s_with_forward_heading_cannot_see_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 2's carve-out: ownship heads north, so south is dead
    astern -- past the cockpit mask's `rear_cutoff_deg` (130). Answering
    "clear" would claim a look that is physically impossible; the honest
    answer is a refusal, not an empty report."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report_bearing_s", now_sim=0.0) == [
        "Can't see south."
    ]


def test_report_bearing_s_still_reports_a_contact_believed_to_be_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Belief survives the aircraft turning away -- only the *absence*
    claim (`render_no_view`) is withheld for the rear hemisphere; a
    contact that is actually believed to sit there is still reported."""
    store = ContactStore()
    store.ingest(
        [_observation_at(obs_id="OBS_S", t_sim=0.0, ownship_x=-1000.0, ownship_z=0.0)],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_bearing_s", now_sim=0.0)

    # Summary wording since BL-13 Stage 3. The claim is unchanged and is
    # the one that matters here: the contact is *named*, so only the
    # absence claim is withheld for the rear hemisphere.
    assert lines == ["One armor, at 6 o'clock, inside 2 kilometres."]


def _enrichment_context_with_heading(
    monkeypatch: pytest.MonkeyPatch, heading_true_deg: float
) -> EnrichmentContext:
    """`_enrichment_context`'s twin with a caller-controlled ownship
    heading -- needed to place `_SECTOR_CENTER_DEG["S"]` (180 degrees) at
    an exact relative bearing from the nose, for the `rear_cutoff_deg`
    boundary test below. Same monkeypatches as `_enrichment_context`."""
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(
            nearest_settlement=_FakeInfo(name="Jableh", distance_m=250.0)
        ),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    # See `_enrichment_context`'s identical stub above.
    monkeypatch.setattr(
        enrichment_module,
        "divides_between",
        lambda conn, theatre, observer, target: 0,
    )
    return EnrichmentContext(
        conn=_FAKE_CONN,
        theatre="Syria",
        ownship=OwnshipState(
            t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=heading_true_deg
        ),
    )


def test_report_bearing_s_just_inside_rear_cutoff_says_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional refinement, `plans/voice-command-completeness/review.md`:
    the two existing rear-hemisphere tests (dead-ahead-north, dead-astern-
    south) are far from `COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg`
    (130 degrees) -- this pins the `>=` comparison itself. Heading 51 puts
    `S`'s sector center (180) at exactly 129 degrees relative -- just
    inside the forward-visible envelope, so an empty result must still
    answer "clear", not the rear-hemisphere refusal."""
    console = CrewConsole(
        store=ContactStore(),
        enrichment=_enrichment_context_with_heading(monkeypatch, 51.0),
    )
    assert console.handle_command("report_bearing_s", now_sim=0.0) == ["South, clear."]


def test_report_bearing_s_just_past_rear_cutoff_cannot_see_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`rear_cutoff_deg`'s other side: heading 49 puts `S`'s sector center
    at exactly 131 degrees relative -- just past the cutoff, so an empty
    result must refuse rather than claim a look that is physically
    impossible."""
    console = CrewConsole(
        store=ContactStore(),
        enrichment=_enrichment_context_with_heading(monkeypatch, 49.0),
    )
    assert console.handle_command("report_bearing_s", now_sim=0.0) == [
        "Can't see south."
    ]


def test_report_bearing_deg_quantises_onto_the_nearest_sector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 3: a numeric bearing reduces to the nearest of the eight
    compass sectors and behaves exactly like `report_bearing_<compass>` --
    185 degrees is inside the `S` (180) bucket, so this must also refuse
    with `"Can't see south."` under a forward-facing ownship, not answer
    `"Clear."`"""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    lines = console.handle_command(
        "report_bearing_deg", now_sim=0.0, slots={"bearing_degrees": 185}
    )
    assert lines == ["Can't see south."]


def test_report_bearing_deg_without_a_bearing_says_say_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report_bearing_deg", now_sim=0.0) == [
        "say again -- no bearing heard"
    ]


def test_report_all_summarises_rather_than_truncating_multiple_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**This test's original subject no longer exists on this path, and
    that is the change rather than a regression.** It was named
    `test_report_all_groups_and_truncates_multiple_contacts` and pinned
    `group_facts`' bucketing driven together with `render_report`'s
    `REPORT_MAX_GROUPS` cap through the real dispatch -- four contacts
    becoming three sentences plus `"And more."`. BL-13 Stage 3 replaced
    the pull site's enumeration with one summary (`plans/
    crew-query-path/plan.md` Decision C), which has no per-group cap to
    truncate at: the whole scene folds into a count, a dominant class, a
    span and a band, so four contacts cost the same breath as two.

    `render_report`/`REPORT_MAX_GROUPS` are deliberately left in place and
    still unit-tested in `test_speech.py`, because reverting the summary
    has to stay a one-call-site change until the user has flown it.

    What this test keeps is the reason it was written: the seam is driven
    end to end through the real dispatch, over a scene of four contacts of
    four classes at four ranges, rather than trusting the renderer's unit
    tests.

    Three of the four are armour-family (BMP-2/T-72/BTR-70) and the fourth
    is a `"ZSU-23-4"`, which `classification.parent_class_of` does **not**
    resolve -- measured while updating this test, and consistent with this
    fixture's own existing note that the ZSU falls back to
    `GROUP_REPORTING_UNKNOWN_SIZE_M`. So the fourth contact is
    unclassified rather than air defence, the answer hedges with "mostly",
    and no air-defence clause is due. Q2's carve-out is tested separately,
    with a type the lattice actually resolves."""
    store = ContactStore()
    store.ingest(
        [
            _observation_at(
                obs_id="OBS_1",
                t_sim=0.0,
                ownship_x=0.0,
                ownship_z=1000.0,
                classification_raw="BMP-2",
            ),
            _observation_at(
                obs_id="OBS_2",
                t_sim=0.0,
                ownship_x=0.0,
                ownship_z=2000.0,
                classification_raw="T-72",
            ),
            _observation_at(
                obs_id="OBS_3",
                t_sim=0.0,
                ownship_x=0.0,
                ownship_z=3000.0,
                classification_raw="BTR-70",
            ),
            _observation_at(
                obs_id="OBS_4",
                t_sim=0.0,
                ownship_x=0.0,
                ownship_z=4000.0,
                classification_raw="ZSU-23-4",
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    # No workaround needed (unlike before the unit-width cohesion backstop,
    # `belief.groups.GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`): these four
    # contacts are all 7 m vehicles (BMP-2/T-72/BTR-70 keyword-match; the
    # ZSU-23-4 falls back to `belief.groups.GROUP_REPORTING_UNKNOWN_SIZE_M`,
    # also 7 m), so the backstop is `20.0 * 7.0 = 140` m -- well under their
    # 1 km spacing. They therefore stay four separate contacts rather than
    # cohering into one `Group`, which is what makes this a four-contact
    # scene at all. (The clause that used to end this comment -- "so this
    # test is naturally about `group_facts`'s report-space bucketing and
    # `REPORT_MAX_GROUPS` truncation alone" -- was true of the test this
    # replaced; the docstring above says what it is about now.)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    assert lines == ["Four units, mostly armor, at 3 o'clock, inside 5 kilometres."]
    # One utterance, and nothing was dropped for want of room: the four
    # contacts are all accounted for in the count, where the old answer
    # spoke three of them and said "And more."
    assert len(lines) == 1
    assert "and more" not in lines[0].lower()


def test_report_speaks_a_persisted_group_as_one_counted_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three same-type contacts a few metres apart cohere into one `Group`
    on `store.tick`, and the report is **one** answer naming all three,
    not three separate reports.

    **Renamed from `..._through_render_group_full_disclosure`, because that
    renderer is no longer how this path answers** (`plans/crew-query-path/
    plan.md` Decision C, BL-13 Stage 3): the summary is computed from the
    in-scope facts, so group cohesion no longer decides the *shape* of the
    answer at all -- three contacts are three contacts whether or not a
    `Group` formed. The property this test protects survives the change
    and is still worth pinning: the pull path accounts for every in-scope
    contact exactly once.

    Its sibling, `test_report_speaks_an_already_spoken_group_in_full`,
    carries the half that was about the renderer split -- see that test's
    own docstring for why the pull path must not inherit the push path's
    delta gate."""
    store = ContactStore()
    store.ingest(
        [
            # `classification_level=3` (type): `_observation_at`'s own
            # default (2/class) paired with a type-shaped raw string like
            # "BMP-2" is a state no real producer emits (see that
            # function's own docstring) -- `plans/group-collapse/plan.md`
            # Stage 3's fixture-correction note, found when `_group_
            # composition_clause`'s re-expression over `collapse_members`
            # started reading `classification.level`, not just the literal
            # string. Corrected to the reachable pairing; the expected
            # "Three BMP-2" wording below is unchanged, since a type-level
            # value renders verbatim either way.
            _observation_at(
                obs_id=f"OBS_{i}",
                t_sim=0.0,
                ownship_x=float(i) * 5.0,
                ownship_z=1000.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
            for i in range(3)
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    assert len(store.groups) == 1
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    # Used to be `[render_group_full_disclosure(...).text]`, i.e. "Three
    # BMP-2, 3 o'clock, 1 kilometre." The count is still three and the
    # direction still three o'clock; the type name becomes the class
    # bucket, as everywhere else the summary speaks.
    assert lines == ["Three armor, at 3 o'clock, inside 2 kilometres."]
    # The push-path renderer still works and still speaks the full roster
    # -- it is simply no longer what answers a pull. Asserted so that
    # "the pull path changed" cannot be confused with "the group renderer
    # broke".
    pushed = render_group_full_disclosure(
        store, store.groups[0], now_sim=0.0, enrichment=console.enrichment
    )
    assert pushed is not None
    assert pushed.text == "Three BMP-2, 3 o'clock, 1 kilometre."


def test_report_speaks_an_already_spoken_group_in_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The case its sibling could not cover: a group that has *already*
    spoken (so `render_group_disclosure`'s delta taxonomy would return a
    delta clause, or `None`, depending on what changed since) must still
    get a full answer from "report" -- **the push path's throttle must
    never reach the pull path.** Marks the group spoken via the same
    `render_group_disclosure` + `mark_group_spoken` sequence `belief.
    callouts.CalloutScheduler.tick` uses, then confirms a second,
    unchanged-membership `render_group_disclosure` call would go silent
    (proving the taxonomy really would gate this) while `"report"` still
    answers in full.

    **The claim outlived the mechanism it was written against.** It used
    to hold because `_handle_report` called the always-full-roster
    renderer rather than the taxonomy-gated one; since BL-13 Stage 3 it
    holds because the summary is computed from facts and consults no
    spoken-signature state at all. The same sentence, protected by a
    different construction -- and still worth a test, because Decision D
    is the standing instruction that D11's own observability work must not
    start filtering this path (`plans/crew-query-path/plan.md`)."""
    store = ContactStore()
    store.ingest(
        [
            # `classification_level=3` -- the same reachable-pairing
            # correction as this test's sibling above; see that call
            # site's comment.
            _observation_at(
                obs_id=f"OBS_{i}",
                t_sim=0.0,
                ownship_x=float(i) * 5.0,
                ownship_z=1000.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
            for i in range(3)
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    assert len(store.groups) == 1
    enrichment = _enrichment_context(monkeypatch)
    group = store.groups[0]

    first = render_group_disclosure(store, group, now_sim=0.0, enrichment=enrichment)
    assert first is not None
    assert first.content_signature is not None
    state = group_membership_state(store, group, now_sim=0.0, enrichment=enrichment)
    assert state is not None
    member_contact_ids, leading_contact_id, differentiated = state
    store.mark_group_spoken(
        group.id,
        first.content_signature,
        now_sim=0.0,
        member_contact_ids=member_contact_ids,
        leading_contact_id=leading_contact_id,
        differentiated=differentiated,
    )

    # Confirms the gate is really armed: an unchanged group, spoken once
    # already, goes silent at group level on the push path.
    assert (
        render_group_disclosure(store, group, now_sim=1.0, enrichment=enrichment)
        is None
    )

    console = CrewConsole(store=store, enrichment=enrichment)
    lines = console.handle_command("report_all", now_sim=1.0)

    # All three contacts, after the push path has gone silent about them.
    assert lines == ["Three armor, at 3 o'clock, inside 2 kilometres."]


# --- the slotted crew query (plans/crew-query-path/plan.md, BL-13) ---


def test_slotted_report_sector_words_mirror_audio_adapters_table() -> None:
    """This side of the `SECTOR_WORDS` <-> `_SECTOR_FOR_WORD` hand-synced
    mirror (`plans/crew-query-path/plan.md` Decision E -- body-layer cannot
    import `audio-adapter`, so the eight words are written down twice).
    audio-adapter's `test_vocabulary.py` asserts the same membership
    against its own table; between them, a word added or renamed on either
    side fails a test rather than a sortie.

    Spelled out literally rather than derived from `_SECTOR_SCAN_LABELS`:
    deriving it would make this test agree with that table by
    construction, which is exactly the agreement the seam does *not*
    guarantee."""
    from belief.crew_console import _SECTOR_FOR_WORD

    assert set(_SECTOR_FOR_WORD) == {
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "northwest",
    }
    assert _SECTOR_FOR_WORD["north"] == "N"
    assert _SECTOR_FOR_WORD["southwest"] == "SW"


def test_slotted_report_with_no_slots_answers_the_whole_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A zero-slot `report` is a legal whole-scene query. audio-adapter
    resolves a bare "report" to `report_all` before this token is ever
    minted, so this is the defensive case (a non-adapter caller, or every
    slot dropped as unrecognised) -- and it must answer, not refuse."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_command("report", now_sim=0.0) == ["Clear."]


def test_slotted_report_clock_matches_the_legacy_clock_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 1's channel test: the slotted token with a `clock` slot
    answers exactly what `report_clock_3` answers. Driven through
    `handle_command` twice on the same store so the two paths are compared
    against each other rather than against a transcribed string -- the
    claim is equivalence, and a pinned string would only test one side.

    `scheduler.busy_until_sim` is reset between the two calls (`plans/
    voice-latency-instrumentation/plan.md` Stage 6): the first call's own
    readback claims the channel for its estimated speech duration, which
    would otherwise make the second call's own report defer to `[]` at the
    same `now_sim` -- a dispatch-order artefact of this comparison, not
    something either path's answer should depend on."""
    store = ContactStore()
    store.ingest(
        [_observation_at(obs_id="OBS_E", t_sim=0.0, ownship_x=0.0, ownship_z=1000.0)],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    legacy = console.handle_command("report_clock_3", now_sim=0.0)
    console.scheduler.busy_until_sim = 0.0
    slotted = console.handle_command("report", now_sim=0.0, slots={"clock": 3})

    assert slotted == legacy
    assert slotted == ["One armor, at 3 o'clock, inside 2 kilometres."]


def test_slotted_report_sector_matches_the_legacy_bearing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `sector` slot's half of the same claim, including the
    rear-hemisphere carve-out: `report south` with a north-facing ownship
    must refuse exactly as `report_bearing_s` does, never answer
    "clear".

    `scheduler.busy_until_sim` is reset between calls -- see
    `test_slotted_report_clock_matches_the_legacy_clock_token`'s identical
    note."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )

    assert console.handle_command("report", now_sim=0.0, slots={"sector": "north"}) == [
        "North, clear."
    ]
    console.scheduler.busy_until_sim = 0.0
    assert console.handle_command("report", now_sim=0.0, slots={"sector": "south"}) == [
        "Can't see south."
    ]


def test_slotted_report_drops_an_unrecognised_slot_value_rather_than_refusing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slots arrive as JSON over the HTTP seam, so no value can be
    assumed well-formed. A garbage `sector`, an out-of-hemisphere `clock`
    and a wrong-typed value each widen the answer instead of producing a
    refusal or an exception -- the same graceful degradation
    `bearing_degrees` already has, and the honest failure for a *query*.

    `scheduler.busy_until_sim` is reset before each iteration -- see
    `test_slotted_report_clock_matches_the_legacy_clock_token`'s identical
    note."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    for slots in (
        {"sector": "nowhere"},
        {"clock": 6},
        {"clock": "three"},
        {"sector": 90},
    ):
        console.scheduler.busy_until_sim = 0.0
        assert console.handle_command(
            "report", now_sim=0.0, slots=cast("dict[str, int | str]", slots)
        ) == ["Clear."], slots


def test_slotted_report_is_dispatched_and_describable() -> None:
    """The two registrations a new token needs beyond its handler:
    membership in `DISPATCHED_COMMAND_TOKENS` (which is what routes a
    confirm-band answer and a brain-layer reply to it at all), and a
    `_describe_token_for_confirm` readback that is not the raw token
    name."""
    assert "report" in DISPATCHED_COMMAND_TOKENS
    assert "report" not in NO_RETURN_VALUE_COMMAND_TOKENS
    assert _describe_token_for_confirm("report") == "report"
    assert _describe_token_for_confirm("report", {"relative": "left"}) == "report left"
    assert _describe_token_for_confirm("report", {"clock": 2}) == "report two o'clock"
    assert (
        _describe_token_for_confirm("report", {"descriptor": "armor", "clock": 2})
        == "report armor two o'clock"
    )


def test_slotted_report_confirm_readback_names_a_slot_it_cannot_yet_filter_on() -> None:
    """The confirm prompt's job is to expose a mishearing, so it reads
    back every slot Petrovich heard -- including `band`, which Stage 1
    does not yet filter on. Hiding a word he heard would defeat the
    prompt; this is the same reasoning that makes `report_bearing_deg`
    read back the *sector* it will act on rather than the raw number."""
    assert (
        _describe_token_for_confirm("report", {"clock": 2, "band": "near"})
        == "report two o'clock near"
    )


def test_scan_bearing_deg_quantises_and_registers_the_nearest_sector_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirrors `test_scan_bearing_n_registers_a_task_with_the_absolute_
    sector` -- `scan_bearing_deg(317)` must reduce to exactly the same
    behaviour as `scan_bearing_nw`, including the readback naming the
    sector, never the raw number (Decision 3's "readback names the sector,
    not the number")."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False

    lines = console.handle_command(
        "scan_bearing_deg", now_sim=0.0, slots={"bearing_degrees": 317}
    )

    assert lines == ["Scanning northwest."]
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].area.sector == "NW"


def test_nearest_sector_quantises_to_the_nearest_compass_bucket() -> None:
    assert _nearest_sector(0) == "N"
    assert _nearest_sector(5) == "N"
    assert _nearest_sector(320) == "NW"
    assert _nearest_sector(185) == "S"
    assert _nearest_sector(225) == "SW"


def test_describe_token_for_confirm_names_the_quantised_sector_not_the_number() -> None:
    """Decision 3 item 5 -- the confirm prompt's job is to expose a
    misunderstanding, and repeating the raw number while the dispatch
    itself acts on a coarser bucket would hide the only discrepancy worth
    hearing."""
    assert (
        _describe_token_for_confirm("scan_bearing_deg", {"bearing_degrees": 317})
        == "scan northwest"
    )
    assert (
        _describe_token_for_confirm("report_bearing_deg", {"bearing_degrees": 5})
        == "report north"
    )
    assert _describe_token_for_confirm("report_clock_3") == "report three o'clock"
    assert _describe_token_for_confirm("report_bearing_n") == "report north"
    assert _describe_token_for_confirm("report_all") == "report"
    assert _describe_token_for_confirm("scan_clock_1") == "scan one o'clock"


def test_a_confirm_band_bearing_survives_the_affirm_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `PendingConfirmation.slots`, a bearing command that lands
    in the confirm band loses its number the moment the player says
    "affirm" -- `handle_command` is called again on commit with no other
    way to recover it. This is the test that would fail if that field were
    removed."""
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.on_ground = False
    confirm_confidence = (ACT_FLOOR + CONFIRM_FLOOR) / 2

    lines = console.handle_transcript(
        transcript="scan bearing three one seven",
        confidence=confirm_confidence,
        token="scan_bearing_deg",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
        slots={"bearing_degrees": 317},
    )
    assert lines == ["Scan northwest, confirm?"]

    lines = console.handle_transcript(
        transcript="affirm",
        confidence=1.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=1.0,
    )

    assert lines == ["Scanning northwest."]
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].area.sector == "NW"


def test_a_reply_extends_the_callout_scheduler_occupancy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 2's fix for the latent defect: every command readback has
    been unbudgeted since readbacks existed, so a routine callout could
    queue immediately behind one. `_print`'s non-urgent path must now
    claim the channel via `CalloutScheduler.note_reply`."""
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.scheduler.busy_until_sim == 0.0

    console.handle_command("report_all", now_sim=10.0)

    assert console.scheduler.busy_until_sim > 10.0


# --- follow (plans/watch-reporting/plan.md Decision 2b) --------------------


def _xz_for_clock(clock: int, range_m: float) -> tuple[float, float]:
    """The `(x, z)` offset from the origin that renders as `clock` o'clock
    at `range_m`, given ownship at the origin facing north -- mirrors
    `test_callouts.py`'s own helper of the same name."""
    bearing = math.radians((clock % 12) * 30.0)
    return range_m * math.cos(bearing), range_m * math.sin(bearing)


def _observation_for_follow(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str,
    classification_level: int,
    clock: int,
    range_m: float,
) -> Observation:
    """Places a contact at a controlled clock/range from `_enrichment_
    context`'s fixed origin ownship, with a caller-controlled
    classification -- `_observation_at`'s shape, extended with
    `classification_level` for `follow`'s descriptor-matching tests."""
    x, z = _xz_for_clock(clock, range_m)
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=x, z=z),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def test_follow_with_descriptor_only_picks_the_matching_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})
    armor_id = next(c.id for c in store.contacts if c.last_class_raw == "OP_ARMORED")
    truck_id = next(c.id for c in store.contacts if c.last_class_raw == "OP_TRUCK")
    # Both contacts sit at the same clock/range, so `GroupStore` resolves
    # them into one real `belief.groups.Group` -- `follow` resolving to
    # the armor contact therefore tags the whole group, not just the one
    # the descriptor picked (sortie 2026-10-05 debrief, Item 3). The
    # readback names the count rather than the single contact's class
    # (`render_watch_group_readback`), and the truck gets tagged watched
    # too even though the descriptor never matched it directly.
    assert "two" in lines[0].lower()
    armor_contact = store.contact(armor_id)
    truck_contact = store.contact(truck_id)
    assert armor_contact is not None and armor_contact.attention == "watch"
    assert truck_contact is not None and truck_contact.attention == "watch"


def test_follow_with_clock_only_picks_the_nearest_matching_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_NEAR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_FAR",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=9,
                range_m=1000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0, slots={"clock": 2})
    assert "armor" in lines[0].lower()


def test_follow_with_no_qualifiers_says_again() -> None:
    console = CrewConsole(store=ContactStore())
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0)
    assert lines == ["say again -- follow needs at least one of what/where/how far"]


# --- Stage 4 (plans/sortie-2026-09-26-fixes/plan.md, Fix C): --------------
# command-dependent lowering. `logger.py` reads `commands_handled`/
# `last_command_target_contact_id` to decide whether to lower the
# binoculars -- these tests pin the `CrewConsole`-side facts that decision
# rests on: what actually increments `commands_handled`, and what
# `_handle_follow` records.


def test_an_unrecognised_utterance_does_not_burn_the_optic_interrupt() -> None:
    """Decision 2: "not every player command should lower the binoculars.
    Especially not those that are not understood." An utterance the
    free-text parser also fails to understand escalates to the brain layer
    (`disposition == "escalated"`) rather than acting on anything -- this
    is the actual bug Stage 4 fixes (`_note_player_command()` used to be
    called unconditionally at the top of `_handle_utterance`, before this
    check)."""
    console = CrewConsole(store=ContactStore())
    commands_before = console.commands_handled

    console.handle_line(
        "completely unrelated free speech nobody could act on", now_sim=0.0
    )

    assert console.commands_handled == commands_before


def test_say_again_does_not_burn_the_optic_interrupt() -> None:
    """Regression guard (plan Stage 4): `say_again` is handled entirely
    inside `_act_on_voice_decision`'s own branch and already never called
    `_note_player_command()` -- nothing was asked for yet, so there is
    nothing to prefer over the current look. Pinned so a future change
    cannot reintroduce the interrupt here."""
    console = CrewConsole(store=ContactStore())
    commands_before = console.commands_handled

    lines = console.handle_transcript(
        "garbled beyond recognition",
        confidence=0.9,
        token=None,
        match_ratio=0.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
    )

    assert lines == ["Say again?"]
    assert console.commands_handled == commands_before


def test_follow_records_its_resolved_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_handle_follow` sets `last_command_target_contact_id` to the
    contact it resolved -- the fact `logger.py`'s glue block reads to
    decide whether a `follow` continued an in-progress look. Confirmed
    directly against `CrewConsole` state, independent of `OpticState`
    (that half is `logger.py`'s own concern, see `test_logger.py`)."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    assert console.last_command_target_contact_id is None

    console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})

    assert console.last_command_target_contact_id == contact_id


def test_follow_target_resets_between_unrelated_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`last_command_target_contact_id` is reset at the top of every
    `handle_command` dispatch -- a stale value from an earlier `follow`
    must not leak into an unrelated later command's evaluation."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})
    assert console.last_command_target_contact_id is not None

    console.handle_command("cancel_task", now_sim=1.0)

    assert console.last_command_target_contact_id is None


def test_follow_beyond_the_match_floor_watches_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A far-off descriptor/clock mismatch must not watch the least-bad
    candidate -- Decision 2b-iii's own "watching the least-bad contact is
    worse than admitting no match" reasoning."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=9,
                range_m=5000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command(
        "follow", now_sim=0.0, slots={"descriptor": "armor", "clock": 2}
    )
    assert lines == ["Nothing like that."]
    assert store.contacts[0].attention == "normal"


def test_follow_with_only_a_clock_names_the_clock_when_nothing_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=8,  # the maximal clock delta from 2 (6 hours)
                range_m=5000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0, slots={"clock": 2})
    assert lines == ["Nothing at two o'clock."]


def test_follow_with_no_contacts_at_all() -> None:
    console = CrewConsole(store=ContactStore(), enrichment=None)
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})
    assert lines == ["no world-model connection configured"]


def test_follow_unclassified_contact_matches_a_descriptor_softly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 2b-iii: "he is pointing at a thing he *believes* is
    armour -- matching it is right." A presence-level dot at the named
    clock, with no competing classified contact, must still be picked."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_DOT",
                t_sim=0.0,
                classification_raw="ground",
                classification_level=0,
                clock=2,
                range_m=2000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command(
        "follow", now_sim=0.0, slots={"descriptor": "armor", "clock": 2}
    )
    assert store.contacts[0].attention == "watch"
    assert lines[0] != "Nothing like that."


def test_follow_group_descriptor_matches_a_plural_cardinality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_GROUP",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                clock=2,
                range_m=2000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    # Force a plural cardinality directly -- fabricating a real clustered
    # naked-eye observation is out of scope for this test's own focus.
    from belief.cardinality import cardinality_belief_from_bucket_name

    contact.cardinality = cardinality_belief_from_bucket_name(
        "OP_TO5UNITS", established_sim=0.0
    )
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    lines = console.handle_command("follow", now_sim=0.0, slots={"descriptor": "group"})
    assert store.contacts[0].attention == "watch"
    assert lines[0] != "Nothing like that."


def test_describe_token_for_confirm_names_the_follow_slots() -> None:
    assert (
        _describe_token_for_confirm(
            "follow", {"descriptor": "armor", "clock": 2, "range_km": 3}
        )
        == "follow armor two o'clock 3 km"
    )
    assert _describe_token_for_confirm("follow", None) == "follow"


def test_follow_readback_survives_the_confirm_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))
    console.on_ground = False
    confirm_confidence = (ACT_FLOOR + CONFIRM_FLOOR) / 2

    lines = console.handle_transcript(
        transcript="follow armor",
        confidence=confirm_confidence,
        token="follow",
        match_ratio=1.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=0.0,
        slots={"descriptor": "armor"},
    )
    assert lines == ["Follow armor, confirm?"]

    lines = console.handle_transcript(
        transcript="affirm",
        confidence=1.0,
        token=None,
        match_ratio=0.0,
        verb_anchored=False,
        ambiguous=False,
        now_sim=1.0,
    )
    assert store.contacts[0].attention == "watch"


# --- BL-14 attack-run selection (plans/attack-run/plan.md Decisions
# 2/5/14, Stage 1) ---


def test_select_target_resolves_and_sets_priority_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )

    lines = console.handle_command(
        "select_target", now_sim=0.0, slots={"descriptor": "armor"}
    )

    assert "armor" in lines[0].lower()
    assert "2 o'clock" in lines[0]
    contact = store.contacts[0]
    assert contact.attention == "priority"
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.contact_id == contact.id
    assert target_task.status == "pending"


def test_select_target_with_no_qualifiers_says_again() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_command("select_target", now_sim=0.0)
    assert lines == ["say again -- select target needs what and/or where"]


def test_select_target_with_no_match_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(),
        tasks=TaskStore(),
        enrichment=_enrichment_context(monkeypatch),
    )
    lines = console.handle_command(
        "select_target", now_sim=0.0, slots={"descriptor": "armor"}
    )
    assert lines == [render_no_contact().text]


def test_select_target_tags_other_group_members_watch_not_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 5's split: only the selected contact itself reaches
    `"priority"` -- its group-mates get the ordinary one-time `"watch"`
    tag, never overridden back onto the target itself."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )

    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})

    armor_contact = next(c for c in store.contacts if c.last_class_raw == "OP_ARMORED")
    truck_contact = next(c for c in store.contacts if c.last_class_raw == "OP_TRUCK")
    assert armor_contact.attention == "priority"
    assert truck_contact.attention == "watch"


def _store_with_armor_and_truck(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ContactStore, TaskStore, CrewConsole, Contact, Contact]:
    """Two grouped, individually-selectable-by-descriptor contacts --
    `plans/attack-run/security-review.md`'s "Required fix in detail"
    reproduction needs two distinct targets reachable by ordinary
    `select target <descriptor>`/`engage <descriptor>` commands with no
    intervening cancel. Returns `(store, tasks, console, armor, truck)`."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=8,  # the maximal clock delta from 2 -- opposite side,
                # so armor/truck are never clustered into one `belief.
                # groups.Group`; this fixture is for the stale-task fix
                # itself, not Decision 5's group-tagging split, which
                # `test_select_target_tags_other_group_members_watch_
                # not_priority` already covers on its own grouped fixture.
                range_m=5000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    armor_contact = next(c for c in store.contacts if c.last_class_raw == "OP_ARMORED")
    truck_contact = next(c for c in store.contacts if c.last_class_raw == "OP_TRUCK")
    return store, tasks, console, armor_contact, truck_contact


def _active_attack_target_tasks(tasks: TaskStore) -> list[PendingIntent]:
    return [
        task
        for task in tasks.tasks
        if task.kind == "attack_target" and task.status != "cancelled"
    ]


def test_reselecting_a_different_target_via_select_target_cancels_the_stale_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`plans/attack-run/security-review.md`'s required fix, reproduced
    with its own exact two-command sequence: `select target armor` then,
    with no intervening `drop target`/`disengage`/`cancel`, `select target
    <something else>`. Before the fix, `TaskStore.tasks` held two
    `"pending"` `attack_target` tasks and every reader of "the current
    target" (`_active_attack_target_task`'s `next(... not cancelled)`)
    resolved to the *oldest* one -- the stale target -- even though the
    readback just spoke the new selection. This is the fail-before/
    pass-after reproduction: reverting the fix in `tools.attack_target_
    task` (dropping the cancel-existing-active-tasks loop) makes this test
    fail with `active[0].contact_id == armor.id` (the stale task
    resolving as "the" target) rather than `truck.id`, and leaves `armor.
    attention == "priority"` instead of demoting to `"normal"` -- both
    asserted below.

    `scheduler.busy_until_sim` is reset before the second command (`plans/
    voice-latency-instrumentation/plan.md` Stage 6): one real second
    between two corrections is well inside the first readback's own
    estimated speech duration, which would otherwise defer the second
    command's readback to `[]` -- a real, correct consequence of Stage 6
    for a genuinely tight correction, but a different thing from what this
    test is reproducing (task-cancellation semantics), so it is held
    constant here rather than conflated."""
    _store, tasks, console, armor, truck = _store_with_armor_and_truck(monkeypatch)

    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    assert armor.attention == "priority"

    console.scheduler.busy_until_sim = 0.0
    lines = console.handle_command(
        "select_target", now_sim=1.0, slots={"descriptor": "truck"}
    )

    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    assert active[0].contact_id == truck.id
    # The old target's attention demotes -- `cancel_task` undoes the
    # belief-state effect `attack_target_task` registered for it, the same
    # "task owns the effect it registered" rule `watch_contact_task`/
    # `scan_area` already follow.
    assert armor.attention == "normal"
    assert truck.attention == "priority"
    # The resolution every reader of "the current target" shares
    # (`drain_attack_run`, `_handle_step`, bare `engage`, `drain_events`'s
    # `_WATCHED_ONLY_KINDS` suppression) now agrees with the readback.
    active_task = console._active_attack_target_task()
    assert active_task is not None
    assert active_task.contact_id == truck.id
    assert "truck" in lines[0].lower()


def test_select_target_readback_defers_while_the_channel_is_busy_then_drains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 6's actual deferred-then-drained path (`plans/
    voice-latency-instrumentation/plan.md`), not merely the non-deferred
    case every other positional-readback test exercises: the selection
    itself (resolving the target, registering the task) is unconditional
    and immediate even while the channel is busy, only the readback's
    *speaking* waits for `drain_pending_positional_replies` to find the
    channel clear."""
    _store, _tasks, console, armor, _truck = _store_with_armor_and_truck(monkeypatch)
    console.scheduler.busy_until_sim = 100.0

    lines = console.handle_command(
        "select_target", now_sim=0.0, slots={"descriptor": "armor"}
    )

    # Deferred: nothing spoken yet, but the selection already happened.
    assert lines == []
    assert armor.attention == "priority"
    active_task = console._active_attack_target_task()
    assert active_task is not None
    assert active_task.contact_id == armor.id
    assert len(console._pending_positional_replies) == 1

    # Still busy: draining now must not speak it early.
    spoken = console.drain_pending_positional_replies(now_sim=50.0)
    assert spoken == []
    assert len(console._pending_positional_replies) == 1

    # Channel clears: the deferred readback is spoken, re-rendered against
    # belief at this later tick rather than the original command's.
    spoken = console.drain_pending_positional_replies(now_sim=100.0)
    assert len(spoken) == 1
    assert "armor" in spoken[0].lower()
    assert console._pending_positional_replies == []


def test_select_target_readback_falls_back_to_lost_contact_if_it_vanishes_before_speaking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the contact no longer resolves by the time the deferred readback
    is drained, it must say so rather than silently dropping it or raising
    (the plan's own "lost track of that contact" requirement)."""
    store, _tasks, console, armor, _truck = _store_with_armor_and_truck(monkeypatch)
    console.scheduler.busy_until_sim = 100.0

    lines = console.handle_command(
        "select_target", now_sim=0.0, slots={"descriptor": "armor"}
    )
    assert lines == []

    # The contact vanishes entirely before the readback is ever spoken --
    # simulated by clearing the store's own record of it (a merge that
    # abandoned this id with no successor, same shape `drain_attack_run`'s
    # own "contact no longer resolves" branch handles).
    store._contacts.pop(armor.id)  # type: ignore[attr-defined]

    spoken = console.drain_pending_positional_replies(now_sim=100.0)
    assert spoken == ["Lost him."]


def test_pending_positional_replies_caps_and_drops_oldest_warning_logged_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`BL-B87` (security deep analysis, `plans/voice-latency-instrumentation/
    security-review.md`) -- `_pending_positional_replies` must not grow
    unboundedly under a sustained flood of deferred readbacks, mirroring
    `TranscriptQueue`/`F10CommandQueue`'s own drop-oldest cap. A dropped
    entry loses only an already-stale spoken echo, never an action: each
    `select_target` call below still resolves and registers its own task
    unconditionally, regardless of whether its readback survives the cap.

    Exceeds the cap by 5 (69 calls against a cap of 64) so the warning's
    rate limiting is actually exercised, not just its first firing -- five
    separate drop events occur, and only the *first* may log."""
    _store, _tasks, console, _armor, _truck = _store_with_armor_and_truck(monkeypatch)
    console.scheduler.busy_until_sim = 1e9  # always busy -- every call defers

    total_calls = _MAX_PENDING_POSITIONAL_REPLIES + 5
    with caplog.at_level("WARNING"):
        for i in range(total_calls):
            lines = console.handle_command(
                "select_target", now_sim=float(i), slots={"descriptor": "armor"}
            )
            assert lines == []  # deferred every time, channel never clears

    pending = console._pending_positional_replies
    assert len(pending) == _MAX_PENDING_POSITIONAL_REPLIES
    # Drop-oldest, not drop-newest: the five oldest entries (calls 0-4) are
    # gone; the oldest survivor is call 5, the newest is the final call.
    assert pending[0].queued_since_sim == 5.0
    assert pending[-1].queued_since_sim == float(total_calls - 1)

    overflow_warnings = [
        r for r in caplog.records if "_pending_positional_replies" in r.message
    ]
    assert len(overflow_warnings) == 1


def test_reselecting_a_different_target_via_engage_descriptor_cancels_the_stale_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same stale-target bug, reached via `engage <what> <where>`'s
    descriptor branch instead of `select target` -- the review's finding
    names both call sites (`_handle_select_target` and `_handle_engage`),
    since both call `tools.attack_target_task` unconditionally."""
    _store, tasks, console, armor, truck = _store_with_armor_and_truck(monkeypatch)

    console.handle_command("engage", now_sim=0.0, slots={"descriptor": "armor"})
    assert armor.attention == "priority"

    console.handle_command("engage", now_sim=1.0, slots={"descriptor": "truck"})

    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    assert active[0].contact_id == truck.id
    assert armor.attention == "normal"
    assert truck.attention == "priority"


def test_bare_engage_after_reselection_follows_the_newly_selected_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare `engage` after a reselect must start the run on the newly
    selected contact, not the stale one -- bare `engage` never mints a
    task itself, it only reads back whatever `_active_attack_target_task`
    resolves, so this is a direct check that the resolution the fix
    guarantees actually reaches that reader."""
    _store, _tasks, console, _armor, _truck = _store_with_armor_and_truck(monkeypatch)
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    console.handle_command("select_target", now_sim=1.0, slots={"descriptor": "truck"})

    lines = console.handle_command("engage", now_sim=2.0, slots=None)

    assert console.attack_run_transition == "engage"
    assert "truck" in lines[0].lower()


def test_step_after_a_reselect_operates_on_the_newly_selected_targets_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`step` mutates the *existing* active task's `contact_id` in place
    (`PendingIntent.descriptor`'s own docstring) rather than minting a new
    one, so it was never itself vulnerable to the insertion-order bug --
    but it must still operate on the group of whichever contact is
    currently active, not a stale one left over from an earlier re-point
    that the fix is supposed to have cancelled. Reselecting `L` onto the
    `T`-selected fixture (simulating a second `select target`/`engage`
    call with no intervening cancel) and then stepping must move within
    `L`'s own left/right ordering."""
    store, tasks, console, t_id, l_id, _r_id = _target_left_right_fixture(monkeypatch)
    # Simulate a second `select target`/`engage` call re-pointing onto `L`
    # without cancelling the `T` selection first -- the exact shape the
    # fix guards against, reached here by calling the fixed primitive
    # directly rather than re-deriving `L`'s own command-level descriptor.
    second_task = attack_target_task(store, tasks, l_id, 1.0, descriptor="armor")
    assert second_task is not None

    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    assert active[0].contact_id == l_id
    assert store.contact(t_id).attention == "normal"  # type: ignore[union-attr]
    assert store.contact(l_id).attention == "priority"  # type: ignore[union-attr]

    lines = console.handle_command("step", now_sim=2.0, slots={"direction": "right"})

    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    # `L` (330 deg) stepping right crosses `T` (0 deg) before `R` (30 deg).
    assert active[0].contact_id == t_id
    assert lines


def test_reselecting_the_same_target_does_not_demote_its_own_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guards the fix's own ordering: cancelling *every* active
    `attack_target` task (including one that already names `contact_id`)
    before promoting `contact_id` to `"priority"` must still leave that
    contact at `"priority"`, not `"normal"`, when the "new" selection is
    actually the same contact -- `cancel_task`'s demote and `attack_target_
    task`'s own promote must run in that order, not the reverse."""
    _store, tasks, console, armor, _truck = _store_with_armor_and_truck(monkeypatch)

    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    console.handle_command("select_target", now_sim=1.0, slots={"descriptor": "armor"})

    assert armor.attention == "priority"
    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    assert active[0].contact_id == armor.id


def test_reselecting_mid_run_repoints_the_run_to_the_new_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mid-run reselection (engaged, then `select target` something else)
    is not covered by `docs/acceptance/2026-10-14-attack-run-guidance-
    direction.md` -- resolved here by matching the precedent `step`
    already sets while engaged (`_handle_step` mutates the active task's
    `contact_id` in place with no special-case for "a run is active," and
    `drain_attack_run`/`drain_events` both resolve the target fresh every
    tick via `_active_attack_target_task` rather than caching it at
    `engage` time): re-pointing, not refusing, is the existing shape for
    "change the target while engaged," so a reselect takes the same path,
    with nothing in `_handle_select_target` that refuses or special-cases
    an in-progress run.

    This test does not re-assert `attack_run_transition` after the second
    command -- that field is a one-shot per-dispatch signal for the poll
    loop (`_act`'s own reset, "so a stale `\"engage\"`/`\"disengage\"`...
    cannot leak into an unrelated later command"), reset to `None` at the
    top of *every* `handle_command` call regardless of what the previous
    command did; the run's actual engaged/disengaged phase lives one layer
    up, on `logger.ConsolePerceptionRunner.attack_run_state`, which this
    test does not model. What matters here, and is asserted, is that
    `select target` neither refuses nor is itself gated by a prior
    `engage` -- it re-points the standing task exactly as it would with no
    run active."""
    _store, tasks, console, armor, truck = _store_with_armor_and_truck(monkeypatch)
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    lines = console.handle_command("engage", now_sim=0.5, slots=None)
    assert console.attack_run_transition == "engage"
    assert lines

    console.handle_command("select_target", now_sim=1.0, slots={"descriptor": "truck"})

    active = _active_attack_target_tasks(tasks)
    assert len(active) == 1
    assert active[0].contact_id == truck.id
    assert armor.attention == "normal"
    assert truck.attention == "priority"


def test_drop_target_cancels_the_attack_target_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    contact = store.contacts[0]
    assert contact.attention == "priority"

    lines = console.handle_command("drop_target", now_sim=1.0)

    assert lines
    assert contact.attention == "normal"
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.status == "cancelled"


def test_drop_target_with_nothing_selected_says_nothing_to_stop() -> None:
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    lines = console.handle_command("drop_target", now_sim=0.0)
    assert lines == [_NOTHING_TO_STOP]


def test_cancel_task_also_drops_the_attack_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The existing cancel/stop path also deselects, per Decision 2 --
    `cancel_task`'s bare all-modes form cancels every active task kind,
    `attack_target` included."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    contact = store.contacts[0]

    console.handle_command("cancel_task", now_sim=1.0)

    assert contact.attention == "normal"


# --- BL-14 attack-run `step` (plans/attack-run/plan.md Decision 6,
# Stage 4) ---


def _observation_at_xz(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str,
    classification_level: int,
    x: float,
    z: float,
) -> Observation:
    """`_observation_for_follow`'s sibling, placing a contact's `relative_
    now` geometry at an explicit `(x, z)` rather than a quantised clock
    hour -- needed for `step`'s own tests, which require two candidates
    at a controlled few-degree separation that no integer clock hour can
    express. Exploits the identical mechanism that fixture's own
    docstring documents: `_enrichment_context`'s stubbed `project_
    terrain_aware` is a passthrough of its `observer` argument, and
    `_terrain_aware_world_position` passes the contributing percept's own
    `ownship_at_observation` as that argument -- so a contact's `relative_
    now` reads exactly the `(x, z)` given here, regardless of where
    `implied_position` (a separate, unrelated computation) would place
    `Contact.last_position` itself."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=x, z=z),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def _enrichment_context_with_ownship(
    monkeypatch: pytest.MonkeyPatch, ownship: OwnshipState
) -> EnrichmentContext:
    """`_enrichment_context`'s twin with a caller-controlled ownship
    *position* (not just heading, `_enrichment_context_with_heading`'s
    own axis) -- `step`'s own "recomputed from ownship's present
    position" test needs to move ownship itself, not merely look a
    different way, since `relative_now["bearing_deg"]` is the *true*
    compass bearing, unaffected by heading. Same monkeypatches as
    `_enrichment_context`."""
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(
            nearest_settlement=_FakeInfo(name="Jableh", distance_m=250.0)
        ),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    monkeypatch.setattr(
        enrichment_module,
        "divides_between",
        lambda conn, theatre, observer, target: 0,
    )
    return EnrichmentContext(conn=_FAKE_CONN, theatre="Syria", ownship=ownship)


def _inject_group(
    store: ContactStore, now_sim: float, member_ids: frozenset[str]
) -> None:
    """Directly installs a synthetic `Group` spanning `member_ids`,
    bypassing real spatial reconciliation entirely -- `step`'s own tests
    need candidates separated by a few degrees of bearing (to prove the
    angular-order claim precisely), far closer than any real `GroupStore.
    reconcile` cohesion bound would tolerate for distinct contacts, so
    this constructs the belief directly instead of fighting the
    clustering formula to produce it. Same injection shape `test_callouts.
    py` already uses for the identical reason (`store._groups._groups[...]
    = group`), with `_last_reconciled_sim` set to match so `GroupStore.
    groups`/`group_for_contact` (filtered to *currently observed* groups)
    find it immediately with no further `tick()` needed."""
    store._groups._last_reconciled_sim = now_sim
    group = Group(
        id=f"GROUP_TEST_{now_sim}",
        member_contact_ids=member_ids,
        established_sim=now_sim,
        last_reconciled_sim=now_sim,
        last_observed_sim=now_sim,
    )
    store._groups._groups[group.id] = group


def _target_left_right_fixture(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ContactStore, TaskStore, CrewConsole, str, str, str]:
    """Three armour contacts at a controlled bearing spread from origin
    ownship -- `T` dead ahead (bearing 0), `R` 30 degrees right, `L` 30
    degrees left, all at ~2 km range (measured via `perception.geometry.
    bearing_deg`/`signed_angular_delta_deg` directly, not hand-derived
    trigonometry, before writing this fixture). `T` is selected and
    grouped with `L`/`R` via `_inject_group`. Returns `(store, tasks,
    console, t_id, l_id, r_id)`."""
    store = ContactStore()
    store.ingest(
        [
            _observation_at_xz(
                obs_id="OBS_T",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                x=2000.0,
                z=0.0,
            ),
            _observation_at_xz(
                obs_id="OBS_L",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                x=1732.0508,
                z=-1000.0,
            ),
            _observation_at_xz(
                obs_id="OBS_R",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                x=1732.0508,
                z=1000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    # The three contacts resolve by their own `relative_now["bearing_
    # deg"]` rather than assumed ingest order, since contact ids are
    # minted, not controllable.
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    by_bearing: dict[int, str] = {}
    for contact in store.contacts:
        result = describe_contact(store, contact.id, 0.0, enrichment=console.enrichment)
        assert result is not None
        relative_now = result["facts"]["relative_now"]
        assert isinstance(relative_now, dict)
        by_bearing[round(relative_now["bearing_deg"])] = contact.id
    t_id = by_bearing[0]
    r_id = by_bearing[30]
    l_id = by_bearing[330]
    _inject_group(store, 0.0, frozenset({t_id, l_id, r_id}))
    # Selected directly, bypassing `select_target`'s own closest-when-
    # unwatched tie-break -- all three sit at ~2 km, within float noise of
    # each other, so that tie-break would not reliably land on `T`.
    task = attack_target_task(store, tasks, t_id, 0.0, descriptor="armor")
    assert task is not None
    return store, tasks, console, t_id, l_id, r_id


def test_step_right_and_left_pick_neighbours_by_current_bearing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`scheduler.busy_until_sim` is reset between the two `step` calls
    (`plans/voice-latency-instrumentation/plan.md` Stage 6): one second
    apart is well inside the first readback's own estimated speech
    duration, which would otherwise defer the second call's readback to
    `[]` -- not what this test is checking (the re-ordering itself)."""
    store, tasks, console, t_id, _l_id, r_id = _target_left_right_fixture(monkeypatch)
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.contact_id == t_id

    lines = console.handle_command("step", now_sim=1.0, slots={"direction": "right"})
    assert store.contact(r_id) is not None
    assert target_task.contact_id == r_id
    assert store.contact(r_id).attention == "priority"  # type: ignore[union-attr]
    assert store.contact(t_id).attention == "watch"  # type: ignore[union-attr]
    assert lines and "armor" in lines[0].lower()

    console.scheduler.busy_until_sim = 0.0
    lines = console.handle_command("step", now_sim=2.0, slots={"direction": "left"})
    assert target_task.contact_id == t_id
    assert store.contact(t_id).attention == "priority"  # type: ignore[union-attr]
    assert store.contact(r_id).attention == "watch"  # type: ignore[union-attr]
    assert lines


def test_step_recomputes_order_from_ownships_present_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 6's own named requirement, and the user's own words
    (direction document §3): *"it changes as/if we circle the contacts."*
    From origin ownship, `step right` of `T` picks `R` (30 degrees
    clockwise of `T`'s own bearing). Flying to the *opposite* side of the
    formation (ownship at `(4000, 0)`, `T` now directly *behind*) mirrors
    the angular order -- `signed_angular_delta_deg` confirms `R` moves to
    the *left* of `T` and `L` to the *right* from that vantage, verified
    by direct computation before this fixture was written, not assumed.
    So the *same* `step right` command, issued from the *same* standing
    selection, must now pick `L` -- a different unit -- proving the order
    is recomputed at press time from ownship's current position, never a
    list fixed at selection time."""
    _store, tasks, console, t_id, l_id, r_id = _target_left_right_fixture(monkeypatch)
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")

    console.handle_command("step", now_sim=1.0, slots={"direction": "right"})
    assert target_task.contact_id == r_id

    # Re-select T and swap to the far-side vantage.
    target_task.contact_id = t_id
    console.enrichment = _enrichment_context_with_ownship(
        monkeypatch,
        OwnshipState(t_sim=2.0, x=4000.0, z=0.0, alt_m=500.0, heading_true_deg=0.0),
    )

    console.handle_command("step", now_sim=2.0, slots={"direction": "right"})

    assert target_task.contact_id == l_id, (
        "step right picked the same unit from a different ownship "
        "position -- the order was not recomputed"
    )


def test_step_stops_at_the_end_rather_than_wrapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 6: wrapping would silently re-target a unit the pilot has
    just stepped past, in the seconds before release -- stop, and say
    so."""
    _store, tasks, console, _t_id, _l_id, r_id = _target_left_right_fixture(monkeypatch)
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    console.handle_command("step", now_sim=1.0, slots={"direction": "right"})
    assert target_task.contact_id == r_id

    lines = console.handle_command("step", now_sim=2.0, slots={"direction": "right"})

    assert lines == ["Unable, that's the last one."]
    assert target_task.contact_id == r_id  # unchanged


def test_step_with_ungrouped_target_says_no_other_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})

    lines = console.handle_command("step", now_sim=1.0, slots={"direction": "right"})

    assert lines == ["Unable, no other units in the group."]


def test_step_with_no_target_selected_says_so() -> None:
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    lines = console.handle_command("step", now_sim=0.0, slots={"direction": "left"})
    assert lines == ["no target selected"]


def test_step_near_and_far_order_by_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """`near`/`far` use the identical signed machinery keyed on `range_m`
    instead of angle (Decision 6) -- same-bearing, different-range
    members, the exact shape `_cohering_contacts_across_a_band_boundary`
    already builds (reused here rather than duplicated)."""
    store = _cohering_contacts_across_a_band_boundary()
    assert len(store.groups) == 1
    near = next(c for c in store.contacts if c.last_class_raw == "OP_ARMORED")
    medium = next(c for c in store.contacts if c.last_class_raw == "OP_TRUCK")
    far = next(c for c in store.contacts if c.last_class_raw == "OP_INFANTRY")
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    # `descriptor=None` -- this test is about the range-ordering
    # mechanism, not the descriptor filter (`_step_candidates`'s own
    # tests cover that); the three members are different classes
    # (armour/truck/infantry) on purpose, straddling a band boundary, and
    # a descriptor would drop two of them as `"wrong"` before ordering
    # ever ran.
    task = attack_target_task(store, tasks, near.id, 0.0)
    assert task is not None
    target_task = next(t for t in tasks.tasks if t.kind == "attack_target")

    lines = console.handle_command("step", now_sim=1.0, slots={"direction": "far"})

    assert target_task.contact_id == medium.id
    assert far.id != medium.id  # sanity: a real third candidate exists
    assert lines


# --- BL-14 attack-run `engage`/`disengage` (plans/attack-run/plan.md
# Decisions 1/2/15, Stage 5) ---


def test_engage_with_no_selection_starts_the_run_via_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`engage <what> <where>` (Decision 15) -- selects exactly as
    `select_target` does, then sets `attack_run_transition` to signal the
    poll loop (`logger.py`'s own wiring, not exercised by this test)."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1500.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )

    lines = console.handle_command("engage", now_sim=0.0, slots={"descriptor": "armor"})

    assert console.attack_run_transition == "engage"
    assert lines[0].startswith("Attack run, armor, 2 o'clock,")
    contact = store.contacts[0]
    assert contact.attention == "priority"
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.contact_id == contact.id


def test_engage_bare_resumes_the_already_selected_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare `engage`/`engage target` (no slots) starts the run on
    whatever is already selected, rather than requiring the target to be
    named again."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1500.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})

    lines = console.handle_command("engage", now_sim=1.0, slots=None)

    assert console.attack_run_transition == "engage"
    assert lines and lines[0].startswith("Attack run,")


def test_engage_accepts_and_ignores_the_weapon_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 15: the weapon token parses and nothing reads it. Pinned
    so the grammar's own acceptance does not silently change when
    something does consume it."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1500.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )

    lines = console.handle_command(
        "engage", now_sim=0.0, slots={"descriptor": "armor", "weapon": "rockets"}
    )

    assert lines[0].startswith("Attack run, armor,")
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.contact_id == store.contacts[0].id


def test_engage_with_no_target_selected_says_so() -> None:
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    lines = console.handle_command("engage", now_sim=0.0, slots=None)
    assert lines == ["no target selected"]
    assert console.attack_run_transition is None


def test_disengage_signals_transition_and_keeps_the_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 2: `disengage` ends the run's own phase only -- "stop the
    run, keep the watch" -- the standing `attack_target` task (and its
    `"priority"` attention) survives."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1500.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})
    console.handle_command("engage", now_sim=1.0, slots=None)

    lines = console.handle_command("disengage", now_sim=2.0)

    assert lines == ["Attack run off."]
    assert console.attack_run_transition == "disengage"
    contact = store.contacts[0]
    assert contact.attention == "priority"
    target_task = next(task for task in tasks.tasks if task.kind == "attack_target")
    assert target_task.status == "pending"


def test_disengage_speaks_unconditionally_even_with_no_run_active() -> None:
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    lines = console.handle_command("disengage", now_sim=0.0)
    assert lines == ["Attack run off."]


def test_observ_on_signals_the_poll_loop_and_speaks() -> None:
    """`BL-B64` Stage 2, direction §6 -- the same one-shot-signal shape
    `attack_run_transition` uses, since `OpticState.home_phase` lives on
    `logger.ConsolePerceptionRunner`, not here. `sight_ready` set so this
    exercises the accepted path, not `BL-B66` Stage 3's readiness gate
    (see `test_observ_on_refused_when_guidance_unit_not_ready` for that
    one)."""
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    console.sight_ready = True
    lines = console.handle_command("observ_on", now_sim=0.0)
    assert lines == ["Observ on."]
    assert console.observ_transition == "on"


def test_observ_on_refused_when_guidance_unit_not_ready() -> None:
    """`BL-B66` Stage 3 (`plans/9k113-effectors/plan.md` §3, Decision 2)
    -- gated synchronously, before `observ_transition` is ever set, so a
    request that arrives before power-up completes is refused outright."""
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    assert console.sight_ready is False  # the safe default

    lines = console.handle_command("observ_on", now_sim=0.0)

    assert lines == ["Unable, guidance unit not ready."]
    assert console.observ_transition is None


def test_observ_off_needs_no_readiness() -> None:
    """Plan §3: "OBSERV OFF needs no gating and no sequence" -- unlike
    OBSERV ON, it dispatches regardless of `sight_ready`."""
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    assert console.sight_ready is False

    lines = console.handle_command("observ_off", now_sim=0.0)

    assert lines == ["Observ off."]
    assert console.observ_transition == "off"


def test_observ_off_signals_the_poll_loop_and_speaks() -> None:
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    lines = console.handle_command("observ_off", now_sim=0.0)
    assert lines == ["Observ off."]
    assert console.observ_transition == "off"


def test_observ_transition_is_reset_at_the_top_of_every_dispatch() -> None:
    """Same convention as `last_command_target_contact_id`/`attack_run_
    transition` -- a stale signal from an earlier dispatch this poll loop
    has not yet consumed must not leak into an unrelated later command's
    evaluation."""
    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    console.sight_ready = True
    console.handle_command("observ_on", now_sim=0.0)
    assert console.observ_transition == "on"

    console.handle_command("disengage", now_sim=1.0)
    assert console.observ_transition is None


def test_drain_attack_run_is_noop_while_not_engaged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`state=None` means "selected but not engaged" (Stage 5's own
    contract) -- `drain_attack_run` must not compute or speak anything."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
        output=None,
    )
    console.handle_command("select_target", now_sim=0.0, slots={"descriptor": "armor"})

    result = console.drain_attack_run(None, now_sim=1.0, ownship=_ownship(x=0.0, z=0.0))

    assert result is None


def test_drain_attack_run_ends_the_run_when_the_contact_record_vanishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision 13 -- a merge that abandons the target's own contact id
    with no successor recorded anywhere leaves nothing to guide on. The
    run ends and says so once (`render_lost_contact`), and the standing
    task is cancelled too -- unlike `disengage`, there is no selection
    left to keep."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    tasks = TaskStore()
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    contact_id = store.contacts[0].id
    task = attack_target_task(store, tasks, contact_id, now_sim=0.0)
    assert task is not None
    # Simulate the id being abandoned by a merge, with no successor --
    # `ContactStore.contact` returns `None` for a removed id.
    del store._contacts[contact_id]

    result = console.drain_attack_run(
        AttackRunState(), now_sim=1.0, ownship=_ownship(x=0.0, z=0.0)
    )

    assert result is None
    target_task = next(t for t in tasks.tasks if t.kind == "attack_target")
    assert target_task.status == "cancelled"


def _attack_run_contact_off_boresight(
    contact_id: str, *, ownship_at_observation: OwnshipState, t_sim: float = 0.0
) -> Contact:
    """A `Contact` carrying a real off-boresight `RelativeDirection` --
    mirrors `test_attack_run.py`'s own `_contact_with_relative_direction`
    helper (kept as a local copy per this file's per-test-file fixture
    convention). 100 m right of boresight at ~1000 m forward is the
    Stage 4-5 review's own reproduction figure (`atan(100/1000)` =~ 5.71
    degrees): past `ATTACK_RUN_LINED_UP_AZIMUTH_DEG` (5.0) but inside the
    "a bit right" band (half the 12 o'clock sector, 7.5), so `decide`
    renders `"A bit right."` and wants to speak on the first call -- real
    geometry, not a stubbed `decide_attack_run`, per this plan's own
    "confirmed by direct reproduction" standard."""
    percept = Percept(
        t_sim=t_sim,
        source="naked_eye_visual_filtered",
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=ownship_at_observation,
        observation_id="OBS_1",
        relative_direction=RelativeDirection(forward_m=1000.0, right_m=100.0, up_m=0.0),
    )
    return Contact.from_percept(contact_id, percept)


def test_drain_attack_run_reoffers_the_line_once_the_channel_frees() -> None:
    """Stage 4-5 review, required fix 1: a guidance change that arrives
    while `scheduler.busy_until_sim` is still ahead of `now_sim` must not
    be recorded as spoken -- `_should_emit`'s baseline is the last
    *spoken* value (direction doc Sec 10), and `decide()` already updates
    `last_spoken_*` as if the line had been heard, before the caller ever
    checks occupancy. Reproduces the reviewer's own busy-then-free
    sequence directly against `drain_attack_run`, with no `engage` in the
    way, then asserts the fixed behaviour: nothing printed while busy, the
    carried-forward state unchanged, and the line spoken once the channel
    frees with the geometry never having moved."""
    ownship = _ownship(x=0.0, z=0.0)
    store = ContactStore()
    contact_id = "CONTACT_1"
    store._contacts[contact_id] = _attack_run_contact_off_boresight(
        contact_id, ownship_at_observation=ownship
    )
    tasks = TaskStore()
    assert attack_target_task(store, tasks, contact_id, now_sim=0.0) is not None

    import io

    output = io.StringIO()
    console = CrewConsole(store=store, tasks=tasks, output=output)
    # Well inside `ATTACK_RUN_RELATIVE_MAX_AGE_S` (2.0 s) of the percept's
    # own `t_sim=0.0` -- this test is about occupancy, not staleness, so
    # the busy window is kept short enough that the percept is still
    # trusted when the channel frees.
    console.scheduler.busy_until_sim = 1.0

    busy_state = console.drain_attack_run(
        AttackRunState(), now_sim=0.0, ownship=ownship
    )

    assert output.getvalue() == ""
    assert busy_state == AttackRunState()

    freed_state = console.drain_attack_run(busy_state, now_sim=1.0, ownship=ownship)

    assert output.getvalue() == "A bit right.\n"
    assert freed_state is not None
    assert freed_state.last_spoken_text == "A bit right."


def test_drain_attack_run_first_utterance_after_engage_survives_a_busy_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The realistic casualty the review names: `engage`'s own readback
    occupies the channel (`CalloutScheduler.note_reply`, via `_print`)
    right as the run begins, which is exactly when the first alignment
    correction is due. Confirms the fix holds through the real `engage`
    path, not only a hand-set `busy_until_sim`."""
    ownship = _ownship(x=0.0, z=0.0)
    store = ContactStore()
    contact_id = "CONTACT_1"
    store._contacts[contact_id] = _attack_run_contact_off_boresight(
        contact_id, ownship_at_observation=ownship
    )
    tasks = TaskStore()
    assert attack_target_task(store, tasks, contact_id, now_sim=0.0) is not None

    import io

    output = io.StringIO()
    console = CrewConsole(
        store=store,
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
        output=output,
    )

    engage_lines = console.handle_command("engage", now_sim=0.0, slots=None)

    assert engage_lines[0].startswith("Attack run,")
    # `note_reply` claimed the channel for the readback's own duration --
    # the precondition the rest of this test depends on.
    assert console.scheduler.busy_until_sim > 0.0
    printed_after_engage = output.getvalue()

    # The poll loop's own first tick after `engage` (`logger.py`): a fresh
    # `AttackRunState()`, drained immediately, same `now_sim` the readback
    # was spoken at -- the channel is still busy.
    busy_state = console.drain_attack_run(
        AttackRunState(), now_sim=0.0, ownship=ownship
    )

    assert output.getvalue() == printed_after_engage  # nothing new printed
    assert busy_state == AttackRunState()  # not falsely marked spoken

    # The channel frees. The engage readback alone occupies several
    # seconds (per the review's own finding), longer than `ATTACK_RUN_
    # RELATIVE_MAX_AGE_S` (2.0 s) -- exactly as it would in a live flight,
    # the naked-eye channel keeps re-observing the same unchanged geometry
    # every poll, so refresh the percept's own `t_sim` rather than letting
    # it go stale for a reason this test is not about.
    freed_now_sim = console.scheduler.busy_until_sim
    store._contacts[contact_id] = _attack_run_contact_off_boresight(
        contact_id, ownship_at_observation=ownship, t_sim=freed_now_sim
    )
    freed_state = console.drain_attack_run(
        busy_state, now_sim=freed_now_sim, ownship=ownship
    )

    assert output.getvalue() == printed_after_engage + "A bit right.\n"
    assert freed_state is not None
    assert freed_state.last_spoken_text == "A bit right."


def test_drain_attack_run_ends_the_run_after_drop_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 4-5 review, required fix 2: `drop target` cancels the
    standing `attack_target` task but (before this fix) left `drain_
    attack_run` returning the unchanged, still-non-`None` state once the
    task was gone -- the engaged flag then survived to wrongly claim the
    gaze for whatever was selected next. `drain_attack_run` must treat
    "the standing task is gone" exactly like the vanished-contact branch:
    return `None`, which is what `logger.py` assigns straight onto
    `runner.attack_run_state`, clearing `attack_run_engaged`."""
    ownship = _ownship(x=0.0, z=0.0)
    store = ContactStore()
    contact_id = "CONTACT_1"
    store._contacts[contact_id] = _attack_run_contact_off_boresight(
        contact_id, ownship_at_observation=ownship
    )
    tasks = TaskStore()
    assert attack_target_task(store, tasks, contact_id, now_sim=0.0) is not None
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("engage", now_sim=0.0, slots=None)

    console.handle_command("drop_target", now_sim=1.0)

    target_task = next(t for t in tasks.tasks if t.kind == "attack_target")
    assert target_task.status == "cancelled"
    result = console.drain_attack_run(AttackRunState(), now_sim=2.0, ownship=ownship)
    assert result is None


def test_drain_attack_run_ends_the_run_after_the_generic_cancel_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same guard, exercised through the generic all-kinds `cancel_task`
    token (`"cancel"`/`"stop"`) rather than `drop_target` -- the Stage
    4-5 review's point that fixing the single shared guard in `drain_
    attack_run` is what makes the fix hold for this path too, found by
    reproduction rather than by reading."""
    ownship = _ownship(x=0.0, z=0.0)
    store = ContactStore()
    contact_id = "CONTACT_1"
    store._contacts[contact_id] = _attack_run_contact_off_boresight(
        contact_id, ownship_at_observation=ownship
    )
    tasks = TaskStore()
    assert attack_target_task(store, tasks, contact_id, now_sim=0.0) is not None
    console = CrewConsole(
        store=store, tasks=tasks, enrichment=_enrichment_context(monkeypatch)
    )
    console.handle_command("engage", now_sim=0.0, slots=None)

    console.handle_command("cancel_task", now_sim=1.0)

    target_task = next(t for t in tasks.tasks if t.kind == "attack_target")
    assert target_task.status == "cancelled"
    result = console.drain_attack_run(AttackRunState(), now_sim=2.0, ownship=ownship)
    assert result is None


# --- the slotted query's filter slots (plans/crew-query-path/plan.md
# Decision B, Stage 2) ---


def _in_scope(
    console: CrewConsole,
    now_sim: float = 0.0,
    *,
    clock: int | None = None,
    sector: Sector | None = None,
    descriptor: str | None = None,
    relative: RelativeSector | None = None,
    band: str | None = None,
) -> set[str]:
    """The raw class words of the contacts one query is in scope for.

    **Asserted against the scope, not the spoken sentence, deliberately.**
    The enumerated answer goes through `render_group_full_disclosure`,
    whose rule is to name a group's *full roster*, so an in-scope contact
    pulls its out-of-scope group-mates into the text. A spoken assertion
    would therefore be testing `belief.groups`' cohesion, not the filter
    -- and the cohesion it would have tested has since moved: this
    docstring cited the 1/3/7 km spread of `_three_banded_contacts`
    cohering into one `Group`, which was `BL-B48`'s infantry bridge and
    stopped being true at BL-12 Stage 0a. The leak itself is unchanged;
    `_cohering_contacts_across_a_band_boundary` is the fixture that still
    produces it. Stage 3's summary (`render_report_summary`) is computed
    from this same in-scope set, which is what removes the leak -- see
    `test_slotted_report_summary_does_not_leak_an_out_of_scope_group_
    member`."""
    scope = console._report_scope(
        now_sim,
        clock=clock,
        sector=sector,
        descriptor=descriptor,
        relative=relative,
        band=band,
    )
    words: set[str] = set()
    for facts in scope.facts:
        contact_id = facts["id"]
        assert isinstance(contact_id, str)
        contact = console.store.contact(contact_id)
        assert contact is not None
        assert contact.last_class_raw is not None
        words.add(contact.last_class_raw)
    return words


def test_report_band_bounds_mirror_audio_adapters_band_names() -> None:
    """This side of the `BAND_WORDS` <-> `_REPORT_BAND_BOUNDS_M` mirror
    (Decision E): the three band *names* cross the seam, the metres do
    not. audio-adapter's `test_vocabulary.py` asserts the same three names
    against its own synonym table. The boundaries are decision 12's own
    numbers and are asserted here because they are this feature's only two
    new constants."""
    from belief.crew_console import _REPORT_BAND_BOUNDS_M

    assert set(_REPORT_BAND_BOUNDS_M) == {"near", "medium", "far"}
    assert _REPORT_BAND_BOUNDS_M["near"] == (0.0, 2000.0)
    assert _REPORT_BAND_BOUNDS_M["medium"] == (2000.0, 5000.0)
    assert _REPORT_BAND_BOUNDS_M["far"] == (5000.0, float("inf"))


def _cohering_contacts_across_a_band_boundary(now_sim: float = 0.0) -> ContactStore:
    """Three contacts at two o'clock that genuinely cohere into one
    `Group` while straddling the near/medium band boundary -- armor just
    inside 2 km, truck and infantry just outside it.

    **This exists because `_three_banded_contacts` stopped forming a
    group.** That fixture's 1/3/7 km spread only ever cohered through
    `BL-B48`'s unbounded infantry edge, which BL-12 Stage 0a removed, so
    it can no longer demonstrate a roster leak at all. The spacing here is
    inside the real per-pair backstops instead (armor<->truck ~100 m
    against `20.0 * mean(7.0, 6.0) = 130` m; truck<->infantry ~70 m
    against `20.0 * mean(6.0, 1.8) = 78` m), so the group forms on the
    ordinary rule with no eager latitude anywhere in it -- which makes it
    a *better* fixture for the leak than the original was.

    The band split is in `range_m`, which `_enrichment_context`'s
    passthrough `project_terrain_aware` makes the reported range exactly:
    armor 1 950 m (near, `< 2 000`), truck 2 050 m and infantry 2 120 m
    (medium). Member spacing is the `range_m` *difference*, because all
    three sit on one radial -- which is why 100 m / 70 m spacing and a
    2 km band boundary coexist here at all.

    `_three_banded_contacts` is left exactly as it was: its own two tests
    assert band filtering and band labelling and never read a group."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_NEAR",
                t_sim=now_sim,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1950.0,
            ),
            _observation_for_follow(
                obs_id="OBS_MEDIUM",
                t_sim=now_sim,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=2050.0,
            ),
            _observation_for_follow(
                obs_id="OBS_FAR",
                t_sim=now_sim,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                clock=2,
                range_m=2120.0,
            ),
        ],
        now_sim=now_sim,
    )
    store.tick(now_sim=now_sim)
    return store


def _three_banded_contacts(now_sim: float = 0.0) -> ContactStore:
    """One contact per band, all at two o'clock: armor at 1 km (near),
    truck at 3 km (medium), infantry at 7 km (far)."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_NEAR",
                t_sim=now_sim,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_MEDIUM",
                t_sim=now_sim,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_FAR",
                t_sim=now_sim,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                clock=2,
                range_m=7000.0,
            ),
        ],
        now_sim=now_sim,
    )
    store.tick(now_sim=now_sim)
    return store


def test_slotted_report_band_filters_rather_than_sorts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Q1, answered by the user 2026-10-08: **"filter."** The band narrows
    the answer, it does not merely order it -- so a contact outside the
    named band is *absent* from the scope, not merely later in it. Three
    contacts, one per band; each query admits exactly one, and the
    unfiltered query admits all three, which is the contrast that makes
    "filter, not sort" checkable."""
    store = _three_banded_contacts()
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, band="near") == {"OP_ARMORED"}
    assert _in_scope(console, band="medium") == {"OP_TRUCK"}
    assert _in_scope(console, band="far") == {"OP_INFANTRY"}
    assert _in_scope(console) == {"OP_ARMORED", "OP_TRUCK", "OP_INFANTRY"}


def test_slotted_report_band_boundary_is_lower_inclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contact at exactly 2 000 m is `medium`, not `near` -- the bounds
    are `lo <= range < hi`, so the two bands cannot both claim it and
    neither can drop it. Decision 12 words it as *near <2 km / medium
    2-5 km*, which is this comparison exactly."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_EDGE",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=2000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, band="near") == set()
    assert _in_scope(console, band="medium") == {"OP_ARMORED"}
    # And the empty-scope answer really is spoken, not merely an empty set.
    assert console.handle_command("report", now_sim=0.0, slots={"band": "near"}) == [
        "Clear."
    ]


def test_slotted_report_descriptor_excludes_only_a_known_wrong_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision B's three-way verdict, as a filter. `report armor` keeps
    the armor **and** the unclassified dot -- *"he is pointing at a thing
    he believes is armour, matching it is right"* -- and drops only the
    truck, which is positively something else."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_ARMOR",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=12,
                range_m=3000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_DOT",
                t_sim=0.0,
                classification_raw="ground",
                classification_level=0,
                clock=12,
                range_m=5000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    # The dot keeps its raw class word ("ground"); it is in scope for
    # *every* descriptor, which is the whole point of the middle verdict.
    assert _in_scope(console, descriptor="armor") == {"OP_ARMORED", "ground"}
    assert _in_scope(console, descriptor="truck") == {"OP_TRUCK", "ground"}
    assert _in_scope(console, descriptor="sam") == {"ground"}


def test_slotted_report_descriptor_can_empty_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The filter has to be able to exclude everything, or "filter" is not
    what it is doing. A scene of nothing but trucks answers `report ship`
    with the empty answer, not with the trucks."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, descriptor="ship") == set()
    assert console.handle_command(
        "report", now_sim=0.0, slots={"descriptor": "ship"}
    ) == ["Clear."]
    # Unfiltered, the same scene is not empty -- so the empty answer came
    # from the filter and not from an empty store.
    assert _in_scope(console) == {"OP_TRUCK"}


def test_slotted_report_group_descriptor_keeps_its_cardinality_meaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`"group"` is not a classification -- it means `cardinality.lo > 1`,
    the same branch `_descriptor_score` has always had. A singleton armor
    contact is therefore excluded from `report group` while a plural one
    is kept, and the class word has nothing to do with either outcome."""
    from belief.cardinality import cardinality_belief_from_bucket_name

    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_SINGLE",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_MANY",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                clock=3,
                range_m=1000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    plural = next(c for c in store.contacts if c.last_class_raw == "OP_INFANTRY")
    plural.cardinality = cardinality_belief_from_bucket_name(
        "OP_TO5UNITS", established_sim=0.0
    )
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, descriptor="group") == {"OP_INFANTRY"}
    # The class word decides nothing here: `report armor` admits the
    # singleton armour and not the plural infantry, the exact opposite
    # split, over the same two contacts.
    assert _in_scope(console, descriptor="armor") == {"OP_ARMORED"}


def test_slotted_report_relative_uses_the_same_wedge_table_as_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision B: `relative` resolves through `perception.gaze`'s
    `(center, half_width)` table -- the same one `attention.project_
    relative_area` reads -- so `report left` and `scan left` agree on what
    "left" means by construction rather than by coincidence.

    Ownship faces north. A contact dead ahead (relative 0) is in `ahead`
    and `full` and in neither side wedge; one at two o'clock (relative
    +60) is in `right` and `full` but not `ahead` or `left`.

    **Both are placed clear of every wedge edge on purpose.** The first
    attempt put the second contact at one o'clock -- relative +30, which
    is `ahead`'s exact half-width, so it was admitted by the
    `> half_width` comparison and the test read as a filter failure when
    it was a boundary. Edge behaviour is a separate question from "do the
    two frames agree", and mixing them makes a failure unreadable."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_AHEAD",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=12,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_RIGHT",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=3000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, relative="ahead") == {"OP_ARMORED"}
    assert _in_scope(console, relative="right") == {"OP_TRUCK"}
    assert _in_scope(console, relative="left") == set()
    assert _in_scope(console, relative="full") == {"OP_ARMORED", "OP_TRUCK"}
    # The empty side speaks the absence rather than refusing it -- see
    # `test_every_relative_sector_is_inside_the_cockpit_mask`.
    assert console.handle_command(
        "report", now_sim=0.0, slots={"relative": "left"}
    ) == ["Left, clear."]


def test_every_relative_sector_is_inside_the_cockpit_mask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The enumeration the `render_no_view` guard promises, checked rather
    than asserted in prose: all four `RelativeSector`s are forward of
    `rear_cutoff_deg`, so the no-view branch cannot fire for a relative
    query today. It is applied anyway, so that widening the wedge table or
    offering a rear sector fails here instead of silently answering
    "left, clear" about something Petrovich cannot see.

    This is why the companion assertion below matters: a relative query
    with an empty scene must answer `render_clear`, which is the observable
    consequence of the whole enumeration being inside the mask."""
    from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT
    from perception.gaze import RELATIVE_SECTORS, SECTOR_WEDGE_DEG

    rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
    assert len(RELATIVE_SECTORS) == 4
    for relative in RELATIVE_SECTORS:
        center, _half_width = SECTOR_WEDGE_DEG[relative]
        assert abs(center) < rear_cutoff_deg, relative

    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    for relative in RELATIVE_SECTORS:
        # Reset between iterations (`plans/voice-latency-instrumentation/
        # plan.md` Stage 6): the previous relative's own readback would
        # otherwise still be claiming the channel at the same `now_sim`,
        # deferring this one to `[]` -- a loop-ordering artefact, not a
        # mask question.
        console.scheduler.busy_until_sim = 0.0
        lines = console.handle_command(
            "report", now_sim=0.0, slots={"relative": relative}
        )
        assert lines[0].endswith(", clear."), (relative, lines)
        assert "can't see" not in lines[0].lower(), relative


def test_slotted_report_clock_filter_spans_one_hour_either_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision B's widening, and **a behaviour change to the shipped
    `report_clock_*` commands**: the filter was an exact hour and is now
    +/- `callouts.CALLOUT_GROUP_CLOCK_SPAN_HOURS`, because a pilot saying
    "two o'clock" means *around* two and D13's answer speaks a span.

    One contact at three o'clock. Querying two o'clock now finds it
    (delta 1, inside the span) and one o'clock still does not (delta 2) --
    so the test shows both the widening and its bound, rather than only
    that something got wider. Reads the constant rather than the literal
    1, so a retune moves the test with the code; the three/one o'clock
    *contrast* is what pins the behaviour."""
    from belief.callouts import CALLOUT_GROUP_CLOCK_SPAN_HOURS

    assert CALLOUT_GROUP_CLOCK_SPAN_HOURS == 1
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_3",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=3,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, clock=3) == {"OP_ARMORED"}
    assert _in_scope(console, clock=2) == {"OP_ARMORED"}
    assert _in_scope(console, clock=4) == {"OP_ARMORED"}
    assert _in_scope(console, clock=1) == set()
    assert _in_scope(console, clock=12) == set()
    # Through the shipped legacy token too, since this is a change to its
    # behaviour and not only to the new one's. `scheduler.busy_until_sim`
    # is reset between the two calls -- see
    # `test_slotted_report_clock_matches_the_legacy_clock_token`'s
    # identical note (`plans/voice-latency-instrumentation/plan.md`
    # Stage 6).
    assert "armor" in console.handle_command("report_clock_2", now_sim=0.0)[0].lower()
    console.scheduler.busy_until_sim = 0.0
    assert console.handle_command("report_clock_1", now_sim=0.0) == [
        "One o'clock, clear."
    ]


def test_slotted_report_combines_a_where_and_a_how_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The slots are independent filters, so a query carrying two narrows
    by both -- `"describe two o'clock near"`, decision 12's own example.
    The medium contact at the same clock is excluded by the band, and the
    near contact at a different clock by the clock span."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_WANTED",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_TOO_FAR",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                clock=2,
                range_m=4000.0,
            ),
            _observation_for_follow(
                obs_id="OBS_WRONG_WAY",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                clock=9,
                range_m=1000.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, clock=2, band="near") == {"OP_ARMORED"}
    # Each slot is doing its own share of the narrowing: drop either one
    # and the contact it excluded comes back.
    assert _in_scope(console, clock=2) == {"OP_ARMORED", "OP_TRUCK"}
    assert _in_scope(console, band="near") == {"OP_ARMORED", "OP_INFANTRY"}


def test_slotted_report_does_not_filter_by_where_petrovich_is_looking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Decision D, and the sentence that exists so D11's work does not
    silently break this one: **`contacts._callout_may_speak` must not be
    applied to the pull path.** A query is the pilot asking; belief is
    already perception-bounded, so a contact he believes in is reported
    *qualified*, never withheld because the aircraft has since turned
    away.

    Driven by making the contact stale enough that the push path's own
    observability/eligibility reasoning would have something to say about
    it -- `certainty` has fallen to `estimated`, past `OBSERVED_WINDOW_S`
    and past `POSITION_HALF_LIFE_S` -- and asserting the report still
    names it."""
    from belief.decay import OBSERVED_WINDOW_S, POSITION_HALF_LIFE_S

    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_REMEMBERED",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    later = POSITION_HALF_LIFE_S + 1.0
    assert later > OBSERVED_WINDOW_S
    store.tick(now_sim=later)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert _in_scope(console, later, clock=2) == {"OP_ARMORED"}
    lines = console.handle_command("report", now_sim=later, slots={"clock": 2})
    assert lines != ["Two o'clock, clear."]
    # Reported *qualified*, which is the honest shape -- not withheld.
    assert lines == ["Last I saw, one armor, at 2 o'clock, inside 2 kilometres."]


# --- the summary answer at the pull site (Decision C, Stage 3) ---


def test_slotted_report_summary_does_not_leak_an_out_of_scope_group_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**The defect Stage 3 closes, and the reason Stage 2's filter tests
    assert the scope rather than the sentence.**

    `render_group_full_disclosure` names a group's *full roster* by
    design, so while the pull site enumerated groups, a filtered query
    whose scope held one member of a group spoke that group's
    out-of-scope members too: three cohering contacts straddling the
    near/medium boundary, and `report two o'clock near` answered by
    naming the truck and the infantry outside the band to a pilot who
    asked about *near*.

    The summary is computed from the in-scope facts, so it cannot leak by
    construction. The group is asserted to actually exist, because
    without it this test would pass while exercising nothing -- and that
    guard is what caught the fixture going hollow when BL-12 Stage 0a
    removed the `BL-B48` infantry bridge the old 1/3/7 km fixture had
    cohered through. See `_cohering_contacts_across_a_band_boundary`."""
    store = _cohering_contacts_across_a_band_boundary()
    assert len(store.groups) == 1, "fixture must reproduce the cohering group"
    assert len(store.groups[0].member_contact_ids) == 3
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command(
        "report", now_sim=0.0, slots={"clock": 2, "band": "near"}
    )

    assert lines == ["One armor, at 2 o'clock, inside 2 kilometres."]
    assert "truck" not in lines[0].lower()
    assert "infantry" not in lines[0].lower()
    # And the group renderer itself is untouched -- it still speaks every
    # member, which is correct for the push path it belongs to.
    pushed = render_group_full_disclosure(
        store, store.groups[0], now_sim=0.0, enrichment=console.enrichment
    )
    assert pushed is not None
    for word in ("armor", "truck", "infantry"):
        assert word in pushed.text.lower(), word


def test_slotted_report_band_label_follows_the_query_then_the_furthest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The distance clause says how far out the pilot has to look.

    When the query named a band, that band bounds the answer -- he asked
    about *near*, so the clause is "inside 2 kilometres" even though the
    only contact in scope sits at 1 km. Unfiltered, it is bucketed from
    the **furthest** in-scope contact, never the nearest: the near edge
    would under-state where things are, which is the one direction a
    pointer must not be wrong in.

    `scheduler.busy_until_sim` is reset between calls -- see
    `test_slotted_report_clock_matches_the_legacy_clock_token`'s identical
    note (`plans/voice-latency-instrumentation/plan.md` Stage 6)."""
    store = _three_banded_contacts()
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert (
        "inside 2 kilometres"
        in console.handle_command("report", now_sim=0.0, slots={"band": "near"})[0]
    )
    console.scheduler.busy_until_sim = 0.0
    assert (
        "beyond 5 kilometres"
        in console.handle_command("report", now_sim=0.0, slots={"band": "far"})[0]
    )
    console.scheduler.busy_until_sim = 0.0
    # Unfiltered: the furthest contact is at 7 km, so the whole-scene
    # answer reaches beyond five, not "inside 2" from the nearest.
    assert "beyond 5 kilometres" in console.handle_command("report_all", now_sim=0.0)[0]


def test_slotted_report_band_labels_are_derived_from_the_filter_bounds() -> None:
    """The number the summary says and the number the filter applies are
    the same number, because the labels are derived from
    `_REPORT_BAND_BOUNDS_M` rather than written out beside it. A retuned
    boundary therefore moves both or neither -- there is no third place
    for "2 kilometres" to go stale in."""
    from belief.crew_console import _REPORT_BAND_BOUNDS_M, _REPORT_BAND_LABELS

    assert set(_REPORT_BAND_LABELS) == set(_REPORT_BAND_BOUNDS_M)
    assert _REPORT_BAND_LABELS["near"] == "inside 2 kilometres"
    assert _REPORT_BAND_LABELS["medium"] == "inside 5 kilometres"
    assert _REPORT_BAND_LABELS["far"] == "beyond 5 kilometres"


def test_slotted_report_freshness_window_is_the_decay_modules_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live call site passes `decay.OBSERVED_WINDOW_S` -- the
    project's existing "how long since a look is still fresh" bound -- so
    no second staleness constant was introduced (`plans/crew-query-path/
    plan.md` Decision D; `decay.py` is read-only in this plan).

    Driven across the boundary rather than by reading the constant back:
    the same scene answers unqualified just inside the window and
    qualified just outside it. The window is read from `decay` to place
    the two probes, never to assert the wording.

    `scheduler.busy_until_sim` is reset between the two calls -- see
    `test_slotted_report_clock_matches_the_legacy_clock_token`'s identical
    note (`plans/voice-latency-instrumentation/plan.md` Stage 6); the two
    `now_sim` values are only 2s apart, well inside the first call's own
    estimated speech duration."""
    store = ContactStore()
    store.ingest(
        [
            _observation_for_follow(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                clock=2,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    fresh = console.handle_command(
        "report", now_sim=OBSERVED_WINDOW_S - 1.0, slots={"clock": 2}
    )
    console.scheduler.busy_until_sim = 0.0
    stale = console.handle_command(
        "report", now_sim=OBSERVED_WINDOW_S + 1.0, slots={"clock": 2}
    )

    assert "Last I saw" not in fresh[0]
    assert stale[0].startswith("Last I saw,")


# --- the shared descriptor verdict (Decision B) ---


def _facts_with_classification(
    level: str | None, value: str | None
) -> dict[str, object]:
    """The two `facts` keys `descriptor_verdict` reads, with nothing else
    -- the predicate is a pure function of them, so a whole `ContactStore`
    would only obscure which input decided the verdict."""
    if level is None:
        return {}
    return {"classification": {"level": level, "value": value}}


def test_descriptor_verdict_three_outcomes() -> None:
    """The predicate `_descriptor_score` and the report filter now share
    (Decision B, and D10's intended target). Three outcomes rather than a
    boolean, because the middle one decides real behaviour: an
    unclassified contact is neither a match nor a mismatch."""
    from belief.crew_console import descriptor_verdict

    assert (
        descriptor_verdict("armor", _facts_with_classification("class", "OP_ARMORED"))
        == "match"
    )
    assert (
        descriptor_verdict("armor", _facts_with_classification("class", "OP_TRUCK"))
        == "wrong"
    )
    assert (
        descriptor_verdict("armor", _facts_with_classification("presence", "ground"))
        == "unclassified"
    )
    assert descriptor_verdict("armor", _facts_with_classification(None, None)) == (
        "unclassified"
    )
    # A `sam` descriptor spans all three tiers deliberately -- the spoken
    # vocabulary is coarser than `speech._OP_CLASS_DISPLAY`'s three SAM
    # words, since a pilot saying "SAM" has not resolved the tier.
    for tier in ("OP_SRSAM", "OP_MRSAM", "OP_LRSAM"):
        assert (
            descriptor_verdict("sam", _facts_with_classification("class", tier))
            == "match"
        ), tier


def test_descriptor_verdict_group_reads_cardinality_not_classification() -> None:
    from belief.crew_console import descriptor_verdict

    plural: dict[str, object] = {"cardinality": {"lo": 3, "hi": 5.0}}
    singleton: dict[str, object] = {"cardinality": {"lo": 1, "hi": 1.0}}
    assert descriptor_verdict("group", plural) == "match"
    # `"wrong"`, not `"unclassified"`: cardinality is always held, so a
    # contact that is not plural is positively not a group.
    assert descriptor_verdict("group", singleton) == "wrong"
    assert descriptor_verdict("group", {}) == "wrong"
    # And it ignores the class entirely, in both directions.
    armour_plural: dict[str, object] = {
        "cardinality": {"lo": 3, "hi": 5.0},
        "classification": {"level": "class", "value": "OP_ARMORED"},
    }
    assert descriptor_verdict("group", armour_plural) == "match"


def test_descriptor_score_maps_the_shared_verdict_onto_its_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_descriptor_score` is now the verdict-to-weight mapping and
    nothing else. Pinned against the three weights directly, so moving
    the lattice walk back into the method (or changing what one verdict
    scores) fails here -- `follow`'s own resolver tests cover the scoring
    *use*, not this mapping."""
    from belief.crew_console import (
        W_FOLLOW_DESC_UNKNOWN,
        W_FOLLOW_DESC_WRONG,
    )

    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert (
        console._descriptor_score(
            "armor", _facts_with_classification("class", "OP_ARMORED")
        )
        == 0.0
    )
    assert (
        console._descriptor_score(
            "armor", _facts_with_classification("presence", "ground")
        )
        == W_FOLLOW_DESC_UNKNOWN
    )
    assert (
        console._descriptor_score(
            "armor", _facts_with_classification("class", "OP_TRUCK")
        )
        == W_FOLLOW_DESC_WRONG
    )
    assert W_FOLLOW_DESC_UNKNOWN != W_FOLLOW_DESC_WRONG
