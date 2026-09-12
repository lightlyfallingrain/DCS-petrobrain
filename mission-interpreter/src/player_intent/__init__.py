"""MI-5: a deterministic ambiguity detector over `MissionUnderstanding`
(`questions.py`) plus a typed console loop (`console.py`) that surfaces
detected questions to the player and writes structured answers back into
`MissionUnderstanding.player_intent` -- `plans/mi5-player-questions/plan.md`.

New top-level sibling of `miz/`, `filter/`, `world_enrich/`, `schema/`,
`synth/`. See `console.py`'s module docstring for why this mirrors
`body-layer/src/belief/crew_console.py`'s shape without importing it
(root `CLAUDE.md`'s module-independence rule).
"""

from __future__ import annotations
