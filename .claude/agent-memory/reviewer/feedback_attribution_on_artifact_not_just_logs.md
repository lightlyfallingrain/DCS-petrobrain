---
name: feedback-attribution-on-artifact-not-just-logs
description: external-data attribution (OSM ODbL etc.) must be burned into the distributable artifact itself, not just printed to console/docs
metadata:
  type: feedback
---

M3 (OSM overlay): the plan required "© OpenStreetMap contributors" on both the research note
*and* any rendered overlay image. Implementation printed the attribution string to stdout and
wrote it in the research note, but never drew it onto the saved PNG (`inspect_osm_overlay.py`,
no `draw.text(...)` before `img.save`). Flagged as a required fix.

**Why:** a rendered image is the thing that actually leaves the pipeline and gets shared/viewed
standalone — console output and research notes don't travel with it. Satisfying an attribution
requirement in logs/docs only is not equivalent to satisfying it on the artifact, even though it
"looks done" (the string exists somewhere in the diff).

**How to apply:** whenever a plan calls for attribution/provenance/license text on a specific
output artifact (image, exported file, report), check that the exact artifact — not just
adjacent logging or documentation — actually contains it. Don't accept "the string appears in the
codebase" as sufficient; verify which file/object the requirement named and check that one file.
