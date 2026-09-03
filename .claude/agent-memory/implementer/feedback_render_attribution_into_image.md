---
name: feedback_render_attribution_into_image
description: OSM/external-data attribution must be drawn onto rendered raster images, not only printed to stdout/research notes
metadata:
  type: feedback
---

Per `docs/concept/WORLD_MODEL_BUILDER.md`, any rendered overlay image derived from OSM (or other
external GIS) data must carry "(c) OpenStreetMap contributors" (or equivalent) baked into the
image itself via `draw.text(...)`, not just printed to the console or written into a research
note. Reviewer flagged this as a required fix on M3 (`plans/m3-osm-overlay/review.md`).

**Why:** the image is a standalone artifact that can be shared/viewed independently of the tool's
stdout — attribution has to travel with it.

**How to apply:** when a tool renders a PNG/image derived from OSM/external data
(`tools/inspect_osm_overlay.py` is the reference implementation), draw the attribution string
onto the image before `img.save(...)`, e.g. bottom-left corner with a filled background box
(`draw.rectangle` + `draw.text`) for legibility against arbitrary underlying imagery.
`ImageFont.load_default()` is sufficient — no new font dependency needed. Verify by actually
opening/viewing the rendered output, not just checking the code path exists.

Also note: `world-model/tools/` is not in the CLAUDE.md-mandated ruff/mypy check commands (those
list only `src` and `tests`), but new/modified tool files should still be format/lint/type
checked individually — pre-existing drift in *other* tools files (e.g. `EXE001` shebang
warnings, an unrelated I001 in `report_control_point_errors.py`) is out of scope for your change
and shouldn't block it; don't fix unrelated pre-existing issues in the same commit.
