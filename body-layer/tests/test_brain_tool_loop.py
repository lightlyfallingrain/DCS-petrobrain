"""Tests for BR-2 Stage 2/3's tool loop (`plans/brain-tool-calls/plan.md`)
-- the part of `belief.crew_console.CrewConsole.drain_brain` that
executes a validated `tool_call`, drives continuation rounds, and
renders the eventual `answer`/`ask`/`unable`/`command` final. A scripted
fake `BrainClient` plus a scripted fake `run_brain_tool` closure drive
exact step sequences through the real `CrewConsole`/`belief.brain_reply`
code -- nothing here talks to brain-layer or Ollama."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

import pytest

from belief import enrichment as enrichment_module
from belief.contacts import ContactStore
from belief.crew_console import BRAIN_MAX_TOOL_ROUNDS, CrewConsole
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainReply, EscalationPayload
from belief.referent import Mention
from belief.tasks import TaskStore
from belief.tool_api import BRAIN_TOOLS_BY_NAME, ToolContext, ToolObservation
from belief.tools import watch_contact_task
from mission_memory.store import MissionMemory
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


@dataclass
class _FakeDescription:
    nearest_settlement: object | None = None
    inside_settlement: object | None = None
    nearest_road: object | None = None
    nearest_water: object | None = None
    nearby_ridges: object | None = None
    nearby_valleys: object | None = None
    inside_landcover: object | None = None
    nearest_coastline: object | None = None


class _ScriptedBrainClient:
    """`belief.escalation.BrainClient`, scripted: every `handle()` call is
    recorded, and `poll_replies()` returns the next queued reply (if the
    queue holds one) and then empties -- a test drives a turn's rounds
    by pushing one reply, draining, pushing the next, draining again."""

    def __init__(self) -> None:
        self.payloads: list[EscalationPayload] = []
        self._queue: list[BrainReply] = []

    def handle(self, payload: EscalationPayload) -> None:
        self.payloads.append(payload)

    def awaiting_reply_id(self) -> str | None:
        return None

    def queue(self, reply: BrainReply) -> None:
        self._queue.append(reply)

    def poll_replies(self) -> list[BrainReply]:
        drained, self._queue = self._queue, []
        return drained

    def available(self) -> bool:
        return True


@dataclass
class _ScriptedToolRunner:
    """A scripted fake `CrewConsole.run_brain_tool` -- canned
    `ToolObservation`s keyed by tool name, and a call log for asserting
    "at most one tool execution per poll" / "repeated call" behaviour."""

    observations: dict[str, ToolObservation] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, object], float]] = field(default_factory=list)

    def __call__(
        self, tool_name: str, args: dict[str, object], now_sim: float
    ) -> ToolObservation:
        self.calls.append((tool_name, dict(args), now_sim))
        return self.observations.get(tool_name, ToolObservation(summary="ok"))


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(obs_id: str, classification_raw: str = "T-72") -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


def _store_with_one_contact() -> ContactStore:
    store = ContactStore()
    store.ingest([_observation("OBS_1")], now_sim=0.0)
    return store


def _store_with_two_far_apart_contacts() -> ContactStore:
    """Two "T-72" contacts far enough apart that `ContactStore.ingest`
    keeps them distinct (mirrors `test_crew_console.py`'s own
    `_two_ambiguous_bmp_contacts` helper, kept as a local copy per that
    file's fixture convention)."""
    store = ContactStore()
    near = _observation("OBS_1", "T-72")
    far = Observation(
        id="OBS_2",
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="T-72",
        bearing_deg=180.0,
        range_m=5000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=-5000.0, z=0.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )
    store.ingest([near, far], now_sim=0.0)
    assert len(store.contacts) == 2
    return store


def _start_turn(console: CrewConsole, brain_client: _ScriptedBrainClient) -> str:
    console.handle_line("Petrovich, where's the T-72?", now_sim=0.0)
    assert len(brain_client.payloads) == 1
    return brain_client.payloads[0].utterance_id


def test_scripted_tool_call_then_final_answer_drives_the_whole_turn() -> None:
    """The plan's own worked case: `find_contact` -> one contact -> a
    `contacts` answer naming it. Two polls: round 0 (tool_call) executes
    the tool and posts the continuation; round 1 (answer) speaks."""
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary=f"{contact_id}: T-72, observed.", handles=(contact_id,)
            )
        }
    )
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    lines = console.drain_brain(now_sim=1.0)
    assert lines == []
    assert tool_runner.calls == [("find_contact", {"text": "t-72"}, 1.0)]
    # The continuation was posted with the growing round/steps.
    assert len(brain_client.payloads) == 2
    continuation = brain_client.payloads[1]
    assert continuation.utterance_id == utterance_id
    assert continuation.round == 1
    assert continuation.mode == "addressed"
    assert len(continuation.steps) == 1
    assert continuation.steps[0]["tool"] == "find_contact"

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="answer",
            t_sim=1.0,
            form="contacts",
            refs=(contact_id,),
        )
    )
    lines = console.drain_brain(now_sim=2.0)
    assert len(lines) == 1
    assert "T-72" in lines[0]
    # The turn is over -- nothing left tracked for it.
    assert utterance_id not in console._brain_turns


def test_unoffered_ref_is_rejected_and_costs_a_round() -> None:
    """D3: a final `answer` naming a ref never offered this turn (no
    tool call ever returned it) degrades rather than being spoken --
    here, with no candidate set recorded, it degrades to `unable
    CANNOT_ANSWER`."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = _ScriptedToolRunner()

    utterance_id = _start_turn(console, brain_client)

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="answer",
            t_sim=0.0,
            form="contacts",
            refs=("CONTACT_NEVER_OFFERED",),
        )
    )
    lines = console.drain_brain(now_sim=1.0)
    assert lines == ["Unable, don't know."]


def test_unoffered_tool_call_arg_is_rejected_as_invalid_and_continues() -> None:
    """D3: a `contact_ref` argument naming a handle not offered this
    turn is rejected by `validate_tool_call` before `run_brain_tool` is
    ever called -- the round still advances (an `invalid: ...`
    observation), it does not crash or silently execute."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="describe_contact",
            args={"contact_ref": "CONTACT_NEVER_OFFERED"},
        )
    )
    console.drain_brain(now_sim=1.0)
    assert tool_runner.calls == []  # never executed
    turn = console._brain_turns[utterance_id]
    assert turn.round == 1
    assert turn.steps[0].observation.startswith("invalid:")


def test_ambiguous_answer_without_evidence_becomes_which_one() -> None:
    """D3's ambiguity-evidence rule: a `find_contact` call that returned
    two candidates, followed by an `answer(contacts, [one of them])`
    with no (or ungrounded) `because`, degrades to "which one?" over the
    two -- never a silent pick."""
    store2 = _store_with_two_far_apart_contacts()
    ids = [contact.id for contact in store2.contacts]

    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary=f"{ids[0]}: T-72, near the village.; {ids[1]}: T-72, near the road.",
                handles=tuple(ids),
                candidate_texts={
                    ids[0]: "T-72, near the village.",
                    ids[1]: "T-72, near the road.",
                },
            )
        }
    )
    console = CrewConsole(store=store2, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="answer",
            t_sim=1.0,
            form="contacts",
            refs=(ids[0],),
            because=None,
        )
    )
    lines = console.drain_brain(now_sim=2.0)
    assert len(lines) == 1
    assert lines[0].startswith("Which one -- ")


def test_evidence_grounded_in_transcript_and_candidate_passes() -> None:
    """The same ambiguous pair, but this time `because` is a word from
    the transcript that appears in the picked candidate's own recorded
    text and in no other candidate's -- the answer is spoken, not
    degraded (`_validate_pick`'s own evidence test, reused)."""
    store2 = _store_with_two_far_apart_contacts()
    ids = [contact.id for contact in store2.contacts]

    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary="ok",
                handles=tuple(ids),
                candidate_texts={
                    ids[0]: "T-72, near the village.",
                    ids[1]: "T-72, near the road.",
                },
            )
        }
    )
    console = CrewConsole(store=store2, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    console.handle_line("Petrovich, the one near the village", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="answer",
            t_sim=1.0,
            form="contacts",
            refs=(ids[0],),
            because="near the village",
        )
    )
    lines = console.drain_brain(now_sim=2.0)
    assert len(lines) == 1
    assert not lines[0].startswith("Which one")


def test_contact_lost_between_call_and_speech_says_lost_him() -> None:
    """D4 revalidation applies to the Stage 2 `contacts` answer form:
    the contact named existed when offered, but is gone from the store
    by the time the final reply lands -> "lost him," not a stale
    readback."""
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary=f"{contact_id}: T-72.", handles=(contact_id,)
            )
        }
    )
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)

    del store._contacts[contact_id]

    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="answer",
            t_sim=1.0,
            form="contacts",
            refs=(contact_id,),
        )
    )
    lines = console.drain_brain(now_sim=2.0)
    assert lines == ["Lost him."]


def test_superseded_turn_never_speaks() -> None:
    """D3: a new addressed utterance supersedes the outstanding turn
    silently -- a reply for the old `utterance_id` that lands afterwards
    is simply untracked and produces no speech at all."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = _ScriptedToolRunner()

    old_utterance_id = _start_turn(console, brain_client)

    console.handle_line("Petrovich, where are we?", now_sim=0.5)
    assert len(brain_client.payloads) == 2
    new_utterance_id = brain_client.payloads[1].utterance_id
    assert new_utterance_id != old_utterance_id

    brain_client.queue(
        BrainReply(
            utterance_id=old_utterance_id,
            kind="answer",
            t_sim=0.0,
            form="nothing_seen",
        )
    )
    lines = console.drain_brain(now_sim=1.0)
    assert lines == []


def test_at_most_one_tool_execution_per_poll() -> None:
    """D6: even if more than one `tool_call` reply were to arrive in a
    single `drain_brain` batch, only the first is executed this poll."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)

    # Queue two tool_call replies for the same turn at once -- an
    # artificial batch (a real transport would never queue two replies
    # for one still-open round), but exactly what the guard must survive.
    brain_client._queue = [
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        ),
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="describe_our_position",
            args={},
        ),
    ]
    console.drain_brain(now_sim=1.0)
    assert len(tool_runner.calls) == 1
    assert tool_runner.calls[0][0] == "find_contact"


def test_repeated_identical_tool_call_is_rejected() -> None:
    """The research note's design input: a `(tool, args)` pair already
    recorded this turn's own `steps` is rejected on a repeat, rather
    than executed (and costing) again."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)

    for _ in range(2):
        brain_client.queue(
            BrainReply(
                utterance_id=utterance_id,
                kind="tool_call",
                t_sim=0.0,
                tool="find_contact",
                args={"text": "t-72"},
            )
        )
        console.drain_brain(now_sim=1.0)

    assert len(tool_runner.calls) == 1  # executed once, rejected the second time
    turn = console._brain_turns[utterance_id]
    assert turn.round == 2
    assert turn.steps[1].observation.startswith("invalid:")
    assert "already called" in turn.steps[1].observation


def test_round_cap_exceeded_degrades_the_turn() -> None:
    """D9: exceeding `BRAIN_MAX_TOOL_ROUNDS` ends the turn in a degraded
    reply rather than looping forever."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner()
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)

    lines: list[str] = []
    for round_index in range(BRAIN_MAX_TOOL_ROUNDS + 1):
        brain_client.queue(
            BrainReply(
                utterance_id=utterance_id,
                kind="tool_call",
                t_sim=0.0,
                tool="describe_our_position",
                args={"_round": round_index},  # type: ignore[dict-item]
            )
        )
        lines = console.drain_brain(now_sim=float(round_index) + 1.0)

    # `describe_our_position` takes no arguments -- each of these calls
    # is itself rejected as an unknown-arg call, which is fine: the
    # point of this test is that the round counter advances regardless
    # and the turn ends once it exceeds the cap.
    assert utterance_id not in console._brain_turns
    assert lines == ["Unable, no answer."] or lines[0].startswith("Which one")


def test_serialised_tool_call_payload_carries_no_raw_coordinates() -> None:
    """D2's "no raw x/z" -- a grep-style check over the actual JSON this
    class would send on the continuation POST: `EscalationPayload.
    steps`/`.tools` never carries an `"x"`/`"z"` key anywhere, even
    though the contact involved has a real position in the store."""
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary=f"{contact_id}: T-72, observed.", handles=(contact_id,)
            )
        }
    )
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)

    continuation = brain_client.payloads[-1]
    serialised = json.dumps({"steps": continuation.steps, "tools": continuation.tools})
    assert '"x"' not in serialised
    assert '"z"' not in serialised


def test_describe_our_position_observation_has_no_x_or_z(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`belief.tool_api._describe_our_position_adapter`'s own observation
    text -- the compact string a model would actually read -- never
    contains the raw position it is built from, only the rendered
    summary (heading/altitude/semantic-fact text)."""
    monkeypatch.setattr(
        enrichment_module, "describe_position", lambda *a, **k: _FakeDescription()
    )
    conn = sqlite3.connect(":memory:")
    enrichment = EnrichmentContext(
        conn=conn, theatre="Syria", ownship=_ownship(x=12345.0, z=67890.0)
    )
    ctx = ToolContext(
        store=ContactStore(), enrichment=enrichment, memory=MissionMemory(), now_sim=0.0
    )
    tool = BRAIN_TOOLS_BY_NAME["describe_our_position"]
    observation = tool.invoke(ctx, {})
    assert "12345" not in observation.summary
    assert "67890" not in observation.summary


# ---------------------------------------------------------------------------
# BR-2 Stage 3 (`plans/brain-tool-calls/plan.md` D5) -- commands through
# `handle_command`.
# ---------------------------------------------------------------------------


def _dispatch_command_final(
    console: CrewConsole,
    brain_client: _ScriptedBrainClient,
    utterance_id: str,
    token: str,
    target: str | None,
    *,
    because: str | None = None,
    # Kept under `STAND_BY_AFTER_S` (2.0) from the turn's own
    # `started_sim` (every `_start_turn` helper call here starts at
    # `now_sim=0.0`) -- otherwise `drain_brain`'s own `_speak_stand_by_
    # if_due` speaks "stand by" first and bumps `self.scheduler.
    # busy_until_sim` past this call's `now_sim`, which would make any
    # `_speak_or_defer`-routed readback (`follow`/`mark_target`/etc.)
    # defer instead of speaking immediately -- a test-timing artefact,
    # not something this stage's dispatch logic should be judged by.
    now_sim: float = 1.0,
) -> list[str]:
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="command",
            t_sim=now_sim,
            token=token,
            target=target,
            because=because,
            slots={},
        )
    )
    return console.drain_brain(now_sim=now_sim)


def test_brain_command_mark_target_matches_phrasebook_dispatch() -> None:
    """E3 differential test: `mark_target` with a tool-resolved `target`
    (the brain path) and a bare "mark target" referent dispatch (the
    phrasebook path, `[[BL-B102]]`'s "mark it" shape) produce identical
    readback text from identical belief state -- `_handle_brain_
    command`'s own docstring: both ultimately call the same
    `handle_command`."""
    marks: list[tuple[str, float]] = []

    def _mark_target_fn(contact_id: str, now_sim: float) -> str:
        marks.append((contact_id, now_sim))
        return f"mark N set on {contact_id}"

    # Phrasebook path: seed the referent directly (the voice "mark it"
    # shape) and dispatch through `handle_command`.
    phrasebook_store = _store_with_one_contact()
    contact_id = phrasebook_store.contacts[0].id
    phrasebook_console = CrewConsole(
        store=phrasebook_store,
        brain_client=_ScriptedBrainClient(),
        mark_target_fn=_mark_target_fn,
    )
    phrasebook_console._referent_memory.record(
        [Mention(kind="contact", id=contact_id, t_sim=0.0)], 0.0
    )
    phrasebook_lines = phrasebook_console.handle_command(
        "mark_target", now_sim=1.0, slots={"referent": True}
    )

    # Brain path: resolve the same contact via a tool call, then a
    # validated `command` final naming it as `target`.
    brain_store = _store_with_one_contact()
    assert brain_store.contacts[0].id == contact_id
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(summary="x", handles=(contact_id,))
        }
    )
    brain_console = CrewConsole(
        store=brain_store, brain_client=brain_client, mark_target_fn=_mark_target_fn
    )
    brain_console.run_brain_tool = tool_runner
    utterance_id = _start_turn(brain_console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    brain_console.drain_brain(now_sim=1.0)
    brain_lines = _dispatch_command_final(
        brain_console, brain_client, utterance_id, "mark_target", contact_id
    )

    assert brain_lines == phrasebook_lines == [f"mark N set on {contact_id}"]
    assert marks == [(contact_id, 1.0), (contact_id, 1.0)]


def test_brain_command_cancel_task_matches_phrasebook_dispatch() -> None:
    """E3, a no-target command: `cancel_task` from the brain path (a
    `command` final with no `target`) cancels the same task and speaks
    the same readback a direct `handle_command("cancel_task", ...)` call
    would, from identical task state."""

    def _build() -> tuple[CrewConsole, TaskStore]:
        store = _store_with_one_contact()
        contact_id = store.contacts[0].id
        tasks = TaskStore()
        assert watch_contact_task(store, tasks, contact_id, now_sim=0.0) is not None
        console = CrewConsole(
            store=store, brain_client=_ScriptedBrainClient(), tasks=tasks
        )
        return console, tasks

    phrasebook_console, phrasebook_tasks = _build()
    phrasebook_lines = phrasebook_console.handle_command("cancel_task", now_sim=1.0)

    brain_console, brain_tasks = _build()
    brain_client = brain_console.brain_client
    assert isinstance(brain_client, _ScriptedBrainClient)
    utterance_id = _start_turn(brain_console, brain_client)
    brain_lines = _dispatch_command_final(
        brain_console, brain_client, utterance_id, "cancel_task", None, now_sim=1.0
    )

    assert brain_lines == phrasebook_lines
    assert [t.status for t in brain_tasks.tasks] == [
        t.status for t in phrasebook_tasks.tasks
    ]


def test_excluded_token_gets_fixed_command_only() -> None:
    """U2: a token the brain is not allowed to dispatch (`engage`, one
    of the weapons/sight tokens excluded by policy) degrades to `unable
    FIXED_COMMAND_ONLY`, never dispatched."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    utterance_id = _start_turn(console, brain_client)
    lines = _dispatch_command_final(console, brain_client, utterance_id, "engage", None)
    assert lines == ["Unable, fixed command only."]


def test_unknown_token_also_gets_fixed_command_only() -> None:
    """D5's own instruction: a token that is not a real command at all
    (not merely excluded by policy) degrades identically -- there is no
    second reason to distinguish "excluded" from "not a command"."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    utterance_id = _start_turn(console, brain_client)
    lines = _dispatch_command_final(
        console, brain_client, utterance_id, "not_a_real_command", None
    )
    assert lines == ["Unable, fixed command only."]


def test_command_target_not_offered_is_rejected() -> None:
    """D3: a `command` final naming a `target` never offered this turn
    (no tool call ever returned it, no header mention) degrades -- here,
    with no candidate set recorded, to `unable CANNOT_ANSWER`."""
    store = _store_with_one_contact()
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    utterance_id = _start_turn(console, brain_client)
    lines = _dispatch_command_final(
        console, brain_client, utterance_id, "follow", "CONTACT_NEVER_OFFERED"
    )
    assert lines == ["Unable, don't know."]


def test_ambiguous_command_target_without_because_becomes_which_one() -> None:
    """D3's ambiguity-evidence rule, extended to a command's own
    `target` (plan D3): a `find_contact` call that returned two
    candidates, followed by `command where_is_it target=<one of them>`
    with no `because`, degrades to "which one?" over the two -- the
    target is never silently dispatched on a guess."""
    store2 = _store_with_two_far_apart_contacts()
    ids = [contact.id for contact in store2.contacts]
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary="two",
                handles=tuple(ids),
                candidate_texts={
                    ids[0]: "T-72, near the village.",
                    ids[1]: "T-72, near the road.",
                },
            )
        }
    )
    console = CrewConsole(store=store2, brain_client=brain_client)
    console.run_brain_tool = tool_runner
    utterance_id = _start_turn(console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)
    lines = _dispatch_command_final(
        console, brain_client, utterance_id, "where_is_it", ids[0]
    )
    assert len(lines) == 1
    assert lines[0].startswith("Which one -- ")
    # Never dispatched -- `where_is_it_requested` stays false, the
    # degrade never reached `handle_command` at all.
    assert console.where_is_it_requested is False


def test_ambiguous_command_target_with_because_dispatches() -> None:
    """The same ambiguous pair, but `because` is a word from the
    transcript that appears in the picked candidate's own text and no
    other's -- the command dispatches (`handle_command` runs, the
    one-shot `where_is_it_requested` signal is set), not degraded."""
    store2 = _store_with_two_far_apart_contacts()
    ids = [contact.id for contact in store2.contacts]
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(
                summary="two",
                handles=tuple(ids),
                candidate_texts={
                    ids[0]: "T-72, near the village.",
                    ids[1]: "T-72, near the road.",
                },
            )
        }
    )
    console = CrewConsole(store=store2, brain_client=brain_client)
    console.run_brain_tool = tool_runner
    console.handle_line("Petrovich, the one near the village", now_sim=0.0)
    utterance_id = brain_client.payloads[0].utterance_id
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)
    lines = _dispatch_command_final(
        console,
        brain_client,
        utterance_id,
        "where_is_it",
        ids[0],
        because="near the village",
    )
    # `where_is_it` has no return-value readback of its own (`body.py`'s
    # `drain_where_is_it` speaks it later) -- `[]` here is the dispatch
    # succeeding, not a degrade (contrast the previous test's single
    # "Which one" line).
    assert lines == []
    assert console.where_is_it_requested is True
    assert console.where_is_it_slots == {"referent": True}


def test_r1_brain_command_signal_survives_an_unrelated_command_same_poll() -> None:
    """R1 regression: `where_is_it`'s one-shot signal, set by a brain
    command dispatch in `drain_brain`, must not be wiped by an unrelated
    command dispatched later in the *same* poll (`_poll_transcripts`,
    which in the real loop runs after `drain_brain`) -- its consumer,
    `body.py`'s `drain_where_is_it`, does not run until the *next*
    poll's own earlier step."""
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    brain_client = _ScriptedBrainClient()
    tool_runner = _ScriptedToolRunner(
        observations={
            "find_contact": ToolObservation(summary="x", handles=(contact_id,))
        }
    )
    console = CrewConsole(store=store, brain_client=brain_client)
    console.run_brain_tool = tool_runner

    utterance_id = _start_turn(console, brain_client)
    brain_client.queue(
        BrainReply(
            utterance_id=utterance_id,
            kind="tool_call",
            t_sim=0.0,
            tool="find_contact",
            args={"text": "t-72"},
        )
    )
    console.drain_brain(now_sim=1.0)
    _dispatch_command_final(
        console, brain_client, utterance_id, "where_is_it", contact_id
    )

    assert console.where_is_it_requested is True
    assert console.where_is_it_slots == {"referent": True}

    # An unrelated command dispatched later in the same poll (standing in
    # for a transcript's own `_poll_transcripts` dispatch) must not wipe
    # the signal before `body.py`'s `drain_where_is_it` ever sees it.
    console.handle_command("report_all", now_sim=1.0)

    assert console.where_is_it_requested is True
    assert console.where_is_it_slots == {"referent": True}


def test_header_refs_offered_without_a_tool_call() -> None:
    """D4's header refs: a contact already in `_referent_memory`'s short
    window (`[[BL-B102]]`'s "recently mentioned") is offered from the
    *first* round, with no tool call needed -- "which one's the BMP?"
    style, D3's ambiguity-evidence rule included (a header-seeded
    candidate set is not pushed, so no `because` is demanded of it,
    `CrewConsole._start_brain_turn`'s own docstring)."""
    store = _store_with_two_far_apart_contacts()
    ids = [contact.id for contact in store.contacts]
    brain_client = _ScriptedBrainClient()
    console = CrewConsole(store=store, brain_client=brain_client)
    console._referent_memory.record(
        [Mention(kind="contact", id=ids[0], t_sim=0.0)], 0.0
    )

    console.handle_line("Petrovich, where is it?", now_sim=0.5)
    assert len(brain_client.payloads) == 1
    payload = brain_client.payloads[0]
    utterance_id = payload.utterance_id

    header = payload.situational_header
    recent = header.get("recent_contacts")
    assert isinstance(recent, list)
    assert [entry["id"] for entry in recent] == [ids[0]]
    # D2's "no raw x/z" -- the header's own recent-contact summaries
    # never carry a raw coordinate, even though the contact has a real
    # position in the store.
    serialised = json.dumps(header)
    assert '"x"' not in serialised
    assert '"z"' not in serialised

    # No tool call needed -- the header already offered it.
    lines = _dispatch_command_final(
        console, brain_client, utterance_id, "where_is_it", ids[0]
    )
    assert lines == []
    assert console.where_is_it_requested is True
