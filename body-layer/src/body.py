"""The crew session's poll loop and CLI entrypoint. Polls ownship telemetry
from the aircraft layer plus whatever `PerceptionSource`s it is given,
feeds every `Observation` into a `belief.contacts.ContactStore`
(`ConsolePerceptionRunner`), and drives `belief.crew_console.CrewConsole` --
the player-facing crew session -- on top of it. `main()` is the one place
that plugs in concrete tiers (`perception.hybrid_source.
HybridPerceptionSource` and `perception.naked_eye_source.
NakedEyePerceptionSource`) and drives the poll loop, kept as thin CLI
wiring, separate from `ConsolePerceptionRunner`'s own tier-agnostic logic.

**Two sources, no `CompositePerceptionSource`** (PB-1.5 plan's Affected
Modules section, a local/reversible decision): `main()` builds a plain
`list[PerceptionSource]`, polled every tick and concatenated before
ingestion -- `PerceptionSource.poll()` already returns `list[Observation]`,
so no new type is needed to combine multiple sources' output. Revisit only
if a third source or real fusion logic (that plan's Decision #3) makes a
composite class earn its keep.

**The belief-consuming poll loop (PB-2 Stage 3, extended by Stage 4)**:
both sources are built at `emit_mode="every_poll"` (Stage 3's fix for the
Interface confirmation section's gap 2: source-level debounce starves the
belief layer of the continuity `belief.decay`'s certainty ladder needs) and
drive `ConsolePerceptionRunner`, which ingests+ticks a `belief.contacts.
ContactStore` each poll, printing a periodic contact/observation-count
line.

`main()` runs `ConsolePerceptionRunner.run_once()` on a background daemon
thread (`_run_crew_text_poll_loop`) while the foreground thread drives
`CrewConsole`'s own REPL against the same `ContactStore` the poll loop is
filling. `ConsolePerceptionRunner.last_t_sim` is the seam between the two:
the poll thread updates it every poll, the REPL thread reads it as
`now_sim` for whatever command the user just typed.

**Thread-affine `sqlite3.Connection` (live acceptance testing finding,
`plans/pb2-contact-memory/implementation.md` "Stage 6 findings"; BL-5 live
acceptance testing finding, `plans/bl5-tool-api/debug.md`)**:
`_run_crew_text_poll_loop` opens its own `world_model_conn` (via
`open_world_model`) and builds its own `sources` (via `_build_sources`) *on
the poll thread itself*, since `sqlite3.Connection`s are thread-affine by
default (`check_same_thread=True`, and `open_world_model` never overrides
that) -- a connection opened on one thread and queried from another raises
`sqlite3.ProgrammingError` on first use. `main()` still constructs
`ConsolePerceptionRunner` up front with an empty `sources` list -- its
`store`/`output`/`last_t_sim` fields are safe to share across threads, only
`sources` (and the connection it holds) needs to move. The same applies to
`ConsolePerceptionRunner.enrichment`, built on the poll thread and holding
*that thread's* `world_model_conn`: the REPL side builds its own REPL-
thread-local `sqlite3.Connection`/`EnrichmentContext` instead of reading
`runner.enrichment` at all.

**`--mission-understanding PATH` (BL-7, `plans/bl7-mission-phase-relevance/
plan.md`)**: optional. When given, `main()` calls `belief.mission_phase.
load_mission_understanding(path)` once at startup (a mission-interpreter
`--emit-compact` JSON artifact -- a plain file read/JSON parse, never a
Python import of mission-interpreter's own code, per root `CLAUDE.md`'s
module-independence rule) and constructs one `belief.mission_phase.
MissionPhaseTracker`, held alongside (not inside) `EnrichmentContext` --
mission phase isn't world-model/ownship-shaped state, it has its own
lifecycle. The *same* tracker instance is threaded into `ConsolePerceptionRunner`
(`.update()`, poll thread) and into `get_situation`'s `mission_phase` fact
(`.current_phase()`, REPL thread) -- the same write-thread/read-thread split
`EnrichmentContext.ownship` already uses, deliberately, to avoid
reproducing this codebase's recurring sqlite thread-affinity defect class
in a new field. Omitted (default `None`): a true no-op, `get_situation`'s
`mission_phase` fact is absent entirely.

**The player-facing crew session (BL-5a,
`plans/bl5a-text-mode-crew-interaction/plan.md`)**: runs `belief.
crew_console.CrewConsole`. After each `runner.run_once()`, it applies
whatever `engage`/`disengage` transition the previous poll's command
dispatch left and calls `crew_console.drain_attack_run(...)`
**immediately before** the next call (`plans/attack-run/plan.md` Stage 5,
Decision 1 -- a guidance line wins the tick by being drained first), then
`crew_console.drain_events(runner.last_t_sim)` so newly ticked lifecycle
events get spoken through `belief.speech.route_event`, then (`plans/
voice-latency-instrumentation/plan.md` Stage 6) `crew_console.
drain_pending_positional_replies(runner.last_t_sim)` so any positional
readback deferred while the channel was modeled busy gets spoken once it
clears, and (`plans/brain-layer/plan.md`) `crew_console.drain_brain(runner.
last_t_sim)` right after it, so whatever the brain has decided since the
last poll gets drained, revalidated against current belief (D4), and
spoken. `--brain-client http|debug|null` selects which `belief.escalation.
BrainClient` handles escalated utterances -- `http` (`plans/brain-layer/
plan.md`, requires `--brain-url`) talks to a real `brain-layer` instance
and speaks its replies; `debug`, the default, prints escalations to stderr
for session visibility; `null` is silent. `debug`/`null` never produce
spoken output.

**Gaze steers the naked-eye channel (slice 2B, `plans/
detection-cones-slice2/plan.md`; the o'clock scan loop added by 2C)**:
`ConsolePerceptionRunner.run_once` resolves whichever ownship-relative
`scan_area` command is currently pending (`_active_gaze`) and assigns the
resulting `perception.gaze.ScanPlan` onto whichever of `self.sources` is a
`NakedEyePerceptionSource` (`_apply_active_gaze`), every poll, before the
sources are polled -- this is what makes a spoken "scan left" command change
what Petrovich can actually see, not just register a belief-level attention
area. No command pending means `perception.gaze.FREE_SCAN_PLAN` (2C's
default o'clock scan loop, not "no restriction" any more) -- see
`perception.gaze`'s own module docstring for the free-scan/commanded-scan
split this now resolves to. `ConsolePerceptionRunner.scan_plan` keeps that
same resolved value visible after `run_once` returns.

**Speech in and out are always on (BL-10 first slice, `plans/
tts-voice-output/plan.md`; Stage 3, `plans/inbound-speech/plan.md`;
unconditional as of `plans/default-crew-pipeline/plan.md`, BL-B96)**:
`main()` builds one `belief.audio_client.AudioAdapterClient` from the now-
required `--audio-adapter-url` and passes it as `CrewConsole.speech_client`,
so every line `CrewConsole` speaks is synthesized and made audible via
`audio-adapter`'s `POST /speak`. The poll loop also polls/dispatches recognised speech
transcripts via the same client's `GET /transcripts/poll`, through
`CrewConsole.handle_transcript`. If `audio-adapter` is unreachable, start-
up and the poll loop continue regardless -- see `ConnectionReporter` and
the "Audio adapter unreachable" note below; Petrovich simply stays silent
until it answers.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Final, Literal, TextIO

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError
from belief.attack_run import AttackRunState
from belief.attention import (
    _SECTOR_CENTER_DEG,
    _SECTOR_HALF_WIDTH_DEG,
    effective_attention,
)
from belief.audio_client import AudioAdapterClient, AudioAdapterError
from belief.brain_client import BrainLayerClient
from belief.contacts import ContactStore
from belief.crew_console import HELP_TEXT as CREW_TEXT_HELP_TEXT
from belief.crew_console import ON_GROUND_AGL_THRESHOLD_M, CrewConsole
from belief.effector_engine import AIRCRAFT as EFFECTOR_AIRCRAFT
from belief.effector_engine import EffectorRunState, EffectorTrigger
from belief.effector_engine import advance as advance_effectors
from belief.effector_engine import fire_trigger as fire_effector_trigger
from belief.effector_registry import (
    DEFAULT_SEQUENCES_DIR,
    EffectorDef,
    PolledSet,
    aircraft_dir_name,
    load_polled_config,
    load_registries_by_aircraft,
)
from belief.effector_sequences import SequenceFile, load_sequences
from belief.enrichment import EnrichmentContext
from belief.escalation import BrainClient, DebugPrintBrainClient, NullBrainClient
from belief.mission_phase import (
    MissionPhaseInfo,
    MissionPhaseTracker,
    MissionUnderstandingData,
    load_mission_understanding,
)
from belief.optic_policy import (
    HANDS_BUSY_DURATION_S,
    SIGHT_SEARCH_FAR_M,
    SIGHT_SEARCH_NEAR_M,
    SIGHT_SEARCH_WIDE_FAR_M,
    SIGHT_SEARCH_WIDE_MID_M,
    SIGHT_STEADY_RATE_LIMIT_DEG_S,
    BoundedSightLook,
    LookTarget,
    OpticDecision,
    OpticPhase,
    OpticState,
    advance_sight_aim,
    is_steady,
    look_target_for,
    lower_binoculars,
    search_pattern,
)
from belief.optic_policy import decide as decide_optic
from belief.sight_effector import (
    REQUIRED_POLLED_ARGS,
    GuidanceUnitState,
    write_sight_target,
)
from belief.sight_effector import refresh_readback as refresh_cockpit_switch_readback
from belief.sight_effector import sight_ready as guidance_unit_sight_ready
from belief.sight_head import SightHead, advance_sight_head, head_body_direction
from belief.tasks import TaskStore
from belief_truth_log import BeliefTruthLogWriter
from connection_reporter import ConnectionReporter
from coordinates.projections import THEATRE_PROJECTIONS
from detection_trace_writer import DetectionTraceWriter
from eyesight_view import DEFAULT_MAX_LINES as EYESIGHT_DEFAULT_MAX_LINES
from eyesight_view import DEFAULT_RADIUS_M as EYESIGHT_DEFAULT_RADIUS_M
from eyesight_view import (
    believed_markers_from_contacts,
    ground_truth_markers_from_trace,
    relative_bearing_deg,
)
from eyesight_view import render_frame as render_eyesight_frame
from group_trace_log import GroupTraceLogWriter
from mission_memory import admission, marks
from mission_memory.admission import FiredOnTracker
from mission_memory.entries import MarkPayload
from mission_memory.log import MissionMemoryLogWriter
from mission_memory.store import MissionMemory
from perception.association import PLAYER_BUBBLE_RADIUS_M, SightCone
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT
from perception.detection_trace import DetectionTrace, DetectionTraceCollector
from perception.forest import ForestOcclusion
from perception.gaze import (
    FREE_SCAN_PLAN,
    SCAN_CYCLE_PERIOD_S,
    SECTOR_WEDGE_DEG,
    SIGHT_AHEAD_LEGS,
    SIGHT_AHEAD_WINDOW_DWELL_S,
    SIGHT_SECTOR_WEDGE_DEG,
    Gaze,
    ScanPlan,
    _gaze_for_clock_hour,
    gaze_at,
    legs_within_wedge,
)
from perception.geometry import (
    GeoPosition,
    alignment_direction,
    heading_relative_to_body_relative,
    open_world_model,
)
from perception.hybrid_source import HybridPerceptionSource
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_field_of_regard,
)
from perception.source import Observation, OwnshipState, PerceptionSource
from pov_view import DEFAULT_MAX_LINES as POV_DEFAULT_MAX_LINES
from pov_view import (
    pov_believed_markers_from_contacts,
    pov_ground_truth_markers_from_trace,
)
from pov_view import render_frame as render_pov_frame
from run_log_paths import per_run_log_path
from sight_trace_writer import SightTraceWriter
from speech_log import SpeechLogWriter
from store.reader import load_only_region
from tuning import render_print_tuning, render_startup_block, validate_against_defaults

logger = logging.getLogger(__name__)

#: Bounded fallback for the mission-start resolving window: how many
#: seconds of **wall clock** (not sim time, not a poll count -- see
#: `ConsolePerceptionRunner.mission_start_resolving_since_wall`'s own
#: docstring for why) `_run_crew_text_poll_loop` may wait for a fresh
#: ownship sample before giving up on `t_sim`-based freshness and firing
#: `MISSION_START` anyway, without `MISSION_START_IN_AIR` (`plans/
#: effector-sequences/review-mission-start.md`'s fix re-review, 2026-10-23:
#: the fallback cannot tell a `t_sim` coincidence apart from no fresh
#: sample at all, and only the former is safe to classify airborne from).
#: Two cases reach this fallback. (1) The pathological coincidence this
#: constant was first written for: the restart happens near `t_sim = 0`
#: **and** the first fresh sample lands on the exact same float as the
#: baseline -- the `!=` check this backs up is sound for the reason stated
#: at its own call site -- the user, confirming the underlying DCS fact:
#: "Mission restart always resets the mission elapsed timer in DCS" -- so
#: this is rare and self-heals on the next restart. (2) The far more
#: ordinary case: no fresh sample has arrived at all within the window --
#: a long mission-load screen, or (common in DCS) a mission that starts
#: paused and the pilot has not yet un-paused. Case (2) does **not**
#: self-heal: firing `MISSION_START_IN_AIR` against `crew_console.
#: on_ground` computed from the stale previous-mission sample would
#: classify this mission from the wrong mission's data, uncorrected for
#: the rest of the sortie -- so the fallback fires `MISSION_START`
#: (a one-shot setup hook that does not depend on air state) but drops the
#: `MISSION_START_IN_AIR` check entirely rather than guess, and ends the
#: takeoff-suppression window the same way normal resolution does, so
#: `on_ground`'s baseline is re-established from the next sample without
#: firing `TAKEOFF` on it. 30 s is long enough that it is never reached by
#: an ordinary restart (which resolves on the very next poll, typically
#: well under a second) and short enough that case (1) still self-heals
#: within the same sortie.
MISSION_START_RESOLVE_FALLBACK_S: Final[float] = tuning.real(
    "body.MISSION_START_RESOLVE_FALLBACK_S",
    30.0,
    lo=5.0,
    hi=120.0,
    status="judgement",
)


@dataclass
class ConsolePerceptionRunner:
    """The crew session's belief-consuming poll loop. `sources` are expected
    to already be constructed at `emit_mode="every_poll"` (`main()`'s job,
    not this class's).

    `run_once` returns the poll's `Observation`s so a REPL/console can drive
    the same loop without re-deriving it.
    """

    aircraft_client: AircraftLayerClient
    #: Defaults to empty -- `main()` constructs this runner on the main
    #: thread before `sources` (and the sqlite connection they hold)
    #: exist, then has the poll thread populate this field with
    #: its own thread-local sources once it starts (see module docstring's
    #: thread-affinity note). Tests that don't care about thread-affinity still pass
    #: `sources` explicitly, same as before.
    sources: list[PerceptionSource] = field(default_factory=list)
    store: ContactStore = field(default_factory=ContactStore)
    #: BL-6's `belief.tasks.TaskStore` (`plans/bl6-commands-inspect-adapt/
    #: plan.md`) -- ticked alongside `store` every poll (see `run_once`),
    #: the same hook point `ContactStore.tick` already runs from. Shared
    #: with whichever `Console`/`CrewConsole` instance `main()` builds on
    #: top of this runner's `store`, since `scan-area`'s handler needs the
    #: same `TaskStore` the poll loop is ticking.
    tasks: TaskStore = field(default_factory=TaskStore)
    output: TextIO | None = None
    last_t_sim: float | None = None
    #: `--group-trace` (`BL-12` Stage 1, amendment A4). `None` (the
    #: default) is a true no-op -- `run_once` passes this straight through
    #: to `ContactStore.tick`'s own `group_trace_sink` keyword, which
    #: already defaults to `None`, so nothing changes for a run that never
    #: sets this field.
    group_trace_sink: Callable[[Mapping[str, object]], None] | None = None
    #: BL-3's world-model connection/theatre (`plans/bl3-world-enrichment/
    #: plan.md` step 6), set once by `_run_crew_text_poll_loop` at the same
    #: point it already builds `sources` -- both need the same thread-local
    #: `sqlite3.Connection` (see the module docstring's thread-affinity
    #: note), so `enrichment` cannot be constructed by `main()` on the main
    #: thread either.
    world_model_conn: sqlite3.Connection | None = None
    theatre: str | None = None
    #: Updated every poll (mirrors `last_t_sim`) -- not otherwise consumed
    #: by this class (`enrichment.ownship` below is the field
    #: `belief.enrichment.relative_geometry` actually reads), kept for
    #: parity with `last_t_sim`'s "latest telemetry snapshot" role and any
    #: future non-enrichment consumer.
    last_ownship_state: OwnshipState | None = None
    #: Built lazily on the first poll that has both real telemetry and a
    #: `world_model_conn`/`theatre` (i.e. always, once `_run_crew_text_poll_
    #: loop` has set those two), then updated in place every poll after --
    #: `EnrichmentContext.ownship` is mutable specifically so the same
    #: `WorldEnrichmentCache` persists across polls (see that dataclass's
    #: own docstring). Poll-thread-local -- `_run_crew_text_repl` never
    #: reads this field (BL-B96 fix: it builds its own REPL-thread-local
    #: connection/cache instead, see that function's own docstring for why).
    enrichment: EnrichmentContext | None = None
    #: BL-7's mission-phase tracker (`plans/bl7-mission-phase-relevance/
    #: plan.md`), built once by `main()` (a plain JSON file load, not a
    #: sqlite connection -- no thread-affinity concern, unlike `sources`/
    #: `world_model_conn`/`enrichment` above) and shared as the *same*
    #: instance across the poll thread and the REPL/crew-text thread.
    #: `run_once` below is the only place that ever calls `.update()` on
    #: it (poll thread, write); `_run_console_repl`/`Console` only ever
    #: call `.current_phase()` on it (REPL thread, read) -- the same
    #: write-thread/read-thread split `last_t_sim`/`last_ownship_state`
    #: already use, chosen deliberately to avoid reproducing the sqlite
    #: thread-affinity defect class this codebase has hit twice (BL-2
    #: Stage 6, BL-5's REPL-thread enrichment fix above). `None` (the
    #: default, when `--mission-understanding` is omitted) is a true
    #: no-op: `run_once` never touches this field, `get_situation` reports
    #: no phase data, unchanged from before this milestone.
    mission_phase_tracker: MissionPhaseTracker | None = None
    #: The `perception.gaze.ScanPlan` this poll resolved (`_active_gaze`) --
    #: `FREE_SCAN_PLAN` until the first poll runs. A read, not new state:
    #: `run_once` already computes this every poll to hand it to
    #: `NakedEyePerceptionSource` (`_apply_active_gaze`); this field just
    #: keeps the same value visible to a poll loop that wants to show the
    #: pilot where Petrovich is currently looking (cones 2C sortie finding
    #: "show where Petrovich is looking") without recomputing it or reaching
    #: into `self.sources` to find the naked-eye one back out.
    scan_plan: ScanPlan = field(default_factory=lambda: FREE_SCAN_PLAN)

    #: The binocular cycle's own state (`plans/binocular-optic/plan.md`
    #: Stage 2), carried across polls because the cycle spans them -- a
    #: glass phase begins at the end of one scan and ends several polls
    #: later. Replaced wholesale each poll rather than mutated, so the
    #: decision stays a pure function and a replay reproduces it exactly.
    optic_state: OpticState = field(default_factory=OpticState)

    #: The attack run's own phase (`plans/attack-run/plan.md` Decision 2,
    #: Stage 5's wiring), carried the same way `optic_state` is -- replaced
    #: wholesale each poll, never mutated. `None` means "not engaged" (no
    #: standing selection, or selected but not yet `engage`d): `drain_
    #: attack_run` is a true no-op whenever this is `None`, and `_active_
    #: gaze` below only claims the gaze while it is not. Set to a fresh
    #: `AttackRunState()` by `_run_crew_text_poll_loop` the poll after
    #: `engage` is dispatched, and back to `None` the poll after
    #: `disengage` -- `CrewConsole` cannot replace this field directly
    #: (it lives on this class, not that one), so it leaves a one-shot
    #: `CrewConsole.attack_run_transition` signal for the poll loop to
    #: apply instead; see that field's own docstring.
    attack_run_state: AttackRunState | None = None

    #: The 9K113 guidance unit's own *observed* state (`BL-B66`, `plans/
    #: 9k113-effectors/plan.md` Stages 2-4), carried the same way
    #: `optic_state`/`attack_run_state` are -- replaced wholesale each
    #: poll via `replace()`, never mutated. `belief.sight_effector` only
    #: carries the readback now; the *sequencing* state that used to live
    #: here too moved to `effector_state` below (`plans/
    #: effector-sequences/plan.md` Stage 2).
    guidance_unit_state: GuidanceUnitState = field(default_factory=GuidanceUnitState)

    #: The effector-sequence engine's own run state (`belief.
    #: effector_engine.EffectorRunState`, `plans/effector-sequences/
    #: plan.md` Stage 2) -- replaces `GuidanceUnitState`'s former
    #: `takeoff_seen`/`power_up_stage`/`next_switch_due_sim`/`observ_
    #: commanded`/`weapon_safety_commanded` fields. Replaced wholesale
    #: each poll via `replace()`, same discipline as every other field
    #: here; **one construction site**, this `field(default_factory=...)`
    #: and mission-reset's re-run `__init__`.
    effector_state: EffectorRunState = field(default_factory=EffectorRunState)

    #: `plans/effector-sequences/plan.md` Stage 4, S4.5 -- the sim time
    #: the continuous feed's `watch_args` install was last (re)sent, or
    #: `None` before the first poll or right after a mission reset. An
    #: **ordinary init field with a default**, not `field(default=...,
    #: init=False)` -- `reset_for_new_mission`'s re-run `__init__` does
    #: not reset the latter kind, so the first post-restart poll must
    #: re-send regardless of the resend timer.
    watch_args_last_sent_sim: float | None = None

    #: One-per-mission latches for the two startup/ops WARNINGs S4.5
    #: describes (feed unavailable; not confirmed after
    #: `WATCH_ARGS_UNCONFIRMED_WARN_S`) -- plain `bool`s, reset by the
    #: same mission-reset re-`__init__` as every other field here.
    watched_args_unavailable_warned: bool = False
    watch_args_unconfirmed_warned: bool = False

    #: Petrovich's **simulated** 9K113 sight head (`[[BL-B80]]` v2,
    #: `plans/9k113-sight-pointing/plan.md`) -- carried the same way
    #: `optic_state`/`guidance_unit_state` are, advanced once per poll by
    #: `advance_sight_head` inside `run_once`. This **is** his sight for
    #: perception; the real DCS sight is a best-effort slave of it.
    sight_head: SightHead = field(default_factory=SightHead)

    #: The `t_sim` of the most recent poll whose *applied* optic was
    #: sight-tier with `sight_head.mode == "free"` -- `None` until the
    #: first such poll. The one freshness stamp `belief.sight_head.
    #: select_sight_goal`'s "seen" row compares a look's own `t_look`
    #: against (plan's "Aim source", Co-moving Fields): a binocular/
    #: unaided look also produces an exact seen direction, and this is
    #: what keeps it from steering the sight. Set at the *end* of
    #: `run_once`, once this poll's percepts have actually been ingested
    #: -- the value `select_sight_goal` reads earlier in the *next* poll
    #: is therefore always one poll old, the same lag `observ_observed`'s
    #: own consumers already accept.
    last_sight_look_sim: float | None = None

    #: Recent `(t_sim, pitch, bank, heading)` samples, oldest first -- the
    #: steadiness gate's only input. Bounded because it is a *rate*
    #: estimate: a longer history would let a manoeuvre a minute ago still
    #: forbid a look, which is the opposite of what the gate is for.
    attitude_history: deque[tuple[float, float, float, float]] = field(
        default_factory=lambda: deque(maxlen=ATTITUDE_HISTORY_LEN)
    )

    #: What this poll resolved to look through, kept visible for the same
    #: reason `scan_plan` is: a poll loop showing the pilot where Petrovich
    #: is looking should be able to say *through what* without recomputing
    #: the decision.
    optic: Optic = UNAIDED_OPTIC

    #: `plans/dcs-driven-los/plan.md` (X-B29) -- the `(hour, fov_half_deg)`
    #: pair last actually pushed via `POST /command/look_direction`, or
    #: `None` before the first poll. "Pushed on change" (plan SS9b) is
    #: enforced here, one source of truth away from the Lua side's own
    #: `lastSentHour`/`lastSentFovHalfDeg` bookkeeping -- this field is
    #: this *process's* last push, the Hook script's is the mission-
    #: scripting state's last applied value; the two can legitimately
    #: differ for one push's worth of network/poll latency (plan SS9c),
    #: which is why the join on the aircraft-layer side is tri-state, not
    #: an assumption that they always agree.
    _last_look_direction: tuple[int, int] | None = field(
        default=None, init=False, repr=False
    )

    #: `BL-15` Stage 1 (`plans/bl15-mission-start/plan.md`) -- the last
    #: `MissionStartEvent.sequence` this runner has seen, or `None` before
    #: the first poll of this process. `_check_for_new_mission` compares
    #: each poll's value against this field to detect a genuine DCS
    #: mission (re)start; `None` means "nothing has been checked yet",
    #: which is deliberately distinct from "sequence 0 was seen" -- the
    #: very first poll of a process must never reset (the process just
    #: started with clean state), even if the collector already holds a
    #: mission-start event from before body-layer connected. **Not** in
    #: `reset_for_new_mission`'s preserved-field list below (it resets to
    #: `None` along with every other per-mission field) -- `_check_for_new_
    #: mission` re-assigns it explicitly, after `_reset_mission_state`
    #: returns, to the sequence just processed, so a reset never leaves
    #: this field looking like "never checked" for the poll that follows.
    last_mission_start_sequence: int | None = None

    #: Set together by `_check_for_new_mission` right after a genuine
    #: reset (`plans/effector-sequences/explore-notes.md`, "Two new
    #: triggers: mission start") -- `True` means `EffectorTrigger.
    #: MISSION_START` has not fired yet for *this* mission (re)start.
    #: Resets to its declared default (`False`) on the next mission
    #: reset's re-run `__init__`, same as every other per-mission field --
    #: a still-pending flag from a restart that is itself being
    #: superseded by another restart is replaced by this reset's own
    #: fresh `True`, assigned explicitly afterward, the same pattern
    #: `last_mission_start_sequence` already uses.
    pending_mission_start_fire: bool = False

    #: Companion to `pending_mission_start_fire`: `True` means the
    #: airborne-or-not decision for `EffectorTrigger.MISSION_START_IN_AIR`
    #: (and whether `TAKEOFF` may fire at all) has not yet been made for
    #: this mission (re)start -- `_run_crew_text_poll_loop`'s poll block
    #: holds off firing *either* new trigger, and suppresses `TAKEOFF`
    #: entirely, for as long as this is `True`. Cleared one of two ways:
    #: the poll a fresh (non-stale) ownship sample is found -- also the
    #: poll `crew_console.on_ground`'s baseline is first established
    #: without a `TAKEOFF` edge -- or, if no fresh sample has arrived at
    #: all, the poll `MISSION_START_RESOLVE_FALLBACK_S` elapses, in which
    #: case the in-air classification is dropped rather than guessed (see
    #: that poll block's own comment, and `MISSION_START_RESOLVE_FALLBACK_S`'s
    #: declaration, for why the two cases cannot be told apart from body-layer's
    #: own telemetry).
    pending_mission_start_in_air_check: bool = False

    #: The `last_t_sim` this runner held *immediately before* the reset
    #: that just set the two flags above -- `None` if no ownship sample
    #: had ever been read this process. `_run_crew_text_poll_loop` treats
    #: the first post-reset ownship sample whose own `t_sim` differs from
    #: this value as the first genuinely fresh one (mission-start
    #: detection can arrive a poll or more before `Export.lua` resumes
    #: sending, during which `GET /telemetry/latest` keeps serving the
    #: previous mission's last cached sample, bit-identical `t_sim` and
    #: all, every poll until a real one lands) -- see that poll block's
    #: own comment for why `!=` rather than `<` against this baseline.
    mission_start_fresh_sample_baseline_t_sim: float | None = None

    #: `time.monotonic()` at the poll `_check_for_new_mission` armed the
    #: two pending flags above -- `MISSION_START_RESOLVE_FALLBACK_S`'s own
    #: bounded-fallback clock (`plans/effector-sequences/
    #: review-mission-start.md`'s optional refinement). `None` whenever
    #: neither pending flag is set (the normal state outside a mission-
    #: start resolving window). Deliberately **wall-clock, not a poll
    #: count**: a poll-count bound would be relative to whatever
    #: `--poll-interval-s` happens to be (1.0 s default, but tests run it
    #: far faster to stay quick), so a count large enough to never
    #: mis-fire during this codebase's own fast-interval stale-cache
    #: tests (`test_stale_telemetry_at_mission_restart_does_not_decide_
    #: airborne` deliberately holds the resolving window open across
    #: several dozen such polls) would be too large to self-heal promptly
    #: at the real 1.0 s interval, and a count small enough to self-heal
    #: promptly there would misfire during those tests' fast polling.
    #: Wall-clock time has neither problem.
    mission_start_resolving_since_wall: float | None = None

    def reset_for_new_mission(self) -> None:
        """Give a clean slate on a genuine DCS mission (re)start (`BL-15`
        Stage 1). Re-invokes `__init__` on this same object, passing
        through only the handful of fields that must survive the reset --
        open network/sqlite handles and the shared `store`/`tasks`
        references (see `plans/bl15-mission-start/plan.md`'s "reset
        mechanism" section for why `store`/`tasks` are passed through
        **unchanged as objects** rather than cleared here: their own
        `reset_for_new_mission()` must already have run before this call,
        via `_reset_mission_state`'s explicit ordering). Everything else
        (`last_t_sim`, `last_ownship_state`, `enrichment`, `mission_phase_
        tracker`, `scan_plan`, `optic_state`, `attack_run_state`,
        `guidance_unit_state`, `effector_state`, `watch_args_last_sent_sim`,
        `watched_args_unavailable_warned`, `watch_args_unconfirmed_warned`,
        `sight_head`, `last_sight_look_sim`, `attitude_history`, `optic`,
        `_last_look_direction`, `last_mission_start_sequence`,
        `pending_mission_start_fire`, `pending_mission_start_in_air_check`,
        `mission_start_fresh_sample_baseline_t_sim`,
        `mission_start_resolving_since_wall`) resets to its
        declared default (D11: a mission (re)start drops every
        running/pending effector-sequence run with nothing carried over;
        the three mission-start-trigger fields reset to `False`/`False`/
        `None` here too -- `_check_for_new_mission` re-assigns them
        explicitly afterward, same pattern as `last_mission_start_
        sequence`).

        **`_last_look_direction` needs an explicit line, not just the
        re-invoked `__init__`.** It is declared `field(default=None,
        init=False, repr=False)` -- a plain `default`, not a
        `default_factory` -- and dataclasses only emits a `self.attr = ...`
        assignment inside the generated `__init__` for an `init=False`
        field when that field has a `default_factory`; a plain `default`
        on an `init=False` field is a class-level attribute, never
        reassigned per instance. Confirmed by running it: `self.__init__()`
        alone left a hand-poisoned `_last_look_direction` untouched, the
        exact silent-survivor class this method exists to prevent. Every
        other non-preserved field above is either an ordinary `init=True`
        field (reassigned as a constructor parameter) or a `default_factory`
        field (reassigned via a fresh factory call either way), so this is
        the one field this pattern does not cover for this class."""
        self.__init__(  # type: ignore[misc]
            aircraft_client=self.aircraft_client,
            sources=self.sources,
            store=self.store,
            tasks=self.tasks,
            output=self.output,
            group_trace_sink=self.group_trace_sink,
            world_model_conn=self.world_model_conn,
            theatre=self.theatre,
        )
        self._last_look_direction = None

    def run_once(self) -> list[Observation]:
        """Poll ownship telemetry once, poll every source for observations
        as of that telemetry's `t_sim`, ingest+tick them into `store`, and
        print one minimal contact/observation-count line. Returns an empty
        list (prints nothing) if the aircraft layer has no telemetry yet.

        `last_t_sim` is updated on every successful poll (Stage 4) -- the
        REPL loop in `main()` reads it as the `now_sim` for whatever command
        the operator just typed, since the REPL has no telemetry feed of
        its own.

        `self.tasks.tick(self.store, ...)` (BL-6) runs immediately after
        `self.store.tick(...)`, the same poll-loop hook point -- a
        `scan_area` task's success check reads `self.store`'s freshly
        ticked contacts, so it must run after that tick, not before or
        independently scheduled."""
        telemetry = self.aircraft_client.get_telemetry_latest()
        if telemetry is None:
            return []
        ownship = OwnshipState.from_telemetry_dict(telemetry)
        self.last_ownship_state = ownship
        # Ownship-anchored attention areas track the nose, and they must be
        # re-projected *before* this tick's `ingest`/`tick` so the contacts
        # ingested below are judged against this tick's heading rather than
        # the previous one (`plans/f10-command-vocabulary/plan.md` D2). A
        # no-op (returns 0, touches nothing) when no relative area is
        # registered, which is the usual case.
        self.store.reproject_relative_areas(
            GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
            ownship.heading_true_deg,
        )
        if self.mission_phase_tracker is not None:
            self.mission_phase_tracker.update(
                GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
            )
        if self.world_model_conn is not None and self.theatre is not None:
            if self.enrichment is None:
                self.enrichment = EnrichmentContext(
                    conn=self.world_model_conn, theatre=self.theatre, ownship=ownship
                )
            else:
                self.enrichment.ownship = ownship
        # 2B: resolve whatever scan sector is currently commanded and hand
        # the naked-eye source a frozen Gaze before it polls (`_active_
        # gaze`'s own docstring) -- a no-op for every other source, and
        # when no scan command is pending.
        self.attitude_history.append(
            (
                ownship.t_sim,
                ownship.pitch_deg,
                ownship.bank_deg,
                ownship.heading_true_deg,
            )
        )
        self.scan_plan = _active_gaze(
            self.tasks,
            ownship.heading_true_deg,
            store=self.store,
            ownship=ownship,
            attack_run_engaged=self.attack_run_state is not None,
        )
        # `plans/dcs-driven-los/plan.md` (X-B29): push the look-direction
        # command only on change (SS9b), from the same `scan_plan` that is
        # about to be handed to `NakedEyePerceptionSource` -- one source of
        # truth for gaze (`perception.gaze.gaze_at`), the Lua side never
        # re-derives it. A push failure degrades to "the Hook script keeps
        # querying whatever wedge it last had" (or its own default), never
        # stops the poll loop.
        gaze_for_look_direction = gaze_at(ownship.t_sim, self.scan_plan)
        look_direction = (
            _hour_for_gaze(gaze_for_look_direction),
            LOOK_DIRECTION_FOV_HALF_DEG,
        )
        if look_direction != self._last_look_direction:
            try:
                self.aircraft_client.post_look_direction(*look_direction)
                self._last_look_direction = look_direction
            except AircraftLayerError:
                logger.warning("look-direction push failed (continuing)", exc_info=True)
        # `[[BL-B80]]` closes the carried-forward `BL-B66` gap: `home_
        # phase` now follows the *observed* arg-886 edge rather than only
        # the pilot's own "Observ on"/"off" command -- `crew_console.
        # observ_transition`'s own drain block (`_run_crew_text_poll_
        # loop`) still drives the cockpit write and the hands-busy
        # suppression, which are about the pilot's hand moving to the
        # switch, not the observed edge. `self.guidance_unit_state.
        # observ_observed` here is the *previous* poll's readback
        # (`refresh_cockpit_switch_readback` runs after `run_once` in the
        # poll loop) -- the same one-poll lag `guidance_request` above
        # already accepts. `None` (no readback yet, or an `Export.lua`
        # predating this field) leaves `home_phase` untouched rather than
        # forcing a phase from an unknown state.
        observ_observed = self.guidance_unit_state.observ_observed
        if (
            observ_observed is True
            and self.optic_state.home_phase is not OpticPhase.SIGHTING
        ):
            self.optic_state = replace(self.optic_state, home_phase=OpticPhase.SIGHTING)
        elif (
            observ_observed is False
            and self.optic_state.home_phase is not OpticPhase.SCANNING
        ):
            # `[[BL-B98]]`, user direction 2026-10-25: OBSERV on->off,
            # whatever the cause, resets the *believed* sight aim to
            # boresight -- this is the one place that transition is
            # detected from the observed switch state (pilot command, DCS
            # AI, or a readback that simply changed), rather than only
            # `_force_observ_off`'s own manoeuvre-triggered path inside
            # `decide_optic` (which already nulls both fields via `_back_
            # to_home`'s non-SIGHTING branch). Without this, OBSERV
            # turning off while mid-glance-away (`phase is SCANNING`,
            # `home_phase` was `SIGHTING`) would leave the pre-glance aim
            # on `self.optic_state` untouched -- `decide_optic` never
            # revisits a `SCANNING` phase that is already `SCANNING` here
            # to null it -- and a later OBSERV-on would resume there
            # instead of boresight.
            self.optic_state = replace(
                self.optic_state,
                home_phase=OpticPhase.SCANNING,
                look_azimuth_deg=None,
                look_elevation_deg=None,
            )
        self.optic_state, optic_decision = decide_optic(
            self.optic_state,
            now_sim=ownship.t_sim,
            scan_cycle_period_s=SCAN_CYCLE_PERIOD_S,
            targets=_look_targets(self.store, ownship),
            steady=is_steady(list(self.attitude_history)),
            search=_search_sweep(self.scan_plan, ownship),
            # `BL-B64` Stage 2, direction §8 -- the sight's own, higher
            # manoeuvre-tolerance threshold, read from the same attitude
            # history the binocular gate above already samples. A second
            # call, not a shared one: `is_steady` is a pure function of
            # its own `rate_limit_deg_s`, and the two thresholds answer
            # different questions (hands vs. gyros) over the same data.
            sight_steady=is_steady(
                list(self.attitude_history),
                rate_limit_deg_s=SIGHT_STEADY_RATE_LIMIT_DEG_S,
            ),
            # `plans/9k113-scan-procedure/plan.md` Stage 1 -- the sight's
            # own active search cycle, computed fresh every poll the same
            # way `search` above already is: a wide S-scan near-to-mid
            # (close threats/targets), then wide far (points of interest),
            # then a narrow far sweep for detection, then -- once per lap,
            # from the glance-away's own resume point rather than as a
            # fourth leg here -- a binocular excursion for whatever a
            # commanded sector left outside the sight's own field of
            # regard.
            sight_wide_near_search=_sight_in_regard_sweep(
                self.scan_plan,
                ownship,
                optic=SIGHT_WIDE_OPTIC,
                near_m=SIGHT_SEARCH_NEAR_M,
                far_m=SIGHT_SEARCH_WIDE_MID_M,
            ),
            sight_wide_far_search=_sight_in_regard_sweep(
                self.scan_plan,
                ownship,
                optic=SIGHT_WIDE_OPTIC,
                near_m=SIGHT_SEARCH_WIDE_MID_M,
                far_m=SIGHT_SEARCH_WIDE_FAR_M,
            ),
            sight_narrow_far_sweep_search=_sight_in_regard_sweep(
                self.scan_plan,
                ownship,
                optic=SIGHT_NARROW_OPTIC,
                near_m=SIGHT_SEARCH_WIDE_FAR_M,
                far_m=SIGHT_SEARCH_FAR_M,
            ),
            sight_out_of_regard_search=_sight_out_of_regard_sweep(
                self.scan_plan, ownship
            ),
            # `plans/9k113-scan-procedure/plan-stage2.md` -- a bounded
            # `look <o'clock>`/`look <compass>`'s own search steps,
            # computed fresh every poll from `self.optic_state.
            # bounded_look` (the *previous* poll's own decision, the same
            # one-poll-behind convention every other `sight_*_search`
            # argument here already follows), empty when none is active.
            sight_point_search=_sight_point_sweep(
                self.optic_state.bounded_look, ownship
            ),
            # `BL-B71`: the attack run's own standing ladder request, from
            # the *previous* poll -- `drain_attack_run` (which recomputes
            # `AttackRunState.requested_optic` for *this* poll) runs later
            # in `_run_crew_text_poll_loop`, after `run_once` (and this
            # call) has already returned, the same one-poll lag `attack_
            # run_transition`/`observ_transition` already accept elsewhere
            # in this file. `None` whenever no run is engaged -- a true
            # no-op, same posture as every other optional `decide_optic`
            # keyword.
            guidance_request=(
                self.attack_run_state.requested_optic
                if self.attack_run_state is not None
                else None
            ),
        )
        # `[[BL-B80]]` v2: Petrovich must not perceive through the sight
        # while the simulated head is not `free` yet -- capped to
        # `BINOCULAR_OPTIC` immediately after `decide_optic` returns,
        # before anything downstream reads `optic_decision.optic`, the
        # same cap value `_apply_guidance` already uses for "home_phase
        # is not SIGHTING". `align_observed`/`observ_observed` are the
        # *previous* poll's readback (`refresh_cockpit_switch_readback`
        # runs after `run_once` in the poll loop), the same one-poll lag
        # `home_phase`'s own derivation above already accepts -- the head
        # advanced a few lines below will reach the identical mode from
        # the identical inputs, so this prediction and that advance never
        # disagree. Re-derived fresh every poll (never cached), so the
        # moment the head reaches `free` the very next poll's check
        # simply passes.
        align_observed = self.guidance_unit_state.align_observed is True
        head_will_be_free = observ_observed is True and align_observed
        if (
            optic_decision.optic
            in (
                SIGHT_WIDE_OPTIC,
                SIGHT_NARROW_OPTIC,
            )
            and not head_will_be_free
        ):
            optic_decision = replace(optic_decision, optic=BINOCULAR_OPTIC)
        self.optic = optic_decision.optic
        is_sight_tier = optic_decision.optic in (SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC)
        # `plans/9k113-sight/plan.md` §15a: `last_t_sim` still holds the
        # *previous* poll's own `t_sim` here (it is updated later in this
        # method), so this is an ordinary poll-to-poll delta, 0.0 on the
        # first poll.
        dt_s = ownship.t_sim - (
            self.last_t_sim if self.last_t_sim is not None else ownship.t_sim
        )
        # `[[BL-B80]]` v2: the look target `decide_optic` just chose for
        # *this* poll (`None` while idle/searching, via `OpticState.
        # look_contact_id`) -- resolved before this poll's own `ingest`
        # below, so its `last_percept` still reflects the *previous*
        # poll's observation (this poll's own look, if any, has not
        # happened yet).
        look_contact = next(
            (
                contact
                for contact in self.store.contacts
                if contact.id == self.optic_state.look_contact_id
            ),
            None,
        )
        self.sight_head = advance_sight_head(
            self.sight_head,
            ownship=ownship,
            dt_s=dt_s,
            align_observed=align_observed,
            observ_observed=observ_observed is True,
            look_contact=look_contact,
            desired_body_az_deg=(
                optic_decision.look_azimuth_deg if is_sight_tier else None
            ),
            desired_body_el_deg=(
                optic_decision.look_elevation_deg if is_sight_tier else None
            ),
            last_sight_look_sim=self.last_sight_look_sim,
        )
        sight_head_body_direction = head_body_direction(self.sight_head, ownship)
        updated_optic_state = _apply_active_gaze(
            self.sources,
            self.tasks,
            scan_plan=self.scan_plan,
            decision=optic_decision,
            optic_state=self.optic_state,
            dt_s=dt_s,
            # `[[BL-B80]]` v2: the sight tier's actual aim is the
            # simulated head's own body direction, never a cockpit
            # readback -- `None` while the head is not `free`, or for a
            # non-sight-tier optic (`head_body_direction` already returns
            # `None` in the first case; the second is excluded here so a
            # `free` head does not leak into a binocular/unaided poll's
            # own pass-through branch).
            sight_head_body_az_deg=(
                sight_head_body_direction[0]
                if is_sight_tier and sight_head_body_direction is not None
                else None
            ),
            sight_head_body_el_deg=(
                sight_head_body_direction[1]
                if is_sight_tier and sight_head_body_direction is not None
                else None
            ),
        )
        if updated_optic_state is not None:
            self.optic_state = updated_optic_state
        # `[[BL-B82]]`: Petrovich does not scan while on the ground --
        # every time, not only before the first takeoff, replacing the
        # old `CrewConsole.maybe_apply_on_ground_default` one-shot silence
        # default. No source is polled at all this tick; `self.store.tick`
        # (below) still runs unconditionally, so existing belief keeps
        # decaying/aging normally -- he just stops adding anything new to
        # it, he does not forget what he already believed.
        observations = (
            [
                observation
                for source in self.sources
                for observation in source.poll(ownship.t_sim, ownship)
            ]
            if ownship.alt_agl_m > ON_GROUND_AGL_THRESHOLD_M
            else []
        )
        self.store.ingest(observations, now_sim=ownship.t_sim)
        # `[[BL-B80]]` v2: stamp the "most recent sight-tier, head-free
        # poll" marker *after* this poll's own percepts have landed, so
        # the *next* poll's `select_sight_goal` reads a fully-settled
        # value -- never this poll's own. `is_sight_tier`/`self.sight_
        # head` were both finalised earlier this same `run_once` call.
        if is_sight_tier and self.sight_head.mode == "free":
            self.last_sight_look_sim = ownship.t_sim
        # `plans/watch-reporting/plan.md` Stage 2 -- `ownship` is already in
        # hand at this call site; `ContactStore.tick`'s sixth block (range
        # crossings) is a no-op without it. The seventh block (engagement)
        # no longer takes a `los_clear` callable at all as of `plans/
        # dcs-driven-los/plan.md` (X-B29): it reads `Contact.live_los_clear`,
        # a value carried on the contact itself (set from `Percept` in
        # `record()`/`from_percept()`), never a live callback into
        # world-model.
        self.store.tick(
            ownship.t_sim, ownship=ownship, group_trace_sink=self.group_trace_sink
        )
        self.tasks.tick(self.store, ownship.t_sim)
        self.last_t_sim = ownship.t_sim
        if self.output is not None:
            print(
                f"t_sim={ownship.t_sim:.2f} "
                f"contacts={len(self.store.contacts)} "
                f"observations={len(self.store.observations)}",
                file=self.output,
            )
        return observations


def _active_gaze(
    tasks: TaskStore,
    heading_true_deg: float = 0.0,
    *,
    store: ContactStore | None = None,
    ownship: OwnshipState | None = None,
    attack_run_engaged: bool = False,
) -> ScanPlan:
    """The `ScanPlan` implied by whatever scan is currently commanded
    (`plans/detection-cones-slice2/plan.md`'s 2B, closing `todo/todo.md`'s
    "Scan commands should drive naked-eye perception"; generalised from a
    static `Gaze` to a `ScanPlan` by 2C, and generalised again by Stage 5
    of `plans/voice-command-completeness/plan.md` to cover every directional
    field `AttentionArea` can carry, not only `relative_sector`) -- or
    `FREE_SCAN_PLAN` (the o'clock scan loop, `perception.gaze`'s own module
    docstring) when no such command is pending.

    Reads `PendingIntent.area.relative_sector`/`relative_clock_hour`/
    `sector`/`created_sim` directly, never the store's live re-projected
    `AttentionArea` (`ContactStore.reproject_relative_areas`) -- a relative
    sector's or o'clock hour's *direction* is body-relative and invariant
    under reprojection; only its absolute world-bearing projection changes
    with ownship heading, which this function resolves itself via
    `heading_true_deg` rather than reading off a stale live projection.
    This also sidesteps `belief.tasks`'s own documented staleness caveat
    around `task.area` (its module docstring) entirely, since nothing here
    needs the live area at all. `task.created_sim` becomes `ScanPlan.
    command_t_sim` -- the sim time the scan was ordered, which is what a
    commanded scan's o'clock legs cycle from (`perception.gaze.gaze_at`'s
    own docstring).

    **Stage 5's fix, in one sentence: a compass-absolute `AttentionArea.
    sector` (`scan north`/`scan bearing 320`) now also resolves here**,
    converted to `ScanPlan.commanded_legs` via `perception.gaze.
    legs_within_wedge` using *this poll's* `heading_true_deg` -- before
    this stage, a `sector`-only task (no `relative_sector`) was silently
    skipped by this function's own filter and fell through to
    `FREE_SCAN_PLAN`, which is the measured defect this plan's Decision 5
    names: "scan north" registered an attention area and spoke a readback
    while Petrovich kept free-scanning. Because `_active_gaze` runs every
    poll (`run_once`), the conversion is naturally recomputed each tick as
    heading changes -- `gaze_at` itself stays a pure function of `t_sim`
    alone (`perception.gaze`'s own hard part 1), the legs it cycles are
    just refreshed by the caller before each poll. A single o'clock hour
    (`AttentionArea.relative_clock_hour`, Stage 5's new field for
    `scan_clock_1`..`scan_clock_12`) resolves to a one-leg `commanded_legs`
    tuple the same way `ahead` already degenerates to a static gaze
    (`perception.gaze.ScanPlan`'s own docstring).

    The most recently created still-active `scan_area` task wins when more
    than one is active -- a later scan command is what a player issuing
    "scan left" then "scan right" would expect to take effect. A task
    carrying no directional field at all (`sector`, `relative_sector`, and
    `relative_clock_hour` all `None`) is skipped, same as before Stage 5 --
    it has nothing for this function to steer by.

    **Unaffected by `watch_contact` tasks** (`plans/watch-as-standing-mode/
    plan.md`) -- the `kind == "scan_area"` check above already excludes
    them, and a `watch_contact` task's `area` is `None` regardless (`belief.
    tasks.PendingIntent`'s own docstring), so gaze and watch can be
    commanded independently and coexist without this function needing to
    know a second kind exists.

    **Cones 2C sortie fix: honours any status except `"cancelled"`, not
    only `"pending"`.** `belief.tasks.TaskStore.tick` flips a `scan_area`
    task to `"succeeded"` the instant any contact is seen inside its area
    -- with the old `status == "pending"` check here, that meant a
    commanded scan silently reverted to free scan on first contact, which
    is what produced the sortie's "commanded scan left, still got reports
    from 12 o'clock" finding (free scan revisits 12 o'clock twice per
    cycle). A `scan_area` task is a standing *mode* (`belief.tasks.
    TaskStatus`'s own docstring, `docs/concept/STATE_TRANSITIONS.md`'s
    "Modes" section): finding something, or timing out
    (`DEFAULT_SCAN_DEADLINE_S`), is an event about what the search has
    (not) confirmed, never the end of the mode. Only an explicit cancel
    (`TaskStore.cancel`, also fixed by this same sortie finding to actually
    reach a resolved task) or a newer scan command (via this function's own
    "most recent" tie-break) ends it.

    **The attack run claims the gaze, checked before the `scan_area` loop
    below** (Decision 9 REVISED, `plans/attack-run/plan.md` -- *"an attack
    run fixes the look on the target. The cost is accepted: no scanning
    elsewhere for the run's duration."*). `attack_run_engaged` is `True`
    only while `ConsolePerceptionRunner.attack_run_state` is non-`None`,
    i.e. the run has been `engage`d, not merely selected -- the gaze claim
    tracks the run's *phase*, the same distinction `drain_attack_run`
    makes. This is what closes the `scan left` + `engage` case: `
    _SECTOR_LEGS["left"]` has no 12, so without this branch the target
    ahead would never be looked at and guidance would run silently against
    an ageing belief. `store`/`ownship` are optional only so every existing
    call site that has no attack run active keeps working unchanged
    (`attack_run_engaged` defaults `False`); `run_once` always supplies
    both. A one-leg `fixed_look` at the target's own *believed* bearing/
    elevation (`perception.geometry.alignment_direction`, bank removed,
    same frame Decision 3 uses) rather than a clock-hour `commanded_legs`
    -- continuous precision keeps the look cone tight on the target, which
    is what keeps the relative-direction channel (Decision 16) populated
    reliably poll after poll, rather than discretising to a 30-degree
    bucket that might drift the target out of frame near a bucket edge."""
    if attack_run_engaged and store is not None and ownship is not None:
        target_task = next(
            (
                task
                for task in reversed(tasks.tasks)
                if task.kind == "attack_target" and task.status != "cancelled"
            ),
            None,
        )
        if target_task is not None and target_task.contact_id is not None:
            contact = store.contact(target_task.contact_id)
            if contact is not None:
                direction = alignment_direction(
                    GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
                    contact.last_position,
                    heading_true_deg=heading_true_deg,
                    pitch_deg=ownship.pitch_deg,
                )
                return ScanPlan.fixed_look_at(
                    azimuth_deg=direction.azimuth_deg,
                    elevation_deg=direction.elevation_deg,
                )
    for task in reversed(tasks.tasks):
        if task.kind != "scan_area" or task.status == "cancelled" or task.area is None:
            continue
        area = task.area
        if area.relative_sector is not None:
            return ScanPlan(
                commanded_sector=area.relative_sector,
                command_t_sim=task.created_sim,
            )
        if area.relative_clock_hour is not None:
            return ScanPlan(
                commanded_sector=None,
                commanded_legs=(area.relative_clock_hour,),
                command_t_sim=task.created_sim,
            )
        if area.sector is not None:
            absolute_center = _SECTOR_CENTER_DEG[area.sector]
            relative_center = (
                absolute_center - heading_true_deg + 180.0
            ) % 360.0 - 180.0
            legs = legs_within_wedge(relative_center, _SECTOR_HALF_WIDTH_DEG)
            return ScanPlan(
                commanded_sector=None,
                commanded_legs=legs,
                command_t_sim=task.created_sim,
            )
    return FREE_SCAN_PLAN


def _look_targets(store: ContactStore, ownship: OwnshipState) -> list[LookTarget]:
    """Every live contact, as the binocular policy needs to see it.

    `watched` comes from `belief.attention.effective_attention` -- the same
    derived level the watched-only callouts and the eyesight view's orange
    read, so "why is he glassing that one" and "why is that one reporting
    to me" have the same answer. It orders which look happens first
    (`optic_policy.choose_look`); it never decides whether an unwatched
    contact gets identified at all.

    **Uses the contact's *believed* type, not ground truth** -- which for a
    presence-level contact is no type at all, and `object_model.profile_for`
    degrades to its default profile there. That is the honest model rather
    than a shortcoming: deciding whether a mark is worth a closer look is a
    judgement made from the mark, and a Petrovich who sized the window by
    what the thing really is would be deciding with knowledge he does not
    have.
    """
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    return [
        look_target_for(
            contact.id,
            observer=observer,
            target_position=contact.last_position,
            heading_true_deg=ownship.heading_true_deg,
            pitch_deg=ownship.pitch_deg,
            bank_deg=ownship.bank_deg,
            object_type=contact.last_class_raw,
            current_level=contact.classification.level.name.lower(),
            position=contact.position,
            watched=effective_attention(
                contact.attention, contact.last_position, store.areas
            )[0]
            in ("watch", "priority"),
        )
        for contact in store.contacts
    ]


#: The band a binocular search sweeps: from where the naked eye runs out
#: to where the binoculars do, for a mid-sized vehicle. Sweeping nearer
#: re-covers ground the scan phase alternating with this one has already
#: covered; sweeping further covers ground the instrument cannot resolve
#: anyway. Stated as a constant rather than computed per contact because a
#: search has no contact yet -- that is what it is looking for.
_SEARCH_BAND_M: tuple[float, float] = (2_333.0, 5_647.0)


def _to_body_relative_steps(
    steps: Sequence[tuple[float, float]], ownship: OwnshipState
) -> list[tuple[float, float]]:
    """Rotate `search_pattern`'s ground-anchored (heading-relative azimuth,
    horizon-relative depression) steps into true body-relative directions,
    using the current pitch and bank -- F5 (`docs/acceptance/
    2026-10-20-sortie-feedback.md`): the 9K113's mechanical limits rotate
    with the airframe, not with the ground, so a step generated from
    altitude/range alone must be rotated into the airframe frame before it
    is tested against `within_field_of_regard` or used as a look aim.
    Shared by every sweep generator below (`_search_sweep`/`_sight_in_
    regard_sweep`/`_sight_out_of_regard_sweep`) so the one conversion lives
    in one place."""
    body_steps: list[tuple[float, float]] = []
    for azimuth_deg, elevation_deg in steps:
        direction = heading_relative_to_body_relative(
            azimuth_deg,
            elevation_deg,
            heading_true_deg=ownship.heading_true_deg,
            pitch_deg=ownship.pitch_deg,
            bank_deg=ownship.bank_deg,
        )
        body_steps.append((direction.azimuth_deg, direction.elevation_deg))
    return body_steps


def _search_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> list[tuple[float, float]]:
    """The binocular sweep for the currently-commanded sector, or empty.

    **Empty for a free scan, deliberately** (`plans/binocular-optic/
    plan.md` D6): searching is something the player asks for by naming a
    place to look. A free scan is Petrovich deciding where to look for
    himself, and turning that into a binocular sweep would spend most of
    every minute glassed for no one's reason.

    The band swept starts where the naked eye runs out and ends where the
    binoculars do -- sweeping nearer than that re-covers ground the scan
    phase alternating with this one has already covered.

    **Still gated on `commanded_sector` alone, not `commanded_legs`**
    (Stage 5, `plans/voice-command-completeness/plan.md`): a bare o'clock
    hour or a converted compass-sector scan gets no binocular search band.
    `SECTOR_WEDGE_DEG` has no entry for either -- there is no named sector
    to look up a half-width for -- and Stage 5's own scope is gaze, not
    binocular search; extending this to the new commanded-legs cases is
    left for a later stage if wanted.

    **Swept around the commanded sector's own centre, not dead ahead**
    (`plans/9k113-narrow-search/plan.md` amendment 2 -- user: *"fix the
    binocular search sector"*). Before this fix, `search_pattern` had no
    centre parameter at all and this function discarded the centre it
    unpacked from `SECTOR_WEDGE_DEG`, so a commanded `left`/`right`/`full`
    scan swept around 0 deg (dead ahead) regardless of which sector was
    actually commanded -- harmless only for `ahead`, whose own centre
    happens to be 0.

    **Rotated into body-relative before being returned** (F5): `search_
    pattern`'s own steps are heading/horizon-relative (level-flight
    geometry), but a binocular aim is a body-relative direction like any
    other (`perception.gaze.Gaze.center_azimuth_deg`'s own convention), so
    pitch and bank have to be applied before this leaves the function --
    `_to_body_relative_steps`'s own docstring has the conversion."""
    if scan_plan.commanded_sector is None:
        return []
    center_deg, half_width_deg = SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    near_m, far_m = _SEARCH_BAND_M
    fov_full_width_deg = (BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    steps = search_pattern(
        center_azimuth_deg=center_deg,
        sector_half_width_deg=half_width_deg,
        near_m=near_m,
        far_m=far_m,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
    )
    return _to_body_relative_steps(steps, ownship)


def _split_sector_by_regard(
    center_deg: float, half_width_deg: float, regard_half_deg: float
) -> tuple[tuple[float, float] | None, list[tuple[float, float]]]:
    """Splits a sector's full span into its in-regard sub-span (a single
    `(center, half_width)`, or `None` if the span and the regard do not
    overlap at all -- never actually reached by any of the four named
    `RelativeSector` values, every one of which straddles or contains
    azimuth 0) and zero, one, or two out-of-regard sub-spans (two only
    for `full`, whose span strictly contains the whole regard band) --
    `plans/9k113-narrow-search/plan.md` Stage 2. Pure geometry, no
    DCS/ownship dependency.

    Worked against `SECTOR_WEDGE_DEG` and `regard_half_deg=60.0`: `ahead`
    (0,30) -> in-span (0,30), no out-spans (fully inside). `left` (-60,30)
    -> in-span (-45,15), one out-span (-75,15). `right` (60,30) -> in-span
    (45,15), one out-span (75,15). `full` (0,90) -> in-span (0,60), two
    out-spans, (-75,15) and (75,15).

    **Each out-span is clamped to the original span's own far edge**
    (`min(span_high, -regard_half_deg)` / `max(span_low, regard_half_deg)`)
    -- not fixed at the regard boundary unconditionally -- so a span that
    lies *entirely* outside the regard on one side (never reached by any
    of the four named sectors, which all straddle or contain azimuth 0)
    still returns its own true extent as the out-span, rather than one
    stretched to include ground between the regard boundary and the span
    that was never actually part of the sector."""
    span_low, span_high = center_deg - half_width_deg, center_deg + half_width_deg
    in_low, in_high = max(span_low, -regard_half_deg), min(span_high, regard_half_deg)
    in_span = (
        ((in_low + in_high) / 2.0, (in_high - in_low) / 2.0)
        if in_low < in_high
        else None
    )
    out_spans: list[tuple[float, float]] = []
    if span_low < -regard_half_deg:
        lo, hi = span_low, min(span_high, -regard_half_deg)
        out_spans.append(((lo + hi) / 2.0, (hi - lo) / 2.0))
    if span_high > regard_half_deg:
        lo, hi = max(span_low, regard_half_deg), span_high
        out_spans.append(((lo + hi) / 2.0, (hi - lo) / 2.0))
    return in_span, out_spans


def _sight_commanded_sector(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> tuple[float, float] | None:
    """The sight's own view of a *commanded* sector, or `None` when
    nothing is commanded (free scan) -- `plans/9k113-scan-procedure/
    plan.md` Stage 1. Reads `SIGHT_SECTOR_WEDGE_DEG`/`SIGHT_AHEAD_LEGS`
    (the sight's own, wider sector widths), never `SECTOR_WEDGE_DEG` (the
    naked eye's/binoculars' own narrower convention, still read by
    `_search_sweep` unchanged) -- "Sector widths diverge from the naked
    eye's" is the plan's own name for why these are two tables, not one.

    `"ahead"` alternates between `SIGHT_AHEAD_LEGS`'s two windows, toggled
    by `ownship.t_sim` on `SIGHT_AHEAD_WINDOW_DWELL_S` -- the explore
    notes' own *"could well be alternating sequence -30 to +10 deg and
    -10 to +30 deg"*. `left`/`right`/`full` are a plain table lookup.

    A commanded single o'clock hour (`ScanPlan.commanded_legs`, exactly
    one entry) resolves to its own 30 deg wedge via `_gaze_for_clock_
    hour`'s existing azimuth formula -- *"one o'clock sector such scan is
    comanded"* -- the same geometry a named sector already gets. A
    multi-leg `commanded_legs` (a compass-absolute scan converted to
    several o'clock hours) is **not** handled here -- out of this stage's
    own scope, same as today (falls through to the no-commanded-sector
    default below, unchanged from before this function existed)."""
    if scan_plan.commanded_sector == "ahead":
        index = int(ownship.t_sim // SIGHT_AHEAD_WINDOW_DWELL_S) % len(SIGHT_AHEAD_LEGS)
        return SIGHT_AHEAD_LEGS[index]
    if scan_plan.commanded_sector is not None:
        return SIGHT_SECTOR_WEDGE_DEG[scan_plan.commanded_sector]
    if scan_plan.commanded_legs is not None and len(scan_plan.commanded_legs) == 1:
        gaze = _gaze_for_clock_hour(scan_plan.commanded_legs[0])
        return gaze.center_azimuth_deg, gaze.half_width_deg
    return None


def _commanded_or_default_sector(
    scan_plan: ScanPlan, ownship: OwnshipState, regard_half_deg: float
) -> tuple[float, float]:
    """The sector the sight's own search cycle should cover -- a commanded
    sector at its own commanded width if one exists (never widened: `ahead`
    stays its own 40 deg window), else the sight's full field of regard
    centred on flight direction (`docs/acceptance/2026-10-20-sortie-
    feedback.md`, F4/F5 "settled": "flight direction as normal default")
    -- there is no commanded width to respect in the default case, and "a
    genuine physical bound, not an invented UX cap" (the same reasoning
    `MAX_SEARCH_SECTOR_HALF_WIDTH_DEG` is deliberately *not* applied here)
    applies identically. Centre `0.0` is the same convention `_back_to_
    home`'s own dead-ahead fallback uses."""
    commanded = _sight_commanded_sector(scan_plan, ownship)
    if commanded is not None:
        return commanded
    return 0.0, regard_half_deg


def _sight_in_regard_sweep(
    scan_plan: ScanPlan,
    ownship: OwnshipState,
    *,
    optic: Optic,
    near_m: float,
    far_m: float,
) -> list[tuple[float, float]]:
    """One leg of the sight's own search cycle (wide, or either of
    narrow's near/far bands) over whatever sub-span of the commanded-or-
    default sector the sight can actually reach -- `plans/
    9k113-narrow-search/plan.md` Stage 3.

    **Rotated into body-relative, then filtered through `within_field_of_
    regard`** (security required fix, `plans/9k113-narrow-search/
    security-review.md`, sharpened by F5 `docs/acceptance/
    2026-10-20-sortie-feedback.md`). `search_pattern`'s azimuth is already
    kept inside `regard` by construction (`max_half_width_deg=regard`
    below), but its elevation is pure range/altitude geometry
    (`atan2(altitude_agl_m, range_m)`, unbounded below) with no awareness
    of pitch, bank, or this optic's own `regard_elevation_down_deg` --
    the mount's actual limit is relative to the airframe's boresight, not
    to the ground (*"nose low position at high altitude would allow a
    near scan... it is not about distance, but angles relative to
    boresight"*), so a step generated from altitude alone has to be
    rotated into the body frame (`_to_body_relative_steps`) before the
    regard check means anything. Rejecting (not clamping) the offending
    steps here is the same choice `look_sweep` already makes for the
    sight's look-sweep path -- a step the mount cannot physically reach is
    dropped, not pointed at the envelope edge and attributed to ground
    that was never validated. A leg that filters down to empty is handled
    by the existing leg-advance/`_idle_sight_rest` fallback, which needs
    no change for this, and is recomputed fresh every poll from the
    current attitude -- so a leg emptied by a transient nose-up attitude
    is reachable again (`BL-B86.md`) the moment the nose comes back down,
    with no extra state to reset."""
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    center_deg, half_width_deg = _commanded_or_default_sector(
        scan_plan, ownship, regard
    )
    in_span, _ = _split_sector_by_regard(center_deg, half_width_deg, regard)
    if in_span is None:
        return []
    in_center_deg, in_half_width_deg = in_span
    fov_full_width_deg = (optic.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    steps = search_pattern(
        center_azimuth_deg=in_center_deg,
        sector_half_width_deg=in_half_width_deg,
        near_m=near_m,
        far_m=far_m,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
        max_half_width_deg=regard,
    )
    body_steps = _to_body_relative_steps(steps, ownship)
    return [
        step for step in body_steps if within_field_of_regard(optic, step[0], step[1])
    ]


def _sight_out_of_regard_sweep(
    scan_plan: ScanPlan, ownship: OwnshipState
) -> list[tuple[float, float]]:
    """Binoculars, for the portion of a *commanded* sector the sight
    cannot reach -- empty when nothing is commanded (the synthesized
    default sector is exactly the regard width, by construction, so it
    never has an out-of-regard remainder). `plans/9k113-scan-procedure/
    plan.md` Stage 1: with the sight's own wider sector table
    (`_sight_commanded_sector`), `left`/`right`/`full`/`ahead` are now all
    [subset of] the regard by construction too, so this is empty for every
    named sector -- only a commanded single o'clock hour straddling or
    outside +-60 deg (4-8 o'clock) still produces a remainder, unchanged
    from today's commanded-sector behaviour. `full`'s two out-spans (were
    it ever to have any) are concatenated into one list -- `OpticPhase.
    SEARCHING`'s own dispatch just steps through whatever sequence it is
    given, so two remainder pieces need no new state, only a longer list.

    **Rotated into body-relative before being returned** (F5), same as
    `_sight_in_regard_sweep`'s own aim -- binoculars have no field of
    regard to filter against, but the binocular aim frame still has to
    agree with every other optic's, or a step generated here would point
    at the wrong patch of ground whenever the aircraft is not level."""
    commanded = _sight_commanded_sector(scan_plan, ownship)
    if commanded is None:
        return []
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    center_deg, half_width_deg = commanded
    _, out_spans = _split_sector_by_regard(center_deg, half_width_deg, regard)
    fov_full_width_deg = (BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    near_m, far_m = (
        _SEARCH_BAND_M  # unchanged binocular band -- Stage 3 only touches the sight's own
    )
    steps: list[tuple[float, float]] = []
    for out_center_deg, out_half_width_deg in out_spans:
        steps.extend(
            search_pattern(
                center_azimuth_deg=out_center_deg,
                sector_half_width_deg=out_half_width_deg,
                near_m=near_m,
                far_m=far_m,
                altitude_agl_m=max(ownship.alt_agl_m, 0.0),
                fov_full_width_deg=fov_full_width_deg,
            )
        )
    return _to_body_relative_steps(steps, ownship)


def _sight_point_sweep(
    bounded_look: BoundedSightLook | None, ownship: OwnshipState
) -> list[tuple[float, float]]:
    """A `look <o'clock>`/`look <compass>`'s own search steps, or empty
    when none is active -- `plans/9k113-scan-procedure/plan-stage2.md`'s
    "The sweep itself". `bounded_look`'s wedge/band is fed straight to
    `search_pattern`, the sibling of `_sight_in_regard_sweep` above but
    driven directly by a given `(center_deg, half_width_deg, near_m,
    far_m)` rather than derived from a commanded sector -- a bounded look
    is not a `ScanPlan` command (the plan's own "no exact aim line, the
    wedge expressed exactly the way Stage 1 already expresses one, not a
    point"), so there is no `ScanPlan` to read it from.

    Filtered through the same `within_field_of_regard` + body-relative
    rotation `_sight_in_regard_sweep` applies -- a wedge that straddles
    the sight's own field of regard (never reached for an o'clock hour,
    possible for a compass bearing behind the regard) yields an empty
    in-span and this returns `[]`, same defensive handling `_advance_
    bounded_look` already gives an empty `steps` sequence."""
    if bounded_look is None:
        return []
    regard = SIGHT_WIDE_OPTIC.regard_azimuth_half_deg or 0.0
    in_span, _ = _split_sector_by_regard(
        bounded_look.center_azimuth_deg, bounded_look.half_width_deg, regard
    )
    if in_span is None:
        return []
    in_center_deg, in_half_width_deg = in_span
    fov_full_width_deg = (SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    if fov_full_width_deg <= 0.0:
        return []
    steps = search_pattern(
        center_azimuth_deg=in_center_deg,
        sector_half_width_deg=in_half_width_deg,
        near_m=bounded_look.near_m,
        far_m=bounded_look.far_m,
        altitude_agl_m=max(ownship.alt_agl_m, 0.0),
        fov_full_width_deg=fov_full_width_deg,
        max_half_width_deg=regard,
    )
    body_steps = _to_body_relative_steps(steps, ownship)
    return [
        step
        for step in body_steps
        if within_field_of_regard(SIGHT_WIDE_OPTIC, step[0], step[1])
    ]


def _apply_active_gaze(
    sources: list[PerceptionSource],
    tasks: TaskStore,
    *,
    scan_plan: ScanPlan | None = None,
    decision: OpticDecision | None = None,
    optic_state: OpticState | None = None,
    dt_s: float = 0.0,
    sight_head_body_az_deg: float | None = None,
    sight_head_body_el_deg: float | None = None,
) -> OpticState | None:
    """Assigns the resolved scan plan and optic onto whichever `sources`
    entry is a `NakedEyePerceptionSource` -- a true no-op for every other
    source, and for a `sources` list (e.g. in tests) that holds no
    naked-eye source at all. The same write-thread/single-assignment
    pattern `last_t_sim` already uses safely (`run_once`'s only caller).

    Both are applied here rather than in two places because they are one
    act -- *where he is looking and through what* -- and splitting the
    application would let a gaze and an optic from different polls be used
    for the same evaluation.

    `scan_plan`/`decision` default to `None` so the pre-binocular call
    shape (`_apply_active_gaze(sources, tasks)`) still works and still
    resolves the scan plan itself: several tests construct sources and call
    this directly, and none of them care about the optic.

    **A glass phase overrides the scan plan with a fixed look**
    (`plans/binocular-optic/plan.md` Stage 2). The look is a `ScanPlan`
    holding one direction rather than a special case in the source: the
    source already resolves `gaze_at(now_sim, scan_plan)` every poll, so a
    plan whose every leg is the same direction *is* a fixed stare, and no
    branch is needed anywhere downstream.

    **`[[BL-B80]]` v2 splits "actual aim" by tier.** For a sight-tier
    optic, `sight_head_body_az_deg`/`sight_head_body_el_deg` (the
    simulated `SightHead`'s own body direction, `None` while it is not
    `free`) are the *only* source of `actual_aim_*` -- `advance_sight_
    aim` is never consulted for this tier any more. For every other optic
    (naked eye, binoculars), `advance_sight_aim`'s pass-through still
    applies, exactly as before `[[BL-B80]]` existed. `optic_state` is
    optional (`None` for every pre-existing caller, including the several
    tests that call this directly with no decision) -- when given, the
    returned `OpticState` (or `None` if nothing changed) is what the
    caller must persist back onto its own `optic_state` field, the same
    way `run_once` already persists `decide_optic`'s return value."""
    resolved_plan = scan_plan if scan_plan is not None else _active_gaze(tasks)
    optic = decision.optic if decision is not None else UNAIDED_OPTIC
    updated_state = optic_state
    is_sight_tier = optic in (SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC)
    if is_sight_tier:
        if sight_head_body_az_deg is not None and sight_head_body_el_deg is not None:
            if optic_state is not None:
                updated_state = replace(
                    optic_state,
                    actual_aim_azimuth_deg=sight_head_body_az_deg,
                    actual_aim_elevation_deg=sight_head_body_el_deg,
                )
            resolved_plan = ScanPlan.fixed_look_at(
                azimuth_deg=sight_head_body_az_deg,
                elevation_deg=sight_head_body_el_deg,
            )
        elif optic_state is not None and (
            optic_state.actual_aim_azimuth_deg is not None
            or optic_state.actual_aim_elevation_deg is not None
        ):
            # The head is not `free` yet -- no aim to perceive through.
            updated_state = replace(
                optic_state,
                actual_aim_azimuth_deg=None,
                actual_aim_elevation_deg=None,
            )
    elif (
        decision is not None
        and decision.look_azimuth_deg is not None
        and decision.look_elevation_deg is not None
    ):
        prior_azimuth = (
            optic_state.actual_aim_azimuth_deg if optic_state is not None else None
        )
        prior_elevation = (
            optic_state.actual_aim_elevation_deg if optic_state is not None else None
        )
        actual_azimuth_deg, actual_elevation_deg = advance_sight_aim(
            prior_azimuth,
            prior_elevation,
            decision.look_azimuth_deg,
            decision.look_elevation_deg,
            dt_s=dt_s,
        )
        # Both desired values are non-`None` on this branch (checked
        # above), and `advance_sight_aim` is a pure pass-through -- so
        # `actual` cannot be `None` here either way.
        assert actual_azimuth_deg is not None
        assert actual_elevation_deg is not None
        if optic_state is not None:
            updated_state = replace(
                optic_state,
                actual_aim_azimuth_deg=actual_azimuth_deg,
                actual_aim_elevation_deg=actual_elevation_deg,
            )
        resolved_plan = ScanPlan.fixed_look_at(
            azimuth_deg=actual_azimuth_deg,
            elevation_deg=actual_elevation_deg,
        )
    elif optic_state is not None and (
        optic_state.actual_aim_azimuth_deg is not None
        or optic_state.actual_aim_elevation_deg is not None
    ):
        # No fixed look is commanded this poll -- actual aim goes back to
        # `None` too, mirroring `OpticState.look_azimuth_deg`'s own
        # None-while-not-glassing contract, rather than holding a stale
        # direction from the last glass phase.
        updated_state = replace(
            optic_state,
            actual_aim_azimuth_deg=None,
            actual_aim_elevation_deg=None,
        )
    # `BL-B64` Stage 2, direction §7 -- the directional player-bubble
    # exemption, pointed at the sight's own *actual* aim (never desired,
    # same reasoning as the `ScanPlan` above). `optic.regard_azimuth_half_
    # deg is not None` is the general test for "this optic can be
    # pointed/slewed" rather than naming the two sight optics -- only they
    # set it (`optics.py`'s own docstring) -- so a future optic with a
    # field of regard picks this up automatically. `None` whenever no
    # actual aim is committed this poll (idle-wide sighting, or any other
    # optic), which is the whole of `association.filter_player_bubble`'s
    # own "guard the whole branch" contract.
    sight_cone: SightCone | None = None
    if (
        optic.regard_azimuth_half_deg is not None
        and updated_state is not None
        and updated_state.actual_aim_azimuth_deg is not None
    ):
        sight_cone = SightCone(
            azimuth_deg=updated_state.actual_aim_azimuth_deg,
            half_angle_deg=optic.fov_half_angle_deg or 0.0,
            depth_m=(
                optic.range_cap_m
                if optic.range_cap_m is not None
                else PLAYER_BUBBLE_RADIUS_M
            ),
        )
    # `BL-B64` Stage 2, direction §6 -- the 1 s hand movement. `None`
    # (the default) on every pre-existing `OpticState`, so this is a
    # true no-op until the pilot's "Observ on"/"Observ off" command sets
    # it (`body.py`'s poll loop).
    suppressed_until_sim = (
        optic_state.hands_busy_until_sim if optic_state is not None else None
    )
    for source in sources:
        if isinstance(source, NakedEyePerceptionSource):
            source.scan_plan = resolved_plan
            source.optic = optic
            source.sight_cone = sight_cone
            source.suppressed_until_sim = suppressed_until_sim
    return updated_state


def _warn_live_los_coverage_gap_once(
    sources: list[PerceptionSource], already_warned: bool
) -> bool:
    """Reads the naked-eye source's `LiveLosCoverage` counter
    (`plans/bl11-stage4-fail-closed/plan.md`, `BL-11` Stage 4 step 4) and
    logs a one-time warning via the standing `logging.getLogger(__name__)`
    channel the first time `no_verdict` becomes nonzero -- called from
    `_run_crew_text_poll_loop`.

    **Not a log-on-change shape, deliberately** -- an earlier revision of
    this function copied that shape from a sibling overlay-pushing
    function (since removed, `BL-B96`) and that was the bug (review
    round 1, `plans/bl11-stage4-fail-closed/review.md`). Log-on-change
    works for a value that can hold steady at a repeating value, so
    "changed since last call" is a real steady-state guard there.
    `no_verdict`
    is cumulative for the process lifetime, so under a continuously dead
    feed it is strictly greater than whatever was last logged on every
    single poll -- there is no steady state for a monotonically
    increasing counter to settle into, so a "log when it grew" guard logs
    every poll for the rest of the sortie, which is backwards from this
    function's whole purpose (one line, not a flood). The fix is an
    edge-trigger instead: log once on the zero-to-nonzero transition, and
    never again regardless of how much further `no_verdict` grows. That
    one line carries all the actionable information ("a gap exists");
    `_log_live_los_coverage_summary` below is where the magnitude lives,
    because it is only known at the end of the run.

    On by default, with no `--flag` to gate it (unlike `--detection-
    trace`) -- this is the regression guard, not an opt-in diagnostic
    (plan Decision 2): a dead feed must be observable on an ordinary
    sortie with no debugging flags set at all. A true no-op for a
    `sources` list holding no naked-eye source (same guard
    `_apply_active_gaze` uses).

    Returns `True` once the warning has fired (unchanged from
    `already_warned=True` on every later call), so the caller's local
    carries the already-fired state forward to the next poll."""
    if already_warned:
        return True
    for source in sources:
        if isinstance(source, NakedEyePerceptionSource):
            coverage = source.live_los_coverage
            if coverage.no_verdict > 0:
                logger.warning(
                    "live LOS coverage gap: naked-eye gate-4 evaluations "
                    "started receiving no live verdict this sortie "
                    "(world-model's offline LOS primitive is no longer "
                    "used as a fallback -- affected candidates are "
                    "rejected, not approximated); see the end-of-run "
                    "summary for the final totals"
                )
                return True
            return False
    return False


def _log_live_los_coverage_summary(sources: list[PerceptionSource]) -> None:
    """Unconditional end-of-run totals for the naked-eye source's
    `LiveLosCoverage` counter -- logged exactly once, from each poll
    loop's own `finally:` block, regardless of whether
    `_warn_live_los_coverage_gap_once` ever fired (user design call,
    `plans/bl11-stage4-fail-closed/review.md`'s dispatching brief, not
    the Reviewer's own required fix).

    **Logged even when `no_verdict` is zero.** A `0/N` line is the guard
    visibly passing; without one, a silent log is indistinguishable from
    a guard that never ran at all -- the same reasoning
    `detection_trace.py`'s `static_enum_failures` counter already applies
    on the Hook side. The transition warning above tells the pilot *that*
    a gap started; this tells whoever reads the log afterward *how big*
    it ended up, which the transition warning cannot know at the moment
    it fires -- this counter's stated purpose
    (`body-layer/ROADMAP.md`, Stage 4) is a post-flight regression guard,
    and the magnitude is the number that guard exists to report.

    Must never raise: this runs during teardown that still has to close
    `trace_writer`/`belief_truth_writer`/`world_model_conn` after it, so
    a failure here is logged and swallowed rather than allowed to skip
    that teardown -- the same non-negotiable `finally:` has for every
    other resource it closes. A true no-op for a `sources` list holding
    no naked-eye source (same guard `_apply_active_gaze` and
    `_warn_live_los_coverage_gap_once` use)."""
    try:
        for source in sources:
            if isinstance(source, NakedEyePerceptionSource):
                coverage = source.live_los_coverage
                logger.info(
                    "live LOS coverage: %d/%d gate-4 evaluations had no "
                    "live verdict this sortie",
                    coverage.no_verdict,
                    coverage.evaluated,
                )
                return
    except Exception:
        logger.exception("live LOS coverage summary failed (ignoring)")


def _resolve_active_gaze(runner: ConsolePerceptionRunner) -> Gaze:
    """Where Petrovich is actually looking, and how wide, this poll -- the
    one resolved value both `--eyesight-view` and `--pov-view` must read
    (`docs/acceptance/2026-10-26-sortie-feedback.md`: *"both should show
    what Petrovich is really looking at and with what optic. Scan plan is
    useless data unless he actually looks there."*).

    **Why not just read `runner.scan_plan` directly** (the bug this
    function fixes): `runner.scan_plan` is the *commanded* plan
    `_active_gaze` resolves before `run_once` calls `_apply_active_gaze`,
    which may override it with a fixed look (a glass phase, or the 9K113
    sight) -- that override lands on the naked-eye source's own private
    `scan_plan` copy (`_apply_active_gaze`'s `source.scan_plan =
    resolved_plan`), never back onto `runner.scan_plan`. Reading `runner.
    scan_plan` is therefore only ever correct while Petrovich is actually
    free-scanning; while on a fixed look it was still showing the sector
    that was commanded *before* the look took over -- `--eyesight-view`
    showing `3_oclock` while the 9K113 held `az=+6` is exactly this.

    **Per-optic resolution, mirroring `_apply_active_gaze`'s own
    inputs rather than its output** (`plans/pov-view/plan.md`'s boresight
    table, previously used by `_render_pov_frame` alone):

    - `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`: the simulated `SightHead`'s
      own world-true direction, converted to heading-relative azimuth --
      never `runner.scan_plan`, even after `_apply_active_gaze` resolves
      it, because that resolution uses the sight head's *body*-relative
      direction (pitch/bank included, `head_body_direction`), which
      `plans/pov-view/plan.md`'s own "Design" section rules out as the
      display frame for this canvas.
    - A fixed look on any other optic (binoculars, or any future optic
      that gets one): `OpticState.actual_aim_azimuth_deg/elevation_deg`,
      which is the same resolved value `_apply_active_gaze` computed for
      the naked-eye source's `scan_plan.fixed_look`, read directly rather
      than through the field that failed to carry it.
    - Otherwise (free-scanning, `actual_aim_*` both `None`): `runner.
      scan_plan` is correct as-is -- `gaze_at` indexes the live scan cycle,
      `_active_gaze` already resolved it for this poll, and no override
      applies.

    `gaze.label` is deliberately the optic's own name (`"sight_wide"`,
    `"binocular"`) while on a fixed look, not a stale scan-plan o'clock
    label -- a debug view's header must never claim a scanning direction
    that is not what is actually happening, which was the screenshot's
    other symptom alongside the wrong bearing."""
    optic = runner.optic
    if optic in (SIGHT_WIDE_OPTIC, SIGHT_NARROW_OPTIC):
        assert runner.sight_head.world_az_true_deg is not None
        assert runner.sight_head.world_el_deg is not None
        assert optic.fov_half_angle_deg is not None
        assert runner.last_ownship_state is not None
        azimuth_deg = relative_bearing_deg(
            runner.sight_head.world_az_true_deg,
            runner.last_ownship_state.heading_true_deg,
        )
        return Gaze(
            center_azimuth_deg=azimuth_deg,
            half_width_deg=optic.fov_half_angle_deg,
            label=optic.name,
            center_elevation_deg=runner.sight_head.world_el_deg,
        )
    actual_azimuth_deg = runner.optic_state.actual_aim_azimuth_deg
    actual_elevation_deg = runner.optic_state.actual_aim_elevation_deg
    if actual_azimuth_deg is not None and actual_elevation_deg is not None:
        assert optic.fov_half_angle_deg is not None
        return Gaze(
            center_azimuth_deg=actual_azimuth_deg,
            half_width_deg=optic.fov_half_angle_deg,
            label=optic.name,
            center_elevation_deg=actual_elevation_deg,
        )
    assert runner.last_t_sim is not None
    return gaze_at(runner.last_t_sim, runner.scan_plan)


def _render_eyesight_frame(
    runner: ConsolePerceptionRunner,
    trace_records: list[DetectionTrace],
    radius_m: float,
    max_lines: int | None = None,
) -> str | None:
    """One `--eyesight-view` frame for the poll that just ran (`todo/
    todo.md`'s "Added 2026-09-25 (user)" entry) -- `None` before the first
    successful poll (`runner.last_ownship_state`/`last_t_sim` still unset).

    `trace_records` must be a snapshot taken *before* `--detection-trace`'s
    own `DetectionTraceWriter.write_poll` clears the shared
    `DetectionTraceCollector` this poll fed into `NakedEyePerceptionSource`
    -- the poll loop calls this ahead of that write, never after, so a
    frame always reflects this poll's own ground truth, not an empty
    collector. Only the naked-eye channel is traced at all (`--detection-
    trace`'s own module docstring), so the ground-truth half of a frame is
    naked-eye-only by the same limit; believed markers come from the full
    `ContactStore`, not the trace, so a scope/hybrid contact still appears
    there.

    `max_lines` defaults to `None`, meaning "read the real terminal"
    (`_eyesight_max_lines()`) -- the poll loop passes an explicit, halved
    budget instead when `--pov-view` is also on (`plans/pov-view/plan.md`,
    `BL-B99`), so the two frames share one terminal's worth of lines
    rather than each assuming it owns the whole thing.

    **Gaze comes from `_resolve_active_gaze`, not `gaze_at(runner.
    scan_plan)` directly** (`docs/acceptance/2026-10-26-sortie-feedback.
    md`) -- see that function's own docstring for why reading `runner.
    scan_plan` alone was wrong whenever a fixed look (glassing, or the
    9K113 sight) was in force."""
    if runner.last_ownship_state is None or runner.last_t_sim is None:
        return None
    ownship = runner.last_ownship_state
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    gaze = _resolve_active_gaze(runner)
    rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
    return render_eyesight_frame(
        gaze=gaze,
        optic_name=runner.optic.name,
        rear_cutoff_deg=rear_cutoff_deg,
        ground_truth=ground_truth_markers_from_trace(
            trace_records, heading_true_deg=ownship.heading_true_deg
        ),
        believed=believed_markers_from_contacts(
            runner.store.contacts,
            observer,
            ownship.heading_true_deg,
            areas=runner.store.areas,
        ),
        radius_m=radius_m,
        max_lines=max_lines if max_lines is not None else _eyesight_max_lines(),
    )


def _render_pov_frame(
    runner: ConsolePerceptionRunner,
    trace_records: list[DetectionTrace],
    max_lines: int | None = None,
) -> str | None:
    """One `--pov-view` frame for the poll that just ran (`plans/pov-view/
    plan.md`, `BL-B99`) -- mirrors `_render_eyesight_frame`'s own `None`
    guard and `max_lines` posture.

    **Boresight comes from `_resolve_active_gaze`**, the same resolved
    value `_render_eyesight_frame` now reads too
    (`docs/acceptance/2026-10-26-sortie-feedback.md`) -- previously this
    function alone did the per-optic resolution (`plans/pov-view/plan.md`'s
    boresight table), which is why only `--eyesight-view` showed the
    stale commanded scan sector and `--pov-view` already read the real
    aim for the sight tier; see that function's own docstring for the
    full per-optic account, including why a fixed look on a non-sight
    optic needed its own fix here too (`OpticState.actual_aim_*`, not
    `runner.scan_plan`, which `_apply_active_gaze` never updates)."""
    if runner.last_ownship_state is None or runner.last_t_sim is None:
        return None
    ownship = runner.last_ownship_state
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    optic = runner.optic
    gaze = _resolve_active_gaze(runner)
    boresight_azimuth_deg = gaze.center_azimuth_deg
    boresight_elevation_deg = gaze.center_elevation_deg
    half_angle_deg = gaze.half_width_deg
    return render_pov_frame(
        optic_name=optic.name,
        boresight_azimuth_deg=boresight_azimuth_deg,
        boresight_elevation_deg=boresight_elevation_deg,
        half_angle_deg=half_angle_deg,
        ground_truth=pov_ground_truth_markers_from_trace(
            trace_records, heading_true_deg=ownship.heading_true_deg
        ),
        believed=pov_believed_markers_from_contacts(
            runner.store.contacts,
            observer,
            ownship.heading_true_deg,
            areas=runner.store.areas,
        ),
        max_lines=max_lines if max_lines is not None else POV_DEFAULT_MAX_LINES,
    )


def _speech_log_sink(
    writer: BeliefTruthLogWriter, runner: ConsolePerceptionRunner
) -> Callable[
    [
        str,
        bool,
        dict[str, object] | None,
        str | None,
        float | None,
        float | None,
        float | None,
    ],
    None,
]:
    """Build `CrewConsole.speech_log_sink` -- every spoken line becomes a
    `kind: "speech"` row in the belief-truth log, carrying the gaze and
    optic **as they are at the moment of speech**.

    That timing is the point. The defect this was added for is a callout
    naming 10 o'clock while a commanded `scan right` is in force, and the
    only way to see it in a log is to record where he was looking when the
    words came out, not where he was looking when the poll started.

    Reads `runner` live rather than capturing values, for the same reason:
    `scan_plan`/`optic` are reassigned every poll, and a closure over the
    runner sees the current ones. Failures are swallowed by the caller --
    a debug log must never be why Petrovich stops talking.

    `gaze_label`/`gaze_center_deg` come from `_resolve_active_gaze`, not
    `gaze_at(now_sim, runner.scan_plan)` directly (`docs/acceptance/
    2026-10-26-sortie-feedback.md`: "I need to know where he is looking" --
    applies to this log the same way it applies to `--eyesight-view`/
    `--pov-view`; see that function's own docstring for why `runner.
    scan_plan` alone is wrong whenever a fixed look is in force).

    `attack_run_fields` (Stage 5, `plans/attack-run/plan.md`) is `_print`'s
    third argument, threaded straight through to `write_speech`'s own
    four attack-run keyword arguments -- `None` for every line but
    `drain_attack_run`'s own, which is the only caller that ever supplies
    it.

    Also carries `runner.last_ownship_state`'s pitch/bank/heading/altitude
    through to `write_speech`'s own ownship fields (added for the
    2026-10-15 attack-run sortie's open question -- see `write_speech`'s
    own docstring). `None` for all four when no poll has completed yet
    (`last_ownship_state` still unset), the same "nothing to report yet"
    case `_render_eyesight_frame` already guards against -- never a
    fabricated `0.0`, which would read as "level, unbanked" rather than
    "unknown".

    `correlation_id`/`push_sent_wall`/`push_acked_wall`/`push_duration_s`
    (Stage 3, `plans/voice-latency-instrumentation/plan.md`) are `_print`'s
    own four latest arguments, carried straight through to `write_speech`'s
    identically-named fields -- this function only relays them, the
    measurement happens in `_print` itself."""

    def sink(
        line: str,
        urgent: bool,
        attack_run_fields: dict[str, object] | None,
        correlation_id: str | None,
        push_sent_wall: float | None,
        push_acked_wall: float | None,
        push_duration_s: float | None,
    ) -> None:
        now_sim = runner.last_t_sim
        if now_sim is None:
            return
        gaze = _resolve_active_gaze(runner)
        ownship = runner.last_ownship_state
        extra = attack_run_fields or {}
        target_contact_id = extra.get("attack_run_target_contact_id")
        tier = extra.get("attack_run_tier")
        azimuth_deg = extra.get("attack_run_azimuth_deg")
        elevation_deg = extra.get("attack_run_elevation_deg")
        writer.write_speech(
            t_sim=now_sim,
            text=line,
            urgent=urgent,
            gaze_label=gaze.label,
            gaze_center_deg=gaze.center_azimuth_deg,
            optic_name=runner.optic.name,
            ownship_pitch_deg=ownship.pitch_deg if ownship is not None else None,
            ownship_bank_deg=ownship.bank_deg if ownship is not None else None,
            ownship_heading_true_deg=(
                ownship.heading_true_deg if ownship is not None else None
            ),
            ownship_alt_m=ownship.alt_m if ownship is not None else None,
            attack_run_target_contact_id=(
                target_contact_id if isinstance(target_contact_id, str) else None
            ),
            attack_run_tier=tier if isinstance(tier, int) else None,
            attack_run_azimuth_deg=(
                azimuth_deg if isinstance(azimuth_deg, float) else None
            ),
            attack_run_elevation_deg=(
                elevation_deg if isinstance(elevation_deg, float) else None
            ),
            correlation_id=correlation_id,
            push_sent_wall=push_sent_wall,
            push_acked_wall=push_acked_wall,
            push_duration_s=push_duration_s,
        )

    return sink


def _eyesight_max_lines() -> int:
    """Lines one eyesight frame may occupy, read from the real terminal so
    the canvas is never scrolled off the top by a long beyond-radius list
    (user, 2026-09-25 -- found in use, with a raised radius as the
    workaround, which trades away resolution to shrink the list).

    Falls back to `eyesight_view.DEFAULT_MAX_LINES` when there is no tty,
    which is the redirected-output and test case."""
    try:
        return max(shutil.get_terminal_size().lines - 1, 12)
    except OSError:  # pragma: no cover - no tty, platform-dependent
        return EYESIGHT_DEFAULT_MAX_LINES


def _print_frames(frames: Sequence[str]) -> None:
    """Clears the terminal and prints one or more debug-view frames,
    separated by a blank line -- the one place `--eyesight-view`/
    `--pov-view` touch the terminal, kept separate from
    `_render_eyesight_frame`/`_render_pov_frame`'s pure string-building so
    the geometry stays testable and this side effect needs no test of its
    own, the same live-process-entrypoint posture `main()` itself already
    has. Generalised from the old `_print_eyesight_frame` (`plans/
    pov-view/plan.md`, `BL-B99`) to take any number of frames, so both
    views share one clear-and-print cycle when both are on."""
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.write("\n\n".join(frames))
    sys.stdout.write("\n")
    sys.stdout.flush()


def _build_sources(
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_conn: sqlite3.Connection,
    emit_mode: Literal["on_change", "every_poll"],
    trace_sink: DetectionTraceCollector | None = None,
    forest_occlusion: bool = False,
) -> list[PerceptionSource]:
    """Construct both concrete tiers at a given `emit_mode` --
    `main()`'s crew-text poll loop always builds at `"every_poll"`
    (`"on_change"` remains a tested capability of this function, not
    currently used by any production caller).

    `trace_sink` (BL-9, `--detection-trace`) is additive, defaults to
    `None`, and is only ever wired into `NakedEyePerceptionSource` -- the
    scope/hybrid channel has no geometric gate chain to trace (plan
    Risks).

    `forest_occlusion` (`--forest-occlusion`, `plans/forest-occlusion/
    plan.md` Stage 2) defaults to `False` -- a true no-op, same additive
    posture as `trace_sink` above. When `True`, constructs one
    `ForestOcclusion` against `world_model_conn`/`theatre` and wires it
    into `NakedEyePerceptionSource` only, for the same reason `trace_sink`
    is naked-eye-only: the scope/hybrid channel has no geometric gate
    chain for a forest gate to join."""
    forest = (
        ForestOcclusion(conn=world_model_conn, theatre=theatre)
        if forest_occlusion
        else None
    )
    return [
        HybridPerceptionSource(
            aircraft_client=aircraft_client, theatre=theatre, emit_mode=emit_mode
        ),
        NakedEyePerceptionSource(
            aircraft_client=aircraft_client,
            theatre=theatre,
            world_model_conn=world_model_conn,
            emit_mode=emit_mode,
            trace_sink=trace_sink,
            forest=forest,
        ),
    ]


#: How many attitude samples the steadiness gate looks back over. Three at
#: the default one-second poll interval is a few seconds of history: long
#: enough to catch a manoeuvre in progress, short enough that a bank a
#: minute ago cannot still forbid a look.
ATTITUDE_HISTORY_LEN = 3

_DEFAULT_POLL_INTERVAL_S = 1.0


def _wait_for_next_tick(
    stop_event: threading.Event, deadline: float, poll_interval_s: float
) -> float:
    """Sleep until `deadline`, then return the next poll's deadline --
    `BL-11` Stage 1.

    **Both poll loops used to end with `stop_event.wait(poll_interval_s)`,
    which sleeps the full interval *after* the work**, so the realised
    period was `work + interval` and never `interval`. With work measured
    at a median ~330 ms at sortie scale, a 1.0 s setting realised 1.33 s
    (`body-layer/research/2026-10-05-performance-review.md`, "The headline
    correction") -- quantitatively the whole of the sortie's observed
    ~1.4x miss. Sleeping to a deadline instead makes the configured number
    mean what it says.

    **Overrun policy: drop the missed ticks, do not queue them.** When the
    work takes longer than `poll_interval_s` the remaining wait clamps to
    zero and the *next* deadline is re-based on the clock now, so a slow
    poll costs exactly the ticks it overran and nothing afterwards. The
    alternative -- advancing the deadline by one interval regardless --
    accumulates debt, and the loop would then run back-to-back with no
    sleep at all for as long as it takes to repay it, which is the worst
    possible behaviour on a thread that is already behind. There is nothing
    to catch up on in any case: each poll reads the *latest* telemetry, so
    a skipped tick has no backlog, only a gap.

    **The cost that statement does not cover: sustained overrun means zero
    voluntary yield.** "Exactly the ticks it overran and nothing afterwards"
    is about tick debt. While the work keeps exceeding `poll_interval_s`,
    `stop_event.wait` is never called at all and this thread runs
    back-to-back, pinning a core on a Mac that also hosts Ollama and the
    brain layer -- the old `wait(poll_interval_s)` tail was an accidental
    1.0 s floor that hid this. Deliberately left as a bare clamp rather
    than floored at ~50 ms: each iteration does real interval-scale work
    (this is not a busy-spin), shutdown stays prompt because
    `stop_event.is_set()` is checked at the top of every iteration, and a
    floor would silently extend every realised period in the one regime
    where the loop is already behind -- reintroducing a smaller version of
    the `work + interval` bug this stage exists to remove. If core pressure
    is ever observed in flight, the fix is a longer `--poll-interval-s`,
    which is the knob that already means this."""
    remaining = deadline - time.monotonic()
    if remaining > 0.0:
        stop_event.wait(remaining)
        return deadline + poll_interval_s
    return time.monotonic() + poll_interval_s


#: The LOS query cone body-layer pushes for an ordinary naked-eye scan --
#: `plans/dcs-driven-los/plan.md` SS17's own settled value: three o'clock
#: hours (the one being scanned plus one either side), wide enough that a
#: poll straddling a dwell change still covers the gaze, so command lag
#: never has to be reasoned about (geometry instead of timing). The Lua
#: side's own `FOV_DEFAULT_DEG` (45) is only the fallback for "no directive
#: has arrived yet" -- this is what gets sent once body-layer starts
#: pushing.
LOOK_DIRECTION_FOV_HALF_DEG = 90


def _hour_for_gaze(gaze: Gaze) -> int:
    """The o'clock hour (`0`..`11`) nearest `gaze.center_azimuth_deg`
    (body-relative, `perception.gaze`'s own convention: `12` o'clock = 0
    degrees, positive clockwise, one hour = 30 degrees) -- the inverse of
    `perception.gaze._gaze_for_clock_hour`'s own formula. Used only to pick
    which wedge to ask the LOS Hook script to query (`plans/dcs-driven-los/
    plan.md` SS9); it is not itself a detectability decision."""
    return round(gaze.center_azimuth_deg / 30.0) % 12


def _is_connection_loss(exc: BaseException) -> bool:
    """Whether `exc` is the aircraft layer being unreachable, as opposed to
    a defect in our own poll cycle.

    `AircraftLayerError` covers both -- `aircraft_client` raises it for a
    dead socket *and* for a reply that is not valid JSON -- so the cause
    chain is what separates them. A `URLError`/`OSError` underneath means
    the collector is not answering (DCS not running, the Windows box
    asleep, the cable out); anything else is ours and still deserves a
    traceback.
    """
    if not isinstance(exc, AircraftLayerError):
        return False
    return isinstance(exc.__cause__, (urllib.error.URLError, OSError))


def _mission_memory_step(
    memory: MissionMemory,
    runner: ConsolePerceptionRunner,
    now_sim: float,
    theatre: str,
    phase: MissionPhaseInfo | None,
    fired_on_tracker: FiredOnTracker,
) -> None:
    """BL-8's writer, called once per poll from the crew-session poll
    loop, **after** `runner.run_once()` (belief is settled;
    `ContactStore.tick()` has already materialised this poll's events)
    and **before** `crew_console.drain_events` -- `mission_memory.
    admission`'s module docstring states the same ordering, and this is
    the one call site responsible for keeping it (plan Decision 3).

    `fired_on_tracker` is owned by the calling poll loop and lives for its
    whole run (Stage 3) -- `FiredOnTracker`'s own docstring on why this is
    not state on `MissionMemory` itself.

    **Never propagates.** Decision 8: a memory write must never kill the
    poll loop. `admission.step` itself only ever raises from a genuine
    programming error (a malformed `strikes`, a TOML/tuning misread would
    already have failed at import) -- this guard exists for exactly the
    cases nobody predicted, the same posture `run_once`'s own callers
    already take around perception/belief failures elsewhere in these
    loops."""
    try:
        admission.step(
            memory,
            runner.store,
            now_sim,
            theatre=theatre,
            phase=phase,
            enrichment=runner.enrichment,
            fired_on_tracker=fired_on_tracker,
        )
    except Exception:
        logger.exception("mission-memory step failed; continuing")


def _reset_mission_state(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole | None,
    mission_memory: MissionMemory,
    fired_on_tracker: FiredOnTracker | None = None,
) -> None:
    """`BL-15` Stage 1 (`plans/bl15-mission-start/plan.md`) -- give every
    piece of belief/mission-memory state a clean slate on a genuine DCS
    mission (re)start. Theatre/world-model are **not** touched here --
    `runner.theatre`/`runner.world_model_conn` are in `ConsolePerceptionRunner.
    reset_for_new_mission`'s preserved-field list, so this call is a true
    no-op for them, matching `BL-15.md`'s own staging (theatre re-resolution
    is a separate, not-yet-implemented stage).

    **Shared-reference ordering is the one real hazard here, not a defect
    in the pattern.** `runner.store`/`crew_console.store` are the same
    `ContactStore` object (and `tasks` likewise) -- deliberately, per
    `belief.crew_console.CrewConsole.store`'s own field docstring. Resetting
    that object happens exactly once, *before* `runner.reset_for_new_mission`/
    `crew_console.reset_for_new_mission` are called -- those two calls pass
    the (now-cleared) same objects straight through, they do not clear them
    a second time. Get this order backwards and `runner.reset_for_new_
    mission`'s own re-run `__init__` would hand back the *same*, still-
    stale `store`/`tasks` objects -- reassigning the field, not clearing
    its contents.

    `crew_console` is `Optional` so a caller with no production command
    surface to reset can pass `None` for a true no-op -- same "optional
    collaborator, None is a no-op" shape as every other optional field in
    this codebase. `main()`'s own poll loop always has a real
    `CrewConsole` and never takes this branch.

    `fired_on_tracker` defaults to `None` so every existing test calling
    this with the original three-argument shape is unaffected (same
    reasoning `_check_for_new_mission`'s own `world_model_dir`/`trace_sink`/
    `forest_occlusion` defaults give, see that function's docstring) --
    `None` only arises if a future caller genuinely has no tracker to
    reset, since both of `body.py`'s own poll loops always build one.
    Batch 2 review follow-up (`plans/bl15-mission-start/review.md`):
    `FiredOnTracker` predates `BL-15` and was not brought under this
    mechanism when it was built -- see its own `reset_for_new_mission`
    docstring for why leaving it out silently stalls `fired_on` mission-
    memory writes after a restart."""
    runner.store.reset_for_new_mission()  # shared with crew_console.store
    runner.tasks.reset_for_new_mission()  # shared with crew_console.tasks
    for source in runner.sources:
        source.reset_for_new_mission()
    runner.reset_for_new_mission()
    if crew_console is not None:
        crew_console.reset_for_new_mission()
    mission_memory.reset_for_new_mission()
    if fired_on_tracker is not None:
        fired_on_tracker.reset_for_new_mission()


def _enter_refusal_mode(
    runner: ConsolePerceptionRunner, crew_console: CrewConsole | None
) -> None:
    """`BL-15` Stage 3 (`plans/bl15-mission-start/plan.md`'s Stage 3, user
    decision 1 REVISED, 2026-10-19): *"wrong terrain model is as useless as
    not terrain model ... On failure to load world model, log error. Have
    Petrovich respond to every player command with 'system error, world
    model not loaded'. On error loud refusal is better."*

    Drops whatever store was running -- a store for the wrong theatre is
    not retained (the user's first answer, kept by the revision) -- and
    stops perception entirely rather than leaving `NakedEyePerceptionSource`
    running with no terrain line-of-sight gate at all (the revision's own
    reasoning: rewiring the eyesight source to tolerate a missing store was
    judged not worth the cost against a loud refusal). `runner.enrichment`
    is also cleared: it would otherwise keep holding a `WorldEnrichmentCache`
    built over the connection just closed, and the next successful switch
    must rebuild it against the *new* connection, not silently keep serving
    stale enrichment computed from a closed one.

    `crew_console` is `Optional`, same shape as `_reset_mission_state`'s
    own -- `None` is a true no-op for a caller with no production command
    surface to refuse on. `main()`'s own poll loop always has a real
    `CrewConsole` and never takes this branch."""
    if runner.world_model_conn is not None:
        runner.world_model_conn.close()
    runner.world_model_conn = None
    runner.enrichment = None
    runner.sources = []
    if crew_console is not None:
        crew_console.refused = True


def _maybe_switch_theatre(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole | None,
    event_theatre: object,
    world_model_dir: Path | None,
    trace_sink: DetectionTraceCollector | None,
    forest_occlusion: bool,
) -> None:
    """`BL-15` Stage 3 -- re-resolve `runner.theatre`/`runner.world_model_conn`/
    `runner.sources` against the live mission's own theatre, called by
    `_check_for_new_mission` immediately after `_reset_mission_state`, only
    when a mission (re)start was just detected (never on an unchanged
    sequence -- `_check_for_new_mission`'s own gating).

    **`event_theatre is None`** (the Hook could not read `env.mission.
    theatre`) is not evidence the live theatre is wrong -- keep the current
    store, log once, do nothing else (user decision 2026-10-19: *"I used
    the initial silence mode as proxy..."* did not touch this point, which
    was never revised -- a `None` theatre has always meant "unknown," not
    "mismatch").

    **Same theatre as `runner.theatre`**: no-op, no log line -- this is the
    overwhelmingly common case (a mission restart that does not change
    theatre) and would otherwise print on every single restart.

    **`world_model_dir is None`**: there is nothing to resolve a new store
    from even if the theatre did change (this stage needs `--world-model-
    dir` regardless of whether `--theatre`/`--world-model-db` or
    `--mission-understanding` supplied the *initial* theatre -- plan Stage
    3) -- enters refusal mode, logging that `--world-model-dir` was not
    given.

    **Security ordering, carried over unchanged from `main()`'s own
    startup guard and required at Mode 2 deep analysis**
    (`security-plan-review.md`): the `THEATRE_PROJECTIONS` membership
    check runs *before* `world_model_dir / f"{theatre.lower()}-full.
    sqlite"` is ever built, and before `open_world_model` is ever called
    on it -- an externally-sourced `theatre` string (from a DCS Hook read
    of the live mission, exactly as untrusted as the `.miz`-derived one
    `main()` already guards) must never reach path construction or a
    sqlite URI unvalidated.

    On any failure past that point (store not built, fails to open, or
    fails the built-region mismatch guard): `_enter_refusal_mode` -- the
    revised decision's "loud refusal, not a reduced crew member," not the
    plan's original "keep the old store and log loudly" default.

    On success: builds the new sources at this runner's own emit mode
    (`"every_poll"`, the only mode the poll loop builds a runner
    against), closes the *old* connection only after the new one is
    confirmed open and sources are already pointed at it, and clears
    `crew_console.refused` if it was set -- the next successful mission
    start is this stage's only path out of refusal mode."""
    if event_theatre is None:
        logger.info("mission-start event carries no theatre; keeping current store")
        return
    if not isinstance(event_theatre, str):
        logger.warning(
            "mission-start event theatre is not a string: %r; keeping current store",
            event_theatre,
        )
        return
    if event_theatre == runner.theatre:
        return
    if world_model_dir is None:
        logger.error(
            "mission theatre changed to %r but --world-model-dir was not "
            "given at startup -- cannot resolve a store for it; refusing "
            "player commands until the next mission (re)start",
            event_theatre,
        )
        _enter_refusal_mode(runner, crew_console)
        return
    # Security (carried over from main()'s own startup guard, see this
    # function's docstring): membership check before any path is built.
    if event_theatre not in THEATRE_PROJECTIONS:
        logger.error(
            "mission theatre %r is not a known theatre -- no entry in "
            "coordinates.projections.THEATRE_PROJECTIONS; refusing player "
            "commands until the next mission (re)start",
            event_theatre,
        )
        _enter_refusal_mode(runner, crew_console)
        return
    candidate_db = world_model_dir / f"{event_theatre.lower()}-full.sqlite"
    try:
        new_conn = open_world_model(candidate_db)
    except (sqlite3.Error, OSError) as exc:
        logger.error(
            "world model for %r not built: %s (%s); refusing player "
            "commands until the next mission (re)start",
            event_theatre,
            candidate_db,
            exc,
        )
        _enter_refusal_mode(runner, crew_console)
        return
    try:
        built_region = load_only_region(new_conn)
    except sqlite3.Error as exc:
        new_conn.close()
        logger.error(
            "failed to read built region for %s (%s); refusing player "
            "commands until the next mission (re)start",
            candidate_db,
            exc,
        )
        _enter_refusal_mode(runner, crew_console)
        return
    if built_region is not None and built_region.theatre != event_theatre:
        new_conn.close()
        logger.error(
            "world model %s was built for theatre %r, but the mission "
            "theatre is %r; refusing player commands until the next "
            "mission (re)start",
            candidate_db,
            built_region.theatre,
            event_theatre,
        )
        _enter_refusal_mode(runner, crew_console)
        return

    old_conn = runner.world_model_conn
    runner.sources = _build_sources(
        runner.aircraft_client,
        event_theatre,
        new_conn,
        emit_mode="every_poll",
        trace_sink=trace_sink,
        forest_occlusion=forest_occlusion,
    )
    runner.world_model_conn = new_conn
    runner.theatre = event_theatre
    # `runner.enrichment` was built (if at all) over `old_conn` -- clear it
    # so `run_once`'s lazy build rebuilds fresh against `new_conn` on the
    # next poll, rather than a stale `WorldEnrichmentCache` silently
    # continuing to query a connection this function is about to close.
    runner.enrichment = None
    if old_conn is not None:
        old_conn.close()
    if crew_console is not None:
        crew_console.refused = False
    logger.info("mission theatre switched to %r (%s)", event_theatre, candidate_db)


def _check_for_new_mission(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole | None,
    mission_memory: MissionMemory,
    aircraft_client: AircraftLayerClient,
    world_model_dir: Path | None = None,
    trace_sink: DetectionTraceCollector | None = None,
    forest_occlusion: bool = False,
    fired_on_tracker: FiredOnTracker | None = None,
) -> bool:
    """`BL-15` Stage 1 -- poll `GET /mission_start/latest` and, if its
    `sequence` has moved since the last poll, reset belief/mission memory
    via `_reset_mission_state`, then (Stage 3) re-resolve the theatre/store
    via `_maybe_switch_theatre`. Returns whether a reset was performed this
    call -- callers use this to decide whether to re-roll per-run log files
    too (`_reroll_run_logs`, decision 5), not just for a future spoken
    acknowledgement.

    `fired_on_tracker` is passed straight through to `_reset_mission_state`
    -- see that function's own docstring for why it defaults to `None` and
    what leaving it out would silently break.

    **A genuine reset also arms `runner.pending_mission_start_fire`/
    `pending_mission_start_in_air_check`**, with `mission_start_fresh_
    sample_baseline_t_sim` set to whatever `last_t_sim` held immediately
    before the reset -- `_run_crew_text_poll_loop`'s poll block is what
    actually fires `EffectorTrigger.MISSION_START`/`MISSION_START_IN_AIR`,
    once it has a ownship sample it trusts is not the previous mission's
    stale cached one -- or, if no such sample arrives before
    `MISSION_START_RESOLVE_FALLBACK_S` elapses, once that bounded fallback
    fires instead (dropping the in-air classification rather than guessing
    it from a stale sample; see that poll block's own comment). Not done
    here: this function has no ownship sample of its own to decide
    freshness or airborne-ness from.

    **Does nothing on the very first poll of a process**, even if a
    sequence is already present (the collector may already hold a mission-
    start event from before body-layer connected) -- `runner.last_mission_
    start_sequence is None` is this function's own signal for "never
    checked before," distinct from "sequence 0 was seen," and the plan's
    explicit design choice is that the process just started with clean
    state, so there is nothing to reset yet; firing a reset anyway would be
    harmless but pointless noise (see the plan's "Decisions Requiring User
    Input").

    **`runner.last_mission_start_sequence` is re-assigned *after*
    `_reset_mission_state` returns, not before.** That field is not in
    `ConsolePerceptionRunner.reset_for_new_mission`'s preserved-field list
    (deliberately -- it is per-mission state, same as every other field
    that resets), so a reset wipes it back to `None`; assigning it here
    afterward is what leaves it holding the sequence just processed rather
    than looking like "never checked" for the very next poll.

    **`world_model_dir`/`trace_sink`/`forest_occlusion` default to the
    Stage-1-and-2 no-op values** (`None`/`None`/`False`) so every existing
    test calling this with the original four-argument shape is unaffected
    -- `_maybe_switch_theatre` itself is the only thing that reads them,
    and it is only ever invoked below, after a reset actually fires.

    A transport failure degrades to "skip this poll, try again next
    cycle," never stops the poll loop -- same posture as every other
    aircraft-layer call in this file's poll loops (e.g. `post_look_
    direction`'s own try/except).

    **An unreachable collector is skipped silently, not logged here.**
    This is the one aircraft-layer call that runs *before* `run_once()`
    in the poll loop, so with the collector down it used to print a
    full traceback every poll -- the exact spew `ConnectionReporter`
    exists to prevent. `run_once()`'s own telemetry read hits the same
    dead host a moment later and reports the transition once ("aircraft
    layer disconnected"), so a second message here would only repeat it.
    Anything that is *not* a connection loss (`_is_connection_loss`:
    invalid JSON, a defect of ours) keeps its traceback."""
    try:
        event = aircraft_client.get_mission_start_latest()
    except AircraftLayerError as exc:
        if not _is_connection_loss(exc):
            logger.warning("mission-start poll failed (continuing)", exc_info=True)
        return False
    if event is None:
        return False

    sequence = event.get("sequence")
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        logger.warning("mission-start event missing/invalid 'sequence': %r", event)
        return False

    if runner.last_mission_start_sequence is None:
        runner.last_mission_start_sequence = sequence
        return False
    if sequence == runner.last_mission_start_sequence:
        return False

    logger.info(
        "mission (re)start detected (sequence %d -> %d) -- resetting belief/mission memory",
        runner.last_mission_start_sequence,
        sequence,
    )
    # Captured *before* `_reset_mission_state` wipes `last_t_sim` back to
    # `None` (it is not in `reset_for_new_mission`'s preserved-field list)
    # -- `_run_crew_text_poll_loop`'s poll block uses this as the baseline
    # to recognise the first post-restart ownship sample that is actually
    # fresh, not the previous mission's last cached one (explore-notes,
    # "Two new triggers: mission start").
    pre_reset_t_sim = runner.last_t_sim
    _reset_mission_state(runner, crew_console, mission_memory, fired_on_tracker)
    _maybe_switch_theatre(
        runner,
        crew_console,
        event.get("theatre"),
        world_model_dir,
        trace_sink=trace_sink,
        forest_occlusion=forest_occlusion,
    )
    # Assigned explicitly after the reset, same pattern as `runner.
    # last_mission_start_sequence` just below -- `reset_for_new_mission`'s
    # re-run `__init__` has already put all three back to their declared
    # defaults (False/False/None), which would otherwise leave this
    # mission (re)start with no record that `MISSION_START`/
    # `MISSION_START_IN_AIR` are still owed.
    runner.pending_mission_start_fire = True
    runner.pending_mission_start_in_air_check = True
    runner.mission_start_fresh_sample_baseline_t_sim = pre_reset_t_sim
    # Starts the bounded-fallback clock the resolving block below checks
    # against `MISSION_START_RESOLVE_FALLBACK_S` -- see that field's own
    # docstring for why this is wall-clock time, not a poll count.
    runner.mission_start_resolving_since_wall = time.monotonic()
    runner.last_mission_start_sequence = sequence
    return True


def _reroll_run_logs(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole | None,
    mission_memory: MissionMemory,
    *,
    trace_writer: DetectionTraceWriter | None,
    belief_truth_writer: BeliefTruthLogWriter | None,
    detection_trace_base: Path | None,
    belief_truth_log_base: Path | None,
    speech_log_base: Path | None,
    group_trace_base: Path | None,
    mission_memory_base: Path | None,
    slew_trace_writer: SightTraceWriter | None = None,
    slew_trace_base: Path | None = None,
    when: float | None = None,
) -> tuple[
    DetectionTraceWriter | None, BeliefTruthLogWriter | None, SightTraceWriter | None
]:
    """`BL-15` Stage 1 user decision 5 ("per mission", not a marker line in
    whatever log happened to be open): called once from the poll loop,
    immediately after `_check_for_new_mission` reports it performed a
    reset, re-stamps every per-run log that is actually enabled to a fresh
    filename (`run_log_paths.per_run_log_path`, the same mechanism
    `main()`'s own CLI boundary already applies once at process start --
    `BL-11` Stage 5) and re-wires every writer this poll loop and
    `CrewConsole`/`ConsolePerceptionRunner` hold onto, including the
    closures that captured one by value.

    **The `*_base` paths are each log's pre-stamp path**, i.e. what
    `main()` resolved (default/`~`-expansion applied) *before* calling
    `_per_run_log_paths`/`_resolve_group_trace_log_path`/`_resolve_
    mission_memory_log_path` -- re-stamping the *already-stamped* path
    `main()` passed into the poll loop as this log's working filename
    would double-stamp it (`trace-20261019-120000-20261019-130500.jsonl`),
    so the caller threads the pre-stamp base through separately rather
    than this function trying to strip a stamp back off. `None` means that
    log was never enabled at all -- this function's own no-op for it,
    mirroring `_per_run_log_paths`'s `None`-passes-through convention.

    **Four distinct re-wiring shapes, enumerated because each is a
    different trap, not because the count matters:**

    - `trace_writer`/`belief_truth_writer` hold an **open file handle**
      (`DetectionTraceWriter`/`BeliefTruthLogWriter.__init__` both
      `open(..., "a")` once) -- closed here before the replacement is
      constructed, the only two of the five per-run logs that need this
      (`GroupTraceLogWriter`/`SpeechLogWriter`/`MissionMemoryLogWriter`
      each `open(..., "a")` fresh per write, so simply constructing a new
      instance pointed at the new path is enough -- no handle to leak).
    - **`belief_truth_writer` is also captured by value inside a closure**
      (`_speech_log_sink(belief_truth_writer, runner)`, built once at poll-
      loop startup and assigned to `crew_console.speech_log_sink`) --
      rerolling the local variable alone would leave that closure writing
      to the *old*, now-closed file forever. Re-building the closure over
      the new writer is this function's job, not an incidental extra step;
      missed once, this would be a silent write-to-closed-file failure
      with no exception (the `OSError` guard inside `write_speech`'s own
      try/except would simply disable belief-truth logging for the rest
      of the sortie the first time anything tried to speak).
    - `runner.group_trace_sink` and `crew_console.transcript_log` are
      **plain fields read fresh every call** (no closure capturing the
      writer by value anywhere else), so reassigning them here is the
      whole of the fix.
    - `mission_memory._sink` is the one case `_reset_mission_state` itself
      already touches -- `MissionMemory.reset_for_new_mission` preserves
      the *old* sink across the belief reset (its own docstring: "the one
      field that must survive"), and this function's job is to immediately
      overwrite that just-restored old sink with a new one pointed at the
      new file, which only makes sense once a reset has actually happened
      (this function is never called otherwise).

    `crew_console` is `Optional`: a caller with no `CrewConsole` has no
    `speech_log_sink`/`transcript_log` to re-wire, so `None` skips
    `_reroll_one`'s `speech-log` branch entirely, same "None is a no-op"
    shape as `_reset_mission_state`'s own `crew_console` handling.
    `main()`'s own poll loop always has a real `CrewConsole`.

    `slew_trace_writer`/`slew_trace_base` (`BL-B66` Stage 4b) are the same
    "open file handle, close before replacing" shape `trace_writer` is.

    A directory that has since become unwritable degrades that one log to
    "stop writing it for the rest of this mission" with a line on stderr
    -- mirrors `_per_run_log_paths`'s own startup-time degrade policy
    (never crash the sortie over a log)."""
    stamp_at = time.time() if when is None else when

    def _reroll_one(base: Path | None, label: str) -> Path | None:
        if base is None:
            return None
        stamped = per_run_log_path(base, stamp_at)
        try:
            stamped.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(
                f"{label}: could not create log directory {stamped.parent} "
                f"({exc}); keeping the previous sortie's log open",
                file=sys.stderr,
            )
            return None
        print(f"{label}: writing {stamped} (mission restart)", file=sys.stderr)
        return stamped

    new_detection_trace = _reroll_one(detection_trace_base, "detection-trace")
    if new_detection_trace is not None:
        if trace_writer is not None:
            trace_writer.close()
        trace_writer = DetectionTraceWriter(new_detection_trace)

    new_belief_truth_log = _reroll_one(belief_truth_log_base, "belief-truth-log")
    if new_belief_truth_log is not None:
        if belief_truth_writer is not None:
            belief_truth_writer.close()
        belief_truth_writer = BeliefTruthLogWriter(new_belief_truth_log)
        if crew_console is not None:
            crew_console.speech_log_sink = _speech_log_sink(belief_truth_writer, runner)

    new_speech_log = _reroll_one(speech_log_base, "speech-log")
    if new_speech_log is not None and crew_console is not None:
        crew_console.transcript_log = SpeechLogWriter(new_speech_log).write

    new_group_trace = _reroll_one(group_trace_base, "group-trace")
    if new_group_trace is not None:
        runner.group_trace_sink = GroupTraceLogWriter(new_group_trace).write

    new_mission_memory = _reroll_one(mission_memory_base, "mission-memory")
    if new_mission_memory is not None:
        mission_memory.set_sink(MissionMemoryLogWriter(new_mission_memory).write)

    new_slew_trace = _reroll_one(slew_trace_base, "slew-trace")
    if new_slew_trace is not None:
        if slew_trace_writer is not None:
            slew_trace_writer.close()
        slew_trace_writer = SightTraceWriter(new_slew_trace)

    return trace_writer, belief_truth_writer, slew_trace_writer


def _mark_here_fn(
    memory: MissionMemory, runner: ConsolePerceptionRunner
) -> Callable[[float], str]:
    """Builds `CrewConsole.mark_here_fn` -- the one closure `_handle_
    mark_here` calls, over the live `MissionMemory` this poll thread
    writes observed entries into (BL-8 Stage 3, Decision 6). Reads
    `runner.enrichment` live rather than capturing it, the same reason
    `_speech_log_sink` does: it is rebuilt by `run_once` and a captured
    reference would go stale the first time that happens.

    **Reads `runner.theatre` live too, as of `BL-15` Stage 3** -- it used
    to be a plain `theatre: str` parameter bound once at construction,
    which went stale the moment a mission-start event switched the live
    theatre (`_maybe_switch_theatre`), silently marking under the
    *previous* theatre's coordinate projection. Same fix, same reasoning,
    as `enrichment` above; `runner.theatre` is never `None` once any poll
    has run (`run_once`'s own guard), which this method's caller
    (`_handle_mark_here`, reached only once belief exists) already implies."""

    def mark_here(now_sim: float) -> str:
        if runner.enrichment is None:
            return "no world-model connection configured"
        assert runner.theatre is not None
        entry = marks.mark_here(
            memory,
            runner.enrichment.ownship,
            now_sim,
            theatre=runner.theatre,
            phase=None,
            enrichment=runner.enrichment,
        )
        assert isinstance(entry.payload, MarkPayload)
        return f"mark {entry.payload.index} set"

    return mark_here


def _mark_target_fn(
    memory: MissionMemory, runner: ConsolePerceptionRunner
) -> Callable[[str, float], str]:
    """`_mark_here_fn`'s own twin for `CrewConsole.mark_target_fn`,
    including its `BL-15` Stage 3 live-`runner.theatre` read."""

    def mark_target(contact_id: str, now_sim: float) -> str:
        assert runner.theatre is not None
        entry = marks.mark_target(
            memory,
            runner.store,
            contact_id,
            now_sim,
            theatre=runner.theatre,
            phase=None,
            enrichment=runner.enrichment,
        )
        if entry is None:
            return f"no such contact: {contact_id}"
        assert isinstance(entry.payload, MarkPayload)
        return f"mark {entry.payload.index} set on {contact_id}"

    return mark_target


def _poll_transcripts(
    audio_client: AudioAdapterClient, crew_console: CrewConsole, now_sim: float
) -> None:
    """Drains pending recognised-speech transcripts (`plans/inbound-speech/
    plan.md` Stage 3) and dispatches each through `CrewConsole.
    handle_transcript`. Wrapped in
    its own `try`/`except AudioAdapterError` (log-and-continue), so one
    failed poll never stops the loop.

    Each item is validated field-by-field against `transcript_queue.
    TranscriptEvent.to_dict`'s eight-field shape before dispatch -- a
    malformed/partial item (a schema mismatch, not an expected runtime
    state) is skipped rather than raising. `t_wall` (wall-clock time the adapter recognised the
    clip) is intentionally not threaded into `handle_transcript` --
    `now_sim` is this poll's own DCS sim time, the same clock every other
    dispatch path in this loop already uses. `slots` (`plans/
    watch-reporting/plan.md` Decision 2b-i, replacing the earlier
    single-purpose `bearing_degrees` field) is threaded straight through,
    `None` allowed -- populated only for tokens that take a parsed slot.

    `correlation_id` (`plans/voice-latency-instrumentation/plan.md` Stage 3)
    is the ninth field `TranscriptEvent.to_dict` now carries -- threaded
    through the same way, `None` allowed (an older capture process, or a
    direct `curl`, never supplied one).

    **BL-B96 Stage 4**: a failed/successful poll reports through
    `crew_console.audio_adapter_reporter` (the same instance `CrewConsole.
    _print`'s push path reports through) instead of logging a full
    traceback every failed poll -- `audio-adapter` unreachable is now the
    default-path case (speech is unconditional), not a rare opt-in
    failure, so the old `exc_info=True` posture would flood the log the
    moment a sortie starts before `audio-adapter` does. `None` (every
    test that doesn't wire one) falls back to the old noisy behaviour."""
    try:
        transcripts = audio_client.get_transcripts()
    except AudioAdapterError as exc:
        if crew_console.audio_adapter_reporter is not None:
            crew_console.audio_adapter_reporter.report_failure(exc)
        else:
            logger.warning("transcript poll failed (continuing)", exc_info=True)
        return
    if crew_console.audio_adapter_reporter is not None:
        crew_console.audio_adapter_reporter.report_success()
    for item in transcripts:
        transcript = item.get("transcript")
        confidence = item.get("confidence")
        token = item.get("token")
        match_ratio = item.get("match_ratio")
        verb_anchored = item.get("verb_anchored")
        ambiguous = item.get("ambiguous")
        slots_raw = item.get("slots")
        correlation_id_raw = item.get("correlation_id")
        if not isinstance(transcript, str):
            continue
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            continue
        if token is not None and not isinstance(token, str):
            continue
        if not isinstance(match_ratio, (int, float)) or isinstance(match_ratio, bool):
            continue
        if not isinstance(verb_anchored, bool):
            continue
        if not isinstance(ambiguous, bool):
            continue
        if correlation_id_raw is not None and not isinstance(correlation_id_raw, str):
            continue
        slots: dict[str, int | str] | None = None
        if slots_raw is not None:
            if not isinstance(slots_raw, dict) or not all(
                isinstance(value, (int, str)) and not isinstance(value, bool)
                for value in slots_raw.values()
            ):
                continue
            slots = slots_raw
        crew_console.handle_transcript(
            transcript,
            float(confidence),
            token,
            float(match_ratio),
            verb_anchored,
            ambiguous,
            now_sim,
            slots=slots,
            correlation_id=correlation_id_raw,
        )


#: How often an unconfirmed `watch_args` install is re-sent (`plans/
#: effector-sequences/plan.md` S4.4) -- a transport retry, not Petrovich
#: behaviour, so a plain literal rather than a tunable. Chosen so a lost
#: first datagram recovers well inside `belief.effector_engine.
#: EFFECTOR_CONDITION_READBACK_WAIT_S` (5.0 s default) -- see that
#: tunable's own "cross-key coupling" comment if lowering it.
WATCH_ARGS_RESEND_S: Final[float] = 2.0

#: How long the continuous feed may go unconfirmed before the one-per-
#: mission "is Export.lua current?" WARNING fires (plan S4.5/§4.5).
WATCH_ARGS_UNCONFIRMED_WARN_S: Final[float] = 10.0


def watch_id_for(args: Sequence[int]) -> str:
    """Content-derived id for a watched-arg set (plan §4.2) -- the first
    12 hex digits of `sha1` over the sorted, comma-joined arg list. Not a
    counter: a restarted body-layer sending id 1 again could name a
    *different* set than the one `Export.lua` still has installed under
    that id if a sequence/`polled.toml` edit happened in between; a
    content hash means the same set always gets the same id, which is
    the property the confirmation check (`watch_args_due`) needs."""
    text = ",".join(str(a) for a in sorted(args))
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def watch_args_due(
    latest: Mapping[str, object] | None,
    desired_id: str,
    last_sent_sim: float | None,
    now_sim: float,
) -> bool:
    """`True` when the continuous feed's own install should be (re)sent
    this poll (plan §4.5): due when not confirmed (`latest` is `None`, or
    its own `"watch_id"` does not match `desired_id`) **and**
    (`last_sent_sim` is `None` -- never sent yet -- **or** at least
    `WATCH_ARGS_RESEND_S` sim-seconds have passed since the last send).
    A matching `watch_id` is never due, regardless of `last_sent_sim`."""
    confirmed = latest is not None and latest.get("watch_id") == desired_id
    if confirmed:
        return False
    return last_sent_sim is None or now_sim - last_sent_sim >= WATCH_ARGS_RESEND_S


def _load_effector_config() -> tuple[
    dict[tuple[str, str, str], SequenceFile],
    dict[str, EffectorDef],
    bool,
    PolledSet,
]:
    """Loads the effector registry/sequence files for this runtime's own
    aircraft (`belief.effector_engine.AIRCRAFT`), `plans/
    effector-sequences/plan.md` D5. Called once at `main()` startup,
    before `_run_crew_text_poll_loop` ever runs.

    Every loader underneath is itself non-fatal on bad content (`belief.
    effector_registry.load_registry`/`belief.effector_sequences.
    load_sequences` both collect errors rather than raise); this
    function's own job is only to aggregate **both** loaders' error lists
    (D5: "pulling from BOTH load_registry's and load_sequences' error
    lists so the root cause is visible") into one unmissable console
    banner plus a `logger.error` per finding, and tell the caller whether
    `CrewConsole.config_error_pending` should be set.

    `load_registries_by_aircraft` loads every aircraft directory under
    `config/sequences/` (R13), not only this runtime's own -- a stray
    second aircraft directory's bad registry cannot affect this one
    (each is loaded fully independently), but its errors are still
    surfaced here for visibility rather than silently dropped. The
    registry this function *returns*, however, is only this runtime's
    own aircraft's (`"mi-24p"`) -- a missing directory for it is its own
    synthetic error, the same severity as an unreadable file."""
    registries_by_aircraft = load_registries_by_aircraft()
    own_dir = aircraft_dir_name(EFFECTOR_AIRCRAFT)

    banner_lines: list[str] = []
    for aircraft_dir_name_, (_, reg_errors) in sorted(registries_by_aircraft.items()):
        for err in reg_errors:
            where = f" {err.name!r}" if err.name is not None else ""
            banner_lines.append(
                f"registry[{aircraft_dir_name_}] ({err.scope}{where}): {err.reason}"
            )
    if own_dir not in registries_by_aircraft:
        banner_lines.append(
            f"registry[{own_dir}]: no config/sequences/{own_dir}/ directory found"
        )

    registries_only = {
        name: registry for name, (registry, _) in registries_by_aircraft.items()
    }
    sequences_by_key, sequence_errors = load_sequences(
        DEFAULT_SEQUENCES_DIR, registries_only
    )
    for seq_err in sequence_errors:
        where = f":{seq_err.line}" if seq_err.line is not None else ""
        banner_lines.append(f"sequence[{seq_err.file}{where}]: {seq_err.reason}")

    own_registry, _ = registries_by_aircraft.get(own_dir, ({}, []))
    # `plans/effector-sequences/plan.md` S4.4a: the continuous feed's own
    # arg set, required-args-union-`polled.toml`. A bad `polled.toml`
    # entry joins the same banner/`config_error_pending` posture as a bad
    # registry/sequence file (D5), so it is folded into `banner_lines`
    # before the one banner below is built. `polled_warnings` (an
    # omitted-required-arg) do **not** join the banner -- the behaviour
    # is already correct, so that one is logged separately, below.
    polled, polled_errors, polled_warnings = load_polled_config(
        DEFAULT_SEQUENCES_DIR / own_dir / "polled.toml",
        own_registry,
        REQUIRED_POLLED_ARGS,
    )
    for perr in polled_errors:
        where = f" {perr.name!r}" if perr.name is not None else ""
        banner_lines.append(f"polled[{own_dir}] ({perr.scope}{where}): {perr.reason}")

    if banner_lines:
        banner = "\n".join(
            [
                "=" * 78,
                (
                    "EFFECTOR CONFIG ERROR -- one or more sequence/registry "
                    "files failed to load."
                ),
                "Petrobrain will continue, but some functionality may not work.",
                *banner_lines,
                "=" * 78,
            ]
        )
        print(banner, file=sys.stderr)
        for line in banner_lines:
            logger.error("effector config: %s", line)

    # Stage 1 review follow-up: `EffectorDef.unverified` had no consumer
    # at all -- surfaced here, once, at startup, so "this write is not
    # confirmed against a live sortie" (e.g. `cplr_distr`) is visible
    # without reading the curated TOML.
    unverified_names = sorted(
        name for name, entry in own_registry.items() if entry.unverified
    )
    if unverified_names:
        logger.info(
            "effector config: %d unverified effector(s), not confirmed "
            "against a live sortie: %s",
            len(unverified_names),
            ", ".join(unverified_names),
        )
    for warning_text in polled_warnings:
        logger.warning("effector config: %s", warning_text)
    logger.info(
        "polling %d args: %s",
        len(polled.args),
        ", ".join(f"{polled.names[a]}({a})" for a in polled.args),
    )
    return sequences_by_key, own_registry, bool(banner_lines), polled


def _apply_point_request_transition(
    optic_state: OpticState,
    transition: Literal["clear"] | BoundedSightLook,
) -> OpticState:
    """Apply `CrewConsole.point_request_transition` (`plans/
    9k113-scan-procedure/plan-stage2.md`'s "Supersession") to `optic_state.
    bounded_look`, the one field `CrewConsole` cannot reach directly.

    `look_started_sim` is reset only when the transition actually concerns
    the bounded-look clock -- a bounded look was running before this change
    or `transition` is a fresh `BoundedSightLook` starting one. It is
    **not** reset for a superseding token (`cancel_scan`, `select_target`,
    `engage`, ...) that fires while `bounded_look` was already `None`: that
    token still clears `bounded_look` (a true no-op) but must leave `look_
    started_sim` alone, because the same field also doubles as the sight's
    own per-target look clock (`optic_policy._decide_sighting`'s mid-look
    continuation check) and the idle 3-leg search cycle's per-leg clock
    (`optic_policy._idle_sight_search`'s own docstring). Resetting it
    unconditionally silently abandoned an unrelated, in-progress contact
    look -- its `pending_attempted_at_range_m` entry was then never
    committed or cleared, locking that contact out of every future look
    until the next OBSERV off->on cycle (review-stage2.md Required Fix 1)."""
    new_bounded_look = None if transition == "clear" else transition
    reset_clock = optic_state.bounded_look is not None or new_bounded_look is not None
    return replace(
        optic_state,
        bounded_look=new_bounded_look,
        look_started_sim=(None if reset_clock else optic_state.look_started_sim),
    )


def _run_crew_text_poll_loop(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole,
    aircraft_client: AircraftLayerClient,
    theatre: str,
    world_model_db: Path,
    poll_interval_s: float,
    stop_event: threading.Event,
    speech_client: AudioAdapterClient | None = None,
    speech_input_enabled: bool = False,
    detection_trace_path: Path | None = None,
    eyesight_view: bool = False,
    eyesight_view_radius_m: float = EYESIGHT_DEFAULT_RADIUS_M,
    pov_view: bool = False,
    belief_truth_log_path: Path | None = None,
    forest_occlusion: bool = False,
    mission_memory_path: Path | None = None,
    world_model_dir: Path | None = None,
    detection_trace_base: Path | None = None,
    belief_truth_log_base: Path | None = None,
    speech_log_base: Path | None = None,
    group_trace_base: Path | None = None,
    mission_memory_base: Path | None = None,
    slew_trace_path: Path | None = None,
    slew_trace_base: Path | None = None,
    effector_sequences: Mapping[tuple[str, str, str], SequenceFile] | None = None,
    effector_registry: Mapping[str, EffectorDef] | None = None,
    polled_args: Sequence[int] | None = None,
) -> None:
    """The crew session's background poll thread: opens `world_model_conn`
    and builds `runner.sources` here, on this thread (`sqlite3.Connection`s
    are thread-affine -- see the module docstring's thread-affinity note),
    then keeps calling `runner.run_once()` (which fills `runner.store` and
    updates `runner.last_t_sim`) until `stop_event` is set, plus one extra
    call per poll: `crew_console.drain_events` speaks whatever lifecycle
    events this poll's `tick()` newly surfaced. `speech_input_enabled` (BL-B96: always
    `True` in `main()`'s own wiring; the parameter stays for tests that
    want it off) polls `speech_client.get_transcripts()` via `_poll_
    transcripts` -- `speech_client` is non-`None` whenever `main()` builds
    this loop, but both are still checked so this function has no implicit
    dependency on how its caller constructs them. `detection_trace_path`
    (BL-9, `--detection-trace`), `eyesight_view`/`eyesight_view_radius_m`
    (`--eyesight-view`), `pov_view` (`--pov-view`, `plans/pov-view/
    plan.md`, `BL-B99`), `belief_truth_log_path` (`--belief-truth-log`),
    and `forest_occlusion` (`--forest-occlusion`) are each additive and
    default to a true no-op when unset. When both `eyesight_view` and
    `pov_view` are on, the poll block below splits one terminal's line
    budget between the two frames and prints them together in one
    clear-and-print cycle; either one alone gets the full budget, the
    same posture `eyesight_view` had on its own before this flag existed.

    `world_model_dir`/`detection_trace_base`/`belief_truth_log_base`/
    `group_trace_base`/`mission_memory_base` (`BL-15` Stage 3/Decision 5)
    are each log's pre-stamp path, threaded through so a mission (re)start
    can re-roll them to a fresh per-mission filename (`_reroll_run_logs`)
    -- `None` for a log that was never enabled. `speech_log_base` is the
    pre-stamp path for `--speech-log`, so a mission (re)start also
    re-rolls `crew_console.transcript_log` to a fresh per-mission speech
    log. `slew_trace_path`/`slew_trace_base` (`--slew-trace`, `BL-B66`
    Stage 4b) are the same shape, for the takeoff/power-up/OBSERV wiring
    this writer reads, which only runs on this loop.

    `effector_sequences`/`effector_registry` (`plans/effector-sequences/
    plan.md` Stage 2) are `main()`'s own `_load_effector_config()` result
    -- loaded once at startup, before this thread exists, and passed in
    read-only rather than reloaded per poll or per mission (nothing about
    them is per-mission state; D11's mission-reset is `effector_state`'s
    own job). `None` (every existing call site that predates the engine,
    and this function's own tests that do not exercise effector triggers)
    is treated as "nothing loaded" -- every trigger fires into nothing,
    same as a genuinely empty sequence directory.

    `polled_args` (`plans/effector-sequences/plan.md` Stage 4, S4.4a) is
    `main()`'s own `_load_effector_config()` result's `PolledSet.args` --
    the continuous feed's resolved set, computed once at startup next to
    `effector_sequences`/`effector_registry` above and passed in the same
    read-only way. `None`/empty is treated as "nothing to watch" (the
    poll block below never sends an install, and `refresh_cockpit_switch_
    readback` always sees `None`), same degenerate-but-safe posture as
    `effector_sequences`/`effector_registry`'s own `None` case."""
    effector_sequences_by_key: Mapping[tuple[str, str, str], SequenceFile] = (
        effector_sequences if effector_sequences is not None else {}
    )
    effector_registry_entries: Mapping[str, EffectorDef] = (
        effector_registry if effector_registry is not None else {}
    )
    desired_watch_args: tuple[int, ...] = (
        tuple(polled_args) if polled_args is not None else ()
    )
    desired_watch_id = watch_id_for(desired_watch_args)
    world_model_conn = open_world_model(world_model_db)
    trace_collector = (
        DetectionTraceCollector()
        if (
            detection_trace_path is not None
            or eyesight_view
            or pov_view
            or belief_truth_log_path is not None
        )
        else None
    )
    trace_writer = (
        DetectionTraceWriter(detection_trace_path)
        if detection_trace_path is not None
        else None
    )
    belief_truth_writer = (
        BeliefTruthLogWriter(belief_truth_log_path)
        if belief_truth_log_path is not None
        else None
    )
    if belief_truth_writer is not None:
        crew_console.speech_log_sink = _speech_log_sink(belief_truth_writer, runner)
    slew_trace_writer = (
        SightTraceWriter(slew_trace_path) if slew_trace_path is not None else None
    )
    mission_memory = MissionMemory()
    if mission_memory_path is not None:
        mission_memory.set_sink(MissionMemoryLogWriter(mission_memory_path).write)
    # BL-8 Stage 3: `mark_here`/`mark_target` reach `crew_console` on the
    # REPL/brain thread, not this poll thread -- both must write into the
    # same `MissionMemory` instance this poll thread builds, so the
    # closures over it are handed to `crew_console` here rather than each
    # side building its own. `belief/crew_console.py` never imports
    # `mission_memory` itself (Decision 1) -- these closures are the
    # entire seam. `phase=None` inside both: `CrewConsole` has no
    # `MissionPhaseTracker` of its own to resolve a current phase from,
    # unlike the poll loop's own observed-entry writes just below.
    crew_console.mark_here_fn = _mark_here_fn(mission_memory, runner)
    crew_console.mark_target_fn = _mark_target_fn(mission_memory, runner)
    fired_on_tracker = FiredOnTracker()
    try:
        runner.sources = _build_sources(
            aircraft_client,
            theatre,
            world_model_conn,
            emit_mode="every_poll",
            trace_sink=trace_collector,
            forest_occlusion=forest_occlusion,
        )
        runner.world_model_conn = world_model_conn
        runner.theatre = theatre
        live_los_warned = False
        connection = ConnectionReporter(logger)
        # BL-11 Stage 1: sleep to a deadline, not for a fixed interval after
        # the work -- see `_wait_for_next_tick`.
        next_tick = time.monotonic() + poll_interval_s
        while not stop_event.is_set():
            # One log-and-continue guard around the whole poll body, not
            # just the HTTP call inside `_poll_transcripts` (it catches its
            # own transport errors and nothing else -- the `CrewConsole`
            # dispatch that follows is outside its `try`).
            #
            # **The failure this prevents is silent and costs a whole
            # sortie.** This runs on a daemon thread, so an exception
            # escaping here kills the thread without killing the process:
            # the REPL keeps accepting input, and perception, belief and
            # speech are simply dead from
            # that moment on, with a stderr traceback as the only symptom.
            # Nothing in the cockpit says so. A skipped poll, by contrast,
            # costs one cycle at the configured poll rate
            # (`_DEFAULT_POLL_INTERVAL_S`, 1.0 s since `abf49cd`) and the
            # next one recovers.
            #
            # (This comment used to name a five-hertz rate, and so did two
            # docstrings in `belief/brain_client.py`. All three were wrong
            # and load-bearing: nothing in body-layer's configuration has
            # ever been five hertz -- that is `Export.lua`'s *producer*
            # rate, not this consumer's -- and they are what produced
            # `BL-B30`'s wrong premise that every decay half-life and
            # cadence constant had been tuned against a tick the runtime
            # never ran. `BL-11` Stage 1; the rate is spelled out in words
            # here so `test_no_stale_five_hertz_claims_remain_in_src` can
            # hold the correction mechanically.)
            #
            # Found by the security pass on `plans/watch-reporting/`
            # (`security-review.md`), pre-existing rather than introduced
            # by that branch.
            try:
                # `BL-15` Stage 1: detect a genuine DCS mission (re)start
                # and reset belief/mission memory before this poll's
                # `run_once()` ingests anything against stale state,
                # including the real `CrewConsole`.
                # Stage 3/Decision 5: re-resolve theatre and re-roll the
                # per-run logs only when a reset actually fired.
                if _check_for_new_mission(
                    runner,
                    crew_console,
                    mission_memory,
                    aircraft_client,
                    world_model_dir=world_model_dir,
                    trace_sink=trace_collector,
                    forest_occlusion=forest_occlusion,
                    fired_on_tracker=fired_on_tracker,
                ):
                    trace_writer, belief_truth_writer, slew_trace_writer = (
                        _reroll_run_logs(
                            runner,
                            crew_console,
                            mission_memory,
                            trace_writer=trace_writer,
                            belief_truth_writer=belief_truth_writer,
                            detection_trace_base=detection_trace_base,
                            belief_truth_log_base=belief_truth_log_base,
                            speech_log_base=speech_log_base,
                            group_trace_base=group_trace_base,
                            mission_memory_base=mission_memory_base,
                            slew_trace_writer=slew_trace_writer,
                            slew_trace_base=slew_trace_base,
                        )
                    )
                runner.run_once()
                if runner.optic_state.point_clear_label is not None:
                    # `plans/9k113-scan-procedure/plan-stage2.md` -- a
                    # bounded `look <o'clock>`/`look <compass>` just
                    # completed `POINT_SWEEP_COUNT` traversals with
                    # nothing found. One-shot, cleared the same poll it is
                    # read (`OpticState.point_clear_label`'s own
                    # docstring), so `crew_console.pending_point_clear`
                    # never sees the same label twice.
                    crew_console.pending_point_clear = (
                        runner.optic_state.point_clear_label
                    )
                    runner.optic_state = replace(
                        runner.optic_state, point_clear_label=None
                    )
                if trace_collector is not None:
                    if eyesight_view or pov_view:
                        # Split one terminal's line budget in half when
                        # both views are on; either alone gets the whole
                        # budget (module docstring).
                        view_max_lines = _eyesight_max_lines()
                        if eyesight_view and pov_view:
                            view_max_lines //= 2
                        trace_snapshot = list(trace_collector.records)
                        frames = []
                        if eyesight_view:
                            eyesight_frame = _render_eyesight_frame(
                                runner,
                                trace_snapshot,
                                eyesight_view_radius_m,
                                max_lines=view_max_lines,
                            )
                            if eyesight_frame is not None:
                                frames.append(eyesight_frame)
                        if pov_view:
                            pov_frame = _render_pov_frame(
                                runner, trace_snapshot, max_lines=view_max_lines
                            )
                            if pov_frame is not None:
                                frames.append(pov_frame)
                        if frames:
                            _print_frames(frames)
                    if (
                        belief_truth_writer is not None
                        and runner.last_ownship_state is not None
                    ):
                        belief_truth_writer.write_poll(
                            trace_collector,
                            runner.store,
                            runner.last_ownship_state,
                            attack_run_target_contact_id=(
                                runner.attack_run_state.last_contact_id
                                if runner.attack_run_state is not None
                                else None
                            ),
                        )
                    if trace_writer is not None:
                        trace_writer.write_poll(trace_collector, runner.store)
                    else:
                        trace_collector.records.clear()
                live_los_warned = _warn_live_los_coverage_gap_once(
                    runner.sources, live_los_warned
                )
                if runner.last_t_sim is not None:
                    crew_console.enrichment = runner.enrichment
                    # `[[BL-B82]]`, replacing `plans/spu8-intercom/
                    # plan.md` Stage 5's one-shot silence default: refresh
                    # `on_ground` every poll a real ownship state is
                    # available, same as `enrichment` above, so a look
                    # command dispatched this same poll (below) sees the
                    # current ground/air state rather than a one-shot
                    # latch from mission start.
                    if runner.last_ownship_state is not None:
                        # `BL-B66` Stage 2 (`plans/9k113-effectors/
                        # plan.md` §2): captured *before* `on_ground` is
                        # reassigned below, so the comparison just after
                        # sees the transition rather than the new value
                        # twice.
                        was_on_ground = crew_console.on_ground
                        crew_console.on_ground = (
                            runner.last_ownship_state.alt_agl_m
                            <= ON_GROUND_AGL_THRESHOLD_M
                        )
                        # `plans/9k113-scan-procedure/plan-stage2.md`,
                        # "Attack-run interaction" -- refreshed every poll,
                        # same as `on_ground` above, so a `look <where>`
                        # dispatched this same poll (below) sees whether a
                        # run is currently *engaged* (`runner.
                        # attack_run_state is not None`, the same test
                        # `_active_gaze`'s own `attack_run_engaged`
                        # parameter already uses), not merely selected.
                        crew_console.attack_run_engaged = (
                            runner.attack_run_state is not None
                        )
                        # `plans/9k113-scan-procedure/plan-stage2.md`,
                        # "What 'ready' means" -- refreshed every poll, so
                        # `drain_pending_point_request` can wait for the
                        # phase cycle actually reaching `SIGHTING` (not
                        # merely the power-up lamp, already checked
                        # synchronously at `_handle_observ_on`) without
                        # reaching into `runner.optic_state` itself.
                        crew_console.sight_phase_is_sighting = (
                            runner.optic_state.home_phase is OpticPhase.SIGHTING
                        )
                        # `plans/effector-sequences/plan.md` Stage 2's own
                        # poll-block ordering: refresh readback -> takeoff
                        # edge fires -> transitions fire -> advance ->
                        # ready edge -> drain_config_error. Stage 4 narrows
                        # what "refresh readback" fetches: only the
                        # continuous feed (polled.toml ∪ REQUIRED_POLLED_
                        # ARGS) -- the engine's own one-shot reads
                        # (`advance_effectors` -> `client.read_args`) are
                        # no longer sourced from here at all.
                        try:
                            watched_args_latest = (
                                aircraft_client.get_watched_args_latest()
                            )
                        except AircraftLayerError:
                            watched_args_latest = None
                        if (
                            watched_args_latest is None
                            and not runner.watched_args_unavailable_warned
                        ):
                            logger.warning(
                                "watched-args feed unavailable -- collector "
                                "older than this body-layer?"
                            )
                            runner.watched_args_unavailable_warned = True
                        # A line for a different set is never used -- it
                        # may lack args this set needs, which would read
                        # as "unknown" piecemeal rather than the honest
                        # "unconfirmed" state.
                        watched_args_confirmed = (
                            watched_args_latest is not None
                            and watched_args_latest.get("watch_id") == desired_watch_id
                        )
                        readback_args = (
                            watched_args_latest.get("args")
                            if watched_args_confirmed
                            and watched_args_latest is not None
                            else None
                        )
                        if watch_args_due(
                            watched_args_latest,
                            desired_watch_id,
                            runner.watch_args_last_sent_sim,
                            runner.last_t_sim,
                        ):
                            try:
                                aircraft_client.set_watch_args(
                                    desired_watch_id, list(desired_watch_args)
                                )
                            except AircraftLayerError:
                                logger.debug("set_watch_args failed", exc_info=True)
                            runner.watch_args_last_sent_sim = runner.last_t_sim
                        if (
                            not watched_args_confirmed
                            and runner.watch_args_last_sent_sim is not None
                            and not runner.watch_args_unconfirmed_warned
                            and (
                                runner.last_t_sim - runner.watch_args_last_sent_sim
                                >= WATCH_ARGS_UNCONFIRMED_WARN_S
                            )
                        ):
                            logger.warning(
                                "Export.lua has not confirmed the watched-arg "
                                "set after %.0fs -- is the deployed Export.lua "
                                "current? (collector log: VERSION MISMATCH)",
                                WATCH_ARGS_UNCONFIRMED_WARN_S,
                            )
                            runner.watch_args_unconfirmed_warned = True
                        runner.guidance_unit_state = refresh_cockpit_switch_readback(
                            runner.guidance_unit_state,
                            readback_args,
                        )
                        is_sight_ready = guidance_unit_sight_ready(
                            runner.guidance_unit_state
                        )
                        # Refreshed every poll, same as `on_ground` --
                        # `_handle_observ_on` reads this to gate the
                        # command (plan §3).
                        crew_console.sight_ready = is_sight_ready
                        # Mission-start triggers (explore-notes, "Two new
                        # triggers: mission start"), and the one reason
                        # `TAKEOFF`'s own edge check below is skipped
                        # entirely while either flag is still pending.
                        #
                        # `_check_for_new_mission` cannot fire these
                        # itself -- it runs before `runner.run_once()`
                        # each poll and has no ownship sample of its own,
                        # and mission-start detection can arrive a poll or
                        # more before `Export.lua` resumes sending (the
                        # collector keeps serving the previous mission's
                        # last cached telemetry meanwhile). So it only
                        # arms `pending_mission_start_fire`/
                        # `pending_mission_start_in_air_check`, and this
                        # block waits for the first sample whose `t_sim`
                        # *differs* from `mission_start_fresh_sample_
                        # baseline_t_sim` (the value held immediately
                        # before the reset) -- `!=`, not `<`: DCS model
                        # time need not be smaller after a restart than
                        # whatever the previous mission's clock happened
                        # to reach (a restart moments into a short
                        # mission could easily have a *larger* baseline
                        # than the new mission's own early samples), so a
                        # strict-decrease check can wait forever; the
                        # stale cached sample, by contrast, is the exact
                        # same object every poll until a real one lands,
                        # so its `t_sim` is bit-identical and any
                        # genuinely new sample's `t_sim` differs from it.
                        # User, confirming the DCS fact this check leans on:
                        # "Mission restart always resets the mission
                        # elapsed timer in DCS" -- so a real restart's
                        # fresh samples almost always differ from the
                        # pre-reset baseline on the first poll; the
                        # coincidence this leaves open (a restart landing
                        # near `t_sim = 0` whose first fresh sample happens
                        # to match the baseline exactly) is covered by the
                        # bounded fallback below
                        # (`MISSION_START_RESOLVE_FALLBACK_S`).
                        mission_start_resolving = (
                            runner.pending_mission_start_fire
                            or runner.pending_mission_start_in_air_check
                        )
                        if mission_start_resolving:
                            baseline = runner.mission_start_fresh_sample_baseline_t_sim
                            fresh_sample_confirmed = (
                                baseline is None
                                or runner.last_ownship_state.t_sim != baseline
                            )
                            # Bounded fallback (`MISSION_START_RESOLVE_
                            # FALLBACK_S`'s own declaration comment and
                            # `mission_start_resolving_since_wall`'s own
                            # docstring for why this is wall-clock, not a
                            # poll count): reached either by the rare
                            # `t_sim`-coincidence case the `!=` check above
                            # cannot resolve on its own, *or* by no fresh
                            # sample having arrived at all within the
                            # window (a long mission-load screen, or a
                            # mission that starts paused) -- the two are
                            # indistinguishable from here, so `fallback_due`
                            # never fires `MISSION_START_IN_AIR` below:
                            # only `fresh_sample_confirmed` may.
                            resolving_since = runner.mission_start_resolving_since_wall
                            fallback_due = not fresh_sample_confirmed and (
                                resolving_since is not None
                                and time.monotonic() - resolving_since
                                >= MISSION_START_RESOLVE_FALLBACK_S
                            )
                            if fallback_due:
                                logger.warning(
                                    "mission-start resolving window hit its "
                                    "%.0fs fallback with no fresh t_sim "
                                    "(baseline=%r) -- firing MISSION_START "
                                    "anyway, but dropping the MISSION_START_"
                                    "IN_AIR check for this mission (re)start "
                                    "(a stale sample's on_ground cannot be "
                                    "trusted to classify it)",
                                    MISSION_START_RESOLVE_FALLBACK_S,
                                    baseline,
                                )
                            if fresh_sample_confirmed or fallback_due:
                                if runner.pending_mission_start_fire:
                                    # Fires unconditionally, on either path
                                    # -- `MISSION_START` is a one-shot setup
                                    # hook that does not depend on air
                                    # state, so it need not wait for a
                                    # fresh sample at all.
                                    runner.effector_state = fire_effector_trigger(
                                        runner.effector_state,
                                        EffectorTrigger.MISSION_START,
                                        runner.last_t_sim,
                                    )
                                    runner.pending_mission_start_fire = False
                                if runner.pending_mission_start_in_air_check:
                                    # `crew_console.on_ground` was just
                                    # reassigned above, from this same
                                    # fresh sample -- this *is* "decide it
                                    # on the first real ownship sample
                                    # after the mission start". Gated on
                                    # `fresh_sample_confirmed`, not just
                                    # `not crew_console.on_ground`: see the
                                    # comment below for why a fallback-
                                    # forced resolution must never reach
                                    # this fire at all.
                                    if (
                                        fresh_sample_confirmed
                                        and not crew_console.on_ground
                                    ):
                                        runner.effector_state = fire_effector_trigger(
                                            runner.effector_state,
                                            EffectorTrigger.MISSION_START_IN_AIR,
                                            runner.last_t_sim,
                                        )
                                    # fallback_due-only case: no fresh
                                    # sample ever arrived, so
                                    # `crew_console.on_ground` here is still
                                    # the *previous* mission's stale cached
                                    # value -- drop the check rather than
                                    # classify this mission from the wrong
                                    # mission's data; unlike the coincidence
                                    # case this would not self-heal, since
                                    # the pending flag is cleared either way.
                                    runner.pending_mission_start_in_air_check = False
                                runner.mission_start_resolving_since_wall = None
                            # `TAKEOFF` is suppressed for every poll this
                            # mission (re)start is still resolving,
                            # including the one that just resolved it --
                            # that poll establishes `crew_console.
                            # on_ground`'s own new-mission baseline
                            # without treating it as a transition (an air
                            # start must never also read as a takeoff).
                        # D2/D4 (`plans/effector-sequences/plan.md`):
                        # fires on **every** real ground->air transition,
                        # no `takeoff_seen` latch -- the takeoff sequence
                        # file's own row conditions (R12's implicit
                        # self-check) make a repeat takeoff a no-op. Never
                        # reached on an air start: that case is handled
                        # entirely by the `mission_start_resolving` branch
                        # above, which suppresses this `elif` for the
                        # whole resolving window.
                        elif was_on_ground and not crew_console.on_ground:
                            runner.effector_state = fire_effector_trigger(
                                runner.effector_state,
                                EffectorTrigger.TAKEOFF,
                                runner.last_t_sim,
                            )
                        # `plans/attack-run/plan.md` Stage 5 -- apply
                        # whatever `engage`/`disengage` the previous
                        # poll's command dispatch left as a one-shot
                        # signal (`CrewConsole.attack_run_transition`'s
                        # own docstring on why this class cannot replace
                        # `runner.attack_run_state` directly), then drain
                        # one tick of guidance **immediately before**
                        # `drain_events` -- Decision 1's ordering: a
                        # guidance line wins the tick by being drained
                        # first, deferring (never dropping) the
                        # scheduler's own candidates.
                        if crew_console.attack_run_transition == "engage":
                            runner.attack_run_state = AttackRunState()
                            crew_console.attack_run_transition = None
                        elif crew_console.attack_run_transition == "disengage":
                            runner.attack_run_state = None
                            crew_console.attack_run_transition = None
                        # `BL-B64` Stage 2, direction §6 -- the same
                        # one-shot-signal shape `attack_run_transition`
                        # just used: `_handle_observ_on`/`_handle_observ_
                        # off` leave this for the poll loop rather than
                        # mutating `runner.optic_state` directly (`belief`
                        # has no reference to it -- the same division
                        # `drain_attack_run`'s own docstring states for
                        # `attack_run_state`). Entering OBSERV also starts
                        # the 1 s hand-movement suppression (direction §6);
                        # leaving it does too -- the pilot's hand is on the
                        # switch either way.
                        #
                        # **`home_phase` itself no longer changes here**
                        # (`[[BL-B80]]`, closing the carried-forward
                        # `BL-B66` gap) -- `run_once` derives it every poll
                        # from the *observed* arg-886 edge instead, so it
                        # also follows DCS's own automatic OBSERV-off (a
                        # hard manoeuvre) and not only this command. This
                        # block still drives the hands-busy suppression,
                        # which is about the pilot's hand moving to the
                        # switch, not the observed edge -- the cockpit
                        # write itself is now the engine's job
                        # (`plans/effector-sequences/plan.md` Stage 2),
                        # fired here and performed by `advance_effectors`
                        # below.
                        if crew_console.observ_transition == "on":
                            runner.optic_state = replace(
                                runner.optic_state,
                                hands_busy_until_sim=(
                                    runner.last_t_sim + HANDS_BUSY_DURATION_S
                                ),
                            )
                            # `_handle_observ_on` has already gated this
                            # on `sight_ready` at command time (plan §3),
                            # so reaching here means the request was
                            # accepted.
                            runner.effector_state = fire_effector_trigger(
                                runner.effector_state,
                                EffectorTrigger.OBSERV_ON,
                                runner.last_t_sim,
                            )
                            crew_console.observ_transition = None
                        elif crew_console.observ_transition == "off":
                            runner.optic_state = replace(
                                runner.optic_state,
                                hands_busy_until_sim=(
                                    runner.last_t_sim + HANDS_BUSY_DURATION_S
                                ),
                            )
                            runner.effector_state = fire_effector_trigger(
                                runner.effector_state,
                                EffectorTrigger.OBSERV_OFF,
                                runner.last_t_sim,
                            )
                            crew_console.observ_transition = None
                        # `BL-B66` Stage 4 (plan §4/Co-moving Fields) --
                        # the weapons safety bar (arg 673), same one-shot-
                        # signal shape as `observ_transition` above. Set by
                        # `_handle_weapons_armed`/`_handle_weapons_safe`
                        # or by `_handle_engage`'s own existing "any
                        # attack run start" trigger.
                        if crew_console.weapon_safety_transition == "armed":
                            runner.effector_state = fire_effector_trigger(
                                runner.effector_state,
                                EffectorTrigger.WEAPONS_ARM,
                                runner.last_t_sim,
                            )
                            crew_console.weapon_safety_transition = None
                        elif crew_console.weapon_safety_transition == "safe":
                            runner.effector_state = fire_effector_trigger(
                                runner.effector_state,
                                EffectorTrigger.WEAPONS_SAFE,
                                runner.last_t_sim,
                            )
                            crew_console.weapon_safety_transition = None
                        # Advances every currently-running trigger by at
                        # most one write each, in fire order (D9) --
                        # takeoff and any of the four transitions fired
                        # above all progress in this one call. No
                        # `readback` argument any more (Stage 4) -- each
                        # running trigger makes its own one-shot
                        # `client.read_args(...)` call internally.
                        runner.effector_state = advance_effectors(
                            runner.effector_state,
                            runner.last_t_sim,
                            aircraft_client,
                            effector_sequences_by_key,
                            effector_registry_entries,
                        )
                        # The "Guidance unit ready" edge, after the
                        # engine has had a chance to run this poll (plan's
                        # own poll-block ordering) -- unaffected either
                        # way, since `ready_observed` is a readback field
                        # the engine never writes, but kept in the stated
                        # order rather than silently reordered. Called
                        # every poll, unconditionally -- not only while
                        # `is_sight_ready` -- so an observed unlit poll
                        # (power-down, or no lamp reading yet) is tracked
                        # too; otherwise a power cycle's falling edge
                        # would never update `guidance_unit_ready_prev_
                        # observed`, and the later rising edge would not
                        # be recognised as one (bug fix, `plans/
                        # 9k113-sight-pointing/plan.md` decision 2).
                        runner.guidance_unit_state = replace(
                            runner.guidance_unit_state,
                            guidance_unit_ready_prev_observed=(
                                crew_console.drain_guidance_unit_ready(
                                    runner.last_t_sim,
                                    ready_observed=(
                                        runner.guidance_unit_state.ready_observed
                                    ),
                                    previously_observed=(
                                        runner.guidance_unit_state.guidance_unit_ready_prev_observed
                                    ),
                                )
                            ),
                        )
                        # D5/D6 (`plans/effector-sequences/plan.md`): the
                        # one-shot "bad sequence file" line, held until
                        # the SPU-8 intercom gate reads open. Only fetch
                        # `/spu8/state` while the flag it serves is still
                        # pending -- `drain_config_error` clears it after
                        # one successful speak, so this GET fires at most
                        # once per process lifetime in the common case
                        # (no bad file), not on every poll of every sortie
                        # (performance review, `plans/effector-sequences/
                        # performance-stage1-2.md`).
                        intercom_open = False
                        if crew_console.config_error_pending:
                            spu8_latest = aircraft_client.get_spu8_state_latest()
                            intercom_open = (
                                spu8_latest is not None
                                and spu8_latest.get("gate_open") is True
                            )
                        crew_console.drain_config_error(
                            runner.last_t_sim, intercom_open=intercom_open
                        )
                        runner.attack_run_state = crew_console.drain_attack_run(
                            runner.attack_run_state,
                            runner.last_t_sim,
                            runner.last_ownship_state,
                            # Review's required fix (`BL-B71`), corrected
                            # 2026-10-16 (user direction: "actual behavior
                            # must measure by used optic"): `runner.optic`,
                            # not `runner.optic_state.guidance_optic`. The
                            # latter is the ladder's own standing *grant*
                            # and is `None` through ordinary glassing
                            # (`OpticPhase.GLASSING` with no guidance
                            # request at all), which would misattribute a
                            # live binocular look as "too far" against the
                            # naked eye's own narrower threshold. `runner.
                            # optic` is `optic_decision.optic` from this
                            # same poll's `decide_optic` call (inside
                            # `run_once`, earlier this poll, assigned at
                            # `self.optic = optic_decision.optic` and onto
                            # `source.optic` by `_apply_active_gaze`) --
                            # the exact optic `perception.visibility.
                            # check_visibility` resolved this tick's
                            # percepts against, so it is not one poll stale
                            # the way `self.attack_run_state.requested_
                            # optic` (read the other direction, into
                            # `decide_optic` above) deliberately is.
                            resolving_optic=runner.optic,
                        )
                        # `plans/attack-run-los/plan.md` F3 -- "where is
                        # it?"'s one-shot signal, consumed right beside
                        # `drain_attack_run` above with the same inputs
                        # (`runner.attack_run_state`/`runner.
                        # last_ownship_state`/`runner.optic`): a true
                        # no-op whenever `crew_console.where_is_it_
                        # requested` is `False`, since `drain_where_is_it`
                        # itself clears the flag inline (`_handle_where_
                        # is_it`'s own one-shot-signal shape).
                        if crew_console.where_is_it_requested:
                            crew_console.drain_where_is_it(
                                runner.attack_run_state,
                                runner.last_t_sim,
                                runner.last_ownship_state,
                                resolving_optic=runner.optic,
                            )
                            crew_console.where_is_it_requested = False
                            # `[[BL-B102]]`'s co-moving field, cleared
                            # alongside the flag above -- never left
                            # holding an already-answered request's slots.
                            crew_console.where_is_it_slots = None
                        # `[[BL-B80]]` v2: send the head's current world
                        # goal every poll while `sight_head.mode ==
                        # "free"` -- idle included, since the idle sight
                        # always carries a real in-regard aim, so there is
                        # always something valid to send (no special case
                        # needed). `t_sim` is the telemetry the decision
                        # used -- the look's own `last_seen_t_look` for a
                        # `seen`/`held` goal, this poll's own `t_sim`
                        # otherwise (the plan's "Wire (sight_target)"
                        # section). A dropped write degrades to
                        # "Export.lua keeps re-asserting whatever goal it
                        # last received" -- never stops the poll loop.
                        if runner.sight_head.mode == "free":
                            goal_az = runner.sight_head.goal_world_az_deg
                            goal_el = runner.sight_head.goal_world_el_deg
                            if goal_az is not None and goal_el is not None:
                                goal_t_sim = (
                                    runner.sight_head.last_seen_t_look
                                    if runner.sight_head.aim_source in ("seen", "held")
                                    and runner.sight_head.last_seen_t_look is not None
                                    else runner.last_t_sim
                                )
                                try:
                                    write_sight_target(
                                        aircraft_client,
                                        goal_az,
                                        goal_el,
                                        runner.sight_head.goal_rate_az_deg_s,
                                        runner.sight_head.goal_rate_el_deg_s,
                                        goal_t_sim,
                                    )
                                except AircraftLayerError:
                                    logger.warning(
                                        "sight-target write failed (continuing)",
                                        exc_info=True,
                                    )
                        # `BL-B66` Stage 4b: every poll a real ownship
                        # state exists (the same guard the guidance-unit/
                        # OBSERV block above this is nested under), after
                        # that block has had its turn to update `optic_
                        # state`/`guidance_unit_state`/`sight_head` this
                        # poll -- never before, or the row would log last
                        # poll's values under this poll's timestamp.
                        if slew_trace_writer is not None:
                            try:
                                sight_servo_latest = (
                                    aircraft_client.get_sight_servo_latest()
                                )
                            except AircraftLayerError:
                                sight_servo_latest = None
                            slew_trace_writer.write_poll(
                                runner.last_t_sim,
                                runner.optic_state,
                                runner.guidance_unit_state,
                                runner.sight_head,
                                sight_servo_latest,
                                commanded_values=runner.effector_state.commanded_values,
                            )
                    # BL-8: after `run_once()` has settled this poll's
                    # belief, before `drain_events` -- Decision 3's
                    # ordering (a mark's seq exists before anything that
                    # might want to name it is drained).
                    phase = (
                        runner.mission_phase_tracker.current_phase()
                        if runner.mission_phase_tracker is not None
                        else None
                    )
                    # `BL-15` Stage 3: `runner.theatre`, not the closed-over
                    # `theatre` parameter -- a successful theatre switch
                    # (`_maybe_switch_theatre`) updates `runner.theatre` in
                    # place, and the local parameter above is only this
                    # poll loop's *initial* value, never reassigned.
                    assert runner.theatre is not None
                    _mission_memory_step(
                        mission_memory,
                        runner,
                        runner.last_t_sim,
                        runner.theatre,
                        phase,
                        fired_on_tracker,
                    )
                    crew_console.drain_events(runner.last_t_sim)
                    # `plans/voice-latency-instrumentation/plan.md` Stage 6
                    # -- speaks any positional readback deferred because the
                    # channel was modeled busy at command time, once it has
                    # cleared. Same per-poll hook point as `drain_events`/
                    # `drain_brain`.
                    crew_console.drain_pending_positional_replies(runner.last_t_sim)
                    # `plans/9k113-scan-procedure/plan-stage2.md` -- speaks
                    # a bounded `look`'s "<where> clear." once set (above),
                    # same per-poll hook point as `drain_events`/
                    # `drain_pending_positional_replies`/`drain_brain`.
                    crew_console.drain_pending_point_clear(runner.last_t_sim)
                    # `plans/9k113-scan-procedure/plan-stage2.md` -- drains
                    # a deferred `look <where>` queued while OBSERV was off
                    # and now confirmed on, once the sight phase actually
                    # reaches `SIGHTING`.
                    crew_console.drain_pending_point_request(runner.last_t_sim)
                    # `plans/brain-layer/plan.md` D2 -- drains whatever
                    # `brain_client.poll_replies()` has decided since the
                    # last poll. A true no-op for NullBrainClient and
                    # DebugPrintBrainClient, both of which return [].
                    crew_console.drain_brain(runner.last_t_sim)
                    commands_before = crew_console.commands_handled
                    if speech_input_enabled and speech_client is not None:
                        _poll_transcripts(
                            speech_client, crew_console, runner.last_t_sim
                        )
                    if crew_console.commands_handled != commands_before:
                        # Any command lowers the binoculars (`plans/
                        # binocular-optic/plan.md` D4) -- not per command
                        # kind: the pilot asking for something is itself
                        # evidence that what Petrovich is doing matters
                        # less than what was just asked for. Counted rather
                        # than inspected so this stays true for a command
                        # surface added later.
                        #
                        # (Reads "kind" rather than "type" because a
                        # comment line starting `# type:` is a *type
                        # comment* to mypy, not prose -- re-indenting this
                        # block under the new guard reflowed the word to
                        # the line start and mypy reported a syntax error
                        # CPython's own parser accepts happily.)
                        #
                        # `plans/sortie-2026-09-26-fixes/decisions.md`
                        # Decision 2's one carve-out: `follow <target>`
                        # naming the contact already being glassed is a
                        # request to continue, not to stop -- lowering and
                        # immediately re-pointing at the same target would
                        # be strictly worse than doing nothing. Every other
                        # dispatched command keeps the unconditional-lower
                        # default above.
                        already_on_target = (
                            crew_console.last_command_target_contact_id is not None
                            and runner.optic_state.phase is OpticPhase.GLASSING
                            and runner.optic_state.look_contact_id
                            == crew_console.last_command_target_contact_id
                        )
                        if not already_on_target:
                            runner.optic_state = lower_binoculars(
                                runner.optic_state, runner.last_t_sim
                            )
                    # `plans/9k113-scan-procedure/plan-stage2.md`'s
                    # "Supersession" -- a one-shot signal `crew_console`
                    # sets (a new `look`/`scan`/cancel/task-changing
                    # command dispatched this poll, or `drain_pending_
                    # point_request` finally starting a deferred look),
                    # applied here to `runner.optic_state.bounded_look`,
                    # the one field `CrewConsole` cannot reach directly.
                    # `None` (the common case: nothing to apply) is a true
                    # no-op. See `_apply_point_request_transition`'s own
                    # docstring for what it does to `look_started_sim` and
                    # why.
                    if crew_console.point_request_transition is not None:
                        runner.optic_state = _apply_point_request_transition(
                            runner.optic_state,
                            crew_console.point_request_transition,
                        )
                        crew_console.point_request_transition = None
                connection.report_success()
            except Exception as exc:
                # Deliberately bare-ish: anything at all, because the
                # alternative is a dead crew member the pilot cannot see.
                # `logger.exception` keeps the traceback, so a real defect
                # is still diagnosable after the flight rather than hidden
                # -- but a dead collector is not a defect, and repeating
                # its traceback every poll buries the ones that are.
                if _is_connection_loss(exc):
                    connection.report_failure(exc)
                else:
                    logger.exception("crew-text poll cycle failed; continuing")
            next_tick = _wait_for_next_tick(stop_event, next_tick, poll_interval_s)
    finally:
        _log_live_los_coverage_summary(runner.sources)
        if trace_writer is not None:
            trace_writer.close()
        if belief_truth_writer is not None:
            belief_truth_writer.close()
        if slew_trace_writer is not None:
            slew_trace_writer.close()
        world_model_conn.close()


def _run_crew_text_repl(
    runner: ConsolePerceptionRunner,
    crew_console: CrewConsole,
    world_model_db: Path,
    theatre: str,
) -> None:
    """The crew session's foreground REPL: reads one line at a time from
    stdin and dispatches it into `CrewConsole.handle_line`.

    **BL-B96 fix (found while porting a `--console`-path regression test
    rather than discarding it, confirmed by grep: `_run_crew_text_repl` had
    zero direct tests before)**: this used to copy `crew_console.enrichment`
    straight from `runner.enrichment` -- `ConsolePerceptionRunner.
    enrichment` is built by the poll thread (a separate real thread from
    this REPL loop) and holds *that thread's* `sqlite3.Connection`, which is
    thread-affine. Any enrichment-aware command run from this thread then
    queried that connection and raised `sqlite3.ProgrammingError` -- exactly
    the same bug class the old `--console` REPL was fixed for (BL-5,
    `plans/bl5-tool-api/debug.md`), just never ported to this twin. BL-B96
    makes this the *only* REPL, and `--crew-text` unconditional, so this
    bug's blast radius goes from "only when `--console` was used" to
    "every player-issued report command touching terrain" -- worth fixing
    now rather than carrying forward.

    Mirrors the old `--console` REPL's own fix exactly: build a REPL-
    thread-local `sqlite3.Connection`/`EnrichmentContext`, lazily, the first
    time `runner.last_ownship_state` is available, and refresh its
    `ownship` from that field before every command rather than reading
    `runner.enrichment` at all. Two separate connections/caches (poll
    thread's and REPL thread's) rather than one shared one -- the same
    accepted cost the old fix took, for the same reason."""
    repl_conn: sqlite3.Connection | None = None
    repl_enrichment: EnrichmentContext | None = None
    try:
        for line in sys.stdin:
            now_sim = runner.last_t_sim if runner.last_t_sim is not None else 0.0
            if runner.last_ownship_state is not None:
                if repl_conn is None:
                    repl_conn = open_world_model(world_model_db)
                if repl_enrichment is None:
                    repl_enrichment = EnrichmentContext(
                        conn=repl_conn,
                        theatre=theatre,
                        ownship=runner.last_ownship_state,
                    )
                else:
                    repl_enrichment.ownship = runner.last_ownship_state
            crew_console.enrichment = repl_enrichment
            crew_console.handle_line(line, now_sim=now_sim)
    except KeyboardInterrupt:
        pass
    finally:
        if repl_conn is not None:
            repl_conn.close()


DEFAULT_SPEECH_LOG_PATH = Path("logs/speech.jsonl")


def _resolve_speech_log_path(
    *,
    speech_log: Path | None,
    no_speech_log: bool,
) -> Path | None:
    """Decide what `--speech-log` should end up pointing at, after
    argparse's own mutual-exclusivity check has already run.

    An ordinary sortie (no explicit `--speech-log`, no `--no-speech-log`)
    gets `DEFAULT_SPEECH_LOG_PATH` without the user having to remember a
    flag -- that is precisely when the garbled-transcript data this file
    exists for gets produced. `--no-speech-log` opts back out; an explicit
    `--speech-log` always wins. (BL-B96: the crew session and speech
    input are both unconditional now, so this no longer gates on a
    `--crew-text`/`--speech-input` pair -- every run is "an ordinary
    sortie" in that sense.)

    Directory creation happens at startup, once, rather than per write --
    so an unwritable location degrades to no log (reported on stderr)
    instead of crashing a sortie over a debug artifact. **The `mkdir` below
    covers only the default path; `_per_run_log_paths` does the same for
    all three resolved logs, including an explicit `--speech-log`, so an
    explicit path is no longer the exception it was when this paragraph
    was first written.** So the policy now is uniform: a missing parent is
    created wherever the path came from, and a parent that cannot be
    created costs that one log, reported once on stderr by
    `_per_run_log_paths`, not per write and not silently.

    That is a change in behaviour and an improvement -- an explicit
    `--speech-log` under a missing directory previously failed *every*
    write via `SpeechLogWriter.write`'s own per-call try/except
    (`CrewConsole._log_transcript`), with no startup line saying so. That
    per-call guard still exists and still catches a path that goes bad
    mid-sortie; it is simply no longer the first thing a missing parent
    hits.

    The `mkdir` here is therefore a strictly earlier report of a condition
    `_per_run_log_paths` would also catch, and what it buys is cosmetic
    rather than structural: a speech-log-specific message, raised before
    the generic per-log one. It is **not** what keeps the "writing <path>"
    startup line honest -- `per_run_log_path` uses `Path.with_name`, so the
    parent is identical and `_per_run_log_paths`' own `resolve` mkdirs the
    same directory and returns `None` on any of `_RESOLVE_FAILURES`,
    `OSError` among them. Verified by execution
    2026-10-06: with `logs` occupied by a regular file, `_per_run_log_paths`
    alone reports the failure and returns `(None, None, None)`.
    """
    if speech_log is not None:
        return speech_log
    if no_speech_log:
        return None
    try:
        DEFAULT_SPEECH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(
            f"speech-log: could not create default log directory "
            f"{DEFAULT_SPEECH_LOG_PATH.parent} ({exc}); continuing without "
            f"a speech log",
            file=sys.stderr,
        )
        return None
    return DEFAULT_SPEECH_LOG_PATH


#: Every exception type a statement inside `_per_run_log_paths.resolve`
#: can raise, enumerated per statement rather than collected by symptom.
#: The tuple is named and sits here so that adding a fourth `pathlib`
#: call to that closure means extending a list that is visibly incomplete,
#: instead of adding a silent fourth way for `main()` to die before the
#: crew starts. That is not hypothetical: `BL-11` rounds 3, 4 and 5 each
#: found one statement's exception type missing from a guard that already
#: caught the others, and round 4's own fix introduced the one round 5
#: removed.
#:
#: * `Path.expanduser()` -- `RuntimeError`, when the first component is
#:   `~<user>` and that user has no resolvable home (a mistyped `~sgotz`
#:   for `~sg`). Bare `~` with `HOME` unset does *not* raise: Python 3.14
#:   falls back to `pwd`.
#: * `per_run_log_path()` -> `run_stamp()` -> `time.localtime()` --
#:   `OverflowError` for a `when` outside the platform's `time_t`, and
#:   `ValueError` for a NaN. Not reachable from `argv` (there is no
#:   `--when` flag, only the keyword argument the tests pass), so this one
#:   is guarded rather than argued away: the closure's contract is about
#:   every statement in it, not only the argv-driven ones.
#: * `per_run_log_path()` -> `Path.with_name()` -- `ValueError`, when the
#:   final component is empty, e.g. `.`, `/` or an empty string.
#: * `Path.mkdir()` -- `OSError`, for every filesystem reason: a
#:   non-directory already in the way, a read-only mount, a permission
#:   denial. **Also `ValueError`**, for an embedded null byte -- this list
#:   is the next author's checklist, so it must not attribute that type to
#:   `with_name` alone.
_RESOLVE_FAILURES = (OSError, OverflowError, RuntimeError, ValueError)


def _per_run_log_paths(
    *,
    detection_trace: Path | None,
    belief_truth_log: Path | None,
    speech_log: Path | None,
    when: float | None = None,
) -> tuple[Path | None, Path | None, Path | None]:
    """Give each of the three JSONL logs this run's own filename -- `BL-11`
    Stage 5, see `run_log_paths.per_run_log_path` for why timestamping
    rather than truncating.

    **One stamp for all three**, taken once here rather than per writer, so
    a sortie's detection trace, belief-truth log and speech log carry the
    same name component and a reader can tell at a glance which three files
    belong to one flight. A run that straddled midnight, or three writers
    opened a second apart, would otherwise produce three unrelated-looking
    names.

    `None` passes through as `None` -- every one of these logs is off by
    default.

    **Expands `~` and creates each resolved path's parent directory**,
    which is the other half of applying path policy at the CLI boundary
    rather than inside the writers. The expansion is here, once, rather
    than on each of the three `argparse` flags: `pathlib.Path` does not
    expand `~`, so without it the `mkdir` below would create a directory
    literally named `~` in the working directory. Nothing else does
    either: `per_run_log_path` only
    renames, and `DetectionTraceWriter.__init__` /
    `BeliefTruthLogWriter.__init__` call `path.open("a")` with no guard --
    so a missing parent is a `FileNotFoundError` raised at construction,
    *before* either writer's own write-failure reporting can fire, and the
    crew does not start at all. The run scripts point at `logs/`, which is
    gitignored and therefore absent in a fresh clone, so this is the
    ordinary case rather than an edge one.

    A path that cannot be resolved to a writable file degrades that one log
    to `None` with a line on stderr, mirroring `_resolve_speech_log_path`
    above: an unwritable log should cost the sortie its trace, not its
    crew. The writers keep their "handed an exact path, writes exactly
    there" property either way.

    **Four exception types, from four statements**, because these three
    adjacent `pathlib` calls raise three unrelated types and `run_stamp`
    a fourth: see `_RESOLVE_FAILURES` above, which enumerates them per
    statement and is the only list of them. Every statement in `resolve`
    *that can fail* is inside the one guard -- the assignments are not, and
    `reported_parent = path.parent` is deliberately outside it (it is pure:
    no syscall, and it does not raise for `.`, `/`, `''`, `//`, an embedded
    null byte or `~nosuchuser/x`, all probed 2026-10-06) -- because a
    `--detection-trace .` or
    `'~nosuchuser/trace.jsonl'` that killed `main()` with a traceback
    would escape this policy rather than apply it. Each of the three
    rounds that widened this guard found exactly one type missing, which
    is why the enumeration is written down next to the guard rather than
    rediscovered."""
    stamp_at = time.time() if when is None else when

    def resolve(path: Path | None, flag: str) -> Path | None:
        if path is None:
            return None
        # Bound before the `try`, so that no statement inside it can leave
        # the handler reaching for a name that statement was supposed to
        # bind. Needing the expanded parent in the message is exactly what
        # pushed `expanduser()` outside the guard last round and let its
        # `RuntimeError` escape; one guard over every statement is what
        # makes the degrade policy total, so the message has to stop
        # depending on how far the body got. Re-pointed at the expanded
        # parent the moment it exists, because a failing `~/x.jsonl` wants
        # `/home/you` reported, not `~`.
        reported_parent = path.parent
        try:
            expanded = path.expanduser()
            reported_parent = expanded.parent
            stamped = per_run_log_path(expanded, stamp_at)
            stamped.parent.mkdir(parents=True, exist_ok=True)
        except _RESOLVE_FAILURES as exc:
            print(
                f"{flag}: could not create log directory {reported_parent} "
                f"({exc}); continuing without this log",
                file=sys.stderr,
            )
            return None
        return stamped

    return (
        resolve(detection_trace, "detection-trace"),
        resolve(belief_truth_log, "belief-truth-log"),
        resolve(speech_log, "speech-log"),
    )


def _resolve_group_trace_log_path(
    group_trace: Path | None, when: float | None = None
) -> Path | None:
    """Apply `_per_run_log_paths`'s own policy (stamp, expand `~`, create
    the parent directory, degrade to `None` on any of `_RESOLVE_FAILURES`
    rather than crash the sortie) to `--group-trace`, the fourth per-run
    JSONL log (`BL-12` amendment A4).

    **A sibling function, not a fifth parameter on `_per_run_log_paths`
    itself.** That function's four-exception guard and "one stamp for all
    three" framing are exercised by nine existing tests
    (`tests/test_run_log_paths.py`) written against a three-log arity;
    widening its signature and return tuple would require rewriting every
    one of those call sites' unpacking for a mechanical reason that has
    nothing to do with what they test, which `body-layer/CLAUDE.md`'s
    "Mechanism and calibration never share a commit" spirit argues against
    doing inside a Stage-1-review fix. The policy itself -- the thing worth
    not duplicating by hand -- is the `resolve` closure's logic, reproduced
    here verbatim rather than factored out, since factoring it out from
    inside `_per_run_log_paths` would touch that function's body for the
    same reason widening its signature would.

    The one divergence from "one stamp for all three": this log gets its
    own `time.time()` call when `when` is `None`, a handful of
    nanoseconds away from `_per_run_log_paths`'s own default stamp rather
    than bit-for-bit identical. Both calls happen within the same `main()`
    invocation before the poll loop starts, so the two timestamps never
    disagree at the second resolution `RUN_STAMP_FORMAT` actually renders
    at, in practice -- and an explicit `when` (what every test above
    passes) makes the two identical by construction regardless."""
    if group_trace is None:
        return None
    stamp_at = time.time() if when is None else when
    reported_parent = group_trace.parent
    try:
        expanded = group_trace.expanduser()
        reported_parent = expanded.parent
        stamped = per_run_log_path(expanded, stamp_at)
        stamped.parent.mkdir(parents=True, exist_ok=True)
    except _RESOLVE_FAILURES as exc:
        print(
            f"group-trace: could not create log directory {reported_parent} "
            f"({exc}); continuing without this log",
            file=sys.stderr,
        )
        return None
    return stamped


def _resolve_mission_memory_log_path(
    mission_memory_path: Path | None, when: float | None = None
) -> Path | None:
    """`_resolve_group_trace_log_path`'s own sibling for `--mission-memory`
    (BL-8) -- same reasoning, same reproduced-rather-than-shared policy
    body, same "its own `time.time()` call" divergence. See that
    function's docstring for why this is a sibling rather than a fifth/
    sixth parameter on `_per_run_log_paths`."""
    if mission_memory_path is None:
        return None
    stamp_at = time.time() if when is None else when
    reported_parent = mission_memory_path.parent
    try:
        expanded = mission_memory_path.expanduser()
        reported_parent = expanded.parent
        stamped = per_run_log_path(expanded, stamp_at)
        stamped.parent.mkdir(parents=True, exist_ok=True)
    except _RESOLVE_FAILURES as exc:
        print(
            f"mission-memory: could not create log directory {reported_parent} "
            f"({exc}); continuing without this log",
            file=sys.stderr,
        )
        return None
    return stamped


def _resolve_slew_trace_log_path(
    slew_trace_path: Path | None, when: float | None = None
) -> Path | None:
    """`_resolve_group_trace_log_path`'s own sibling for `--slew-trace`
    (`BL-B66` Stage 4b) -- same reasoning, same reproduced-rather-than-
    shared policy body, same "its own `time.time()` call" divergence. See
    that function's docstring for why this is a sibling rather than a
    parameter on `_per_run_log_paths`."""
    if slew_trace_path is None:
        return None
    stamp_at = time.time() if when is None else when
    reported_parent = slew_trace_path.parent
    try:
        expanded = slew_trace_path.expanduser()
        reported_parent = expanded.parent
        stamped = per_run_log_path(expanded, stamp_at)
        stamped.parent.mkdir(parents=True, exist_ok=True)
    except _RESOLVE_FAILURES as exc:
        print(
            f"slew-trace: could not create log directory {reported_parent} "
            f"({exc}); continuing without this log",
            file=sys.stderr,
        )
        return None
    return stamped


def _configure_logger_for_main() -> None:
    """Give this module's own `logger` (`logging.getLogger(__name__)`,
    above) a level and a handler, so `_log_live_los_coverage_summary`'s
    end-of-run line and `_warn_live_los_coverage_gap_once`'s transition
    warning are actually visible on a real run (`plans/
    bl11-stage4-fail-closed/dod-check.md`'s required fix).

    **Why this was needed at all**: nothing in this codebase configured
    logging anywhere, so with no handler attached anywhere in the
    hierarchy, Python falls back to `logging.lastResort`, whose threshold
    is `WARNING` (30) -- `logger.warning(...)` calls printed by accident
    of that fallback, but every `logger.info(...)` call, including the
    coverage summary's unconditional `0/N` line, was silently dropped on
    every real sortie. `_configure_logger_for_main()` runs once,
    unconditionally, at the top of `main()`, before any flag is read, so
    this covers the one remaining entry point regardless of which flags
    are given.

    **Deliberately scoped to this module's own logger instance, never
    `logging.basicConfig`/the root logger.** `main()` is this subproject's
    own standalone entrypoint (`python -m body ...`), so touching
    logging configuration here is defensible -- but a global
    `basicConfig` call would do two things this fix does not want: clobber
    a host application's own logging setup if this module were ever
    imported into a larger process instead of run standalone, and raise
    *every other module's* logger to `INFO` as a side effect, which would
    turn on `perception.hybrid_source`'s per-dropped-detection `INFO` line
    globally -- a flood, and a second regression of the exact kind this
    fix exists to close in the opposite direction. Named loggers
    (`logging.getLogger(__name__)`) are independent of each other unless
    one's name is a dotted child of another's; `"logger"` (this module's
    `__name__` when run via `python -m body`) is not a parent of
    `"perception.hybrid_source"` or `"belief.crew_console"`, so this call
    cannot reach them.

    Clears and re-adds this logger's own handler on every call rather than
    checking `if not logger.handlers:` first -- idempotent in production
    (`main()` runs this exactly once per process), and correct under
    repeated in-process calls in tests, where a guard would bind the
    handler's `StreamHandler` to whichever `sys.stderr` was current on the
    *first* call and never see a later test's `capsys`-substituted stream
    again."""
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def main() -> None:
    """CLI entrypoint: `python -m body --aircraft-layer-url ... --theatre
    ... --world-model-db ...` -- polls `ConsolePerceptionRunner.run_once()`
    on a fixed interval against a real `HybridPerceptionSource` and
    (PB-1.5) `NakedEyePerceptionSource` until interrupted. Not exercised
    by automated tests (a live/replay-loop driver, same posture as
    `aircraft-layer/src/collector/__main__.py`'s own untested `main()`);
    `ConsolePerceptionRunner`'s, `HybridPerceptionSource`'s, and
    `NakedEyePerceptionSource`'s own logic is.

    First line is `_configure_logger_for_main()` -- see its own docstring
    for why logging needs configuring here at all."""
    _configure_logger_for_main()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-tuning",
        action="store_true",
        help=(
            "print every tuning.py-registered constant's resolved value, "
            "default, status, and (if rejected) the reason, then exit 0 -- "
            "plans/configurable-constants/plan.md, 'Verifying a changed "
            "value took effect'. The only flag that works without "
            "--aircraft-layer-url, since nothing else runs."
        ),
    )
    parser.add_argument(
        "--aircraft-layer-url",
        default=None,
        help=(
            "aircraft-layer LAN API base URL, e.g. http://192.168.1.50:7791 "
            "-- required unless --print-tuning is given"
        ),
    )
    parser.add_argument(
        "--theatre",
        default=None,
        help=(
            "DCS theatre name for world-object lat/lon -> DCS x/z conversion, "
            "e.g. Syria. Together with --world-model-db, this wins unchanged "
            "(needed for small test regions like latakia-20km/gemerek-20km, "
            "and for running without a mission-understanding artifact at "
            "all). Omit both to derive theatre from --mission-understanding "
            "instead (Stage 5, multi-theatre-afghanistan plan) -- see "
            "--world-model-dir."
        ),
    )
    parser.add_argument(
        "--world-model-db",
        default=None,
        type=Path,
        help=(
            "path to a built world-model region .sqlite (see body-layer/CLAUDE.md's "
            "world-model seam note) -- NakedEyePerceptionSource's visibility filter "
            "needs it for the terrain line-of-sight gate. See --theatre on when this "
            "can be omitted in favour of --mission-understanding + --world-model-dir."
        ),
    )
    parser.add_argument(
        "--world-model-dir",
        default=None,
        type=Path,
        help=(
            "directory holding per-theatre full-theatre world-model stores, named "
            "<theatre.lower()>-full.sqlite (Stage 5, multi-theatre-afghanistan plan) "
            "-- required together with --mission-understanding when --theatre/"
            "--world-model-db are omitted, so theatre and store are derived from "
            "the loaded mission-understanding artifact's theatre field instead of "
            "a remembered flag. Also optional alongside an explicit --theatre/"
            "--world-model-db pair (BL-15 Stage 3, plans/bl15-mission-start/plan.md): "
            "when given there too, a live mission-start event naming a different "
            "theatre re-resolves the store at <dir>/<theatre.lower()>-full.sqlite "
            "and switches to it at runtime. Without it, a theatre change detected "
            "mid-run has nowhere to resolve a new store from and enters refusal "
            "mode (every player command answered 'system error, world model not "
            "loaded') until the next mission (re)start resolves successfully."
        ),
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=_DEFAULT_POLL_INTERVAL_S,
        help="seconds between poll ticks",
    )
    parser.add_argument(
        "--mission-understanding",
        type=Path,
        default=None,
        help=(
            "path to a mission-interpreter --emit-compact JSON artifact "
            "(BL-7, plans/bl7-mission-phase-relevance/plan.md) -- when "
            "given, loaded once at startup and used to track live mission "
            "phase against ownship position, surfaced via get_situation's "
            "'situation' command. Omitted (default): no phase data, "
            "unchanged from before this milestone."
        ),
    )
    parser.add_argument(
        "--brain-client",
        choices=("http", "debug", "null"),
        default="debug",
        help=(
            "which belief.escalation.BrainClient handles escalated "
            "utterances -- 'http' (plans/brain-layer/"
            "plan.md) talks to a running brain-layer instance over "
            "--brain-url and speaks real replies; 'debug' (default) "
            "prints escalations to stderr and never speaks; 'null' is "
            "silent. 'http' requires --brain-url."
        ),
    )
    parser.add_argument(
        "--brain-url",
        default=None,
        help=(
            "brain-layer base URL, e.g. http://127.0.0.1:7796 -- required "
            "together with --brain-client http, unused otherwise"
        ),
    )
    parser.add_argument(
        "--audio-adapter-url",
        default=None,
        help=(
            "audio-adapter base URL, e.g. http://127.0.0.1:7795 -- "
            "required (BL-B96: speech in/out are always on). If the "
            "adapter is unreachable at startup or at any point during the "
            "sortie, body-layer warns once and keeps trying -- everything "
            "else (perception, belief, voice-command dispatch, mission "
            "memory) runs unaffected; Petrovich simply stays silent until "
            "it answers."
        ),
    )
    parser.add_argument(
        "--speech-log",
        type=Path,
        default=None,
        help=(
            "write one JSON line per recognised transcript to this path -- "
            "what was heard, the seven recognition fields, and what was done "
            "about it (act/confirm/say_again/fallthrough). The answer to "
            "'why did nothing happen when I said that': an utterance matching "
            "no command otherwise reaches only the brain-layer stand-in, "
            f"which does nothing. Defaults on ({DEFAULT_SPEECH_LOG_PATH}, "
            "created if absent, appended across sorties) even without this "
            "flag -- pass it only to log somewhere else. See --no-speech-log "
            "to suppress the default instead."
        ),
    )
    parser.add_argument(
        "--no-speech-log",
        action="store_true",
        help=(
            "suppress --speech-log's default sink; mutually exclusive "
            "with --speech-log."
        ),
    )
    parser.add_argument(
        "--detection-trace",
        type=Path,
        default=None,
        help=(
            "write a per-poll, per-object naked-eye visibility gate trace "
            "(JSONL) to this path -- BL-9, plans/bl9-debug-visualization/"
            "plan.md. Answers 'why did Petrovich not see that' after a "
            "flight: reduce it with body-layer/tools/"
            "summarize_detection_trace.py. Defaults off, a true no-op "
            "when absent."
        ),
    )
    parser.add_argument(
        "--group-trace",
        type=Path,
        default=None,
        help=(
            "write one JSON line per belief.groups.GroupStore.reconcile "
            "resolution outcome (overlap/property/found/expired) to this "
            "path -- BL-12 amendment A4, plans/group-contact-identity/"
            "plan.md. Answers 'how often did a group survive by matching "
            "remembered properties rather than its own members' -- the "
            "only way D5's rarity claim and BL-B50's lapse condition "
            "(membership flipping on consecutive ticks) are checkable from "
            "an actual sortie rather than from a wrong spoken line in "
            "flight. Defaults off, a true no-op when absent."
        ),
    )
    parser.add_argument(
        "--slew-trace",
        type=Path,
        default=None,
        help=(
            "write one JSON line per poll to this path -- desired vs. "
            "actual sight aim (azimuth/elevation), the readback source "
            "('readback' or 'model'), the error, OBSERV commanded/"
            "observed, and optic mode -- BL-B66 Stage 4b, plans/"
            "9k113-effectors/plan.md. Data for BL-B80's rate-loop "
            "tuning; reduce with .claude/skills/sortie-log-triage. "
            "Defaults off, a true no-op when absent."
        ),
    )
    parser.add_argument(
        "--eyesight-view",
        action="store_true",
        help=(
            "print a live top-down ASCII view of what Petrovich is looking "
            "at and with what, redrawn every poll -- a debug/calibration "
            "instrument (todo/todo.md's 'Added 2026-09-25 (user)' entry), "
            "deliberately allowed to show ground truth alongside belief "
            "(see eyesight_view.py's module docstring). Defaults off, a "
            "true no-op when absent. Offline: body-layer/tools/"
            "eyesight_replay.py replays a --detection-trace JSONL file "
            "with no live DCS session at all."
        ),
    )
    parser.add_argument(
        "--eyesight-view-radius-m",
        type=float,
        default=EYESIGHT_DEFAULT_RADIUS_M,
        help=(
            "--eyesight-view's display radius in metres (default 5000m, "
            "user direction -- a display-scale choice, not the naked-eye "
            "channel's own 10000m detection cap). A contact beyond this "
            "radius is never dropped: it is marked at the canvas rim and "
            "listed in the frame's trailing legend with its exact bearing/"
            "range."
        ),
    )
    parser.add_argument(
        "--pov-view",
        action="store_true",
        help=(
            "print a live forward-POV ASCII view of the current optic's "
            "field of view/boresight and what Petrovich detects through "
            "it, redrawn every poll -- the forward-looking twin of "
            "--eyesight-view, same debug/calibration posture (may show "
            "ground truth, see pov_view.py's module docstring). Ignores "
            "units outside the player bubble. Defaults off, a true no-op "
            "when absent. When combined with --eyesight-view, the two "
            "frames share one terminal's line budget and print together."
        ),
    )
    parser.add_argument(
        "--mission-memory",
        type=Path,
        default=None,
        help=(
            "write one JSON line per mission-memory entry (group/air-"
            "defence identifications, pilot-ordered marks, being-fired-"
            "on events) to this path -- BL-8, plans/bl8-mission-memory/"
            "plan.md. An append-only, per-sortie record of what Petrovich "
            "saw/marked/was shot at, written from settled belief after "
            "every poll's ContactStore.tick(); the in-flight read half is "
            "in-memory only and not wired by this flag. Defaults off, a "
            "true no-op when absent."
        ),
    )
    parser.add_argument(
        "--belief-truth-log",
        type=Path,
        default=None,
        help=(
            "write a per-poll, per-contact ground-truth/belief consistency "
            "log (JSONL) to this path -- catches drift between what "
            "Petrovich believes and what is actually there (position, "
            "cardinality, classification) automatically rather than "
            "relying on a pilot noticing, which is how the 2026-09-24 "
            "87.5km-callout defect went unnoticed for a whole sortie "
            "(plans/position-belief-runaway/debug.md). Prints a loud "
            "stderr tripwire line for the physically-impossible cases "
            "(believed range beyond the naked-eye channel's own detection "
            "cap, or a position error far beyond the contact's own stated "
            "uncertainty) -- see belief_truth_log.py's module docstring. "
            "Defaults off, a true no-op when absent."
        ),
    )
    parser.add_argument(
        "--forest-occlusion",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "gate 5 of visibility.check_visibility: a ground unit inside a "
            "mapped forest landcover polygon is not detected -- flat and "
            "binary, no directionality, no altitude term -- plans/"
            "forest-occlusion/plan.md Stage 1-2, specification docs/"
            "acceptance/2026-10-13-tree-cover-direction.md. Defaults off, "
            "a true no-op when absent (--no-forest-occlusion makes that "
            "explicit)."
        ),
    )
    args = parser.parse_args()

    # plans/configurable-constants/plan.md Stage 2: validate the override
    # file against the full config/defaults.toml registry (independent of
    # import order) and render the result -- before any other validation,
    # since --print-tuning must work standalone. This call also builds the
    # live registry's final classification: every tunable module above
    # has already been imported by the time this line runs.
    tuning_resolution = validate_against_defaults()
    if args.print_tuning:
        print(render_print_tuning(tuning_resolution))
        return
    print(render_startup_block(tuning_resolution))

    if args.aircraft_layer_url is None:
        parser.error(
            "--aircraft-layer-url is required (omit only together with --print-tuning)"
        )
    if args.audio_adapter_url is None:
        parser.error(
            "--audio-adapter-url is required (omit only together with "
            "--print-tuning) -- BL-B96: speech in/out are always on"
        )
    if args.speech_log is not None and args.no_speech_log:
        parser.error("--speech-log is mutually exclusive with --no-speech-log")
    if args.brain_client == "http" and args.brain_url is None:
        parser.error("--brain-client http requires --brain-url")

    # Stage 5 (multi-theatre-afghanistan plan): resolve theatre/world-
    # model-db. --theatre/--world-model-db win unchanged when both are
    # given (needed for small test regions like latakia-20km/
    # gemerek-20km, and for running without a mission-understanding
    # artifact at all). Otherwise derive both from a loaded
    # --mission-understanding artifact's own theatre field -- never a
    # silent fallback to a default theatre.
    mission_data: MissionUnderstandingData | None = None
    if args.mission_understanding is not None:
        mission_data = load_mission_understanding(args.mission_understanding)

    if args.theatre is not None and args.world_model_db is not None:
        theatre = args.theatre
        world_model_db = args.world_model_db
    elif mission_data is not None:
        if mission_data.theatre is None:
            parser.error(
                "--mission-understanding artifact has no 'theatre' field -- "
                "cannot derive --theatre/--world-model-db from it"
            )
        if args.world_model_dir is None:
            parser.error(
                "deriving theatre from --mission-understanding requires "
                "--world-model-dir"
            )
        theatre = mission_data.theatre.value
        # Security (multi-theatre-afghanistan plan, required fix): `theatre`
        # is the raw .miz-derived string from an externally-sourced mission
        # file, unvalidated all the way up the mission-interpreter chain
        # (see plans/multi-theatre-afghanistan/security.md). Reject anything
        # outside the known-theatre registry before it is used to build a
        # path or (transitively, via open_world_model's sqlite3 URI) a
        # connection string -- a path-traversal/UNC/absolute-path value or a
        # SQLite URI-query-string injection otherwise reaches both.
        if theatre not in THEATRE_PROJECTIONS:
            parser.error(
                f"--mission-understanding artifact's theatre {theatre!r} is "
                "not a known theatre -- no entry in "
                "coordinates.projections.THEATRE_PROJECTIONS"
            )
        world_model_db = args.world_model_dir / f"{theatre.lower()}-full.sqlite"
    else:
        parser.error(
            "give either both --theatre and --world-model-db, or "
            "--mission-understanding together with --world-model-dir"
        )

    # Mismatch guard, independent of how theatre was resolved: the
    # resolved store's own built region must agree with the resolved
    # theatre -- catches "pointed --theatre Syria at an Afghanistan
    # store" before the first poll, rather than silently applying the
    # wrong projection and producing a plausible-looking, wrong position
    # for every contact.
    try:
        guard_conn = open_world_model(world_model_db)
        try:
            built_region = load_only_region(guard_conn)
        finally:
            guard_conn.close()
    except (sqlite3.Error, OSError):
        parser.error(f"world model for {theatre} not built: {world_model_db}")
    if built_region is not None and built_region.theatre != theatre:
        parser.error(
            f"--world-model-db {world_model_db} was built for theatre "
            f"{built_region.theatre!r}, but the resolved theatre is "
            f"{theatre!r}"
        )

    args.speech_log = _resolve_speech_log_path(
        speech_log=args.speech_log,
        no_speech_log=args.no_speech_log,
    )

    # `BL-15` Stage 1 decision 5 ("per mission", not a marker line):
    # capture each per-run log's pre-stamp path now, before the stamping
    # calls below overwrite `args.*` with this run's own stamped filename.
    # A later in-process mission (re)start re-stamps from these, via
    # `_reroll_run_logs`, rather than double-stamping an already-stamped
    # name -- see that function's own docstring for why the pre-stamp path
    # has to be threaded through separately. `expanduser()` can raise
    # `RuntimeError` (no such user); degrading to `None` here is harmless,
    # since the same call inside `_per_run_log_paths`/`_resolve_group_
    # trace_log_path`/`_resolve_mission_memory_log_path` immediately below
    # fails identically and already reports it on stderr for the initial
    # stamp -- a `None` base below then simply means this log gets no
    # Stage-1-decision-5 reroll, not a second, silent failure.
    def _expand_log_base(path: Path | None) -> Path | None:
        if path is None:
            return None
        try:
            return path.expanduser()
        except RuntimeError:
            return None

    detection_trace_base = _expand_log_base(args.detection_trace)
    belief_truth_log_base = _expand_log_base(args.belief_truth_log)
    speech_log_base = _expand_log_base(args.speech_log)
    group_trace_base = _expand_log_base(args.group_trace)
    mission_memory_base = _expand_log_base(args.mission_memory)
    slew_trace_base = _expand_log_base(args.slew_trace)

    # BL-11 Stage 5: each run writes its own files rather than appending to
    # one that grows across sorties. Applied after the default resolution
    # above, so `--speech-log`'s default and an explicit path roll alike.
    args.detection_trace, args.belief_truth_log, args.speech_log = _per_run_log_paths(
        detection_trace=args.detection_trace,
        belief_truth_log=args.belief_truth_log,
        speech_log=args.speech_log,
    )
    # BL-12 amendment A4: a fourth per-run log, resolved by its own sibling
    # function rather than a fifth `_per_run_log_paths` parameter -- see
    # `_resolve_group_trace_log_path`'s own docstring for why.
    args.group_trace = _resolve_group_trace_log_path(args.group_trace)
    # BL-8: a fifth per-run log, resolved by its own sibling function for
    # the same reason `--group-trace` has one -- see
    # `_resolve_mission_memory_log_path`'s own docstring.
    args.mission_memory = _resolve_mission_memory_log_path(args.mission_memory)
    # BL-B66 Stage 4b: a sixth per-run log, same sibling-function shape.
    args.slew_trace = _resolve_slew_trace_log_path(args.slew_trace)
    for label, rolled in (
        ("detection-trace", args.detection_trace),
        ("belief-truth-log", args.belief_truth_log),
        ("speech-log", args.speech_log),
        ("group-trace", args.group_trace),
        ("mission-memory", args.mission_memory),
        ("slew-trace", args.slew_trace),
    ):
        if rolled is not None:
            print(f"{label}: writing {rolled}", file=sys.stderr)

    aircraft_client = AircraftLayerClient(base_url=args.aircraft_layer_url)

    # BL-7: `mission_data` was already loaded above (Stage 5 needs it to
    # resolve theatre before this point) -- built once, on the main
    # thread, before either poll thread starts, and shared as the same
    # MissionPhaseTracker instance across threads (see
    # ConsolePerceptionRunner.mission_phase_tracker's own docstring for the
    # write-thread/read-thread split this relies on).
    mission_phase_tracker: MissionPhaseTracker | None = None
    if mission_data is not None:
        mission_phase_tracker = MissionPhaseTracker(data=mission_data)

    brain_client: BrainClient
    if args.brain_client == "http":
        brain_client = BrainLayerClient(base_url=args.brain_url)
    elif args.brain_client == "debug":
        brain_client = DebugPrintBrainClient()
    else:
        brain_client = NullBrainClient()
    crew_runner = ConsolePerceptionRunner(
        aircraft_client=aircraft_client,
        output=None,
        mission_phase_tracker=mission_phase_tracker,
        group_trace_sink=(
            GroupTraceLogWriter(args.group_trace).write
            if args.group_trace is not None
            else None
        ),
    )
    # BL-B96: speech in (`get_transcripts`) and out (`push_speech`) are
    # both always on now, so exactly one `AudioAdapterClient` is always
    # built -- no more "only if --speech-audio/--speech-input" branching.
    audio_adapter_client = AudioAdapterClient(base_url=args.audio_adapter_url)
    # BL-B96 Stage 4 (user direction: "warn and keep trying ... as with a
    # bad config file"): one shared ConnectionReporter for the audio
    # adapter, covering both CrewConsole._print's push path and
    # _poll_transcripts' poll path -- see CrewConsole.audio_adapter_
    # reporter's own docstring for why this must be the *same* instance,
    # not one per path.
    audio_adapter_reporter = ConnectionReporter(logger, label="audio adapter")
    # `plans/effector-sequences/plan.md` D5/D6, BL-B90 Stage 2 --
    # loaded once here, before `CrewConsole` exists, so a bad
    # registry/sequence file can set `config_error_pending` at
    # construction time rather than needing a second mutation after
    # the fact.
    (
        effector_sequences_by_key,
        effector_registry_entries,
        had_config_errors,
        polled_args_set,
    ) = _load_effector_config()
    crew_console = CrewConsole(
        store=crew_runner.store,
        brain_client=brain_client,
        output=sys.stdout,
        aircraft_client=aircraft_client,
        tasks=crew_runner.tasks,
        speech_client=audio_adapter_client,
        audio_adapter_reporter=audio_adapter_reporter,
        transcript_log=(
            SpeechLogWriter(args.speech_log).write
            if args.speech_log is not None
            else None
        ),
        config_error_pending=had_config_errors,
    )
    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            crew_runner,
            crew_console,
            aircraft_client,
            theatre,
            world_model_db,
            args.poll_interval_s,
            stop_event,
            audio_adapter_client,
            True,  # speech_input_enabled -- BL-B96: always on
            args.detection_trace,
            args.eyesight_view,
            args.eyesight_view_radius_m,
            args.pov_view,
            args.belief_truth_log,
            args.forest_occlusion,
            args.mission_memory,
            args.world_model_dir,
            detection_trace_base,
            belief_truth_log_base,
            speech_log_base,
            group_trace_base,
            mission_memory_base,
            args.slew_trace,
            slew_trace_base,
            effector_sequences_by_key,
            effector_registry_entries,
            polled_args_set.args,
        ),
        daemon=True,
    )
    poll_thread.start()
    print(CREW_TEXT_HELP_TEXT, file=sys.stdout)
    try:
        _run_crew_text_repl(crew_runner, crew_console, world_model_db, theatre)
    finally:
        stop_event.set()
        poll_thread.join()


if __name__ == "__main__":
    main()
