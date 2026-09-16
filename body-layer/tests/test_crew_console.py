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
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.escalation import EscalationPayload
from belief.tasks import TaskStore
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
    *, obs_id: str, t_sim: float, classification_raw: str, ownship_x: float
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


# -- handle_f10_command (plans/f10-crew-commands/plan.md) -------------------


def test_handle_f10_command_unrecognized_token_returns_empty_list() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_f10_command("shut_down_dcs", now_sim=0.0) == []


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
    assert lines == ["Watching T-72, 12 o'clock, 0.5 km near Jableh (~200m)."]
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


def test_scan_ahead_registers_a_task_and_triggers_a_live_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert client.triggered_modes == ["forward"]
    # D5: a real PendingIntent is registered over an ownship-anchored area.
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


def test_scan_registers_task_even_when_the_live_trigger_fails() -> None:
    """D5's core fix: a failed live trigger must not prevent the task from
    being registered -- the register-then-trigger ordering means the task
    already exists by the time the trigger call (and its failure) happens."""
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

    assert lines == ["Scanning the full forward arc."]
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

    assert lines == [f"cancelled task {task_id}"]
    assert tasks.get(task_id) is not None
    resolved = tasks.get(task_id)
    assert resolved is not None and resolved.status == "cancelled"


def test_cancel_task_without_tasks_configured_reports_no_pending_task() -> None:
    console = CrewConsole(store=ContactStore())
    assert console.handle_f10_command("cancel_task", now_sim=0.0) == ["no pending task"]


def test_cancel_task_reports_no_pending_task_when_none_pending() -> None:
    store = ContactStore()
    tasks = TaskStore()
    console = CrewConsole(store=store, tasks=tasks)

    assert console.handle_f10_command("cancel_task", now_sim=0.0) == ["no pending task"]


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

    assert lines == [f"cancelled task {task2.id}"]
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
