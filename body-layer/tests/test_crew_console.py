"""Tests for `belief.crew_console` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 4's typed-input/printed-output crew session.

Includes the plan's required acceptance test: a scripted session reproducing
`docs/concept/PETROBRAIN_RUNTIME.md`'s "First useful success criterion"
(detect -> watch -> readback -> lost -> reacquired -> "where was that BMP?"
-> memory-backed answer), plus one contact-report trigger and one injected
urgent call -- the four pieces the milestone's acceptance criterion names
explicitly."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from aircraft_client import AircraftLayerError
from belief import enrichment as enrichment_module
from belief.audio_client import AudioAdapterError
from belief.classification import PRESENCE_CLASS
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.escalation import EscalationPayload
from belief.tasks import TaskStore
from belief.voice_commands import ACT_FLOOR, CONFIRM_FLOOR, CONFIRM_WINDOW_S
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
    def __init__(self) -> None:
        self.payloads: list[EscalationPayload] = []

    def handle(self, payload: EscalationPayload) -> None:
        self.payloads.append(payload)

    def awaiting_reply_id(self) -> str | None:
        return None


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

    # Petrovich later detects it again.
    reacquired_at = lost_at + 1.0
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=reacquired_at, classification_raw="BMP-2")],
        now_sim=reacquired_at,
    )
    store.tick(now_sim=reacquired_at)
    reacquired_lines = console.drain_events(now_sim=reacquired_at)
    assert "BMP-2." in reacquired_lines

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


# -- handle_f10_command (plans/f10-crew-commands/plan.md) -------------------


def test_handle_f10_command_unrecognized_token_returns_empty_list() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_f10_command("shut_down_dcs", now_sim=0.0) == []


# -- stop_talking (Stage 3, plans/inbound-speech/plan.md, revised by the ----
# Stage 3 follow-up, user direction 2026-09-20: "no readback or            --
# confirmation, just stop talking" -- an exception to the readback/confirm --
# rule, not the deferred-from-Stage-2 "Copy." acknowledgement this token   --
# originally shipped with) -----------------------------------------------


def test_stop_talking_speaks_nothing() -> None:
    console = CrewConsole(store=ContactStore())
    lines = console.handle_f10_command("stop_talking", now_sim=0.0)
    assert lines == []


def test_stop_talking_calls_speech_client_stop_not_push_speech() -> None:
    """The whole point of `stop_talking`: it must reach the interrupt-only
    `AudioAdapterClient.stop()` (`POST /stop`), never `push_speech` -- no
    audio is ever synthesized or delivered for this token."""
    speech_client = FakeSpeechClient()
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_f10_command("stop_talking", now_sim=0.0)

    assert lines == []
    assert speech_client.pushed == []
    assert speech_client.stop_calls == 1


def test_stop_talking_pushes_nothing_to_the_overlay() -> None:
    """No line, no overlay push, no `"!! "` prefix -- `_print` is never
    called for this token at all."""
    overlay_client = FakeOverlayClient()
    console = CrewConsole(store=ContactStore(), overlay_client=overlay_client)  # type: ignore[arg-type]

    console.handle_f10_command("stop_talking", now_sim=0.0)

    assert overlay_client.pushed == []


def test_stop_talking_interrupt_failure_does_not_raise() -> None:
    """A failed interrupt call degrades silently -- same per-sink isolation
    posture as every other `speech_client` use in `_print`, even though
    this call bypasses `_print` entirely."""
    speech_client = FakeSpeechClient(fail_on=frozenset({"Copy."}))
    console = CrewConsole(store=ContactStore(), speech_client=speech_client)  # type: ignore[arg-type]

    lines = console.handle_f10_command("stop_talking", now_sim=0.0)

    assert lines == []


def test_watch_nearest_without_enrichment_reports_no_contact_to_watch() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store)

    assert console.handle_f10_command("watch_nearest", now_sim=0.0) == [
        "no contact to watch"
    ]


def test_watch_nearest_reports_no_contact_to_watch_when_store_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    console = CrewConsole(store=store, enrichment=_enrichment_context(monkeypatch))

    assert console.handle_f10_command("watch_nearest", now_sim=0.0) == [
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
    lines = console.handle_f10_command("watch_nearest", now_sim=0.0)

    # Contact-report wording (unit type, clock, range), no spoken id -- the
    # player named no contact, so the readback has to say which one it was.
    assert lines == [
        "Watching T-72, 12 o'clock, 0.5 kilometres near Jableh (~200 metres)."
    ]
    assert near_contact.id not in lines[0]
    assert near_contact.attention == "watch"


def test_scan_ahead_without_enrichment_reports_not_configured() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_f10_command("scan_ahead", now_sim=0.0) == [
        "no world-model connection configured"
    ]


def test_scan_ahead_without_tasks_reports_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = CrewConsole(
        store=ContactStore(), enrichment=_enrichment_context(monkeypatch)
    )
    assert console.handle_f10_command("scan_ahead", now_sim=0.0) == [
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

    lines = console.handle_f10_command("scan_ahead", now_sim=0.0)

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

    lines = console.handle_f10_command("scan_bearing_n", now_sim=0.0)

    assert lines == ["Scanning north."]
    task = tasks.tasks[0]
    assert task.area.sector == "N"
    assert task.area.relative_sector is None


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

    lines = console.handle_f10_command("scan_full", now_sim=0.0)

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

    console.handle_f10_command("scan_ahead", now_sim=0.0)
    task_id = tasks.tasks[0].id

    lines = console.handle_f10_command("cancel_task", now_sim=1.0)

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

    console.handle_f10_command("scan_ahead", now_sim=0.0)
    task = tasks.tasks[0]
    task.status = "succeeded"

    lines = console.handle_f10_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan ahead."]
    resolved = tasks.get(task.id)
    assert resolved is not None and resolved.status == "cancelled"


def test_cancel_task_without_tasks_configured_reports_nothing_to_stop() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_f10_command("cancel_task", now_sim=0.0) == ["nothing to stop"]


def test_cancel_task_reports_nothing_to_stop_when_none_pending() -> None:
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(store=store, tasks=tasks)

    assert console.handle_f10_command("cancel_task", now_sim=0.0) == ["nothing to stop"]


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

    lines = console.handle_f10_command("cancel_task", now_sim=2.0)

    # This task was built directly with no sector on its area, so the
    # phrase falls back to the bare kind rather than naming a sector.
    assert lines == ["Copy, stop scan."]
    assert task2.id not in lines[0]
    resolved_task2 = tasks.get(task2.id)
    resolved_task1 = tasks.get(task1.id)
    assert resolved_task2 is not None and resolved_task2.status == "cancelled"
    assert resolved_task1 is not None and resolved_task1.status == "pending"


def test_handle_f10_command_pushes_to_overlay_via_the_print_funnel(
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

    lines = console.handle_f10_command("scan_ahead", now_sim=0.0)

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
    lines = console.handle_f10_command("watch_nearest_air_defence", now_sim=0.0)

    assert "Osa" in lines[0]
    assert sam.attention == "watch"
    # The nearer tank must be untouched -- it was never a candidate.
    assert tank.attention == "normal"


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
    assert console.handle_f10_command("watch_nearest_air_defence", now_sim=0.0) == [
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

    assert console.handle_f10_command("watch_nearest_air_defence", now_sim=0.0) == [
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

    console.handle_f10_command("scan_bearing_se", now_sim=0.0)
    lines = console.handle_f10_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan southeast."]


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

    console.handle_f10_command("watch_nearest", now_sim=0.0)

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
    console.handle_f10_command("watch_nearest", now_sim=0.0)
    assert contact.attention == "watch"

    lines = console.handle_f10_command("cancel_task", now_sim=1.0)

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

    lines = console.handle_f10_command("watch_nearest", now_sim=0.0)

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

    console.handle_f10_command("scan_ahead", now_sim=0.0)
    console.handle_f10_command("watch_nearest", now_sim=0.0)
    assert len(tasks.tasks) == 2
    assert contact.attention == "watch"

    lines = console.handle_f10_command("cancel_task", now_sim=1.0)

    assert lines == ["Copy, stop scan ahead and watch."]
    assert contact.attention == "normal"
    assert all(task.status == "cancelled" for task in tasks.tasks)


def test_cancel_task_only_cancels_the_newest_task_per_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A superseded scan (never explicitly cancelled, just no longer
    honoured by `logger._active_gaze`) must not be swept up by a later
    "Cancel Task" alongside the current watch -- only the newest task of
    each kind is "currently governing" (`_active_tasks_by_kind`)."""
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

    console.handle_f10_command("scan_ahead", now_sim=0.0)
    console.handle_f10_command("scan_left", now_sim=1.0)
    first_scan, second_scan = tasks.tasks
    console.handle_f10_command("watch_nearest", now_sim=1.0)

    lines = console.handle_f10_command("cancel_task", now_sim=2.0)

    assert lines == ["Copy, stop scan left and watch."]
    assert first_scan.status == "pending"
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

    # The window elapsed -- "roger" is no longer answering anything, and
    # (verb_anchored=False here) falls through instead of committing.
    assert lines == []
    assert tasks.tasks == []


def test_handle_transcript_cancel_task_needs_the_higher_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = TaskStore()
    console = CrewConsole(
        store=ContactStore(),
        tasks=tasks,
        enrichment=_enrichment_context(monkeypatch),
    )
    console.handle_f10_command("scan_ahead", now_sim=0.0)
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
    console.handle_f10_command("scan_ahead", now_sim=0.0)
    console.handle_f10_command("watch_nearest", now_sim=0.0)

    lines = console.handle_f10_command("cancel_scan", now_sim=1.0)

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
    console.handle_f10_command("scan_ahead", now_sim=0.0)
    console.handle_f10_command("watch_nearest", now_sim=0.0)

    lines = console.handle_f10_command("cancel_watch", now_sim=1.0)

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
    console.handle_f10_command("watch_nearest", now_sim=0.0)

    lines = console.handle_f10_command("cancel_scan", now_sim=1.0)

    assert lines == ["nothing to stop"]
    assert contact.attention == "watch"
