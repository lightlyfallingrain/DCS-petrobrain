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
from typing import Self

import pytest

from aircraft_client import AircraftLayerError
from belief import enrichment as enrichment_module
from belief.audio_client import AudioAdapterError
from belief.brain_client import BrainLayerClient
from belief.classification import PRESENCE_CLASS
from belief.contacts import ContactStore
from belief.crew_console import (
    _AIR_DEFENCE_OP_CLASSES,
    DISPATCHED_COMMAND_TOKENS,
    CrewConsole,
    _describe_token_for_confirm,
    _nearest_sector,
)
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainReply, EscalationPayload
from belief.speech import render_group_disclosure
from belief.tasks import TaskStore
from belief.voice_commands import (
    ACT_FLOOR,
    CONFIRM_FLOOR,
    CONFIRM_LATE_ANSWER_GRACE_S,
    CONFIRM_WINDOW_S,
)
from perception import object_model
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


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
        self.stop_calls = 0
        self._fail_on = fail_on

    def push_speech(self, text: str, urgent: bool) -> None:
        if text in self._fail_on:
            raise AudioAdapterError("simulated push failure")
        self.pushed.append((text, urgent))

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
    driving `relative_now`."""
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
        classification_level=2,
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


def test_watch_nearest_without_enrichment_reports_no_contact_to_watch() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store)

    assert console.handle_command("watch_nearest", now_sim=0.0) == [
        "no contact to watch"
    ]


def test_watch_nearest_reports_no_contact_to_watch_when_store_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

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
    lines = console.handle_command("watch_nearest", now_sim=0.0)

    # Contact-report wording (unit type, clock, range), no spoken id -- the
    # player named no contact, so the readback has to say which one it was.
    assert lines == [
        "Watching T-72, 12 o'clock, 0.5 kilometres near Jableh (~200 metres)."
    ]
    assert near_contact.id not in lines[0]
    assert near_contact.attention == "watch"


def test_scan_ahead_without_enrichment_reports_not_configured() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_command("scan_ahead", now_sim=0.0) == [
        "no world-model connection configured"
    ]


def test_scan_ahead_without_tasks_reports_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
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
    lines = console.handle_command("watch_nearest_air_defence", now_sim=0.0)

    assert "Osa" in lines[0]
    assert sam.attention == "watch"
    # The nearer tank must be untouched -- it was never a candidate.
    assert tank.attention == "normal"


def test_watch_nearest_air_defence_selects_a_long_range_sam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression, 2026-09-24: `OP_LRSAM` was absent from
    `_AIR_DEFENCE_OP_CLASSES`, so an S-300 -- long-range SAM, unambiguously
    air defence -- could never be selected by "watch nearest air defence".

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
    lines = console.handle_command("watch_nearest_air_defence", now_sim=0.0)

    assert s300.attention == "watch"
    assert lines and "no air defence contact" not in lines[0]
    assert tank.attention == "normal"


def test_air_defence_classes_cover_every_air_defence_class_in_the_object_model() -> (
    None
):
    """Guards the drift that caused the `OP_LRSAM` omission above, rather
    than only the one instance of it.

    `_AIR_DEFENCE_OP_CLASSES` is enumerated by hand against
    `perception.object_model`'s profile table, and nothing connects the two:
    when that table gained a long-range SAM entry, this set had no way to
    notice. `object_model` carries no structural air-defence marker to
    derive the set from (an `ObjectTypeProfile` is a size and an `op_class`,
    nothing more), so this test matches on the `OP_*` naming instead -- any
    class whose name says SAM or names a gun system must be covered.

    If a future profile entry introduces an air-defence class this pattern
    does not catch, that is a signal to give `object_model` a real marker,
    not to loosen the assertion."""
    profiled_classes = {
        profile.op_class
        for _keyword, profile in (
            *object_model._KEYWORD_PROFILES,
            *object_model._REPORTING_NAME_KEYWORD_PROFILES,
        )
    }
    air_defence_by_name = {
        op_class
        for op_class in profiled_classes
        if op_class.endswith("SAM") or op_class in {"OP_SPAAG", "OP_ZU23"}
    }

    assert air_defence_by_name, "naming heuristic matched nothing -- it has gone stale"
    assert air_defence_by_name <= _AIR_DEFENCE_OP_CLASSES


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
    project claims to have wired must either speak something or be
    `stop_talking`'s documented, deliberate no-readback no-op -- never the
    silent `[]` that sent 20 of 41 recognised voice tokens nowhere."""
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    for token in sorted(DISPATCHED_COMMAND_TOKENS):
        lines = console.handle_command(token, now_sim=0.0)
        if token == "stop_talking":
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
    and pins the spoken output, not just that something was said."""
    store = ContactStore()
    store.ingest(
        [_observation_at(obs_id="OBS_1", t_sim=0.0, ownship_x=0.0, ownship_z=1000.0)],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    assert lines == ["BMP-2, 3 o'clock, 1 kilometre near Jableh (~200 metres)."]


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
    # and `test_report_speaks_a_persisted_group_through_render_group_
    # disclosure`, below.
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    # OBS_E is east of ownship (3 o'clock); OBS_N is dead ahead (12 o'clock)
    # -- only the 3 o'clock contact must be named.
    lines = console.handle_command("report_clock_3", now_sim=0.0)

    assert lines == ["BMP-2, 3 o'clock, 1 kilometre near Jableh (~200 metres)."]


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

    assert lines == ["BMP-2, 6 o'clock, 1 kilometre near Jableh (~200 metres)."]


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


def test_report_all_groups_and_truncates_multiple_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional refinement, `plans/voice-command-completeness/review.md`:
    `group_facts`'s bucketing and `render_report`'s `REPORT_MAX_GROUPS`
    truncation are each unit-tested in isolation (`test_callouts.py`,
    `test_speech.py`) but never driven together through the real
    `_handle_report` dispatch path -- the reviewer verified this seam
    correct by hand, once, with a throwaway script; this pins it. Four
    distinct classification types, each due east at a different range,
    never share a `(unit word, range word)` bucket, so each forms its own
    singleton group -- four groups, capped at `REPORT_MAX_GROUPS` (3),
    ordered nearest-first (`report_priority`'s equal-attention-rank
    tiebreak), with a trailing "And more."."""
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
    # 1 km spacing. They no longer cohere into one `Group`, so this test is
    # naturally about `group_facts`'s report-space bucketing and `REPORT_
    # MAX_GROUPS` truncation alone, as intended.
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    assert lines == [
        (
            "BMP-2, 3 o'clock, 1 kilometre near Jableh (~200 metres). "
            "T-72, 3 o'clock, 2 kilometres near Jableh (~200 metres). "
            "BTR-70, 3 o'clock, 3 kilometres near Jableh (~200 metres). "
            "And more."
        )
    ]


def test_report_speaks_a_persisted_group_through_render_group_disclosure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`plans/group-reporting/plan.md` Stage 4 design, section 6:
    `_handle_report` resolves each in-scope contact's `belief.groups.Group`
    and speaks it once via `render_group_disclosure` -- the same renderer
    `CalloutScheduler.tick` uses for the push path -- rather than the older
    `group_facts`/`render_group_report` report-space bucketing, once a real
    group exists. Three same-type contacts a few metres apart cohere into
    one `Group` on `store.tick`; the report names all three as one line,
    not three separate `"BMP-2, ..."` reports."""
    store = ContactStore()
    store.ingest(
        [
            _observation_at(
                obs_id=f"OBS_{i}",
                t_sim=0.0,
                ownship_x=float(i) * 5.0,
                ownship_z=1000.0,
                classification_raw="BMP-2",
            )
            for i in range(3)
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    assert len(store.groups) == 1
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    lines = console.handle_command("report_all", now_sim=0.0)

    expected = render_group_disclosure(
        store, store.groups[0], now_sim=0.0, enrichment=console.enrichment
    )
    assert expected is not None
    assert lines == [expected.text]
    assert lines == ["Three BMP-2, 3 o'clock, 1 kilometre."]


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
    lines = console.handle_command("follow", now_sim=0.0, slots={"descriptor": "armor"})
    assert "armor" in lines[0].lower()
    armor_id = next(c.id for c in store.contacts if c.last_class_raw == "OP_ARMORED")
    assert (
        store.contacts[[c.id for c in store.contacts].index(armor_id)].attention
        == "watch"
    )


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
    lines = console.handle_command("follow", now_sim=0.0, slots={"clock": 2})
    assert "armor" in lines[0].lower()


def test_follow_with_no_qualifiers_says_again() -> None:
    console = CrewConsole(store=ContactStore())
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
    lines = console.handle_command("follow", now_sim=0.0, slots={"clock": 2})
    assert lines == ["Nothing at two o'clock."]


def test_follow_with_no_contacts_at_all() -> None:
    console = CrewConsole(store=ContactStore(), enrichment=None)
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
