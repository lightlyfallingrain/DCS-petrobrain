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

### Tests Added

- `body-layer/tests/test_geometry.py` -- `test_elevation_deg_level_target_is_zero`,
  `test_elevation_deg_target_above_is_positive`, `test_elevation_deg_target_below_is_negative`,
  `test_elevation_deg_directly_overhead_is_90` (the degenerate zero-horizontal-separation case).
- `body-layer/tests/test_detection_trace.py` -- `test_admitted_entry_records_true_elevation_deg`,
  `test_rejected_entry_also_records_true_elevation_deg` (ground truth is recorded regardless of
  which gate decided the outcome).
- `body-layer/tests/test_pov_view.py` (**new**, 21 tests) -- ground-truth/believed marker builders
  (azimuth/elevation carried through correctly, player-bubble rows/contacts dropped, a row with no
  elevation dropped rather than fabricated), `render_frame` draw order (believed wins over
  disc/border, ground truth doesn't survive under a believed marker), azimuth-cutoff drop vs.
  elevation clip-not-drop, the border-vs-disc distinction for `unaided` vs. every other optic
  (verified both ways -- the border test was re-run against `binocular` to confirm it goes red for
  the stated reason before being trusted), the brown colour code for `sight_narrow`, colour
  on/off, watched=orange/unwatched=yellow, axis tick labels present, and the `max_lines` budget.
- `body-layer/tests/test_body.py` -- `test_render_pov_frame_none_before_first_poll`,
  `test_render_pov_frame_unaided_optic_uses_gaze_boresight`,
  `test_render_pov_frame_binocular_optic_uses_fixed_look_boresight`,
  `test_render_pov_frame_sight_tier_uses_sight_head_world_direction` (confirms the sight-tier
  boresight comes from `SightHead.world_az_true_deg`/`world_el_deg`, converted to heading-relative
  azimuth, not from `gaze`/`OpticState`), `test_render_pov_frame_respects_max_lines`.

### Checks (body-layer/)

- `ruff format --check src tests`: pass (176 files)
- `ruff check src tests`: pass (all checks passed)
- `cd body-layer && mypy src`: pass (76 source files, no issues)
- `pytest tests -q`: pass -- 2608 passed, 4 xfailed

### Sample frames

Produced from the final `pov_view.render_frame`, `color=False`, with synthetic ground-truth and
believed markers (not hand-drawn):

**Unaided optic (green eye border, two vertical lines at the gaze wedge's azimuth edges):**

```
optic=unaided  boresight az=-10 el=+0
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: . seen / x not seen, eyes=green border, optic=dots)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10                            |            |                                      +10
                                |            |                                     
                                |            |                                     
                       x        |            |                                     
   0                            |            |                                      0
                                |            |                                     
                                |            |  AR                                 
                                | .          |                                     
 -10                            |            |                                      -10
                                |            |                     TR              
                                |            |                                     
                                |            |                                     
 -20                            |            |                                      -20
```

**Binoculars (blue filled dot-disc, 4.25-degree half-angle):**

```
optic=binocular  boresight az=+12 el=-5
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: . seen / x not seen, eyes=green border, optic=dots)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10                                                                                +10
                                                                                   
                                                                                   
                       x                                                           
   0                                                                                0
                                               ...                                 
                                               .AR.                                 
                                  .            ...                                 
 -10                                                                                -10
                                                                   TR              
                                                                                   
                                                                                   
 -20                                                                                -20
```

**9K113 narrow (brown filled dot-disc, 3-degree half-angle -- visibly smaller than the binoculars'):**

```
optic=sight_narrow  boresight az=+12 el=-5
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: . seen / x not seen, eyes=green border, optic=dots)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10                                                                                +10
                                                                                   
                                                                                   
                       x                                                           
   0                                                                                0
                                                .                                  
                                               .AR                                 
                                  .             .                                  
 -10                                                                                -10
                                                                   TR              
                                                                                   
                                                                                   
 -20                                                                                -20
```

(ANSI colour codes stripped for this document; `AR`/`TR` render bold-orange/bold-yellow, the "x"
ground-truth glyph dim gray, and the disc/border in the optic's own colour when `color=True`.)

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
