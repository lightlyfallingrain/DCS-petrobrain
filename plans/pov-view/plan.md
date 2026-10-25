### Goal

Add `--pov-view`: a live ASCII rendering of Petrovich's forward point of view — azimuth
(heading-relative) on the x-axis, elevation (horizon-relative) on the y-axis — showing the
current optic's field of view/boresight and what he detects (ground truth + believed), the
forward-looking twin of `--eyesight-view`'s top-down plan view. Debug/calibration tool; may show
ground truth deliberately (same exemption `eyesight_view.py` already documents and the user
restated for this tool, BL-B99 roadmap entry).

### Prior art checked

Graph query (`gq.sh`) and `memory-search.py` found no prior plan or decision on this feature —
BL-B99 is new (roadmap entry filed today). The query did surface
`aircraft-layer/research/2026-09-11-quickstart-ru-9k113-manual.md`'s "Elevation/azimuth limits
misreading (console vs sight head, corrected 2026-09-21)" — read and not relevant here: it is
about a DCS cockpit-indication sign convention, not the body-layer `SightHead` simulation this
plan reads from, which already has its own settled world-frame convention (`sight_head.py`'s own
docstring, elevation positive above world-horizontal).

### Design — how the frame maps

**Axis frame (already settled by the roadmap entry, restated here for the Implementer):**
azimuth relative to airframe heading (`0` dead ahead, positive clockwise — `eyesight_view`'s own
convention), elevation relative to the world-horizontal plane (gyro/world quantity, pitch- and
roll-independent). Rationale already on record in `body-layer/ROADMAP/BL-B99.md`: the 9K113 is
gyro-stabilised and a target's depression is a world quantity, so this frame keeps a ground target
still on the canvas while the airframe pitches/rolls. Revisit if it reads wrong in flight (same
"revisit if wrong" posture the roadmap entry already takes).

**Unlike `eyesight_view`'s polar (bearing, range) canvas, this canvas is a plain Cartesian grid of
two angles — no range dimension at all.** Columns = azimuth, rows = elevation. This is genuinely
simpler than the top-down view's polar math; `_polar_to_cell` has no equivalent here, just a
linear `(azimuth_deg, elevation_deg) -> (row, col)` scale.

**Boresight resolution, per optic** (the brief's open question 2 — resolved by reading what
already exists rather than adding anything):

| `runner.optic` | boresight source | why |
|---|---|---|
| `UNAIDED_OPTIC` | `gaze.center_azimuth_deg`, `gaze.center_elevation_deg` from `gaze_at(last_t_sim, scan_plan)` — the same call `_render_eyesight_frame` already makes | `Gaze.center_elevation_deg` already exists on `main` (`perception/gaze.py` L187) and is `0.0` for every scanning gaze, which is already the horizon-relative frame for level flight |
| `BINOCULAR_OPTIC` | same `gaze.center_azimuth_deg`/`center_elevation_deg` — `OpticState.look_elevation_deg` is computed by `optic_policy.search_pattern`'s ground-anchored `atan2(altitude_agl_m, range_m)` (`perception/geometry.py` L364), i.e. already horizon-relative, and is threaded into `Gaze.center_elevation_deg` via `fixed_look_at` | no new geometry — this field already carries the canvas's own frame |
| `SIGHT_WIDE_OPTIC` / `SIGHT_NARROW_OPTIC` | `relative_bearing_deg(sight_head.world_az_true_deg, heading_true_deg)` for azimuth, `sight_head.world_el_deg` **unchanged** for elevation | `SightHead` holds its aim in the true world frame (`belief/sight_head.py` L99-101); world elevation *is* horizon-relative by construction, so no conversion at all. `body.run_once` already guarantees `sight_head.mode == "free"` (and thus both fields non-`None`) whenever `runner.optic` is actually one of the two sight optics — the "not yet free" window is forced to read as `BINOCULAR_OPTIC` by the existing cap at `body.py` L784-792, so this render path never has to handle "sight tier selected but head not free" |

No new rotation math anywhere in this feature — every boresight is read off a field that was
already in the requested frame, once traced to its source. This is the one place a shortcut would
have been wrong: `head_body_direction`/`body_relative_direction` (full body-relative, pitch+bank
included) is the *wrong* frame for this canvas and must not be used for the sight optics'
boresight — `sight_head.world_az_true_deg`/`world_el_deg` is the right one.

**Ground truth needs a new field — checked and confirmed missing.** `DetectionTrace` carries
`true_bearing_deg`/`true_range_m` but no elevation at all. Both of its two construction sites
(`visibility.py` `_record`, `naked_eye_source.py`'s `PLAYER_BUBBLE` row) already have `observer`/
`target` `GeoPosition`s (with `alt_m`) in scope at the point they build the row — exactly the same
inputs `bearing_deg`/`range_m` already consume there. Add one new pure helper beside them in
`perception/geometry.py`:

```python
def elevation_deg(observer: GeoPosition, target: GeoPosition) -> float:
    """World-horizon-relative elevation from observer to target, degrees,
    positive up -- pitch/bank independent by construction (a pure function
    of the two positions' altitudes and horizontal separation)."""
    delta_alt = target.alt_m - observer.alt_m
    horizontal_m = math.hypot(target.x - observer.x, target.z - observer.z)
    return math.degrees(math.atan2(delta_alt, horizontal_m))
```

Add `true_elevation_deg: float | None = None` to `DetectionTrace` (default `None` so no existing
test-constructed row breaks), set it at both construction sites. `_entry_to_dict` uses `asdict`
generically, so the JSONL trace gains the field for free — no writer change needed, only its
docstring's "`DetectionTrace` has 25 fields" count needs bumping to 26 (a doc-staleness trap this
project has been burned by before; call it out explicitly for Reviewer). This value is *already*
horizon-relative (a pure world quantity), so `pov_view`'s ground-truth markers use it unconverted —
same free ride as the believed-marker side above.

### Affected Modules / Files

- `body-layer/src/perception/geometry.py` — add `elevation_deg(observer, target)`.
- `body-layer/src/perception/detection_trace.py` — add `DetectionTrace.true_elevation_deg: float | None = None`; bump the "25 fields" docstring count in `src/detection_trace_writer.py`.
- `body-layer/src/perception/visibility.py` — `_record` closure: compute and pass `true_elevation_deg=elevation_deg(observer, target)`.
- `body-layer/src/perception/naked_eye_source.py` — the `PLAYER_BUBBLE` trace row: same addition, same `observer`/`target` already in scope.
- `body-layer/src/ascii_canvas.py` (**new**) — extract `_Canvas`, `_wrap`, and the shared ANSI colour constants (`_RESET`/`_DIM`/`_BOLD`/`_GREEN`/`_BLUE`/`_GRAY`/`_YELLOW`/`_ORANGE`) out of `eyesight_view.py`, as public names (`Canvas`, `wrap`, `RESET`/`DIM`/`BOLD`/`GREEN`/`BLUE`/`GRAY`/`YELLOW`/`ORANGE`, plus new `BROWN` for the 9K113 narrow colour). Pure move + rename, no behaviour change — `eyesight_view.py` re-imports from here instead of defining its own. This is the one new abstraction this plan introduces, and the duplication it removes is concrete: without it, `pov_view.py` would either fork `_Canvas`/`_wrap` (exactly what the brief says not to do) or import module-private (`_`-prefixed) names across a module boundary, which has no precedent anywhere in this codebase (checked: `grep` of every cross-module import in `src/` turned up none).
- `body-layer/src/eyesight_view.py` — import canvas/colour primitives from `ascii_canvas` instead of defining them locally; rename `_object_type_label` to `object_type_label` (drop the leading underscore — it is about to gain a second caller) and export it from `__all__`. No other change: `contact_label`, `relative_bearing_deg`, `believed_markers_from_contacts`, `ground_truth_markers_from_trace`, `BeliefMarker`, `GroundTruthMarker` are reused as-is by `pov_view.py`.
- `body-layer/src/pov_view.py` (**new**) — the renderer. `PovGroundTruthMarker(azimuth_deg, elevation_deg, visible)`, `PovBeliefMarker(label, azimuth_deg, elevation_deg, watched)`; `pov_ground_truth_markers_from_trace`/`pov_believed_markers_from_contacts` (mirroring `eyesight_view`'s own builders, reusing `contact_label`/`object_type_label` for the label logic verbatim); `render_frame(*, optic_name, boresight_azimuth_deg, boresight_elevation_deg, ground_truth, believed, azimuth_half_deg=90.0, elevation_up_deg=10.0, elevation_down_deg=-20.0, width=73, color=True, max_lines=None)`.
- `body-layer/src/body.py` — `_render_pov_frame(runner, trace_records)` mirroring `_render_eyesight_frame`'s own shape (resolves `gaze`/`sight_head`/`heading` into the boresight table above and calls `pov_view.render_frame`); wire `--pov-view` through `_run_crew_text_poll_loop` and `main()`'s argparse/thread-args, additive and a no-op when absent, same posture as every existing per-run flag (`body-layer/CLAUDE.md`'s own invariant).
- `body-layer/tools/pov_replay.py` (**new**, Stage 5, optional) — offline replay from a `--detection-trace` JSONL file, mirroring `tools/eyesight_replay.py`'s shape and its honest degradations (no heading, no gaze/boresight recorded — same two gaps that tool already documents, now joined by a third: no recorded sight-tier boresight either, so a replayed frame always shows a flat `0°` boresight labelled accordingly).
- `body-layer/tests/test_pov_view.py` (**new**) — pure render/geometry tests, mirroring `tests/test_eyesight_view.py`'s structure.
- `body-layer/tests/test_geometry.py`, `tests/test_detection_trace.py` (or equivalent) — new cases for `elevation_deg` and the new `DetectionTrace` field.

### Implementation Plan

1. **`elevation_deg` + `DetectionTrace.true_elevation_deg`.** Add the geometry helper, the new
   field, wire both construction sites, bump the stale field-count docstring. Pure, additive,
   independently testable before any rendering code exists.
2. **Extract `ascii_canvas.py`** out of `eyesight_view.py` (move + rename only); confirm
   `tests/test_eyesight_view.py` passes unchanged (it exercises the same canvas through the same
   public `render_frame`, so this stage should be invisible to it).
3. **`pov_view.py`**: marker dataclasses, builders (reusing `eyesight_view`'s label logic), and
   `render_frame` — the Cartesian azimuth/elevation grid, border rendering for `UNAIDED_OPTIC`
   (green vertical lines at the gaze wedge's two azimuth edges, full canvas height — see "Open
   decisions" below for why no elevation bound is drawn), filled dot-disc rendering for the other
   three optics (angular-radius test against `optic.fov_half_angle_deg`, same great-circle-style
   separation `within_optic_fov` already uses — reuse that math via a small local helper rather
   than re-deriving it, since `pov_view.py` takes a resolved boresight + angle, not an `Optic`).
   Draw order: eyes border / optic disc first, ground truth next, believed last — same
   "believed always wins its cell" rule `eyesight_view.py`'s module docstring states, for the same
   reason (losing a believed contact behind an FOV disc is exactly what this instrument exists to
   make visible). Pure functions throughout — testable with no DCS/aircraft-layer/world-model
   dependency, same as `eyesight_view.py`.
4. **Wire into `body.py`**: `_render_pov_frame`, the `--pov-view` flag (boolean, additive,
   default off), threading through `_run_crew_text_poll_loop`'s parameter list and `main()`'s
   thread-args tuple at the same positions `eyesight_view`/`eyesight_view_radius_m` already occupy
   in that list. **Coexistence with `--eyesight-view`:** when both are set, print both frames in
   one combined clear-and-print cycle (top-down frame, blank separator line, POV frame), splitting
   `_eyesight_max_lines()`'s terminal-height budget roughly in half between them; when only one is
   set, it gets the full budget — same degenerate-to-today's-behaviour posture `eyesight_view`
   alone already has. One shared print helper, generalised slightly from `_print_eyesight_frame`.
5. **Tests.** `test_pov_view.py`: boresight-to-cell geometry at known angles, each optic's colour/
   glyph selection, draw-order (believed wins over disc/border), off-canvas clipping behaviour
   (see Decisions below), the green-border-not-disc distinction for `UNAIDED_OPTIC`. `test_
   geometry.py`: `elevation_deg` at known observer/target pairs including the directly-overhead
   degenerate case. Extend `test_eyesight_view.py`'s existing coverage only as needed to prove
   stage 2's extraction changed nothing.
6. **`pov_replay.py` (optional, do only if stage 1-5 land cleanly and budget allows).** Same
   shape as `eyesight_replay.py`; explicitly document the three recorded-trace gaps (no heading,
   no gaze/boresight, no sight-tier aim) rather than silently approximating them.

### Open decisions (resolved here, reversible, stated so the user can revisit after seeing it fly)

- **Eye sector has no elevation bound to draw.** `Gaze` carries only a *centre* elevation, never a
  half-angle (naked-eye vertical limit is governed by the cockpit mask's per-azimuth depression
  table, not a single number) — so the green "sector he sees" marking is two vertical border lines
  at the gaze wedge's azimuth edges, spanning the full canvas height, not a bounded box. This is a
  faithful rendering of what the model actually encodes, not an approximation of something the
  model has and the view is dropping.
- **Elevation canvas extent is fixed at +10/-20 (the user's own mock numbers), not derived from
  the current optic's field of regard.** The canvas is a window onto the world-horizon frame, not
  an optic-specific view — drawing it at a fixed extent keeps the frame stable as the optic
  changes poll to poll, which matters for reading motion on this instrument. The 9K113's own
  field-of-regard envelope (+20/-15) is **not** drawn as a boundary on this cut — out of scope,
  matching "keep it small"; worth adding later if a sortie finds the sight's gimbal limit itself
  is what needs debugging.
- **Off-canvas handling differs by axis, not symmetric.** Azimuth beyond ±90° is dropped (never
  drawn, no legend entry) because it is the naked eye's own hard FOV limit
  (`UNAIDED_OPTIC.fov_half_angle_deg = 90.0`) — nothing believed or observed can legitimately sit
  beyond it regardless of optic, so there is nothing lost by not drawing it. Elevation beyond
  +10/-20 is clipped to the canvas edge rather than dropped, because that boundary is a display
  choice, not a perceptual one, and a real nearby low contact could otherwise vanish from the
  picture entirely. No trailing "beyond" legend like `eyesight_view`'s — that legend exists there
  to recover information lost to a *display-scale* radius smaller than the detection range; here
  the azimuth cutoff is the perceptual limit itself, so there is no equivalent "it's out there
  somewhere" case to list.
- **`--pov-view` has no radius-equivalent CLI knob this cut** (no `--pov-view-radius-m`-style
  parameter) — the canvas has no range axis at all, and the fixed azimuth/elevation extents above
  are plain module constants, not `tuning.py` entries (display geometry, not behaviour-affecting,
  same classification `DEFAULT_RADIUS_M`/`DEFAULT_WIDTH` already have in `eyesight_view.py`).

### Risks & Unknowns

- **BL-B89 (`feature/9k113-scan-procedure`, unmerged) touches `gaze.py`/`optic_policy.py`/
  `body.py`.** This plan is designed against `main`'s current `Gaze`/`ScanPlan`/`_active_gaze`
  shapes. If BL-B89 changes how `OpticState.look_elevation_deg` is derived, how `Gaze.center_
  elevation_deg` is populated, or the sight-tier cap logic at `body.py` L784-792 this plan relies
  on (the guarantee that `runner.optic` only ever reads as a sight optic when `sight_head.mode ==
  "free"`), `_render_pov_frame`'s boresight-resolution table needs re-checking against whatever
  BL-B89 actually lands as. Flagging now per this role's own standing instruction to scan open
  plans for assumptions a merge invalidates — this is the mirror case (an *unmerged* plan this one
  depends on, not the other direction) and is worth a one-line check when BL-B89 merges.
  **Architect pass on BL-B89's eventual plan should look at this file in turn.**
- **`SIGHT_NARROW_OPTIC`'s brown needs an actual 256-colour code** — not yet chosen; a reasonable
  default (something in the 94/130/136 olive/khaki/brown range) is a cosmetic pick for the
  Implementer, same posture `_ORANGE`'s own comment already has ("the nearest -- bright yellow --
  is too close"). Pick one visibly distinct from `_GRAY` (sight wide) and `_YELLOW`/`_ORANGE`
  (believed markers).
- **No live acceptance yet.** Like `eyesight_view` originally, the geometry is exercised by unit
  tests against synthetic fixtures; whether the frame "reads right" in the cockpit is only
  answerable by flying it, same as the axis-frame choice itself says ("revisit if it reads wrong
  in flight").

### Second-order effect

None identified beyond the BL-B89 interaction noted above — this is a pure, additive, read-only
debug instrument with no effect on belief state, the brain-facing API, or any other milestone's
behaviour. It does make `perception.geometry.elevation_deg` and `DetectionTrace.
true_elevation_deg` available for the first time, which is a small new capability a future
feature (e.g. a richer detection-trace debrief, or BL-B66/BL-B80 rate-loop tuning) could reuse
rather than re-deriving.

### Sample frame (prototype output, real computed layout — not hand-drawn)

Produced by a throwaway script implementing just the azimuth/elevation -> cell math above (not
the final renderer) to check the aspect-ratio derivation against the user's own mock, with two
ground-truth (not-yet-admitted, `×`) markers and one believed armour (`AR`) contact, and the eyes'
green border drawn as two vertical lines around a gaze centred slightly left of the nose:

```
    90          -60          -30           +0           +30          +60         +9
    |            |            |             |            |            |           |
 +10|                               |            |                                  |
    |                               |            |                                  |
  +1|               x               |        AR  |                                  |
  -4|                               |            |                                  |
    |                        x      |            |                                  |
    |                               |            |                                  |
 -17|                               |            |                                  |
(deg_per_col=2.28 deg_per_row=4.56 rows=7 cols=79)
```

The real renderer should reuse `eyesight_view.py`'s already-solved header-tick alignment code
(this prototype's header line is crude and mis-truncates `+90`) rather than re-deriving it. The
7-row height for a 30°-tall, 79-column-wide canvas confirms the `_ROW_METER_STRETCH`-equivalent
aspect correction (renamed to a degree-based constant in `ascii_canvas.py` or kept in `pov_view.py`
directly, Implementer's call) produces a sane picture — the user's own mock is illustrative, not
drawn to this scale.
