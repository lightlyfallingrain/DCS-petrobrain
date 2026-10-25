---
name: ascii-canvas-additive-bg-layer
description: How to add a background-colour highlight to ascii_canvas.Canvas without hiding whatever glyph already occupies a cell, and without touching eyesight_view.py's own tests
metadata:
  type: feedback
---

When a debug ASCII view needs a region highlight (e.g. `pov_view.py`'s optic-FOV disc, BL-B99) that
must not hide a marker/gridline already drawn in that region, do not draw it as a glyph overwrite.
Add a second, independent layer to `ascii_canvas.Canvas`: a `set_bg(row, col, code)` method plus a
parallel `self.bg: list[list[str | None]]` grid, defaulting to `None` everywhere. `render()`
composes a cell's `bg` code with its existing foreground `codes` tuple only when `bg` is set, so a
caller that never calls `set_bg` (e.g. `eyesight_view.py`) sees zero behaviour change — no code
review of that module's own tests is needed, and none broke.

**Why:** the user's own words, 2026-10-25, correcting a prior-round fix that drew the FOV as `.`
dots: "the optics FOV highlight could use background color instead, I believe that's possible with
ASCII." A glyph overwrite (even `set_if_blank`-guarded) necessarily wins or loses against whatever
else wants that cell; a background tint composes with it instead, which is what "nothing gets
hidden behind the disc" actually requires once a marker can legitimately be inside the FOV it's
inside.

**How to apply:** when two debug views share one `Canvas`/`wrap` module (`ascii_canvas.py` here),
and only one of them needs a highlight feature, add the feature as a new orthogonal layer/method on
the shared class rather than branching the shared `set`/`render` behaviour — keeps the other view's
tests a pure regression check with no new scenario to reason about. Also: when colour is off there
is no way to express a tint in plain text, so keep (not remove) the original glyph-based fallback
for `color=False` — two rendering strategies gated on the same `color: bool` the caller already
passes, not a second flag.
