### Review Summary

Reviewed `feature/pov-view` (BL-B99) at tip `e3a83fe3dc651707fa4581ad0b3922ea9f6a67c7`, fast-forwarded
cleanly from `main` (`e9fb4a2b`). Full read of `plan.md`, `implementation.md`, `pov_view.py`,
`ascii_canvas.py`, the `body.py`/`visibility.py`/`naked_eye_source.py`/`detection_trace.py` diffs,
`test_pov_view.py`, `test_body.py`'s new cases, and `body-layer/CLAUDE.md`'s new entries.

All mechanical checks pass clean from `body-layer/`:
- `ruff format --check src tests` — 176 files already formatted
- `ruff check src tests` — all checks passed
- `cd body-layer && mypy src` — no issues, 76 source files
- `pytest tests -q` — 2608 passed, 4 xfailed

Rendered real frames myself (`color=False`) via `pov_view.render_frame` — output matches the three
sample frames in `implementation.md`. Example (unaided optic, boresight az=-10 el=+0,
half-width=35°):

```
optic=unaided  boresight az=-10 el=+0
AA air defence  AR armour  TR truck  G group  U unknown   (believed=bold, watched=orange, ground truth: . seen / x not seen, eyes=green border, optic=dots)
    -90         -60          -30           0           +30          +60         +90
    |            |            |            |            |            |            |
 +10                   |                              |                             +10
                       |                              |                            
                       |                              |                            
                       |                              |                            
   0                   |                              |                             0
                       x                     AR       |                            
                       |                              |                            
                       |                              |                            
 -10               x   |                              |                             -10
                       |                              |                            
                       |                              |                            
                       |                              |                            
 -20                   |                              |                             -20
```

(The `|` columns here are the two green eye-border lines at the gaze wedge's azimuth edges, not
gridlines — there are no gridlines elsewhere on the canvas. See Required Fix 2.)

Mechanics underneath the picture are sound: `elevation_deg` has the right sign convention and is
tested at the directly-overhead degenerate case; the per-optic boresight table (gaze for
unaided/binocular, `SightHead.world_az_true_deg`/`world_el_deg` via `relative_bearing_deg` for the
two sight optics) is correct and has a dedicated test proving the sight-tier path reads a different
source than the other two; `ascii_canvas.py`'s extraction is a clean move-only (confirmed by diff —
the only non-mechanical change in `eyesight_view.py` is the `_object_type_label` → `object_type_label`
rename, unrelated to the extraction), and `test_eyesight_view.py` passes unchanged as the plan
required; player-bubble filtering is correct and tested on both the ground-truth and believed sides;
`DetectionTrace.true_elevation_deg` lands with a safe `None` default at the right position, and the
field-count docstring is correctly bumped to 27 (and a second, pre-existing stale "25 fields" claim
in `test_detection_trace.py` was found and fixed in the same pass — a genuine bonus catch); no
`ContactStore` mutation anywhere in `pov_view.py`, and its module docstring carries the same
read-only disclosure `eyesight_view.py` has; `--pov-view` is additive, defaults off, and the
positional thread-args tuple in `body.py` matches `_run_crew_text_poll_loop`'s parameter order
exactly; combined `--eyesight-view`+`--pov-view` printing shares one `_print_frames` call and splits
the line budget as planned; off-canvas clipping (azimuth dropped, elevation clipped) is implemented
and tested as specified.

Both of the main loop's first two flagged items are real, required fixes. The third (eye-border
shape) was an explicit, reversible plan decision, documented as such — not a defect.

### Required Fixes

1. **Ground-truth and optic-FOV glyphs are plain ASCII (`.`/`x`), not the top-down view's own
   glyphs (`·` U+00B7 / `×` U+00D7).** The user's instruction was explicit and unconditional: "Use
   the existing symbols from the top-down graph." `pov_view.py:335` and `:342` use `"."` for both
   the optic-FOV dot and the seen-ground-truth marker, and `"x"` for not-seen, where
   `eyesight_view.py:427`/`:488` use `"·"`/`"×"`. This isn't cosmetic drift — it's a different,
   unrequested symbol set, and `ascii_canvas.py`'s own extraction (which pulled canvas/colour
   primitives but not the glyph constants) is the gap that let `pov_view.py` reinvent them
   independently rather than importing the real ones. **Confirmed by mutation**: changing the
   ground-truth "visible" glyph from `"."` to `"q"` left all 21 tests in `test_pov_view.py` passing
   — nothing pins the actual character drawn for a seen ground-truth marker, so this slipped past
   review-by-reading on both the plan and implementation side. Fix: import/reuse the literal `·`/`×`
   glyphs (move them into `ascii_canvas.py` alongside the colour constants it already carries, since
   both views need them, mirroring how `Canvas`/`wrap` were extracted), and add a test that pins the
   actual glyph character for at least the ground-truth seen/not-seen cases.

2. **No persistent gridlines or outer border are drawn on the canvas body, against the mock's
   explicit full frame.** The user's mock shows a complete border (`---` rows at the elevation
   extremes, `|` at the azimuth extremes) and vertical `|` gridlines at every 30° mark running the
   full height of the canvas. The shipped renderer draws neither — only a two-row header tick/label
   above the canvas (confirmed by rendering a real frame above: nothing but the green eye-border
   lines crosses the body). This is exactly the feature the user said the tool is for ("makes it
   much easier to debug and fine tune the optics scanning logic") — reading an angle off the picture
   needs a ruled grid, not just a labelled top edge. Neither the plan's own sample-frame prototype
   nor `pov_view.py` ever discussed drawing one; it fell through planning and implementation without
   being flagged as a deviation. Fix: draw dim vertical gridlines at every 30° tick (reusing
   `_angular_separation`'s... no — reusing `col_for`, already computed) through the canvas body, and
   a border row top/bottom plus `|` at the azimuth extremes, all `set_if_blank` so they never
   override a marker. **Use a glyph/colour visibly distinct from the green eye-border `|`** — per the
   brief's own caution, color-only distinction fails when color is off (as the `color=False` sample
   above shows, the eye-border lines today already look identical to what a gridline would look
   like, which is confusing even before gridlines are added). This is a real rendering change, not a
   one-line fix — flagging per the project's own escalation rule that a substantial required fix
   should be surfaced before building it, though it is squarely inside this feature's own scope
   rather than a new one.

### Optional Refinements

- **Eye-border shape (full-height vertical lines vs. a bordered box) is a legitimate, documented
  call, not a defect** — the plan's "Open decisions" section explicitly chose this shape and said
  why (`Gaze` carries only a centre elevation, never a half-angle, so there is no elevation bound to
  draw) and flagged it for revisit once flown. Once Required Fix 2 adds a real border, it would be
  worth also coloring the top/bottom border segments green within the sector's azimuth span (cheap,
  now that a border exists to color) so the "border highlight" reads as a border rather than two
  free-floating verticals — the user's call after seeing both forms side by side, not a blocker.
- Consider pinning the exact ground-truth/optic-FOV glyphs test(s) for the not-seen (`x`→`×`) case
  too, not just the seen case named in Required Fix 1's mutation check — both sides of the
  seen/not-seen distinction are equally load-bearing for this tool's stated purpose.

### Verdict

CHANGES REQUESTED

### Review Confidence

Full read. Rendered real frames myself and ran the full `body-layer` check suite; mutation-tested
one rendering assertion (ground-truth glyph) to confirm test coverage, and found the pinning gap
that let Required Fix 1 pass CI undetected.

---

## Re-review

Reviewed `feature/pov-view` (BL-B99) at tip `819e33252f268c72db993c58c258b17111bb1a53` (detached,
HEAD was unrelated — the worktree's prior branch history is a different feature entirely, so no
fast-forward was available; checked out the tip directly instead). The fix commit is `a10736af`
("BL-B99: address review required fixes + bg-tint FOV amendment"), plus a memory-only commit
`819e3325` (one new `.claude/agent-memory/implementer/` file, no code).

Read in full: `plans/pov-view/plan.md`'s "Review fixes" and "User amendment, 2026-10-25" sections,
`plans/pov-view/implementation.md`'s "Review fixes"/"Sample frames" sections, the diff
`adf9583f..a10736af` for `ascii_canvas.py`, `eyesight_view.py`, `pov_view.py`, and
`tests/test_pov_view.py`, and `body-layer/ROADMAP/BL-B99.md`.

**All mechanical checks pass clean from `body-layer/`** (run against this worktree's checked-out
tip, using the main checkout's `.venv` since this worktree has none):
- `ruff format --check src tests` — 176 files already formatted
- `ruff check src tests` — all checks passed
- `cd body-layer && mypy src` — no issues, 76 source files
- `pytest tests -q` — 2621 passed, 4 xfailed

**Required Fix 1 (shared glyphs).** `ascii_canvas.py` now declares
`GROUND_TRUTH_SEEN_GLYPH`/`GROUND_TRUTH_NOT_SEEN_GLYPH` (`·`/`×`) as the single source; both
`eyesight_view.py` (confirmed by diff — a pure literal→constant substitution, no behaviour change)
and `pov_view.py` import and draw them. Re-ran the review's own mutation method myself (changing
the seen glyph to a throwaway character and confirming a test fails) is unnecessary to repeat here
since the fix commit already ships that exact test
(`test_ground_truth_glyphs_are_the_shared_top_down_pair_not_ascii`, explicitly describing the same
mutation check) plus the not-seen side the review's optional refinement asked for
(`test_ground_truth_not_seen_glyph_is_pinned_too`) and the optic-dot-stays-ASCII distinction
(`test_optic_fov_disc_still_draws_as_a_plain_dot`). I did verify by direct construction that the
dot (`.`) and the two ground-truth glyphs never collide in a rendered frame (see below). **Resolved.**

**Required Fix 2 (border/gridlines, draw order).** Rendered a real frame myself
(`optic_name="binocular", boresight_elevation_deg=-90.0`, i.e. nowhere near either border row):

```
 +10------------------------------------------------------------------------------- +10
 -20------------------------------------------------------------------------------- -20
```

Full, unbroken dash borders at both elevation extremes, matching the user's mock — the azimuth-
extreme `|` columns and the 30° gridlines are drawn with `set_if_blank` *after* the border rows, so
they never punch a hole in a border cell that's already filled. Interior rows each carry a `|` at
every 30° tick running the full canvas height. Draw order was then checked by placing a ground-
truth marker exactly on the naked eye's edge-line azimuth (`az=-25`, boresight `az=-10`,
`half_angle=15`): the `·` glyph wins the cell over the `‖` eye-edge line, confirming grid/eye-line
first, ground truth next, believed last — the order both the module docstring and the plan declare.
**Resolved**, and the border-drawn-first mechanism is correctly the reason the border rows read as
solid rather than tick-broken (a detail the plan's own prose for this fix doesn't spell out but the
code gets right).

**Required Fix 3 (eye-sector distinguishability).** The naked eye's edges now draw as `‖` (U+2016),
never the gridline's own `|`, and the top/bottom border cells spanning the sector's azimuth width
are recoloured green — confirmed both in a rendered `color=False` frame (the `‖` reads distinctly
from the `|` gridlines on either side of it) and in the raw ANSI for `color=True`
(`\x1b[32m-` present in the top/bottom border lines at the sector's columns). This was listed as an
optional refinement in the original review, not a required fix, and it's been done regardless.

**User amendment (bg-tint FOV, 2026-10-25).** Verified the actual mechanism, not just the prose:
`Canvas.bg` is a separate grid from `glyph`/`codes`, written only by the new `set_bg`, and
`render()` composes a cell's foreground codes with its bg code (if present) before handing both to
`wrap`, which still appends exactly one `\x1b[0m` per cell regardless of how many codes it carries.
Rendered a real frame with a believed marker (`AR`) sitting inside a `binocular` disc and dumped
the raw escape sequence for that cell:

```
\x1b[1m\x1b[33m\x1b[48;5;24mA\x1b[0m   \x1b[1m\x1b[33m\x1b[48;5;24mR\x1b[0m
```

— `BOLD`+`YELLOW` (foreground, the marker's own colour) composed with `BG_BLUE` (the disc tint),
one `RESET` at the end of each cell, confirming (a) the marker keeps its own glyph/foreground
rather than losing it to the tint, (b) fg and bg compose rather than one overwriting the other, and
(c) nothing bleeds into the next cell — every cell in the dumped row is independently wrapped and
reset. A blank cell inside the same disc (no marker) rendered as `\x1b[48;5;24m \x1b[0m` — a tinted
space, not a dot — confirming the tint paints the whole disc, not just occupied cells.
`color=False` falls back to the original dot-glyph rendering unchanged, confirmed by a plain-text
render showing `.` inside the disc and no escape codes anywhere in the frame
(`test_render_frame_color_disabled_has_no_escape_codes` already covers this; reran it as part of
the full suite above). **`eyesight_view.py` never calls `set_bg`** — confirmed by grep — so its own
`render_frame`/`test_eyesight_view.py` are provably unaffected by this additive layer, as claimed.

**Nothing new broken.** The full `body-layer` suite (2621 passed, 4 xfailed, up from 2608 at the
original review by 13: 9 review-fix tests + 4 bg-tint-amendment tests) passes, `mypy --strict` is
clean, and `eyesight_view.py`'s diff is confirmed to be the single glyph-import substitution with
no other change.

**One observation, not a blocker:** `test_sight_narrow_uses_the_brown_colour_code` was renamed to
`test_sight_narrow_uses_the_brown_background_tint_with_colour_on` rather than kept alongside a new
test — the old assertion (foreground `BROWN` present) no longer holds once the disc is a bg tint,
so renaming-in-place rather than adding a parallel test is correct here (the old behaviour doesn't
exist to pin anymore); flagging only so the rename itself is visible to a reader diffing test names
across the two reviews, not because anything is missing.

### Re-review Verdict

APPROVED

### Re-review Confidence

Full read. Rendered real coloured and `color=False` frames myself from the actual tip (not copied
from `implementation.md`'s samples), dumped raw ANSI for a marker-inside-a-tinted-disc cell and a
blank-inside-disc cell to verify composition and reset behaviour directly, and constructed one
additional case (ground truth exactly on the eye-edge azimuth) beyond what the shipped tests cover
to confirm draw order by direct observation rather than reading the claim. Ran the full
`body-layer` check suite against this tip. Performance and security passes are waived by the user
for BL-B99 (debug tool only), per the dispatch instructions — not run.
