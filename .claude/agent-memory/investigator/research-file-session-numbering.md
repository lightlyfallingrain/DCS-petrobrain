---
name: research-file-session-numbering
description: Check for concurrent/unrelated session-number collisions before appending a new dated session to a shared research/*.md file
metadata:
  type: feedback
---

`world-model/research/*.md` files can receive concurrent appends from other
agent sessions working a different sub-thread (observed: `2026-09-03-m2-rastercharts-
recon.md` had multiple parallel investigator sessions appending "Session N" sections
around the same time, landing out of physical/chronological order in the file).

**Why:** blindly using "next sequential session number" risks colliding with a number
another concurrent session already used, or landing badly out of order in the file
even when numbers don't strictly collide — confusing to a later reader trying to
follow the investigation's actual chronology.

**How to apply:** before appending a new dated session section, grep the target file
for `^## Session`/`^### Session` (and check `git diff --stat` / whether the file
changed since last Read, which the Edit tool will also warn about). If the highest
existing session number was used by a different topical thread, or several parallel
sessions are landing concurrently, skip ahead to a clearly non-colliding number and
add a one-line parenthetical note explaining why the numbering isn't strictly
sequential, rather than silently overwriting/colliding.
