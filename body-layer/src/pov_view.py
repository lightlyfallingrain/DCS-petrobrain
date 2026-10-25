"""The real-time ASCII Petrovich-POV debug view -- the forward-looking twin
of `eyesight_view.py`'s top-down plan view (`plans/pov-view/plan.md`,
`BL-B99`, the user's own request `body-layer/ROADMAP/BL-B99.md`).

**This module may show ground truth, deliberately, for exactly the reason
`eyesight_view.py`'s own module docstring states** -- same debug/testing/
calibration exemption, same user direction (2026-09-25), restated for this
tool specifically (`BL-B99` roadmap entry, 2026-10-25). A view restricted
to belief could not answer "why did his optic not see that," which is what
this instrument exists for.

**The invariant that still binds: read-only, one-directional flow.**
Nothing here mutates `belief.contacts.ContactStore`, and no ground-truth
field read here is ever passed into `ContactStore.ingest`, `Percept`, or
`Contact`.

**Geometry.** A plain Cartesian grid of two angles -- azimuth (columns),
elevation (rows) -- with no range dimension at all, unlike
`eyesight_view`'s polar (bearing, range) canvas. Azimuth is
ownship-heading-relative (`eyesight_view.relative_bearing_deg`'s own
convention, `0` dead ahead, positive clockwise); elevation is
world-horizon-relative, pitch/roll-independent (`perception.geometry.
elevation_deg`'s own convention, positive up) -- the gyro-stabilised 9K113
sight and a target's world depression both read naturally in this frame,
which keeps a ground target still on the canvas while the airframe
pitches and rolls. Revisit if it reads wrong in flight.

**Player bubble (user, 2026-10-25): "Ignore all units outside player
bubble."** Ground-truth trace rows dropped by the bubble
(`GateOutcome.PLAYER_BUBBLE`) are excluded by the ground-truth builder, and
a believed contact beyond `perception.association.PLAYER_BUBBLE_RADIUS_M`
is excluded by the believed-marker builder -- both before any drawing
happens, mirroring the bubble's own "never gated late" posture.

**Boresight and FOV/border are per-optic, drawn before markers** (user's
own scheme): the naked eye draws a green border -- two vertical lines at
the gaze wedge's own azimuth edges, spanning the full canvas height,
because `perception.gaze.Gaze` carries only a *centre* elevation, never a
half-angle, so there is no elevation bound to draw. Binoculars/9K113 wide/
9K113 narrow each draw a filled dot-disc instead, the angular-radius test
against that optic's own `fov_half_angle_deg` -- reimplemented locally
(`_angular_separation_deg`) rather than importing `optics.within_optic_fov`,
since this module takes a resolved boresight + half-angle, not an `Optic`.

**A persistent border and gridline frame is drawn first, per the user's
own mock** (`plans/pov-view/review.md` Required Fix 2): a dim gray `-`
border row at the elevation extremes, a dim gray `|` border column at the
azimuth extremes, and dim gray `|` gridlines at every 30-degree azimuth
tick, all the way through the canvas body -- a ruled grid, not just a
labelled top edge, since reading an angle off the picture is the point of
this instrument.

**Draw order is load-bearing, same rule as `eyesight_view.py`'s own
docstring**: border/gridlines first (dim, `set_if_blank`), eyes border /
optic disc next (unconditional `set`, so it always wins over a gridline
underneath it), ground truth next, believed last -- a believed contact
always wins its cell. The naked eye's green sector is doubly marked: its
two edges draw as `_EYE_EDGE_GLYPH` (distinct from the gridline's own
`|`, so it still reads without colour), and the top/bottom border cells
spanning the sector's azimuth width are recoloured green so the sector
reads as a highlighted band rather than two free-floating lines.

**Off-canvas handling differs by axis, not symmetric** (`plans/pov-view/
plan.md`'s "Open decisions"): azimuth beyond `azimuth_half_deg` is dropped
(the naked eye's own hard FOV limit -- nothing can legitimately sit beyond
it), elevation beyond `elevation_up_deg`/`elevation_down_deg` is clipped to
the canvas edge (a display choice, not a perceptual one).

**The optic-FOV disc is a background tint when colour is on, dots when it
is off** (user amendment, 2026-10-25: "the optics FOV highlight could use
background color instead"). A `.`-glyph disc hides whatever already
occupied the cell -- a gridline, a believed marker, a ground-truth glyph
-- which is exactly what this instrument must never do to a real marker.
With colour on, every cell inside the disc's angular radius gets
`Canvas.set_bg` instead of a glyph overwrite, so whatever is drawn there
(including nothing -- a tinted blank) keeps its own glyph/foreground.
With colour off there is no way to show a tint in plain text, so this
falls back to the dot-glyph the user originally specified ("draw the
current optic's FOV with dots '.'"), unchanged from before this
amendment. The naked eye's green sector is unaffected by this -- it has
no disc, only the two edge lines and the border highlight."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from ascii_canvas import (
    BG_BLUE,
    BG_BROWN,
    BG_GRAY,
    BLUE,
    BOLD,
    BROWN,
    DIM,
    GRAY,
    GREEN,
    GROUND_TRUTH_NOT_SEEN_GLYPH,
    GROUND_TRUTH_SEEN_GLYPH,
    ORANGE,
    YELLOW,
)
from ascii_canvas import Canvas as _Canvas
from belief.attention import AttentionArea, effective_attention
from belief.contacts import Contact
from eyesight_view import contact_label, relative_bearing_deg
from perception.association import PLAYER_BUBBLE_RADIUS_M
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.geometry import GeoPosition, bearing_deg, elevation_deg, range_m

#: The naked eye's own hard FOV limit (`optics.UNAIDED_OPTIC.
#: fov_half_angle_deg`) -- azimuth beyond this is dropped, never drawn
#: (module docstring's off-canvas rule). Not imported from `optics.py`
#: directly: this module takes a plain float, not an `Optic` (module
#: docstring).
DEFAULT_AZIMUTH_HALF_DEG: Final[float] = 90.0

#: The user's own mock numbers (`BL-B99` roadmap entry) -- +10/-20 degrees
#: of elevation, asymmetric because Petrovich looks down at ground targets
#: far more often than up.
DEFAULT_ELEVATION_UP_DEG: Final[float] = 10.0
DEFAULT_ELEVATION_DOWN_DEG: Final[float] = -20.0

#: Canvas width, columns -- odd, so there is a single centre column the
#: boresight sits under (`eyesight_view.DEFAULT_WIDTH`'s own reasoning).
#: Chosen with `DEFAULT_AZIMUTH_HALF_DEG` so one column reads ~2.3 deg --
#: fine enough that the 9K113 narrow FOV (6 deg total) spans several
#: columns, not one (main-loop amendment to `plans/pov-view/plan.md`: the
#: plan's own 79-col/4.56-deg-per-row prototype was too coarse for exactly
#: this reason).
DEFAULT_WIDTH: Final[int] = 79

#: Degrees of elevation per canvas row -- the user's own mock is
#: ~2.5 deg/row (12 rows for a 30-degree +10..-20 span). Chosen directly,
#: not aspect-ratio-corrected like `eyesight_view._ROW_METER_STRETCH`: this
#: canvas has no physical distance unit to keep circular, just two angles.
DEFAULT_DEG_PER_ROW: Final[float] = 2.5

#: Total lines one frame may occupy, mirroring `eyesight_view.
#: DEFAULT_MAX_LINES`'s own purpose -- this canvas is small enough
#: (`DEFAULT_ELEVATION_UP_DEG`/`DEFAULT_ELEVATION_DOWN_DEG` at
#: `DEFAULT_DEG_PER_ROW` is 13 rows, plus a handful of header/legend lines)
#: that the budget is rarely binding, but the parameter exists for the
#: same reason it exists there: a caller with an unusually small terminal
#: should not have this view silently push something else off the top.
DEFAULT_MAX_LINES: Final[int] = 60

#: Per-optic colour, the user's own scheme (`BL-B99` roadmap entry):
#: binoculars blue, 9K113 wide gray, 9K113 narrow brown. `"unaided"` is not
#: looked up here -- it draws the green border, a different code path
#: entirely (module docstring).
_OPTIC_DISC_COLOR: Final[dict[str, str]] = {
    "binocular": BLUE,
    "sight_wide": GRAY,
    "sight_narrow": BROWN,
}

#: The same per-optic scheme, as a background tint instead of a dot's
#: foreground colour -- the colour-on disc rendering (module docstring,
#: user amendment 2026-10-25). Unknown optic names fall back to `BG_GRAY`
#: in `render_frame` itself, mirroring `_OPTIC_DISC_COLOR.get`'s own
#: `GRAY` fallback above.
_OPTIC_DISC_BG_COLOR: Final[dict[str, str]] = {
    "binocular": BG_BLUE,
    "sight_wide": BG_GRAY,
    "sight_narrow": BG_BROWN,
}

#: The naked-eye sector's two green edge lines (`plans/pov-view/review.md`
#: Required Fix 3) -- deliberately not the dim gray gridline's own `|`, so
#: the eye sector still reads distinctly with colour off. U+2016 DOUBLE
#: VERTICAL LINE, chosen over `:` for a closer visual match to a border
#: line; swap for `:` if a target terminal's font renders this unreliably.
_EYE_EDGE_GLYPH: Final[str] = "‖"

#: Vertical gridline columns, azimuth ticks every 30 degrees -- dim gray,
#: drawn before any marker/disc/eye-line so every one of those wins its
#: cell (`plans/pov-view/review.md` Required Fix 2).
_GRIDLINE_STEP_DEG: Final[int] = 30


@dataclass(frozen=True, slots=True)
class PovGroundTruthMarker:
    """One real object, ground truth, for one poll -- `eyesight_view.
    GroundTruthMarker`'s forward-POV twin. `azimuth_deg` is already
    ownship-heading-relative, `elevation_deg` already world-horizon-
    relative (both module docstring's convention); `visible` is whether
    `check_visibility`'s gates admitted it this poll."""

    azimuth_deg: float
    elevation_deg: float
    visible: bool


@dataclass(frozen=True, slots=True)
class PovBeliefMarker:
    """One believed contact, for one poll -- `eyesight_view.BeliefMarker`'s
    forward-POV twin. `label` is `eyesight_view.contact_label`'s own
    `AA`/`AR`/`TR`/`G`/`U` vocabulary; `watched` is `effective_attention`'s
    derived level, same definition the watched-only callouts use."""

    label: str
    azimuth_deg: float
    elevation_deg: float
    watched: bool = False


def pov_ground_truth_markers_from_trace(
    records: Iterable[DetectionTrace], heading_true_deg: float
) -> list[PovGroundTruthMarker]:
    """`PovGroundTruthMarker`s for one poll's worth of `perception.
    detection_trace.DetectionTrace` records -- `eyesight_view.
    ground_truth_markers_from_trace`'s forward-POV twin.

    **Player-bubble rows are dropped, not drawn as unseen** (user,
    2026-10-25, "Ignore all units outside player bubble"): a
    `GateOutcome.PLAYER_BUBBLE` row never reached `check_visibility` at
    all, so it is not a "rejected" sighting in the sense every other
    outcome is -- it was never computation in the first place.

    **A row with no `true_elevation_deg` is also dropped**, not plotted at
    a fabricated elevation -- this is only ever a pre-`BL-B99` trace row
    (the field's `None` default), never a row this plan's own construction
    sites produce."""
    return [
        PovGroundTruthMarker(
            azimuth_deg=relative_bearing_deg(entry.true_bearing_deg, heading_true_deg),
            elevation_deg=entry.true_elevation_deg,
            visible=entry.outcome is GateOutcome.ADMITTED,
        )
        for entry in records
        if entry.outcome is not GateOutcome.PLAYER_BUBBLE
        and entry.true_elevation_deg is not None
    ]


def pov_believed_markers_from_contacts(
    contacts: Iterable[Contact],
    observer: GeoPosition,
    heading_true_deg: float,
    areas: Sequence[AttentionArea] | None = None,
) -> list[PovBeliefMarker]:
    """`PovBeliefMarker`s for a live `belief.contacts.ContactStore.contacts`
    snapshot -- `eyesight_view.believed_markers_from_contacts`'s
    forward-POV twin.

    **A contact beyond `PLAYER_BUBBLE_RADIUS_M` is dropped** (user,
    2026-10-25) -- the same bubble `pov_ground_truth_markers_from_trace`
    honours on the ground-truth side, applied here because a believed
    contact has no gate outcome of its own to read: the bubble is a
    computation-scope limit on the naked-eye channel's own candidate pool
    (`association.PLAYER_BUBBLE_RADIUS_M`'s own docstring), and a contact
    this stale/far belongs to a different debug question than this
    instrument answers."""
    area_list = list(areas or ())
    markers = []
    for contact in contacts:
        if range_m(observer, contact.last_position) > PLAYER_BUBBLE_RADIUS_M:
            continue
        true_bearing = bearing_deg(observer, contact.last_position)
        level, _area_id = effective_attention(
            contact.attention, contact.last_position, area_list
        )
        markers.append(
            PovBeliefMarker(
                label=contact_label(contact),
                azimuth_deg=relative_bearing_deg(true_bearing, heading_true_deg),
                elevation_deg=elevation_deg(observer, contact.last_position),
                watched=level in ("watch", "priority"),
            )
        )
    return markers


def _angular_separation_deg(
    azimuth_a_deg: float,
    elevation_a_deg: float,
    azimuth_b_deg: float,
    elevation_b_deg: float,
) -> float:
    """True angular separation between two body-relative directions --
    the same small-angle-safe great-circle-style separation
    `optics.within_optic_fov` uses, reimplemented locally rather than
    imported (module docstring: this module takes a resolved boresight +
    half-angle, not an `Optic`)."""
    az_delta_rad = math.radians(azimuth_a_deg - azimuth_b_deg)
    el_a_rad = math.radians(elevation_a_deg)
    el_b_rad = math.radians(elevation_b_deg)
    cos_separation = math.sin(el_a_rad) * math.sin(el_b_rad) + math.cos(
        el_a_rad
    ) * math.cos(el_b_rad) * math.cos(az_delta_rad)
    cos_separation = max(-1.0, min(1.0, cos_separation))
    return math.degrees(math.acos(cos_separation))


def _elevation_ticks(elevation_up_deg: float, elevation_down_deg: float) -> list[float]:
    """Every multiple of 10 degrees within `[elevation_down_deg,
    elevation_up_deg]`, ascending -- the user's own mock marks +10/0/-10/
    -20, which is exactly this for the default range."""
    ticks = []
    value = math.ceil(elevation_down_deg / 10.0) * 10.0
    while value <= elevation_up_deg + 1e-9:
        ticks.append(value)
        value += 10.0
    return ticks


def _format_deg(value: float) -> str:
    return "0" if value == 0.0 else f"{value:+.0f}"


def render_frame(
    *,
    optic_name: str,
    boresight_azimuth_deg: float,
    boresight_elevation_deg: float,
    half_angle_deg: float,
    ground_truth: Sequence[PovGroundTruthMarker] = (),
    believed: Sequence[PovBeliefMarker] = (),
    azimuth_half_deg: float = DEFAULT_AZIMUTH_HALF_DEG,
    elevation_up_deg: float = DEFAULT_ELEVATION_UP_DEG,
    elevation_down_deg: float = DEFAULT_ELEVATION_DOWN_DEG,
    width: int = DEFAULT_WIDTH,
    deg_per_row: float = DEFAULT_DEG_PER_ROW,
    color: bool = True,
    max_lines: int | None = DEFAULT_MAX_LINES,
) -> str:
    """Render one frame: a forward-POV Cartesian azimuth/elevation grid.
    See module docstring for the geometry/draw-order/off-canvas rules;
    this function composes them.

    `half_angle_deg` is the single number that drives either drawing:
    for `optic_name == "unaided"` it is the active gaze wedge's own
    half-width (`perception.gaze.Gaze.half_width_deg`), used to place the
    green border's two edges; for every other optic it is that optic's
    own `fov_half_angle_deg`, the filled dot-disc's angular radius.

    `optic_name` also selects the disc's colour via `_OPTIC_DISC_COLOR`
    (the user's own scheme) -- any name not in that table (including
    `"unaided"`, which never reaches it) falls back to a dim grey dot
    rather than raising, mirroring `eyesight_view.render_frame`'s own
    unknown-optic fallback."""
    if width % 2 == 0:
        width += 1
    cols = width
    center_col = cols // 2
    deg_per_col = azimuth_half_deg / center_col
    total_rows = round((elevation_up_deg - elevation_down_deg) / deg_per_row) + 1

    canvas = _Canvas(rows=total_rows, cols=cols)

    def row_for(elevation: float) -> int:
        clipped = max(elevation_down_deg, min(elevation_up_deg, elevation))
        row = round((elevation_up_deg - clipped) / deg_per_row)
        return max(0, min(total_rows - 1, row))

    def col_for(azimuth: float) -> int:
        col = center_col + round(azimuth / deg_per_col)
        return max(0, min(cols - 1, col))

    def to_cell(azimuth: float, elevation: float) -> tuple[int, int] | None:
        if abs(azimuth) > azimuth_half_deg:
            return None
        return row_for(elevation), col_for(azimuth)

    def cell_center(row: int, col: int) -> tuple[float, float]:
        return (col - center_col) * deg_per_col, elevation_up_deg - row * deg_per_row

    # Azimuth tick/gridline azimuths -- every 30 deg within the canvas's
    # own azimuth extent, shared by the header labels below and the
    # vertical gridlines drawn here.
    tick_values = [
        value
        for value in range(-90, 91, _GRIDLINE_STEP_DEG)
        if abs(value) <= azimuth_half_deg + 1e-9
    ]

    # Border + gridlines, dim gray, drawn first so every marker/disc/
    # eye-line below wins its cell (Required Fix 2, module docstring).
    # Border rows first: a `set_if_blank` vertical gridline below this
    # point skips an already-filled border cell, which is what keeps the
    # top/bottom rows solid dashes rather than broken by a "|" (matches
    # the user's own mock).
    for col in range(cols):
        canvas.set_if_blank(0, col, "-", GRAY, DIM)
        canvas.set_if_blank(total_rows - 1, col, "-", GRAY, DIM)
    for value in tick_values:
        col = col_for(float(value))
        for row in range(total_rows):
            canvas.set_if_blank(row, col, "|", GRAY, DIM)
    for col in (0, cols - 1):
        for row in range(total_rows):
            canvas.set_if_blank(row, col, "|", GRAY, DIM)

    if optic_name == "unaided":
        # Eye sector: recolour the top/bottom border cells across the
        # sector's azimuth width green first (Required Fix 3's "reads as a
        # highlighted sector, not two free-floating lines"), then draw the
        # two edge lines in green, full canvas height, overriding any
        # border/gridline cell beneath them -- no elevation bound to draw
        # (module docstring: `Gaze` carries only a centre elevation).
        left_azimuth = max(-azimuth_half_deg, boresight_azimuth_deg - half_angle_deg)
        right_azimuth = min(azimuth_half_deg, boresight_azimuth_deg + half_angle_deg)
        if left_azimuth <= right_azimuth:
            left_col = col_for(left_azimuth)
            right_col = col_for(right_azimuth)
            for col in range(left_col, right_col + 1):
                canvas.set(0, col, "-", GREEN)
                canvas.set(total_rows - 1, col, "-", GREEN)
        for edge_azimuth in (
            boresight_azimuth_deg - half_angle_deg,
            boresight_azimuth_deg + half_angle_deg,
        ):
            if abs(edge_azimuth) > azimuth_half_deg:
                continue
            col = col_for(edge_azimuth)
            for row in range(total_rows):
                canvas.set(row, col, _EYE_EDGE_GLYPH, GREEN)
    else:
        # Optic FOV: every cell within half_angle_deg's angular separation
        # of the boresight (module docstring). With colour on, a
        # background tint (`set_bg`, additive -- never overwrites
        # whatever glyph/foreground already occupies the cell, so a
        # gridline or a believed/ground-truth marker inside the FOV stays
        # visible, user amendment 2026-10-25). With colour off, falls
        # back to the dot-glyph the user originally specified
        # (unconditional `set`, not `set_if_blank`, so the dot still wins
        # over a border/gridline cell beneath it -- there is no
        # background layer to carry that distinction in plain text).
        disc_fg_color = _OPTIC_DISC_COLOR.get(optic_name, GRAY)
        disc_bg_color = _OPTIC_DISC_BG_COLOR.get(optic_name, BG_GRAY)
        for row in range(total_rows):
            for col in range(cols):
                azimuth, elevation = cell_center(row, col)
                if (
                    _angular_separation_deg(
                        azimuth,
                        elevation,
                        boresight_azimuth_deg,
                        boresight_elevation_deg,
                    )
                    <= half_angle_deg
                ):
                    if color:
                        canvas.set_bg(row, col, disc_bg_color)
                    else:
                        canvas.set(row, col, ".", disc_fg_color, DIM)

    # Ground truth, dim -- drawn before believed markers so a believed
    # marker always wins the cell (module docstring's draw-order rule).
    # Glyphs are `ascii_canvas`'s shared ground-truth pair, not this
    # module's own optic-FOV dot (Required Fix 1).
    for gt_marker in ground_truth:
        cell = to_cell(gt_marker.azimuth_deg, gt_marker.elevation_deg)
        if cell is not None:
            glyph = (
                GROUND_TRUTH_SEEN_GLYPH
                if gt_marker.visible
                else GROUND_TRUTH_NOT_SEEN_GLYPH
            )
            canvas.set(*cell, glyph, GRAY, DIM)

    # Believed markers, last, unconditional -- never `set_if_blank`.
    for belief_marker in believed:
        cell = to_cell(belief_marker.azimuth_deg, belief_marker.elevation_deg)
        if cell is None:
            continue
        row, col = cell
        label = belief_marker.label[:2]
        marker_color = ORANGE if belief_marker.watched else YELLOW
        canvas.set(row, col, label[0], BOLD, marker_color)
        if len(label) > 1:
            canvas.set(row, min(col + 1, cols - 1), label[1], BOLD, marker_color)

    canvas_lines = canvas.render(color=color)

    # Azimuth header: tick marks every 30 deg, labels above them -- the
    # user's own mock layout.
    margin = "    "
    label_row = [" "] * cols
    tick_row = [" "] * cols
    for value in tick_values:
        col = col_for(float(value))
        tick_row[col] = "|"
        label = _format_deg(float(value))
        start = max(0, min(cols - len(label), col - len(label) // 2))
        for offset, char in enumerate(label):
            label_row[start + offset] = char
    header_lines = [margin + "".join(label_row), margin + "".join(tick_row)]

    elevation_tick_rows = {
        row_for(value): value
        for value in _elevation_ticks(elevation_up_deg, elevation_down_deg)
    }
    canvas_block = []
    for row, line in enumerate(canvas_lines):
        if row in elevation_tick_rows:
            label = _format_deg(elevation_tick_rows[row]).rjust(4)
            canvas_block.append(
                f"{label}{line} {_format_deg(elevation_tick_rows[row])}"
            )
        else:
            canvas_block.append(f"{' ' * 4}{line}")

    info = (
        f"optic={optic_name}  boresight az={boresight_azimuth_deg:+.0f} "
        f"el={boresight_elevation_deg:+.0f}"
    )
    legend = (
        "AA air defence  AR armour  TR truck  G group  U unknown   "
        f"(believed=bold, watched=orange, ground truth: {GROUND_TRUTH_SEEN_GLYPH} "
        f"seen / {GROUND_TRUTH_NOT_SEEN_GLYPH} not seen, eyes=green "
        f"{_EYE_EDGE_GLYPH} sector, optic=dim ., grid=dim |)"
    )

    parts = [info, legend, *header_lines, *canvas_block]
    if max_lines is not None and len(parts) > max_lines:
        parts = parts[:max_lines]
    return "\n".join(parts)


__all__ = [
    "DEFAULT_AZIMUTH_HALF_DEG",
    "DEFAULT_DEG_PER_ROW",
    "DEFAULT_ELEVATION_DOWN_DEG",
    "DEFAULT_ELEVATION_UP_DEG",
    "DEFAULT_MAX_LINES",
    "DEFAULT_WIDTH",
    "PovBeliefMarker",
    "PovGroundTruthMarker",
    "pov_believed_markers_from_contacts",
    "pov_ground_truth_markers_from_trace",
    "render_frame",
]
