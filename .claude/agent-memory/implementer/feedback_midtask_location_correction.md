---
name: feedback-midtask-location-correction
description: A coordinator message mid-task can override the dispatch prompt's own file-location instruction -- apply it immediately, including to already-committed-but-not-yet-pushed plan/explore-notes text, before finishing.
metadata:
  type: feedback
---

On BL-B90 Stage 1, the dispatch prompt said sequence files + curated registry go to
`body-layer/sequences/`. Mid-task, a coordinator message arrived correcting this to
`body-layer/config/sequences/` (user's own words: "actually, body-layer/config/sequences is
better"), and asked for the plan's R-table, explore-notes, and any already-created files to be
updated to match.

**Why this matters**: a mid-task correction from the coordinator carries the same weight as the
original dispatch instruction -- it is not a suggestion to note for "later" or to mention in the
handoff report while finishing under the old instruction. Apply it immediately, to every artifact
the original instruction touched: code paths, test fixtures, the plan's own revision-history
table (add a new R-row, do not silently edit an old one), and any "explore-notes" file that is
supposed to hold the user's verbatim words -- append the new quote there too, do not just act on
it silently.

**How to apply**: before writing any file under a location named by the dispatch prompt, if a
correction has arrived, re-derive the path from the correction rather than from memory of the
original prompt text. If files were already written under the old location, `git mv` them (the
coordinator asked for this explicitly) rather than leaving a duplicate copy -- in this case no
files existed yet under the old path, so there was nothing to move, but check before assuming
that is always true.

See [[project_generator_tool_convention_reuse]] for the sibling lesson from the same task (reusing
`generate_defaults.py`'s conventions for a second dev tool).
