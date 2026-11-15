---
name: expected-area-look-probe-points-deep-analysis
description: BL-B111 expected-area-look deep security analysis — PASS; probe_points extends the %d-only dostring_in splice to the coordinate case the prior memory had explicitly left open, and AC-B11 is now reproduced by a sixth POST handler
metadata:
  type: project
---

`feature/expected-area-look` (BL-B111, tip `27eaed47`) deep analysis: PASS. Report
`plans/expected-area-look/security.md`.

**Resolves the open boundary condition from
[[project_xb29_los_two_percent_d_splice_approved]].** That memory explicitly said a future
`look_around(x_coord, y_coord, alt)`-shaped extension would need its own review because
coordinates are a different value class (no natural small range, and floats don't have `%d`'s
"only digits" guarantee). `probe_points` is exactly that extension, and it stays safe because the
Hook truncates to **integer** coordinates before splicing (still `%d`, never `%f`/`%g`) and
bounds each one to `±2,000,000` (`PROBE_COORD_ABS_MAX`) via the same `_safeClampInt` used
everywhere else in this file. **If a future splice ever needs a true float/world-coordinate
substitution (not integer-truncated), that is the case still not covered — re-review then, don't
assume this clearance extends to it.**

**`AC-B11` (unbounded `Content-Length` on every aircraft-layer POST handler) is now reproduced by
a sixth handler**, `_handle_command_probe_points`. `AC-B11.md`'s own 2026-10-29 correction said
the count "stays five unless some other feature adds a new POST handler" — this one did. Not
blocking (same low/low rating), cited under the existing ID rather than filed new. **`AC-B11.md`
itself was not edited** by this review (the dispatching orchestrator explicitly asked not to edit
the roadmap) — a follow-up docs-only commit should bump its handler count and name
`probe_points`. Check whether that follow-up has landed before re-citing this as "not yet
corrected."

**Pattern worth repeating on the next multi-field wire extension**: when a Lua `dostring_in`
splice gains new substitution points, check (a) are they still integers truncated before
splicing (keeps the `%d`-only argument valid), and (b) does each one go through the *same* total
clamp function as the existing cleared ones, with no special-cased weaker path. Both held here;
verified by reading the spliced chunk directly, not inferred from the surrounding comments.
