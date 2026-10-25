### Implementation Summary

Built `--pov-view`, the Petrovich-POV debug view (`BL-B99`) -- a forward-looking, Cartesian
azimuth/elevation twin of `--eyesight-view`'s top-down plan view. All six stages from the plan
landed except the optional Stage 6 (`pov_replay.py`), skipped per the main-loop amendment ("do only
if 1-5 are clean and it's genuinely small" -- out of scope for this cut).

### Files Changed

- `body-layer/src/perception/geometry.py` -- added `elevation_deg(observer, target)`, a pure
  world-horizon-relative elevation helper (positive up, pitch/bank independent).
- `body-layer/src/perception/detection_trace.py` -- added `DetectionTrace.true_elevation_deg: float
  | None = None`.
- `body-layer/src/perception/visibility.py` -- `_record` closure now computes and passes
  `true_elevation_deg=elevation_deg(observer, target)`; added `elevation_deg` to the
  `perception.geometry` import.
- `body-layer/src/perception/naked_eye_source.py` -- the `PLAYER_BUBBLE` trace row now sets
  `true_elevation_deg=elevation_deg(observer, target)` the same way; added the import.
- `body-layer/src/detection_trace_writer.py` -- bumped the `_entry_to_dict` docstring's field-count
  claim (see Notable Discoveries -- it was already stale before this change).
- `body-layer/src/ascii_canvas.py` (**new**) -- `Canvas`/`wrap` and the ANSI colour constants
  (`RESET`/`DIM`/`BOLD`/`GREEN`/`BLUE`/`GRAY`/`YELLOW`/`ORANGE`, plus new `BROWN =
  "\x1b[38;5;130m"` for the 9K113 narrow optic) extracted from `eyesight_view.py`. Pure move +
  rename, no behaviour change.
- `body-layer/src/eyesight_view.py` -- imports canvas/colour primitives from `ascii_canvas` instead
  of defining them locally; `_object_type_label` renamed to `object_type_label` (dropped the
  leading underscore and added it to `__all__`) since it has a second potential caller across the
  module boundary. No other behaviour change -- `tests/test_eyesight_view.py` passes unchanged.
- `body-layer/src/pov_view.py` (**new**) -- the renderer: `PovGroundTruthMarker`/`PovBeliefMarker`,
  `pov_ground_truth_markers_from_trace`/`pov_believed_markers_from_contacts` (reusing
  `eyesight_view.contact_label`/`relative_bearing_deg`), and `render_frame`.
- `body-layer/src/body.py` -- `_render_pov_frame(runner, trace_records, max_lines=None)` (mirrors
  `_render_eyesight_frame`'s shape, resolves the per-optic boresight table); `--pov-view` CLI flag,
  threaded through `_run_crew_text_poll_loop`'s parameter list (right after
  `eyesight_view_radius_m`) and `main()`'s thread-args tuple; `_print_eyesight_frame` generalised to
  `_print_frames(frames: Sequence[str])` so both views can share one clear-and-print cycle;
  `_render_eyesight_frame` gained an optional `max_lines` parameter so the poll loop can hand it a
  halved budget when both views are on.
- `body-layer/CLAUDE.md` -- module-map entries for `ascii_canvas.py`/`eyesight_view.py` (previously
  undocumented there)/`pov_view.py`, and a short flag-docs paragraph for `--eyesight-view`/
  `--pov-view` (also previously undocumented).
- `plans/pov-view/plan.md` -- appended "Main-loop amendments" and "Deviations from the plan found
  during implementation" sections (below).

**Review fixes (`plans/pov-view/review.md`, tip `adf9583f`):**

- `body-layer/src/ascii_canvas.py` -- added `GROUND_TRUTH_SEEN_GLYPH`/`GROUND_TRUTH_NOT_SEEN_GLYPH`
  (`·`/`×`), shared by both views (Required Fix 1).
- `body-layer/src/eyesight_view.py` -- its ground-truth glyph selection now imports the two
  constants above instead of using its own local literal (no behaviour change -- same characters).
- `body-layer/src/pov_view.py` -- ground-truth markers now draw `GROUND_TRUTH_SEEN_GLYPH`/
  `GROUND_TRUTH_NOT_SEEN_GLYPH` instead of the old local `"."`/`"x"` pair (Required Fix 1);
  `render_frame` now draws a dim-gray border row/column and 30-degree gridlines first, overridden
  by the eye-sector/disc/ground-truth/believed layers in turn (Required Fix 2); the naked-eye
  sector's edges draw as `‖` (`_EYE_EDGE_GLYPH`) instead of `|`, and the sector's top/bottom border
  cells are recoloured green (Required Fix 3); the legend line updated to describe all of the
  above.
- `body-layer/tests/test_pov_view.py` -- one existing test renamed/updated
  (`test_unaided_optic_draws_a_border_not_a_disc` → `test_unaided_optic_draws_eye_edges_not_a_disc`,
  since the eye-edge glyph changed from `|` to `‖`); nine new tests (see "Tests Added").

**User amendment (2026-10-25, mid-review-fix): "the optics FOV highlight could use background
color instead."** `ascii_canvas.Canvas` gained an additive `set_bg`/`bg` layer, independent of the
existing glyph/foreground layer (`eyesight_view.py` never calls it, so it and its tests are
unaffected); `ascii_canvas.py` gained `BG_BLUE`/`BG_GRAY`/`BG_BROWN`. `pov_view.render_frame`'s
optic-disc branch now paints a background tint per cell when `color=True` (keeping whatever glyph
already occupies the cell -- a gridline, a marker, a blank), and only falls back to the original
`.`-dot rendering when `color=False`, since there is no way to show a tint in plain text. One
existing test (`test_sight_narrow_uses_the_brown_colour_code`) updated to check the background
code instead of the foreground one, since the colour-on disc no longer uses the foreground colour
at all; four new tests cover the tint/dot split, a marker inside the disc keeping its own glyph
while gaining the tint, and a blank cell inside the disc rendering as a tinted space. Full account
in `plans/pov-view/plan.md`'s "User amendment, 2026-10-25" section.

### Tests Added

- `body-layer/tests/test_geometry.py` -- `test_elevation_deg_level_target_is_zero`,
  `test_elevation_deg_target_above_is_positive`, `test_elevation_deg_target_below_is_negative`,
  `test_elevation_deg_directly_overhead_is_90` (the degenerate zero-horizontal-separation case).
- `body-layer/tests/test_detection_trace.py` -- `test_admitted_entry_records_true_elevation_deg`,
  `test_rejected_entry_also_records_true_elevation_deg` (ground truth is recorded regardless of
  which gate decided the outcome).
- `body-layer/tests/test_pov_view.py` (**new**, originally 21 tests, now 30 after the review
  fixes below) -- ground-truth/believed marker builders (azimuth/elevation carried through
  correctly, player-bubble rows/contacts dropped, a row with no elevation dropped rather than
  fabricated), `render_frame` draw order (believed wins over disc/border, ground truth doesn't
  survive under a believed marker), azimuth-cutoff drop vs. elevation clip-not-drop, the
  eye-edge-vs-disc distinction for `unaided` vs. every other optic (verified both ways), the brown
  colour code for `sight_narrow`, colour on/off, watched=orange/unwatched=yellow, axis tick labels
  present, and the `max_lines` budget. Nine tests added for the review fixes (glyph pinning on
  both sides with a mutation check, the optic-FOV-dot-stays-ASCII distinction, border/gridline
  presence and draw order, the eye-edge glyph, and the sector border-highlight colour) -- see
  "Review fixes" below.
- `body-layer/tests/test_body.py` -- `test_render_pov_frame_none_before_first_poll`,
  `test_render_pov_frame_unaided_optic_uses_gaze_boresight`,
  `test_render_pov_frame_binocular_optic_uses_fixed_look_boresight`,
  `test_render_pov_frame_sight_tier_uses_sight_head_world_direction` (confirms the sight-tier
  boresight comes from `SightHead.world_az_true_deg`/`world_el_deg`, converted to heading-relative
  azimuth, not from `gaze`/`OpticState`), `test_render_pov_frame_respects_max_lines`.

### Checks (body-layer/)

- `ruff format --check src tests`: pass (177 files, after reformatting `test_pov_view.py`)
- `ruff check src tests`: pass (all checks passed)
- `cd body-layer && mypy src`: pass (76 source files, no issues)
- `pytest tests -q`: pass -- 2617 passed, 4 xfailed (up from 2608 by the 9 review-fix tests)

### Review fixes

`plans/pov-view/review.md` (tip `adf9583f`) required three fixes before this could land; all three
are now addressed, and the sample frames below are re-rendered from the fixed code.

1. **Ground-truth glyphs.** Moved `GROUND_TRUTH_SEEN_GLYPH = "·"` (`·`)/
   `GROUND_TRUTH_NOT_SEEN_GLYPH = "×"` (`×`) into `ascii_canvas.py`, so both views share one
   literal rather than each defining its own. `eyesight_view.py`'s own ground-truth glyph selection
   now imports them too (previously a local literal), closing the drift the review's own mutation
   check found. The optic FOV's dot stays plain ASCII `.`, unchanged, per the user's own
   instruction ("draw the current optic's FOV with dots '.'") -- deliberately a different
   character from either ground-truth glyph, not a third alias for one of them.
   `test_ground_truth_glyphs_are_the_shared_top_down_pair_not_ascii` pins the seen glyph and is
   confirmed, by mutation, to fail if it reverts to `"q"` (or anything else);
   `test_ground_truth_not_seen_glyph_is_pinned_too` does the same for the not-seen side (the
   review's own optional refinement); `test_optic_fov_disc_still_draws_as_a_plain_dot` pins the
   disc side of the same distinction.
2. **Border and gridlines.** `render_frame` now draws a dim-gray `-` border row at both elevation
   extremes and a dim-gray `|` border column at both azimuth extremes, plus dim-gray `|`
   gridlines at every 30-degree azimuth tick running the full canvas height -- all drawn first,
   via `set_if_blank`, so a marker/disc/eye-line below always wins its cell (`test_top_and_bottom_
   border_rows_are_full_dash_lines`, `test_vertical_gridlines_run_through_the_full_canvas_body`,
   `test_gridlines_and_border_are_drawn_before_the_optic_disc`).
3. **Eye sector highlight.** The naked-eye sector's two edges now draw as `‖` (U+2016 DOUBLE
   VERTICAL LINE), not the gridline's own `|`, so the sector still reads without colour
   (`test_eye_edge_glyph_differs_from_the_gridline_glyph`); the top/bottom border cells spanning
   the sector's azimuth width are recoloured green (`test_eye_sector_border_cells_are_recoloured_
   green`), so the sector reads as one highlighted band rather than two free-floating lines. The
   legend line was updated to describe all three glyphs (ground truth, eye sector, optic FOV) and
   the gridlines.

### Sample frames

Produced from the final `pov_view.render_frame`, `color=False`, with synthetic ground-truth and
believed markers (not hand-drawn) -- re-rendered after the review fixes above:

**Unaided optic (green `‖` eye-sector edges, green sector highlight on the top/bottom border):**

```
optic=unaided  boresight az=-10 el=+0
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: · seen / × not seen, eyes=green ‖ sector, optic=dim ., grid=dim |)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10--------------------------‖----------------‖----------------------------------- +10
    |            |            ‖            |   ‖        |            |            |
    |            |            ‖            |   ‖        |            |            |
    |            |            ‖            |   ‖        |            |            |
   0|            |            ‖            |   ‖        |            |            | 0
    |            |     ×      ‖            |   ‖        |            |            |
    |            |            ‖            |   ‖        |            |            |
    |           ×|            ‖            |   ‖AR      |            |            |
 -10|            |            ‖            |   ‖        |            |            | -10
    |            |            ‖            |   ‖        |          TR|            |
    |            |            ‖            |   ‖        |            |            |
    |            |            ‖            |   ‖        |            |            |
 -20--------------------------‖----------------‖----------------------------------- -20
```

**Binoculars (blue filled dot-disc, 4.25-degree half-angle):**

```
optic=binocular  boresight az=+12 el=-5
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: · seen / × not seen, eyes=green ‖ sector, optic=dim ., grid=dim |)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10------------------------------------------------------------------------------- +10
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
   0|            |            |            |            |            |            | 0
    |            |     ×      |            |   ...      |            |            |
    |            |            |            |   ....     |            |            |
    |           ×|            |            |   .AR      |            |            |
 -10|            |            |            |            |            |            | -10
    |            |            |            |            |          TR|            |
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
 -20------------------------------------------------------------------------------- -20
```

**9K113 narrow (brown filled dot-disc, 3-degree half-angle -- visibly smaller than the binoculars'):**

```
optic=sight_narrow  boresight az=+12 el=-5
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: · seen / × not seen, eyes=green ‖ sector, optic=dim ., grid=dim |)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10------------------------------------------------------------------------------- +10
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
   0|            |            |            |            |            |            | 0
    |            |     ×      |            |    .       |            |            |
    |            |            |            |   ...      |            |            |
    |           ×|            |            |    AR      |            |            |
 -10|            |            |            |            |            |            | -10
    |            |            |            |            |          TR|            |
    |            |            |            |            |            |            |
    |            |            |            |            |            |            |
 -20------------------------------------------------------------------------------- -20
```

(ANSI colour codes stripped for this document; `AR`/`TR` render bold-orange/bold-yellow, the `×`
ground-truth glyph dim gray, the gridlines/border dim gray, the eye-sector edges/border highlight
green, and the disc in the optic's own colour when `color=True`.)

### Notable Discoveries

- **`eyesight_view.py` had no "already-solved header-tick alignment code" to reuse**, contrary to
  the plan's sample-frame section ("The real renderer should reuse `eyesight_view.py`'s
  already-solved header-tick alignment code") -- confirmed by `grep` of the whole module before
  writing `pov_view.py`'s own tick/label logic from scratch. Recorded in the plan's new "Deviations"
  section so a future reader does not go looking for code that was never there.
- **`render_frame`'s plan-listed signature could not actually draw the border/disc** without one
  more input: the naked eye's border needs the active gaze's own half-width, and every other
  optic's disc needs that optic's `fov_half_angle_deg` -- neither was in the plan's parameter list.
  Added one keyword, `half_angle_deg: float`, resolved per-optic by `_render_pov_frame` in
  `body.py` from the same table the plan already specifies.
- **A second stale field-count docstring, found by actually counting.** `detection_trace_writer.py`
  claimed "`DetectionTrace` has 25 fields" (and `test_detection_trace.py` repeated the same number
  in its own docstring) -- an `ast`-walk of `DetectionTrace`'s `AnnAssign` nodes found the real count
  was already **26** before this change (one past the stale claim), now **27** with
  `true_elevation_deg` added. Both one-line references are fixed; the test docstring's count was
  dropped entirely rather than replaced with a new number that will go stale the next time a field
  is added -- the sentence reads fine without it ("`asdict` emitted all fields including the ~13
  that are `None`...").
- **`eyesight_view.py`/`--eyesight-view` had no entries anywhere in `body-layer/CLAUDE.md`** before
  this change (module map or flag docs) -- a pre-existing documentation gap, not introduced here.
  Added entries for it alongside the new `ascii_canvas.py`/`pov_view.py` rather than leaving the
  sibling module undocumented next to its own new twin.
- **BL-B89 risk flagged by the plan did not land during this implementation** -- `git log`/`git
  branch` show no merge of `feature/9k113-scan-procedure` onto this branch's base, so the plan's own
  "re-check if BL-B89 merges" caveat about `Gaze`/`ScanPlan`/`sight_head.py` shapes still applies
  unchanged to whatever BL-B89 eventually ships.
