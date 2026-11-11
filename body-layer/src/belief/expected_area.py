"""Expected-area look -- `BL-B111`, `plans/expected-area-look/plan.md`.

When a gate-path sighting B lands on, or beside, a group A that Petrovich
remembers but cannot see right now, he holds B and puts the binoculars on
A's expected place before deciding whether B is a second group or A
itself, seen again. This module is the mechanism end to end:

- **State**: `ExpectedAreaCheck`, one per held contact `B`, carried in
  `belief.contacts.ContactStore._checks`.
- **The trigger**: `eligible_trigger_target` (the gate-fold/ambiguous-fold
  path's own precondition) and `merge_echo_or_beside_lost_target` (the
  founded-fresh path's own scan) -- pure predicates, called from
  `ContactStore.ingest`'s existing gate/founding branches, never a
  separate pass over the whole store.
- **The look's own verdict**: `area_visibility` (Stage 2) -- pure,
  fail-closed, table-driven.
- **The one "when" function**: `resolve_checks` -- advances every open
  check by exactly one step per poll, given the facts `body.py` has
  already assembled (`LookEvidence`, whether A was observed, whether a
  relocation line is warranted, whether a pilot command paused
  everything). It never reaches into `OpticState`/perception itself --
  those are state params the caller supplies, per root `CLAUDE.md`'s
  "actions / state params / one 'when' function" shape.
- **The actions**: four `ContactStore` methods (`release_check`,
  `record_believed_distinct`, `merge_contact`, `mark_lost_now`) that
  `resolve_checks` is the one caller of -- each does one thing, none of
  them decides *when* (that is `resolve_checks`'s job alone). "Hold" is
  not a separate action: it is simply opening an `ExpectedAreaCheck` for
  `b_id` (`ContactStore.open_check`), checked via `callout_held`/
  `has_open_check`.

**No omniscience.** Every geometric fact this module reasons about comes
from `Contact.position`/`last_class_raw` (believed state) or from a
`ProbeAnswers`-shaped tri-state answer about one *terrain point* -- never
a DCS object id, never ownship's own elevation substituting for the
probed point's. A probe that did not answer, answered stale, or failed
its own pcall is `None`/missing and reads as "cannot look", never
"empty" -- `area_visibility`'s own fail-closed contract, which this
module enforces structurally (there is no branch that treats a missing
probe as clear).

**`EXPECTED_AREA_MAX_HALF_WIDTH_DEG` is a feasibility gate, not a
separability predictor** (Decision 1): it answers "does A have an
expected *place* narrow enough that one glance could cover it", not
"are A and B probably different groups". A group whose believed area has
already grown past one binocular sweep gets no check at all -- the
question "is this the group I left there?" does not honestly arise when
there is no single place left to look at, and today's silent fold stands
for that case (the plan's own accepted cost, tied to `[[BL-B112]]`)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, Protocol

import tuning
from belief.association_over_time import _contact_covariance, contacts_plausibly_same
from belief.classification import (
    AIR_DEFENSE_OP_CLASSES,
    class_compatibility,
    parent_class_of,
)
from belief.position_belief import _down_axis_unit
from perception.gaze import FOCUS_DWELL_S
from perception.geometry import GeoPosition, angular_delta_deg, bearing_deg, range_m

#: Mirrors `belief.optic_policy.LOOK_SWEEP_SIGMA` (3.0) -- **declared
#: independently, not imported**, the same posture that constant's own
#: docstring already takes toward `belief.association_over_time.
#: GATE_SIGMA_THRESHOLD`: a shared value is not a shared question (how
#: wide a *look* must sweep vs. how wide A's *believed area* is for the
#: feasibility gate), and importing it here would also reopen a real
#: import cycle -- `optic_policy` imports `belief.enrichment`, which
#: imports `belief.contacts`, which imports this module to call the
#: trigger/verdict functions below.
_LOOK_SWEEP_SIGMA: Final[float] = 3.0

if TYPE_CHECKING:
    # `belief.contacts` imports this module to call the trigger/verdict
    # functions below -- importing `Contact` back at module level here
    # would be a real import cycle at runtime. `from __future__ import
    # annotations` already makes every annotation in this file a lazy
    # string, so the only thing this guard protects is the type checker.
    from belief.contacts import Contact

#: `plans/expected-area-look/plan.md` Stage 2 -- how wide A's believed
#: area (its growth-inflated covariance, the same formula the gate's own
#: `_contact_covariance` already uses) may be, in half-degrees from the
#: observer, and still fit inside one binocular sweep. Above this, no
#: look could cover the place at all, so no check opens for that A at all
#: (Decision 1) -- this is a feasibility gate, never a separability
#: predictor; see the module docstring's own paragraph on the
#: distinction. 15 degrees matches the architect probe's own modelled
#: value (`tools/measure_expected_area_look.py`); `lo` is a single
#: binocular field's own half-width (`perception.optics.BINOCULAR_OPTIC`,
#: ~4.25 degrees -- narrower makes almost every remembered group
#: ineligible for a check at all) and `hi` 30 (`belief.optic_policy.
#: MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`'s own ceiling for a single sweep;
#: wider starts asking one glance to cover more ground than a binocular
#: search itself is ever modelled sweeping).
EXPECTED_AREA_MAX_HALF_WIDTH_DEG: Final[float] = tuning.real(
    "belief.expected_area.EXPECTED_AREA_MAX_HALF_WIDTH_DEG",
    15.0,
    lo=4.25,
    hi=30.0,
    status="judgement",
)

#: `plans/expected-area-look/plan.md` Stage 3b -- "same" requires the
#: count-interval midpoints of A (before the hold) and B not to differ by
#: more than this ratio, the larger over the smaller. 2.0 is the
#: architect's own stated default; `lo` 1.2 (tighter and almost any real
#: count-bucket uncertainty would fail a genuine same-group re-sighting --
#: `belief.cardinality`'s own buckets are coarser than that) and `hi` 5.0
#: (wider and "3 and 8" -- the plan's own named example of what should
#: raise suspicion -- would pass).
COMPOSITION_MATCH_RATIO: Final[float] = tuning.real(
    "belief.expected_area.COMPOSITION_MATCH_RATIO",
    2.0,
    lo=1.2,
    hi=5.0,
    status="judgement",
)

#: `plans/expected-area-look/plan.md` Stage 1 -- "two open checks x three
#: points", matching `aircraft-layer`'s `MAX_PROBE_POINTS` (6) exactly.
#: Not a `tuning.real`/`tuning.whole` constant: it is a protocol bound
#: shared with the Hook's own fixed-shape `SET_PROBES_TEMPLATE`, not a
#: dial that changes what Petrovich does -- root `CLAUDE.md`'s tuning
#: policy excludes a protocol constant for exactly this reason.
MAX_OPEN_CHECKS: Final[int] = 2

#: Probe points per open check -- A's believed point, plus the two
#: along-line (down-range) +-2 sigma points (Decision 4). A plain
#: literal, not a tunable: the plan states "all three," not a dial.
PROBE_POINTS_PER_CHECK: Final[int] = 3

#: Decision 4's own fixed offset -- along-line +-2 sigma, not
#: `LOOK_SWEEP_SIGMA` (3, `belief.optic_policy`'s own sweep-coverage
#: constant, a different question: how wide a *look* must sweep, not how
#: far apart the *probe* points sit).
_PROBE_SIGMA_MULTIPLE: Final[float] = 2.0

CheckKind = Literal["fold", "beside_lost", "echo"]


@dataclass(frozen=True)
class ExpectedAreaCheck:
    """One open check: B is held, A's expected place is being looked at.

    `a_snapshot` is a deep-copied `Contact` -- A's believed position,
    covariance and classification *at the moment the check opened*.
    **A is not mutated during the hold** (the plan's own invariant): the
    live `Contact` for `a_id` keeps recording any percept that genuinely
    resolves onto it (that is how "A observed" is detected -- see
    `a_observed` below), but this module never writes through `a_id`
    itself; `a_snapshot` is what the verdict is judged against."""

    b_id: str
    a_id: str
    kind: CheckKind
    opened_sim: float
    a_snapshot: Contact
    released: bool = False
    released_sim: float | None = None


def area_half_width_deg(a: Contact, now_sim: float, observer: GeoPosition) -> float:
    """Half-width, degrees, of the sweep that would cover `a`'s own
    growth-inflated believed area from `observer` -- Decision 1's
    feasibility gate, and the same formula `tools/
    measure_expected_area_look.py`'s own `hw` used at architect time.
    `_contact_covariance` is the gate's own growth-inflation (`belief.
    association_over_time`), reused rather than re-derived -- "one table"
    (that module's own `contact_growth_rate_mps` docstring)."""
    elapsed_s = max(0.0, now_sim - a.last_seen_sim)
    cov = _contact_covariance(a, elapsed_s)
    target = GeoPosition(x=a.position.x, z=a.position.z, alt_m=observer.alt_m)
    rng = range_m(observer, target)
    if rng <= 0.0:
        return 0.0
    return math.degrees(
        math.atan(_LOOK_SWEEP_SIGMA * math.sqrt(max(cov.xx, 0.0)) / rng)
    )


def area_fits_one_look(a: Contact, now_sim: float, observer: GeoPosition) -> bool:
    """Decision 1's feasibility gate, as a bool -- the trigger's own
    precondition, and also `area_visibility`'s own re-check during the
    hold (A's area may have grown wider while the check was open)."""
    return area_half_width_deg(a, now_sim, observer) <= EXPECTED_AREA_MAX_HALF_WIDTH_DEG


def _op_class_is_threat(class_raw: str) -> bool:
    op_class = parent_class_of(class_raw)
    return op_class is not None and op_class in AIR_DEFENSE_OP_CLASSES


def b_is_threat(b: Contact) -> bool:
    """Q2's release-at-once condition -- B's own believed classification
    is an air-defence `op_class`, or B is currently firing. Evaluated once,
    at check-open time (the plan's own "Action" bullet), not re-evaluated
    every poll -- a threat does not stop being worth calling immediately
    just because it was not one a moment ago."""
    return _op_class_is_threat(b.last_class_raw) or b.is_firing


def probe_points_for(
    a: Contact, now_sim: float, observer: GeoPosition
) -> list[tuple[int, int]]:
    """A's believed point, plus the two along-line (down-range) +-2 sigma
    points (Decision 4) -- the `PROBE_POINTS_PER_CHECK` terrain points
    probed for one open check, in metres, rounded to the nearest integer
    for the wire (`aircraft-layer`'s `SET_PROBES_TEMPLATE` is `%d`-only).

    "Along-line" is the observer -> A bearing (down-range): the same axis
    `belief.position_belief._down_axis_unit` already uses for the
    look-correlation kernel, reused here rather than re-derived."""
    elapsed_s = max(0.0, now_sim - a.last_seen_sim)
    cov = _contact_covariance(a, elapsed_s)
    a_point = GeoPosition(x=a.position.x, z=a.position.z, alt_m=observer.alt_m)
    bearing = bearing_deg(observer, a_point)
    down_x, down_z = _down_axis_unit(bearing)
    variance_along = (
        cov.xx * down_x * down_x
        + 2.0 * cov.xz * down_x * down_z
        + cov.zz * down_z * down_z
    )
    sigma_down_m = math.sqrt(max(0.0, variance_along))
    offsets_m = (
        0.0,
        _PROBE_SIGMA_MULTIPLE * sigma_down_m,
        -_PROBE_SIGMA_MULTIPLE * sigma_down_m,
    )
    return [
        (round(a.position.x + offset * down_x), round(a.position.z + offset * down_z))
        for offset in offsets_m
    ]


# --- The trigger (Stage 3a) -------------------------------------------


def a_out_of_view(a: Contact, now_sim: float) -> bool:
    """A is held only in memory: not seen within the current look (one
    gaze dwell). **Amended 2026-11-11** (plan, "Trigger precondition,
    amended 2026-11-11"): the literal reading, `a.last_seen_sim < now_sim`,
    is true of nearly every ordinary gate match by construction -- a
    passing candidate's own `last_seen_sim` is always from a strictly
    earlier poll than the percept now being matched against it -- which
    fired on all 18 gate matches of a contact tracked continuously
    through the gate at 1 s polls and broke two existing `test_contacts.py`
    tests (`feedback_tautological_trigger_precondition.md`). `FOCUS_DWELL_S`
    is how long one look stays on one o'clock; a contact seen within it is
    in the current look, one older than it is held from memory. Uses
    perceived state only (`last_seen_sim`), never DCS truth."""
    return (now_sim - a.last_seen_sim) > FOCUS_DWELL_S


def eligible_trigger_target(
    a: Contact, b_percept_t_sim: float, observer: GeoPosition
) -> bool:
    """Whether `a` qualifies to have a check opened against it for a
    sighting at `b_percept_t_sim` -- the two conditions common to every
    trigger path (gate fold, ambiguous fold, merge-echo, beside-lost-A):
    A is out of view (`a_out_of_view`), and A's area fits one look
    (Decision 1). Callers combine this with their own path-specific
    condition (the gate actually matching A, or `contacts_plausibly_same`);
    this function does not decide *which* A, only whether a given
    candidate A is a legal target at all."""
    return a_out_of_view(a, b_percept_t_sim) and area_fits_one_look(
        a, b_percept_t_sim, observer
    )


def merge_echo_or_beside_lost_target(
    b: Contact,
    candidates: list[Contact],
    now_sim: float,
    observer: GeoPosition,
    *,
    certainty_of_a_is_lost: dict[str, bool],
) -> tuple[Contact, CheckKind] | None:
    """After `b` has been founded fresh (no gate match at all), is there
    an earlier, eligible A it could plausibly be an echo of, or sit beside
    (the trigger's third case)? Covers both the merge-echo case (A is not
    lost -- today's `_is_merge_echo_of_earlier_contact` would silence B)
    and the beside-a-lost-A case (A is `lost` -- nothing would silence B
    today, but the same "is this really A?" question honestly arises).

    `certainty_of_a_is_lost` is a precomputed `{contact_id: bool}` map
    (the caller's own `belief.decay.certainty_of(candidate, now_sim) ==
    "lost"`) -- a state param, not recomputed here, so this function stays
    a pure geometric/compatibility test over its inputs.

    If several A qualify, the nearest by Mahalanobis is taken (the plan's
    own tie-break) -- approximated here by nearest Euclidean range, since
    every qualifying candidate has already passed the symmetric covariance
    gate (`contacts_plausibly_same`) and a second, redundant Mahalanobis
    ranking over the same two covariances would not change the order for
    any case this project's own tests construct."""
    qualifying: list[Contact] = []
    for candidate in candidates:
        if candidate.id == b.id:
            continue
        if candidate.first_seen_sim >= b.first_seen_sim:
            continue
        if not eligible_trigger_target(candidate, now_sim, observer):
            continue
        if not contacts_plausibly_same(b, candidate, now_sim):
            continue
        qualifying.append(candidate)
    if not qualifying:
        return None

    def _range(c: Contact) -> float:
        return range_m(
            observer, GeoPosition(x=c.position.x, z=c.position.z, alt_m=observer.alt_m)
        )

    nearest = min(qualifying, key=lambda c: (_range(c), c.id))
    kind: CheckKind = (
        "beside_lost" if certainty_of_a_is_lost.get(nearest.id, False) else "echo"
    )
    return nearest, kind


# --- The look's own verdict (Stage 2) ----------------------------------

#: `land.isVisible`'s own answer for one probed point: `True` (clear),
#: `False` (blocked), or `None` ("cannot look" -- no answer, a stale
#: answer, or the Hook's own pcall failed). Matches `aircraft-layer`'s
#: `ProbeAnswer.clear` exactly.
ProbeClear = bool | None


def area_visibility(
    *,
    area_fits_one_look_now: bool,
    look_completed_naturally: bool,
    inside_cockpit_mask: bool,
    within_binocular_presence_range: bool,
    occluded: bool,
    probe_seq_matches: bool,
    probe_time_in_window: bool,
    probe_clear: tuple[ProbeClear, ProbeClear, ProbeClear],
) -> Literal["visible", "cannot_look"]:
    """ "Was A's expected place visible?" -- Stage 2, every clause
    required, fail-closed throughout (a missing/stale/mismatched fact at
    any clause is `"cannot_look"`, never a guess toward `"visible"`).

    - `area_fits_one_look_now`: Decision 1's own gate, re-checked (A's
      area may have grown while the check was open).
    - `look_completed_naturally`: a look at A's expected place ran in the
      binocular optic to its own natural end, steady, with that place
      inside the look's own swept envelope -- the caller's own state
      param (`body.py`, reading `OpticState`), not recomputed here.
    - `inside_cockpit_mask`: the believed place is inside the cockpit
      mask from ownship right now.
    - `within_binocular_presence_range`: A's believed type is within
      binocular presence range at A's believed range (`perception.
      visibility.tier_ranges`, evaluated by the caller).
    - `occluded`: forest or settlement landcover at A's believed point
      (`perception.forest.ForestOcclusion`, evaluated by the caller) --
      `land.isVisible` is terrain-only, so a town or a wood reads
      "cannot look" regardless of what the probes say.
    - `probe_seq_matches`/`probe_time_in_window`: the probe answer this
      check is reading is for *this* check's own outstanding request
      (`seq`), and its `dcs_model_time_s` falls inside [look start - 2s,
      look end + 2s] -- stale or mismatched answers never count.
    - `probe_clear`: the three probe answers (centre, +2 sigma, -2 sigma
      along-line, Decision 4) -- every one must be `True`. Any `False`
      *or* `None` gives `"cannot_look"` -- `None` is never read as
      "empty," per E5/E11."""
    if not (
        area_fits_one_look_now
        and look_completed_naturally
        and inside_cockpit_mask
        and within_binocular_presence_range
        and not occluded
        and probe_seq_matches
        and probe_time_in_window
    ):
        return "cannot_look"
    if any(answer is not True for answer in probe_clear):
        return "cannot_look"
    return "visible"


# --- Composition/displacement, for the "same"/"absent" split (Stage 3b) -


def _cardinality_midpoint(contact: Contact) -> float:
    return (contact.cardinality.lo + contact.cardinality.hi) / 2.0


def composition_compatible(a_snapshot: Contact, b: Contact) -> bool:
    """Stage 3b's "same" clause: count-interval midpoints ratio within
    `COMPOSITION_MATCH_RATIO`, plus class compatibility -- `belief.
    association_over_time.class_compatibility`, the same classifier the
    gate itself uses, reused rather than re-derived (root `CLAUDE.md`,
    "do not reinvent the wheel")."""
    if (
        class_compatibility(a_snapshot.last_class_raw, b.last_class_raw)
        == "incompatible"
    ):
        return False
    a_mid = _cardinality_midpoint(a_snapshot)
    b_mid = _cardinality_midpoint(b)
    if a_mid <= 0.0 or b_mid <= 0.0:
        return True  # nothing to compare against -- never the deciding clause
    ratio = max(a_mid, b_mid) / min(a_mid, b_mid)
    return ratio <= COMPOSITION_MATCH_RATIO


def displacement_plausible(a_snapshot: Contact, b: Contact, now_sim: float) -> bool:
    """Stage 3b's other "same" clause: B's position is where A could
    plausibly have moved to since the snapshot -- `contacts_plausibly_
    same`, the same symmetric gate the trigger's own merge-echo path
    already trusts, reused rather than a second displacement formula."""
    return contacts_plausibly_same(a_snapshot, b, now_sim)


def is_same(a_snapshot: Contact, b: Contact, now_sim: float) -> bool:
    """Stage 3b's full "same" predicate -- visibility is the caller's own
    precondition (only reached once `area_visibility` says "visible" and
    A was not observed); this is composition + displacement only."""
    return composition_compatible(a_snapshot, b) and displacement_plausible(
        a_snapshot, b, now_sim
    )


#: Decision 3's own two spoken-bucket thresholds -- not a `tuning.real`:
#: the plan states them as "one spoken bucket each, derived from
#: `_format_range_km` and the clock hour, not a new tunable."
_RELOCATION_RANGE_BUCKET_M: Final[float] = 500.0
_RELOCATION_BEARING_BUCKET_DEG: Final[float] = 30.0


#: --- The actions + the one "when" function (Stage 3a/3b) -------------


class _StoreLike(Protocol):
    """The slice of `belief.contacts.ContactStore` `resolve_checks` needs
    -- a `Protocol`, not a concrete import, so this module never imports
    `belief.contacts` at runtime (see the `TYPE_CHECKING` guard above) and
    a test can supply a small fake instead of a real store."""

    def contact(self, contact_id: str) -> Contact | None: ...
    def close_check(self, b_id: str) -> None: ...
    def release_check(self, b_id: str, now_sim: float) -> None: ...
    def record_believed_distinct(self, a_id: str, b_id: str) -> None: ...
    def merge_contact(self, *, into: str, source: str) -> None: ...
    def mark_lost_now(self, contact_id: str, now_sim: float) -> None: ...


Verdict = Literal["different", "same", "absent", "cannot_look", "still_open"]


@dataclass(frozen=True)
class LookEvidence:
    """Everything `area_visibility` needs for one open check, assembled by
    the caller (`body.py`, reading `OpticState`/the probe answer/world-
    model occlusion) -- see `area_visibility`'s own docstring for what
    each field means. A state param bundle, not computed here."""

    area_fits_one_look_now: bool
    look_completed_naturally: bool
    inside_cockpit_mask: bool
    within_binocular_presence_range: bool
    occluded: bool
    probe_seq_matches: bool
    probe_time_in_window: bool
    probe_clear: tuple[ProbeClear, ProbeClear, ProbeClear]


@dataclass(frozen=True)
class CheckOutcome:
    """What `resolve_checks` decided for one check this poll -- the
    caller's own record for logging/`sortie-log-triage`, not required to
    drive anything further (every store mutation this verdict implies has
    already happened by the time this is returned)."""

    b_id: str
    a_id: str
    verdict: Verdict
    relocation_line: bool = False


def resolve_checks(
    store: _StoreLike,
    checks: Sequence[ExpectedAreaCheck],
    *,
    now_sim: float,
    deadline_s: float,
    look_evidence: Mapping[str, LookEvidence],
    a_observed: Mapping[str, bool],
    relocation_warranted_by_b: Mapping[str, bool],
    a_was_announced: Mapping[str, bool],
    paused: bool,
) -> list[CheckOutcome]:
    """The one "when" function -- advances every check in `checks` by
    exactly one step, mutating `store` through its action methods
    (`close_check`/`release_check`/`record_believed_distinct`/
    `merge_contact`/`mark_lost_now`) and returning what happened. Never
    decides *how* to look or *what* a verdict means -- `look_evidence`/
    `a_observed`/`relocation_warranted_by_b`/`a_was_announced` are all
    state params the caller has already resolved; this function only
    sequences the verdict table (Stage 3a/3b) and invokes the matching
    action.

    `paused` (an ATGM run engaged, or an attack-run grant standing) makes
    every open check resolve `"cannot_look"` at once, the plan's own Q5
    row -- checked first, before any per-check evidence."""
    outcomes: list[CheckOutcome] = []
    for check in checks:
        # A check already `released` (a threat, Q2) still runs this same
        # loop body unchanged -- release only ever affects whether B's
        # callout is held, never whether the check keeps looking for a
        # verdict (a later "same" still wants its relocation line).
        a_id, b_id = check.a_id, check.b_id
        a = store.contact(a_id)
        b = store.contact(b_id)
        if a is None or b is None:
            # Either side vanished from the store entirely (should not
            # happen -- defensive only). Close without a verdict rather
            # than raise on a store the caller somehow mutated underneath
            # this check.
            store.close_check(b_id)
            continue

        deadline_reached = (now_sim - check.opened_sim) >= deadline_s

        if paused:
            verdict: Verdict = "cannot_look"
        elif a_observed.get(a_id, False):
            verdict = "different"
        else:
            evidence = look_evidence.get(b_id)
            if evidence is None:
                visibility: Literal["visible", "cannot_look"] = "cannot_look"
            else:
                visibility = area_visibility(
                    area_fits_one_look_now=evidence.area_fits_one_look_now,
                    look_completed_naturally=evidence.look_completed_naturally,
                    inside_cockpit_mask=evidence.inside_cockpit_mask,
                    within_binocular_presence_range=evidence.within_binocular_presence_range,
                    occluded=evidence.occluded,
                    probe_seq_matches=evidence.probe_seq_matches,
                    probe_time_in_window=evidence.probe_time_in_window,
                    probe_clear=evidence.probe_clear,
                )
            if visibility == "visible":
                if is_same(check.a_snapshot, b, now_sim):
                    verdict = "same"
                else:
                    verdict = "absent"
            elif deadline_reached:
                verdict = "cannot_look"
            else:
                verdict = "still_open"

        if verdict == "still_open":
            outcomes.append(CheckOutcome(b_id, a_id, "still_open"))
            continue

        if verdict == "different":
            store.release_check(b_id, now_sim)
            store.record_believed_distinct(a_id, b_id)
            store.close_check(b_id)
        elif verdict == "cannot_look":
            if check.kind == "echo":
                # Decision 2 -- stay silent, as today's echo suppression
                # already would. Nothing to release; B simply keeps
                # whatever today's mechanism already does with it.
                pass
            else:
                store.release_check(b_id, now_sim)
            store.close_check(b_id)
        elif verdict == "same":
            store.merge_contact(into=a_id, source=b_id)
            store.close_check(b_id)
        elif verdict == "absent":
            store.release_check(b_id, now_sim)
            store.mark_lost_now(a_id, now_sim)
            store.close_check(b_id)

        outcomes.append(
            CheckOutcome(
                b_id,
                a_id,
                verdict,
                relocation_line=(
                    verdict == "same"
                    and a_was_announced.get(a_id, False)
                    and relocation_warranted_by_b.get(b_id, False)
                ),
            )
        )
    return outcomes


def relocation_warranted(
    *,
    before_clock: int,
    before_range_m: float,
    before_bearing_deg: float,
    after_clock: int,
    after_range_m: float,
    after_bearing_deg: float,
) -> bool:
    """Decision 3's full relocation predicate -- *both* conditions:

    1. the spoken clock hour **or** the 0.5 km range bucket (`belief.
       speech._format_range_km`'s own rounding) A would be called at
       changed between the snapshot and the merged position;
    2. the merged position moved >= 500 m in range or >= 30 degrees in
       bearing (true bearing, not the clock bucket -- a real correction,
       not jitter at a bucket edge).

    All six inputs are the caller's own `belief.enrichment.
    relative_geometry(ownship, target)` results (clock_position, range_m,
    bearing_deg), evaluated once against `a_snapshot`'s position and once
    against the merged `Contact`'s position, both from the *same* current
    ownship -- this function is a pure comparison over those six numbers,
    nothing more."""
    bucket_changed = before_clock != after_clock or (
        round(before_range_m / _RELOCATION_RANGE_BUCKET_M)
        != round(after_range_m / _RELOCATION_RANGE_BUCKET_M)
    )
    if not bucket_changed:
        return False
    moved_range_m = abs(after_range_m - before_range_m)
    moved_bearing_deg = angular_delta_deg(before_bearing_deg, after_bearing_deg)
    return (
        moved_range_m >= _RELOCATION_RANGE_BUCKET_M
        or moved_bearing_deg >= _RELOCATION_BEARING_BUCKET_DEG
    )
