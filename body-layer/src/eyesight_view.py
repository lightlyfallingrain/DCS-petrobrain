"""The real-time ASCII eyesight view -- a debug, testing and calibration
instrument, `todo/todo.md`'s "Added 2026-09-25 (user)" entry: *"it'd help
if I could visually see where Petrovich is looking and with what. A
realtime ascii graphic would do just fine."*

**This module may show ground truth, deliberately, and it says so here so
the next reader does not mistake that for an omniscience violation.** The
user, 2026-09-25: *"it's a debug and testing tool. Can break no-omniscience
boundary because the whole purpose is testing, debugging and calibration."*
A view restricted to belief could not answer the question it exists to
answer -- *why did he not see that* -- so it draws both a ground-truth
marker (`GroundTruthMarker`, from `perception.detection_trace.
DetectionTrace` -- true bearing/range and whether the gate admitted it)
and a believed marker (`BeliefMarker`, from a live `belief.contacts.
Contact` or, offline, from a trace row's own `contact_id`) for the same
poll, side by side.

**The invariant that still binds: read-only, one-directional flow, exactly
`detection_trace_writer.py`'s own precedent and model.** Nothing in this
module calls anything that mutates `belief.contacts.ContactStore`, and no
ground-truth field it reads is ever passed into `ContactStore.ingest`,
`Percept`, or `Contact` -- it only *renders* state two other modules
already computed. `belief/` gains no import of this module; this module's
own `belief.contacts.Contact` import is read-only attribute access, the
same posture `detection_trace_writer.py` already established for the one
module in this codebase allowed to hold both ground truth and belief at
once.

**Geometry.** Top-down plan view, ownship anchored near the bottom of the
canvas (not the literal last row -- see `render_frame`'s docstring on why
a few rows are reserved below it), forward pointing up the screen. Bearing
is *ownship-heading-relative*, `perception.gaze.Gaze`'s own convention (`0`
dead ahead, positive clockwise) -- `relative_bearing_deg` converts a true
(world-compass) bearing into it. Terminal character cells read roughly
2:1 tall, so a metre of range needs about twice as many rows as columns to
look circular rather than elliptical (`_ROW_METER_STRETCH`).

**Radius (user, 2026-09-25, correcting an earlier draft's 10 km): the view
defaults to 5 km, not the naked-eye channel's own 10 km detection cap.**
Those are different quantities -- display scale, not perception limit --
and the calibration table's own furthest-detectable entries (an S-300
tracking-radar mast at 8.89 km, `visibility.py`'s tier constants) exceed
5 km, so a contact beyond `radius_m` is never silently dropped: it is
placed at the canvas rim on its own true bearing (`_clip_range`) *and*
listed in the frame's trailing legend with its exact range, exactly so
"there is an AA out that way at 8.8 km" stays legible even though it
cannot be plotted to scale. `radius_m` is a `render_frame` parameter, not
a constant, so a caller can step it out to 10 km (or any other value) for
a long-range question without a code change.

**Draw order is load-bearing** (mock-pass finding, orchestrator brief):
range rings and the gaze cone are laid down first, ground-truth markers
next, and believed markers last -- a believed contact always wins its
cell, even when the gaze cone or a range ring would otherwise occupy it.
Losing a contact behind the cone drawing is exactly the case this
instrument exists to make visible, so it may never happen."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from belief.attention import AttentionArea, effective_attention
from belief.classification import SpecificityLevel, parent_class_of
from belief.contacts import Contact
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.gaze import Gaze
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.object_model import profile_for

#: `belief.classification`'s ED-vocabulary `OP_*` buckets this view reads
#: as "air defence" -- SAM launchers/radars plus the two self-propelled AA
#: guns, `object_model.py`'s own `op_class` vocabulary (grepped, not
#: guessed: these are the only eight `OP_*` values that table assigns).
_AIR_DEFENCE_CLASSES: Final[frozenset[str]] = frozenset(
    {"OP_SRSAM", "OP_MRSAM", "OP_LRSAM", "OP_SPAAG", "OP_ZU23"}
)

#: Rows read roughly twice as tall as columns read wide in a typical
#: terminal font -- without this, a range ring draws as a flattened
#: ellipse rather than a circle (mock-pass finding #1, orchestrator
#: brief). Applied by scaling `meters_per_row` up relative to
#: `meters_per_col`, not by scaling the canvas itself.
_ROW_METER_STRETCH: Final[float] = 2.0

#: The view's default radius (user, 2026-09-25) -- see module docstring.
DEFAULT_RADIUS_M: Final[float] = 5000.0

#: Default canvas width in columns. Odd, so there is a single centre
#: column ownship sits under.
DEFAULT_WIDTH: Final[int] = 61

#: Total lines one frame may occupy -- canvas, header, legend and the
#: beyond-radius list together.
#:
#: **Found in use, not in testing** (user, 2026-09-25): with a long
#: beyond-radius list the frame overflowed the console and the canvas
#: scrolled off the top, so the picture the tool exists to show was the
#: part that got lost. His workaround was raising the radius to 10 km,
#: which is exactly backwards -- it shrinks the list by making the view
#: coarser.
#:
#: Resolved by capping the list rather than the canvas: the canvas is the
#: instrument, the list is an overflow note about things it could not
#: draw. A truncated list says so on its last line and keeps the *nearest*
#: entries, which are the ones most likely to matter.
DEFAULT_MAX_LINES: Final[int] = 60

#: How many concentric range rings to draw, evenly spaced from the centre
#: out to `radius_m`.
_RING_COUNT: Final[int] = 4

#: Angular step (degrees) used to trace a ring or a cone edge -- fine
#: enough that consecutive plotted cells are contiguous at this canvas's
#: typical resolution, coarse enough not to cost real time per frame.
_TRACE_STEP_DEG: Final[float] = 2.0

_RESET: Final[str] = "\x1b[0m"
_DIM: Final[str] = "\x1b[2m"
_BOLD: Final[str] = "\x1b[1m"
_GREEN: Final[str] = "\x1b[32m"
_BLUE: Final[str] = "\x1b[34m"
_GRAY: Final[str] = "\x1b[90m"
_YELLOW: Final[str] = "\x1b[33m"

#: Watched contacts (user, 2026-09-25). 256-colour orange rather than one of
#: the eight basic codes, because the basic set has no orange and the nearest
#: -- bright yellow -- is too close to `_YELLOW` to distinguish a watched
#: contact from an ordinary one at a glance, which is the entire point.
_ORANGE: Final[str] = "\x1b[38;5;208m"


def _wrap(text: str, *codes: str, color: bool) -> str:
    """Apply ANSI `codes` to `text`, or return it unchanged when `color` is
    `False` -- the one place this module branches on colour support, so
    every caller can simply pass `color=` through without its own
    conditional."""
    if not color or not codes:
        return text
    return "".join(codes) + text + _RESET


def relative_bearing_deg(true_bearing_deg: float, heading_true_deg: float) -> float:
    """`true_bearing_deg` (world-compass) expressed relative to
    `heading_true_deg`, in `perception.gaze.Gaze`'s convention: `0` dead
    ahead, positive clockwise, range `(-180, 180]`."""
    return (true_bearing_deg - heading_true_deg + 180.0) % 360.0 - 180.0


@dataclass(frozen=True, slots=True)
class GroundTruthMarker:
    """One real object, ground truth, for one poll -- from a `perception.
    detection_trace.DetectionTrace` record. `bearing_deg` is already
    ownship-heading-relative (module docstring's convention); `visible` is
    whether `check_visibility`'s gates admitted it this poll (`GateOutcome.
    ADMITTED`), the signal that drives which glyph it draws as."""

    bearing_deg: float
    range_m: float
    visible: bool


@dataclass(frozen=True, slots=True)
class BeliefMarker:
    """One believed contact, for one poll -- `label` is a short id
    (`contact_label`'s `AA`/`AR`/`TR`/`G`/`U` vocabulary), `bearing_deg`
    already ownship-heading-relative."""

    label: str
    bearing_deg: float
    range_m: float

    #: Drawn in orange rather than yellow (user, 2026-09-25). Read from
    #: `belief.attention.effective_attention`, i.e. the *derived* level --
    #: a contact inside a `watch`-level `AttentionArea` counts as watched
    #: even with an unmarked direct attention, which is the same definition
    #: every watched-only callout uses. Keeping the two in step matters:
    #: the reason to see watched-ness on the plan is to understand why a
    #: contact is producing unprompted reports, and a view using a
    #: different definition than the callouts would answer the wrong
    #: question.
    watched: bool = False


def contact_label(contact: Contact) -> str:
    """The short id `render_frame` draws for `contact` -- `AA` air
    defence, `AR` armour, `TR` truck, `G` group, `U` unknown, per the
    user's own five-item vocabulary.

    **`G` is driven by `cardinality`, not by classification.** A single
    two-character cell cannot carry both "what kind" and "how many," and
    `Contact.classification`'s own presence-level value (`PRESENCE_CLASS`)
    is literally `object_model.DEFAULT_OP_CLASS` -- the same string a
    classification lattice that generalised to "unclassifiable group" also
    holds -- so the two cannot be told apart by `classification.value`
    alone. `cardinality.lo > 1` (definitely more than one unit) is an
    unambiguous, independently-populated signal instead: any contact
    genuinely believed to be more than one thing draws `G` regardless of
    its own type claim, since "how many" is judged the more useful two
    characters to spend on a formation than "what kind" would be. A
    singular contact (`lo <= 1`) falls through to the ordinary
    classification-based mapping.

    Classification below `SpecificityLevel.CLASS` (i.e. `PRESENCE` or
    `UNKNOWN`) carries no resolvable type at all, so it draws `U`.
    `parent_class_of` resolves a `CLASS`-level value (already an `OP_*`
    bucket) or a `TYPE`-level value (a specific reporting name, resolved
    via the same keyword table `belief.classification._op_class_of`
    already uses) to its `OP_*` bucket; a bucket outside the three named
    ground vocabularies (`OP_SHIP`, `OP_INFANTRY`, an unresolvable parent)
    also draws `U` -- the user's vocabulary names four kinds plus unknown,
    not every `OP_*` bucket this codebase tracks."""
    if contact.cardinality.lo > 1:
        return "G"
    if (
        contact.classification.level < SpecificityLevel.CLASS
        or contact.classification.value is None
    ):
        return "U"
    op_class = parent_class_of(contact.classification.value)
    if op_class in _AIR_DEFENCE_CLASSES:
        return "AA"
    if op_class == "OP_ARMORED":
        return "AR"
    if op_class == "OP_TRUCK":
        return "TR"
    return "U"


def _object_type_label(object_type: str) -> str:
    """Ground-truth-side twin of `contact_label`, for the offline replay
    path (`believed_markers_from_trace_rows`) where no `Contact.
    cardinality`/`classification` exists at all -- only a raw DCS
    `object_type` string. Resolved through the same `object_model.
    profile_for` keyword table `belief.classification._op_class_of` uses
    for scope/hybrid free text, so a truck reads `TR` offline exactly as
    it would from a live `Contact`. No `G`: a single trace row is one
    object, not a cluster, and the offline JSONL carries no cardinality to
    read (documented gap, `tools/eyesight_replay.py`'s own docstring)."""
    op_class = profile_for(object_type).op_class
    if op_class in _AIR_DEFENCE_CLASSES:
        return "AA"
    if op_class == "OP_ARMORED":
        return "AR"
    if op_class == "OP_TRUCK":
        return "TR"
    return "U"


def believed_markers_from_contacts(
    contacts: Iterable[Contact],
    observer: GeoPosition,
    heading_true_deg: float,
    areas: Sequence[AttentionArea] | None = None,
) -> list[BeliefMarker]:
    """`BeliefMarker`s for a live `belief.contacts.ContactStore.contacts`
    snapshot -- the real-time path (`logger.py`'s poll loop), which always
    has an actual `Contact.last_position`/`cardinality`/`classification`
    to read, so this is the accurate source; the offline replay path
    (`believed_markers_from_trace_rows`) is a documented approximation of
    this."""
    area_list = list(areas or ())
    markers = []
    for contact in contacts:
        true_bearing = bearing_deg(observer, contact.last_position)
        level, _area_id = effective_attention(
            contact.attention, contact.last_position, area_list
        )
        markers.append(
            BeliefMarker(
                label=contact_label(contact),
                bearing_deg=relative_bearing_deg(true_bearing, heading_true_deg),
                range_m=range_m(observer, contact.last_position),
                watched=level in ("watch", "priority"),
            )
        )
    return markers


def ground_truth_markers_from_trace(
    records: Iterable[DetectionTrace], heading_true_deg: float
) -> list[GroundTruthMarker]:
    """`GroundTruthMarker`s for one poll's worth of `perception.
    detection_trace.DetectionTrace` records -- works identically whether
    `records` came from a live `DetectionTraceCollector.records` snapshot
    or was reconstructed from JSONL rows (`believed_markers_from_trace_
    rows`'s sibling would do the same, but ground truth needs no
    `contact_id` join, so JSONL rows are turned into `DetectionTrace`-like
    reads directly by the replay tool -- see `tools/eyesight_replay.py`)."""
    return [
        GroundTruthMarker(
            bearing_deg=relative_bearing_deg(entry.true_bearing_deg, heading_true_deg),
            range_m=entry.true_range_m,
            visible=entry.outcome is GateOutcome.ADMITTED,
        )
        for entry in records
    ]


def believed_markers_from_trace_rows(
    rows: Sequence[Mapping[str, object]], heading_true_deg: float = 0.0
) -> list[BeliefMarker]:
    """Offline replay's stand-in for `believed_markers_from_contacts`,
    built from one poll's worth of already-JSON-decoded `--detection-trace`
    rows (`detection_trace_writer._entry_to_dict`'s own shape) instead of
    a live `ContactStore` -- there is no live belief state to read when
    replaying a recorded flight on a machine with no DCS session at all.

    **A documented approximation, not the real thing** (mirrors `tools/
    summarize_detection_trace.py`'s own posture on its "never admitted"
    list): a cluster's *members* are individually traced, but the JSONL
    has no record of the cluster's own centroid, so this uses the first
    admitted member's own true bearing/range for the whole contact rather
    than the centroid `NakedEyePerceptionSource` actually emitted -- close
    for a tight cluster, visibly off for a loose one. No cardinality
    either (no cluster size survives into the trace row), so every
    believed marker here comes from `_object_type_label`, never `G`.

    `heading_true_deg` defaults to `0.0` because the recorded JSONL does
    not carry ownship heading at all (`DetectionTraceWriter` never wrote
    it) -- see `tools/eyesight_replay.py`'s own docstring for what that
    means for the frame this produces."""
    markers: dict[str, BeliefMarker] = {}
    for row in rows:
        contact_id = row.get("contact_id")
        if contact_id is None or row.get("outcome") != "admitted":
            continue
        if contact_id in markers:
            continue
        true_bearing = float(row["true_bearing_deg"])  # type: ignore[arg-type]
        markers[str(contact_id)] = BeliefMarker(
            label=_object_type_label(str(row["object_type"])),
            bearing_deg=relative_bearing_deg(true_bearing, heading_true_deg),
            range_m=float(row["true_range_m"]),  # type: ignore[arg-type]
        )
    return list(markers.values())


def _polar_to_cell(
    bearing_deg_value: float,
    range_m_value: float,
    *,
    meters_per_col: float,
    meters_per_row: float,
    center_col: int,
    ownship_row: int,
    total_rows: int,
    total_cols: int,
) -> tuple[int, int]:
    """A `(row, col)` cell for a body-relative `(bearing_deg_value,
    range_m_value)` -- clipped into the canvas bounds, never raising.
    Forward (`bearing=0`) decreases row (up the screen); the stretch
    factor is already folded into `meters_per_row` by the caller."""
    bearing_rad = math.radians(bearing_deg_value)
    x_m = range_m_value * math.sin(bearing_rad)
    y_m = range_m_value * math.cos(bearing_rad)
    col = center_col + round(x_m / meters_per_col)
    row = ownship_row - round(y_m / meters_per_row)
    col = max(0, min(total_cols - 1, col))
    row = max(0, min(total_rows - 1, row))
    return row, col


@dataclass
class _Canvas:
    rows: int
    cols: int

    def __post_init__(self) -> None:
        self.glyph: list[list[str]] = [[" "] * self.cols for _ in range(self.rows)]
        self.codes: list[list[tuple[str, ...]]] = [
            [() for _ in range(self.cols)] for _ in range(self.rows)
        ]

    def set(self, row: int, col: int, glyph: str, *codes: str) -> None:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.glyph[row][col] = glyph
            self.codes[row][col] = codes

    def set_if_blank(self, row: int, col: int, glyph: str, *codes: str) -> None:
        if (
            0 <= row < self.rows
            and 0 <= col < self.cols
            and self.glyph[row][col] == " "
        ):
            self.set(row, col, glyph, *codes)

    def render(self, *, color: bool) -> list[str]:
        lines = []
        for row in range(self.rows):
            cells = [
                _wrap(self.glyph[row][col], *self.codes[row][col], color=color)
                for col in range(self.cols)
            ]
            lines.append("".join(cells))
        return lines


def render_frame(
    *,
    gaze: Gaze,
    optic_name: str,
    rear_cutoff_deg: float,
    ground_truth: Sequence[GroundTruthMarker] = (),
    believed: Sequence[BeliefMarker] = (),
    radius_m: float = DEFAULT_RADIUS_M,
    width: int = DEFAULT_WIDTH,
    color: bool = True,
    max_lines: int | None = DEFAULT_MAX_LINES,
) -> str:
    """Render one frame: a top-down plan view, ownship near the bottom,
    forward up. See module docstring for the geometry/draw-order/off-edge
    rules; this function composes them.

    `rear_cutoff_deg` (`perception.cockpit_mask.OcclusionMask.
    rear_cutoff_deg`, `130.0` for the co-pilot seat) decides the canvas's
    own vertical extent as well as which bearings can be drawn at all: a
    marker beyond it is never plotted (module docstring's "ownship near
    the bottom, not the literal last row" -- a few rows are reserved below
    ownship for the `90..rear_cutoff_deg` sliver the mask actually admits,
    rather than clipping it to a flat forward hemisphere and silently
    hiding something the mask says is visible).

    `optic_name` selects the gaze cone's colour: `"unaided"` draws green,
    `"binocular"` draws blue (the user's own scheme), anything else draws
    plain/dim (no optic table lookup here -- this module takes a name, not
    an `Optic`, to stay decoupled from `perception.optics`)."""
    if width % 2 == 0:
        width += 1
    cols = width
    center_col = cols // 2
    meters_per_col = radius_m / center_col
    meters_per_row = meters_per_col * _ROW_METER_STRETCH

    rows_forward = math.ceil(radius_m / meters_per_row)
    y_min_m = radius_m * math.cos(math.radians(min(rear_cutoff_deg, 180.0)))
    rows_aft = math.ceil(-y_min_m / meters_per_row) if y_min_m < 0 else 0
    total_rows = rows_forward + rows_aft + 1
    ownship_row = rows_forward

    canvas = _Canvas(rows=total_rows, cols=cols)

    def to_cell(bearing: float, rng: float) -> tuple[int, int] | None:
        if abs(bearing) > rear_cutoff_deg:
            return None
        clipped_rng = min(rng, radius_m)
        return _polar_to_cell(
            bearing,
            clipped_rng,
            meters_per_col=meters_per_col,
            meters_per_row=meters_per_row,
            center_col=center_col,
            ownship_row=ownship_row,
            total_rows=total_rows,
            total_cols=cols,
        )

    # Range rings, dim.
    for ring_index in range(1, _RING_COUNT + 1):
        ring_range = radius_m * ring_index / _RING_COUNT
        bearing = -rear_cutoff_deg
        while bearing <= rear_cutoff_deg:
            cell = to_cell(bearing, ring_range)
            if cell is not None:
                canvas.set_if_blank(*cell, "·", _GRAY, _DIM)
            bearing += _TRACE_STEP_DEG

    # Rear-cutoff boundary rays -- beyond these nothing is visible at all.
    for edge_bearing in (-rear_cutoff_deg, rear_cutoff_deg):
        step_range = 0.0
        while step_range <= radius_m:
            cell = to_cell(edge_bearing, step_range)
            if cell is not None:
                canvas.set_if_blank(*cell, ":", _GRAY, _DIM)
            step_range += meters_per_row / 2

    # Gaze cone: edges, a centreline, and a sparse shaded interior --
    # edges-only fragmented at long range in the mock pass (orchestrator
    # brief, finding #2), so the centreline plus interior dots are what
    # keep a narrow (binocular) cone legible out to the canvas edge.
    gaze_color = (
        _GREEN
        if optic_name == "unaided"
        else (_BLUE if optic_name == "binocular" else _GRAY)
    )
    edge_a = gaze.center_azimuth_deg - gaze.half_width_deg
    edge_b = gaze.center_azimuth_deg + gaze.half_width_deg
    for edge_bearing in (edge_a, gaze.center_azimuth_deg, edge_b):
        step_range = 0.0
        while step_range <= radius_m:
            cell = to_cell(edge_bearing, step_range)
            if cell is not None:
                canvas.set_if_blank(*cell, "'", gaze_color)
            step_range += meters_per_row / 2
    # Sparse interior shading -- every other angular/range step, so the
    # cone reads as filled without burying anything drawn inside it later.
    bearing = edge_a
    step_index = 0
    while bearing <= edge_b:
        step_range = meters_per_row
        while step_range <= radius_m:
            if step_index % 2 == 0:
                cell = to_cell(bearing, step_range)
                if cell is not None:
                    canvas.set_if_blank(*cell, ".", gaze_color, _DIM)
            step_range += meters_per_row * 1.5
            step_index += 1
        bearing += _TRACE_STEP_DEG * 3

    # Ownship -- unconditional (never `set_if_blank`), so it always shows
    # even though the gaze centreline and the rear-cutoff boundary rays
    # both start their own trace exactly at range 0, i.e. ownship's own
    # cell (a real bug caught rendering the sample frame: `set_if_blank`
    # here left ownship permanently hidden under whichever ray happened to
    # be drawn first). Placed *before* ground truth/believed so a marker
    # genuinely at range 0 -- essentially a collision -- still wins the
    # cell per the module docstring's draw-order rule, exactly like every
    # other background layer.
    canvas.set(ownship_row, center_col, "^", _BOLD)

    # Ground truth, dim -- drawn before believed markers so a believed
    # marker always wins the cell (module docstring's draw-order rule).
    for gt_marker in ground_truth:
        cell = to_cell(gt_marker.bearing_deg, gt_marker.range_m)
        if cell is not None:
            glyph = "·" if gt_marker.visible else "×"
            canvas.set(*cell, glyph, _GRAY, _DIM)

    # Believed markers, last, unconditional -- never `set_if_blank`.
    for belief_marker in believed:
        cell = to_cell(belief_marker.bearing_deg, belief_marker.range_m)
        if cell is None:
            continue
        row, col = cell
        label = belief_marker.label[:2]
        marker_color = _ORANGE if belief_marker.watched else _YELLOW
        canvas.set(row, col, label[0], _BOLD, marker_color)
        if len(label) > 1:
            canvas.set(row, min(col + 1, cols - 1), label[1], _BOLD, marker_color)

    lines = canvas.render(color=color)

    header = (
        f"gaze: {gaze.label} centre={gaze.center_azimuth_deg:+.0f} deg "
        f"+/-{gaze.half_width_deg:.0f} deg  optic={optic_name}  "
        f"radius={radius_m / 1000:.1f}km"
    )
    legend = (
        "AA air defence  AR armour  TR truck  G group  U unknown   "
        "(believed=bold, watched=orange, ground truth: . seen / x not seen)"
    )

    # (range, text) so the list can be ordered by what is nearest -- the
    # previous ordering was alphabetical on the rendered line, which sorted
    # "believed" before "truth" and then by label, so a 9 km contact could
    # outrank a 5.1 km one. Nearest-first is what survives truncation.
    beyond: list[tuple[float, str]] = []
    for belief_marker in believed:
        if belief_marker.range_m > radius_m:
            beyond.append(
                (
                    belief_marker.range_m,
                    (
                        f"  believed {belief_marker.label:<2} "
                        f"{belief_marker.bearing_deg:+04.0f} deg "
                        f"{belief_marker.range_m / 1000:.1f}km"
                    ),
                )
            )
    for gt in ground_truth:
        if gt.range_m > radius_m:
            tag = "seen" if gt.visible else "not seen"
            beyond.append(
                (
                    gt.range_m,
                    (
                        f"  truth    ({tag}) {gt.bearing_deg:+04.0f} deg "
                        f"{gt.range_m / 1000:.1f}km"
                    ),
                )
            )
    beyond.sort(key=lambda entry: (entry[0], entry[1]))

    parts = [header, legend, *lines]
    if beyond:
        heading = f"beyond {radius_m / 1000:.1f}km radius:"
        entries = [text for _range_m, text in beyond]
        if max_lines is not None:
            # Budget: everything already committed, plus the heading, plus
            # one line held back for the truncation note so that note can
            # never itself be the thing that overflows.
            room = max_lines - len(parts) - 1
            if room < len(entries):
                shown = max(room - 1, 0)
                hidden = len(entries) - shown
                entries = entries[:shown]
                entries.append(f"  ... and {hidden} more, nearest shown first")
        parts.append(heading)
        parts.extend(entries)
    return "\n".join(parts)


__all__ = [
    "DEFAULT_RADIUS_M",
    "DEFAULT_WIDTH",
    "BeliefMarker",
    "GroundTruthMarker",
    "believed_markers_from_contacts",
    "believed_markers_from_trace_rows",
    "contact_label",
    "ground_truth_markers_from_trace",
    "relative_bearing_deg",
    "render_frame",
]
