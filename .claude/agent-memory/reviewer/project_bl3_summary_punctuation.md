---
name: bl3-summary-punctuation
description: belief/tools.py _contact_summary appends fragments onto a string that already ends in "." — check for double punctuation before approving new appends
metadata:
  type: project
---

`_contact_summary` (`body-layer/src/belief/tools.py`) builds a sentence ending in `.`, then
optionally appends `" Being watched."`. Commit 19bd7f9 (overlay-clock-range-summary) added a third
append — `, <clock> o'clock, <range> km.` — directly onto the already-`.`-terminated string,
producing `"...ago., 11 o'clock, 3.0 km."` (period immediately followed by comma). This was a
genuine, newly-introduced defect: pre-commit, `" Being watched."` was always the last thing
appended, so no prior code path exercised "more content after a trailing period." Required fix:
strip trailing `.` before appending, re-add one final `.`.

**Why:** naive string concatenation onto a sentence-terminated summary is an easy, easy-to-miss
defect class in this file — the fragment looks fine printed in isolation, only shows up wrong when
read as a whole sentence.

**How to apply:** any future change that appends another fragment to `_contact_summary` (or
similar sentence-building helpers in `belief/`) — check the join point for double punctuation.
Don't assume an existing `" X."`-style suffix is precedent for `.`-then-more-content unless it was
actually followed by further appends before.
