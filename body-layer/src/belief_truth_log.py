"""`BeliefTruthLogWriter` -- a flag-gated ground-truth/belief consistency
log (`--belief-truth-log`), added alongside the real-time eyesight view
(`eyesight_view.py`) for the same underlying reason, `todo/todo.md`'s
"Added 2026-09-25 (user)" entry and its 2026-09-26 follow-up.

**Why this exists, in one line: the defect it is built to catch was
already sitting in `--detection-trace`'s own output, every poll, and
nobody found it until a pilot happened to say so out loud.** On
2026-09-24 Petrovich reported contacts at 87.5 km against a 10 km
detection cap (`plans/position-belief-runaway/debug.md`) -- a slow drift
with no single step large enough to look wrong in isolation. A log nobody
reads does not fix that; this module exists to make the check automatic
and loud rather than manual and lucky.

**Read-only and one-directional, exactly `detection_trace_writer.py`'s own
precedent and model** -- this is the second module in this codebase
deliberately allowed to hold both ground truth and belief at once. It
reads `perception.detection_trace.DetectionTrace` (ground truth) and
`belief.contacts.Contact` (belief) side by side, and it reuses that
module's own `observation_id_to_contact_id` join rather than building a
second, differently-wrong one (user direction, 2026-09-26: "reuse rather
than duplicate ... that pairing belongs in one place that both read").
Nothing here ever calls anything that mutates `ContactStore`, and no
ground-truth field it reads is ever passed into `ContactStore.ingest`,
`Percept`, or `Contact`.

**What one row compares, and what counts as a real discrepancy rather
than honest vagueness:**

- **Position** -- Euclidean error between the ground-truth position
  (`perception.geometry.project_from_bearing_range` from the trace
  entry's own true bearing/range) and `Contact.last_position`. Always
  comparable: a contact always has a believed position the moment it
  exists.
- **Cardinality** -- the ground-truth count is however many real
  `object_id`s the naked-eye channel actually clustered into this
  observation this poll (`DetectionTrace.cluster_member_object_ids`, set
  once clustering/emission have run). A discrepancy is the count falling
  **outside** `Contact.cardinality`'s held `(lo, hi)` interval -- a wider
  interval that still contains the true count is correct hedging, not an
  error.
- **Classification** -- compared only when belief actually holds a claim
  at `SpecificityLevel.CLASS` or above; `PRESENCE`/`UNKNOWN` never counts
  as a discrepancy no matter what the ground truth is, because a vaguer
  belief than the truth is the honest, correct case this project's whole
  classification lattice exists to allow (`belief.classification`'s own
  module docstring). A discrepancy is the belief's own `OP_*` bucket
  (`belief.classification.parent_class_of`, resolving either a `CLASS`-
  level bucket directly or a `TYPE`-level reporting name) disagreeing with
  the ground-truth object's own bucket (`perception.object_model.
  profile_for`). This is class-level only -- a `TYPE`-level belief that
  names the wrong specific vehicle within the right class (e.g. "T-72"
  when it is actually a T-80) is not flagged as a discrepancy here; that
  finer distinction is out of this module's scope.

**The tripwire is narrower than the full row, deliberately** (user
direction: "catching the absurd, not tuning a detector"). Two physically-
impossible checks only, printed to stderr the moment either fires so a
developer sees it live rather than having to grep a file afterward:

- a believed range from ownship beyond `perception.visibility.
  NAKED_EYE_RANGE_CAP_M` -- the channel that produced this contact could
  never have detected anything that far out in the first place (this is
  exactly the shape of the 87.5 km/10 km defect above).
- a position error more than `POSITION_ERROR_UNCERTAINTY_MULTIPLE` times
  the contact's own stated position uncertainty -- belief claiming
  precision it plainly does not have (`plans/precise-position-belief/
  plan.md`'s own failure mode).

Cardinality/classification discrepancies are still recorded on every row
(so they are discoverable by grepping the JSONL) but do not fire the
stderr tripwire -- neither is "physically impossible" the way a
10 km-cap channel reporting 87.5 km is; both are ordinary, expected
perception error at some rate, and a tripwire that fires on ordinary
error is one that gets ignored (user direction, same message).

Buffers before flushing, mirroring `DetectionTraceWriter`'s own reasoning
-- disk I/O never sits on the poll loop's own critical path. Deliberately
does **not** clear the shared `perception.detection_trace.
DetectionTraceCollector` it reads (unlike `DetectionTraceWriter.
write_poll`): `body.py`'s poll loop may run `--detection-trace`,
`--eyesight-view`, and `--belief-truth-log` in any combination against the
one collector each poll builds, so exactly one of them -- `DetectionTraceWriter`
if present, else the poll loop itself -- owns clearing it once every reader
has had its turn."""

from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TextIO

from belief.cardinality import CardinalityBelief
from belief.classification import (
    ClassificationBelief,
    SpecificityLevel,
    parent_class_of,
)
from belief.contacts import Contact, ContactStore
from belief.decay import OBJECT_ID_MEMORY_S
from detection_trace_writer import observation_id_to_contact_id
from perception.detection_trace import DetectionTraceCollector, GateOutcome
from perception.geometry import GeoPosition, project_from_bearing_range, range_m
from perception.object_model import DEFAULT_OP_CLASS, profile_for
from perception.source import OwnshipState
from perception.visibility import NAKED_EYE_RANGE_CAP_M

#: See module docstring -- matches `detection_trace_writer.
#: DEFAULT_FLUSH_EVERY_N_POLLS`.
DEFAULT_FLUSH_EVERY_N_POLLS = 5

#: How many multiples of a contact's own stated position uncertainty its
#: position error may exceed before the tripwire fires. Deliberately loose
#: (module docstring) -- the goal is catching the absurd, not tuning a
#: detector.
POSITION_ERROR_UNCERTAINTY_MULTIPLE: float = 5.0


@dataclass(frozen=True, slots=True)
class BeliefTruthRow:
    """One matched ground-truth/believed pair, for one poll -- the shape
    `BeliefTruthLogWriter` writes as one JSON line. Kept as a real
    dataclass (not an inline dict) so `evaluate_pair`'s logic is
    independently testable from the JSON-writing/tripwire-printing side
    effects (`tests/test_belief_truth_log.py`)."""

    t_sim: float
    contact_id: str
    object_id: int
    object_type: str
    true_x: float
    true_z: float
    believed_x: float
    believed_z: float
    position_error_m: float
    position_uncertainty_m: float
    believed_range_m: float
    range_cap_tripwire: bool
    position_uncertainty_tripwire: bool
    ground_truth_count: int | None
    believed_cardinality_lo: int
    believed_cardinality_hi: float
    cardinality_discrepancy: bool
    believed_classification_level: str
    believed_classification_value: str | None
    true_op_class: str | None
    classification_discrepancy: bool

    @property
    def tripwire(self) -> bool:
        """The two "physically impossible" checks only -- see module
        docstring on why cardinality/classification discrepancies do not
        set this."""
        return self.range_cap_tripwire or self.position_uncertainty_tripwire


def _cardinality_discrepancy(
    cardinality: CardinalityBelief, ground_truth_count: int | None
) -> bool:
    """`True` only when a real ground-truth count is known *and* it falls
    outside the held `(lo, hi)` interval -- a wider interval that still
    contains the true count is correct hedging (module docstring), not an
    error, and `ground_truth_count is None` (no cluster membership
    recorded this poll -- see `evaluate_pair`) can never be judged either
    way."""
    if ground_truth_count is None:
        return False
    return not (cardinality.lo <= ground_truth_count <= cardinality.hi)


def _classification_discrepancy(
    classification: ClassificationBelief, true_op_class: str | None
) -> bool:
    """`True` only when belief holds a `CLASS`-or-above claim *and* its
    own resolved `OP_*` bucket disagrees with the ground-truth bucket.
    `PRESENCE`/`UNKNOWN` (no claim at all) is never a discrepancy -- see
    module docstring on honest vagueness. `true_op_class is None` (the
    ground-truth object's own type resolves to no known bucket at all,
    `object_model.profile_for`'s default) is also never a discrepancy --
    there is nothing to compare against."""
    if classification.level < SpecificityLevel.CLASS or classification.value is None:
        return False
    if true_op_class is None:
        return False
    believed_op_class = parent_class_of(classification.value)
    return believed_op_class != true_op_class


def evaluate_pair(
    *,
    t_sim: float,
    contact: Contact,
    object_id: int,
    object_type: str,
    true_bearing_deg: float,
    true_range_m: float,
    observer: GeoPosition,
    ground_truth_count: int | None,
) -> BeliefTruthRow:
    """Build one `BeliefTruthRow` comparing `contact`'s current belief
    against one matched ground-truth object -- pure, no I/O, the piece
    `BeliefTruthLogWriter.write_poll` calls per matched pair each poll."""
    true_position = project_from_bearing_range(observer, true_bearing_deg, true_range_m)
    believed_position = contact.last_position
    position_error_m = range_m(true_position, believed_position)
    position_uncertainty_m = contact.last_position_uncertainty_m
    believed_range_m = range_m(observer, believed_position)

    true_op_class: str | None = profile_for(object_type).op_class
    # profile_for's own default/unresolved reading is the same string
    # PRESENCE_CLASS/DEFAULT_OP_CLASS uses for "no class claim at all" --
    # read here as "unresolved," matching _classification_discrepancy's
    # own None-means-nothing-to-compare convention.
    if true_op_class == DEFAULT_OP_CLASS:
        true_op_class = None

    return BeliefTruthRow(
        t_sim=t_sim,
        contact_id=contact.id,
        object_id=object_id,
        object_type=object_type,
        true_x=true_position.x,
        true_z=true_position.z,
        believed_x=believed_position.x,
        believed_z=believed_position.z,
        position_error_m=position_error_m,
        position_uncertainty_m=position_uncertainty_m,
        believed_range_m=believed_range_m,
        range_cap_tripwire=believed_range_m > NAKED_EYE_RANGE_CAP_M,
        position_uncertainty_tripwire=(
            position_error_m
            > POSITION_ERROR_UNCERTAINTY_MULTIPLE * position_uncertainty_m
        ),
        ground_truth_count=ground_truth_count,
        believed_cardinality_lo=contact.cardinality.lo,
        believed_cardinality_hi=contact.cardinality.hi,
        cardinality_discrepancy=_cardinality_discrepancy(
            contact.cardinality, ground_truth_count
        ),
        believed_classification_level=contact.classification.level.name,
        believed_classification_value=contact.classification.value,
        true_op_class=true_op_class,
        classification_discrepancy=_classification_discrepancy(
            contact.classification, true_op_class
        ),
    )


class BeliefTruthLogWriter:
    """Appends one JSON line per matched ground-truth/believed pair to
    `path`, and prints one stderr line for every row whose `tripwire` is
    `True`. Buffers before flushing (module docstring)."""

    def __init__(
        self,
        path: Path,
        flush_every_n_polls: int = DEFAULT_FLUSH_EVERY_N_POLLS,
        stderr: TextIO = sys.stderr,
    ) -> None:
        self._path = path
        self._file: TextIO = path.open("a", encoding="utf-8")
        self._flush_every_n_polls = flush_every_n_polls
        self._polls_since_flush = 0
        self._stderr = stderr
        #: Set by `_fail` after the first write error -- see that method.
        self._disabled = False
        #: `BL-B76`'s own object-permanence cache: the DCS `object_id`s a
        #: contact's *admitted* observations have ever carried, so a later
        #: poll's *rejected* candidate (which has an `object_id` but no
        #: `observation_id` -- `Contact` itself retains no ground-truth
        #: object id at all, by the no-omniscience boundary) can still be
        #: attributed to the contact it belongs to. See
        #: `_update_object_id_contact_cache`/`_object_ids_for_contact`
        #: below for the join and its one accepted risk (DCS `object_id`
        #: reuse), bounded by `OBJECT_ID_MEMORY_S` the same way `belief.
        #: decay.object_id_continuity_valid` already bounds it elsewhere.
        self._object_id_to_contact_id: dict[int, str] = {}
        self._object_id_last_seen_sim: dict[int, float] = {}

    def write_speech(
        self,
        *,
        t_sim: float,
        text: str,
        urgent: bool,
        gaze_label: str | None = None,
        gaze_center_deg: float | None = None,
        optic_name: str | None = None,
        ownship_pitch_deg: float | None = None,
        ownship_bank_deg: float | None = None,
        ownship_heading_true_deg: float | None = None,
        ownship_alt_m: float | None = None,
        attack_run_target_contact_id: str | None = None,
        attack_run_tier: int | None = None,
        attack_run_azimuth_deg: float | None = None,
        attack_run_elevation_deg: float | None = None,
        correlation_id: str | None = None,
        push_sent_wall: float | None = None,
        push_acked_wall: float | None = None,
        push_duration_s: float | None = None,
    ) -> None:
        """Write one `kind: "speech"` row -- what Petrovich actually said,
        on the same timeline as the belief-versus-truth rows.

        **Why it belongs in this file and not its own** (user, 2026-09-25):
        *"we should also have ... what Petrovich says to that log also, then
        all the information would be in one log file."* Correlating a
        callout against the belief state that produced it is the whole
        point, and two files with two clocks make that a join the reader has
        to perform by hand.

        `gaze_label`/`gaze_center_deg`/`optic_name` capture **where he was
        looking at the moment he spoke**. That is what turns the defect this
        was added for -- *"callouts like 'ground 10 o'clock, 2 km' even
        though scan right has been commanded"* -- from two observations a
        human has to correlate into one line that either shows the
        contradiction or does not.

        `ownship_pitch_deg`/`ownship_bank_deg`/`ownship_heading_true_deg`/
        `ownship_alt_m` (added for the 2026-10-15 attack-run sortie's open
        question, `docs/acceptance/2026-10-15-attack-run-sortie-feedback.md`
        S3: an ", obstructed" qualifier firing with the target in plain
        sight, on flat desert) capture ownship's own attitude/position **at
        the moment of the utterance**, exactly mirroring `perception.source.
        OwnshipState`'s own fields and sign convention -- positive
        `ownship_pitch_deg` is nose up, positive `ownship_bank_deg` is right
        bank (right wing down), `ownship_heading_true_deg` is true heading
        in `[0, 360)`, `ownship_alt_m` is MSL. These are what `cockpit_mask.
        is_visible`'s body-relative azimuth/elevation are rotated from
        (`perception.visibility`'s own call site passes `ownship.bank_deg`
        into that rotation) -- recording them is what makes a later
        "was the mask verdict right" question reconstructible from the log
        rather than merely asserted.

        Rows carry `kind` so a reader can tell them apart. Belief-truth rows
        written before this existed have no `kind` field, so **treat a
        missing `kind` as `"belief_truth"`** rather than skipping the row --
        there are already such files on the user's disk.

        `attack_run_target_contact_id`/`attack_run_tier`/`attack_run_
        azimuth_deg`/`attack_run_elevation_deg` (`plans/attack-run/
        plan.md` Stage 5) carry one attack-run guidance utterance's own
        context -- the target, which tier produced it, and the current
        axis errors -- so a sortie can be triaged from this log instead of
        recalled. **These are `belief.attack_run._tier1_alignment`'s own
        azimuth/elevation, which is explicitly bank-removed** (that
        function's own docstring: "re-rotating by current attitude via
        geometry.alignment_direction (bank removed)") -- a different
        rotation from the one `cockpit_mask.is_visible` is checked against,
        so they must not be read as a stand-in for the mask's own verdict.
        That is also why no mask-verdict field is recorded here: computing
        one from these axis values would answer a question about a
        different rotation than the one that actually ran during
        perception, which risks looking like an answer while being wrong
        in exactly the way this investigation is trying to rule out. `None`
        (the default, every row that is not attack-run guidance, or where
        ownship state was unavailable) omits the corresponding field, the
        same absent-not-null convention `gaze_label`/`gaze_center_deg`/
        `optic_name` already follow -- a missing field means "not known",
        never "zero".

        `correlation_id`/`push_sent_wall`/`push_acked_wall`/`push_duration_s`
        (`plans/voice-latency-instrumentation/plan.md` Stage 3) join this
        row to the rest of one utterance's timeline across every process it
        crosses (`tools/join_voice_latency.py`). `push_sent_wall`/
        `push_acked_wall` are ordinary wall-clock, recorded for ordering/
        context only -- `_print`'s own `time.monotonic()` bracket around
        the `push_speech` call is what makes `push_duration_s` the
        trustworthy number (see that method's docstring and the plan's
        "What the investigation found" on cross-machine clocks). `None`
        for every line that was never pushed to `speech_client` at all
        (`silenced`, or no `speech_client` configured)."""
        row: dict[str, object] = {
            "kind": "speech",
            "t_sim": t_sim,
            "text": text,
            "urgent": urgent,
        }
        if gaze_label is not None:
            row["gaze_label"] = gaze_label
        if gaze_center_deg is not None:
            row["gaze_center_deg"] = gaze_center_deg
        if optic_name is not None:
            row["optic_name"] = optic_name
        if ownship_pitch_deg is not None:
            row["ownship_pitch_deg"] = ownship_pitch_deg
        if ownship_bank_deg is not None:
            row["ownship_bank_deg"] = ownship_bank_deg
        if ownship_heading_true_deg is not None:
            row["ownship_heading_true_deg"] = ownship_heading_true_deg
        if ownship_alt_m is not None:
            row["ownship_alt_m"] = ownship_alt_m
        if attack_run_target_contact_id is not None:
            row["attack_run_target_contact_id"] = attack_run_target_contact_id
        if attack_run_tier is not None:
            row["attack_run_tier"] = attack_run_tier
        if attack_run_azimuth_deg is not None:
            row["attack_run_azimuth_deg"] = attack_run_azimuth_deg
        if attack_run_elevation_deg is not None:
            row["attack_run_elevation_deg"] = attack_run_elevation_deg
        if correlation_id is not None:
            row["correlation_id"] = correlation_id
        if push_sent_wall is not None:
            row["push_sent_wall"] = push_sent_wall
        if push_acked_wall is not None:
            row["push_acked_wall"] = push_acked_wall
        if push_duration_s is not None:
            row["push_duration_s"] = push_duration_s
        if self._disabled:
            return
        try:
            self._file.write(json.dumps(row) + "\n")
            # Speech is rare (a handful of lines a minute) and is the row
            # most likely to be the last thing written before something
            # goes wrong, so it flushes immediately rather than waiting for
            # the poll buffer -- the same reasoning `--speech-log` already
            # applies.
            self._file.flush()
        except OSError as exc:
            self._fail(exc)

    def write_poll(
        self,
        collector: DetectionTraceCollector,
        store: ContactStore,
        ownship: OwnshipState,
        *,
        attack_run_target_contact_id: str | None = None,
    ) -> None:
        """Match this poll's admitted `DetectionTrace` entries against
        `store`'s current contacts (via `detection_trace_writer.
        observation_id_to_contact_id`, the shared join) and write one row
        per matched pair. **Deliberately does not clear `collector.
        records`** -- see module docstring; the poll loop owns that, once
        every reader of this poll's collector has had its turn.

        `attack_run_target_contact_id` (`plans/attack-run-sortie-fixes/
        plan.md` BL-B70 §9) is the caller's (`body.py`'s poll loop,
        reading `ConsolePerceptionRunner.attack_run_state.last_contact_id`)
        own knowledge of which contact an active attack run is guiding
        on -- this module computes nothing about *which* contact matters,
        it only measures the one it is told about. When supplied, writes
        one extra `kind: "attack_run_los_tripwire"` row per poll
        (`_write_attack_run_tripwire`) -- a measurement, not an invariant
        assertion (the plan's own reasoning: an unenforced guarantee
        declared in one stage and never checked in the next is exactly
        `BL-B64`'s field-of-regard finding's shape)."""
        if self._disabled:
            return
        contacts_by_id = {contact.id: contact for contact in store.contacts}
        obs_to_contact_id = observation_id_to_contact_id(store)
        observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)

        # `BL-B76`'s object-permanence cache (see `_write_attack_run_
        # tripwire`'s own docstring) is kept warm every poll, regardless of
        # whether a run is active -- a run that starts targeting a contact
        # that was already being observed should not have to wait for its
        # own first admission before the cache knows that contact's
        # object_ids.
        self._update_object_id_contact_cache(collector, obs_to_contact_id)

        if attack_run_target_contact_id is not None:
            self._write_attack_run_tripwire(
                collector,
                obs_to_contact_id,
                attack_run_target_contact_id,
                now_sim=ownship.t_sim,
            )

        for entry in collector.records:
            if (
                entry.outcome is not GateOutcome.ADMITTED
                or entry.observation_id is None
            ):
                continue
            contact_id = obs_to_contact_id.get(entry.observation_id)
            if contact_id is None:
                continue
            contact = contacts_by_id.get(contact_id)
            if contact is None:
                continue
            ground_truth_count = (
                len(entry.cluster_member_object_ids)
                if entry.cluster_member_object_ids is not None
                else None
            )
            row = evaluate_pair(
                t_sim=entry.t_sim,
                contact=contact,
                object_id=entry.object_id,
                object_type=entry.object_type,
                true_bearing_deg=entry.true_bearing_deg,
                true_range_m=entry.true_range_m,
                observer=observer,
                ground_truth_count=ground_truth_count,
            )
            try:
                self._file.write(json.dumps(asdict(row)))
                self._file.write("\n")
            except OSError as exc:
                self._fail(exc)
                break
            if row.tripwire:
                self._stderr.write(
                    f"BELIEF-TRUTH TRIPWIRE t_sim={row.t_sim:.1f} "
                    f"contact={row.contact_id} object_id={row.object_id} "
                    f"believed_range_m={row.believed_range_m:.0f} "
                    f"(cap={NAKED_EYE_RANGE_CAP_M:.0f}) "
                    f"position_error_m={row.position_error_m:.0f} "
                    f"(uncertainty={row.position_uncertainty_m:.0f})\n"
                )
                self._stderr.flush()

        self._polls_since_flush += 1
        if self._polls_since_flush >= self._flush_every_n_polls:
            self.flush()

    def _write_attack_run_tripwire(
        self,
        collector: DetectionTraceCollector,
        obs_to_contact_id: dict[str, str],
        attack_run_target_contact_id: str,
        *,
        now_sim: float,
    ) -> None:
        """One `kind: "attack_run_los_tripwire"` row per poll, for the one
        contact an active attack run is guiding on -- `plans/
        attack-run-sortie-fixes/plan.md` BL-B70 §9's own measurement,
        widened by `BL-B76` Step 1 to distinguish *why* there was no fresh
        observation this poll, not only whether there was one.

        **Three outcomes, not two.** The original (`present_in_snapshot`
        alone) could not tell "rejected at gate 4, blocked" apart from
        "never evaluated this poll" -- both read as `False`. `outcome` now
        names which of the three actually happened:

        - `"admitted"` -- the target's candidate cleared every gate this
          poll (the original, only, case `present_in_snapshot=True` used
          to mean). `join_skew_s`/`live_los_clear` are the live-LOS join's
          own fields, as before.
        - `"rejected"` -- the target's candidate was evaluated this poll
          and a gate rejected it; `gate_outcome` names which one
          (`GateOutcome.value`: `"terrain_los"`, `"range_or_size"`,
          `"cockpit_mask"`, `"gaze"`, `"optic_fov"`, `"forest"`,
          `"player_bubble"`). For a `"terrain_los"` rejection specifically,
          `live_los_clear` is `False` (genuinely blocked, gate 4's verdict
          this poll) or `None` (no fresh verdict this poll) -- `annotate_los`
          (`perception.detection_trace.DetectionTraceCollector`) runs
          upstream of the gate chain, so it is set on a rejected row exactly
          as it would be on an admitted one; this `False`-vs-`None` split
          is the whole point of this change (direction, 2026-10-16: *"Before
          acting on LOS none, we should know how often that happens ...
          log it and then ignore in cockpit behaviour."*).
        - `"absent"` -- the target was not evaluated by `check_visibility`
          at all this poll (outside the pushed wedge, F5's own residual
          cause, or gated out even earlier by gaze/player-bubble in a way
          this module cannot further distinguish without a second join).

        **The join for `"rejected"`, and why it is sound enough to ship.**
        A rejected `DetectionTrace` entry carries an `object_id` but no
        `observation_id` (`observation_id` is only ever set on an
        `ADMITTED` row, once clustering/emission have run) -- and `Contact`
        itself retains no ground-truth `object_id` at all, by the
        no-omniscience boundary (`belief/percept.py`), so there is no
        belief-side field to join a rejected row against. The only sound
        source left is this poll's own `GateOutcome.ADMITTED` entries from
        *other* polls: `_update_object_id_contact_cache` remembers, every
        poll, which `object_id`s an admitted entry's cluster actually
        contributed to which contact, and `_object_ids_for_contact` reads
        that memory back, bounded by `OBJECT_ID_MEMORY_S` -- the same
        window `belief.decay.object_id_continuity_valid` already uses to
        decide how long a DCS `object_id` is still trusted to name the same
        real vehicle. Most of the time a stale or wrong entry in that cache
        can only cause a **miss** (no `"rejected"` row is written; the poll
        looks `"absent"` instead) -- it is the same trust model this
        codebase already accepts for object-permanence, not a new one.

        **One residual case is not a miss, and inflates `"rejected"`
        rather than `"absent"`.** `NakedEyePerceptionSource` resolves a
        cluster split by majority-overlap vote across its member
        `object_id`s, and the vote only takes effect once the split child
        is *admitted* -- `_update_object_id_contact_cache` only ever reads
        `ADMITTED` rows, so it cannot see a split that happens and is
        rejected on the same poll. If the attack target's cluster splits
        and the minority child is rejected that same poll, the cache still
        holds the previous poll's mapping (child's `object_id` -> target's
        `contact_id`), and that rejection gets attributed to the target even
        though it is, or is about to become, a different real contact. This
        is bounded by `OBJECT_ID_MEMORY_S` the same way the accepted
        object_id-reuse risk is, but it biases in one direction: it can only
        ever inflate the `"rejected"` count for the target, never deflate
        it, and a group scattering under fire -- exactly what an attack run
        is likely to encounter -- is exactly when it fires. Read the
        `"rejected"` rate with that in mind; it is an upper bound, not an
        exact count.

        `present_in_snapshot` is kept for backward compatibility and is now
        `outcome != "absent"` -- **its meaning has widened**: it used to be
        `True` only for `"admitted"`, and is now also `True` for
        `"rejected"`. `plans/`, the `sortie-log-triage` skill, and anything
        else reading this field for "was this an admission" rather than
        "was the target evaluated at all" should be checked against the new
        `outcome` field instead."""
        t_sim: float | None = None
        outcome = "absent"
        gate_outcome: str | None = None
        join_skew_s: float | None = None
        live_los_clear: bool | None = None

        for entry in collector.records:
            if (
                entry.outcome is not GateOutcome.ADMITTED
                or entry.observation_id is None
            ):
                continue
            if (
                obs_to_contact_id.get(entry.observation_id)
                != attack_run_target_contact_id
            ):
                continue
            t_sim = entry.t_sim
            outcome = "admitted"
            join_skew_s = entry.los_skew_s
            live_los_clear = entry.live_los_clear
            break

        if outcome == "absent":
            target_object_ids = self._object_ids_for_contact(
                attack_run_target_contact_id, now_sim=now_sim
            )
            for entry in collector.records:
                if entry.outcome is GateOutcome.ADMITTED:
                    continue
                if entry.object_id not in target_object_ids:
                    continue
                t_sim = entry.t_sim
                outcome = "rejected"
                gate_outcome = entry.outcome.value
                join_skew_s = entry.los_skew_s
                live_los_clear = entry.live_los_clear
                break

        row: dict[str, object] = {
            "kind": "attack_run_los_tripwire",
            "t_sim": t_sim,
            "contact_id": attack_run_target_contact_id,
            "present_in_snapshot": outcome != "absent",
            "outcome": outcome,
            "gate_outcome": gate_outcome,
            "join_skew_s": join_skew_s,
            "live_los_clear": live_los_clear,
        }
        try:
            self._file.write(json.dumps(row) + "\n")
        except OSError as exc:
            self._fail(exc)

    def _update_object_id_contact_cache(
        self,
        collector: DetectionTraceCollector,
        obs_to_contact_id: dict[str, str],
    ) -> None:
        """Remember, for every `GateOutcome.ADMITTED` entry this poll that
        resolved to a real contact, which `object_id`s contributed to it --
        `entry.object_id` itself plus every id in
        `entry.cluster_member_object_ids` when clustering/emission filled
        it in. Runs every poll regardless of whether an attack run is
        active, so the cache is already warm by the time a run starts
        guiding on a contact that was seen before the run began. See
        `_write_attack_run_tripwire`'s own docstring for why this is the
        only sound source left for the `object_id -> contact_id` join."""
        for entry in collector.records:
            if (
                entry.outcome is not GateOutcome.ADMITTED
                or entry.observation_id is None
            ):
                continue
            contact_id = obs_to_contact_id.get(entry.observation_id)
            if contact_id is None:
                continue
            self._object_id_to_contact_id[entry.object_id] = contact_id
            self._object_id_last_seen_sim[entry.object_id] = entry.t_sim
            if entry.cluster_member_object_ids is not None:
                for member_id in entry.cluster_member_object_ids:
                    self._object_id_to_contact_id[member_id] = contact_id
                    self._object_id_last_seen_sim[member_id] = entry.t_sim

    def _object_ids_for_contact(
        self, contact_id: str, *, now_sim: float
    ) -> frozenset[int]:
        """Every `object_id` the cache still trusts as belonging to
        `contact_id` -- bounded by `OBJECT_ID_MEMORY_S`, same window and
        same reasoning as `belief.decay.object_id_continuity_valid`. An
        entry older than the window is silently excluded rather than
        trusted indefinitely, so a `contact_id` that has not been admitted
        in a long time yields an empty set (read as `"absent"`, not a
        wrong attribution) rather than a stale one."""
        return frozenset(
            object_id
            for object_id, mapped_contact_id in self._object_id_to_contact_id.items()
            if mapped_contact_id == contact_id
            and now_sim - self._object_id_last_seen_sim[object_id] <= OBJECT_ID_MEMORY_S
        )

    def flush(self) -> None:
        if self._disabled:
            return
        try:
            self._file.flush()
        except OSError as exc:
            self._fail(exc)
        self._polls_since_flush = 0

    def close(self) -> None:
        """Flush and close, never raising -- the same `BL-11` Stage 5
        reasoning as `detection_trace_writer.DetectionTraceWriter.close`:
        `flush` early-returns once disabled, so unwritable buffered data
        comes out of `close()`, which the poll loop calls from a `finally:`
        block."""
        self.flush()
        with contextlib.suppress(OSError):
            self._file.close()

    def _fail(self, exc: OSError) -> None:
        """Report one write failure, then stop writing for the rest of the
        run -- `BL-11` Stage 5, the same policy and the same reasoning as
        `detection_trace_writer.DetectionTraceWriter._fail`: a full disk
        mid-flight was previously swallowed by the poll loop's own broad
        `except Exception`, one traceback per poll, with nothing saying the
        log had stopped being useful. Only this writer stops; perception,
        belief and speech are untouched.

        Reported on this writer's own `self._stderr`, not `sys.stderr`
        directly, so it lands wherever the tripwire lines already do."""
        self._disabled = True
        self._stderr.write(
            f"belief-truth-log: write to {self._path} failed ({exc}); "
            f"no further rows will be written this run\n"
        )
        self._stderr.flush()
