---
name: feedback_adjacent_calibration_note_silently_assumes_a_different_optic
description: a docstring's adjacent calibration-derivation note can use a different optic/multiplier than the constant's own function default -- don't transcribe its numbers into new pilot-facing prose without checking which optic the consuming function actually defaults to
metadata:
  type: feedback
---

X-T26 fix pass 2 added three new pilot-facing sentences to `LOWRES`/`MEDRES`/
`HIRES_ANGULAR_RADIUS_RAD`'s `#:` blocks in `body-layer/src/perception/visibility.py`, stating
"the default puts the boundary at ~9.3/2.0/1.0 km". Security review (fix pass 2) caught that all
three were exactly 4x too high. The root cause: the three figures were lifted from the *adjacent*
calibration-derivation note two paragraphs above, which explicitly derives its own numbers with
`size / threshold * BINOCULAR_RANGE_MULTIPLIER` (a binocular-ladder case) -- but the function these
constants actually feed, `_recognition_thresholds_m`/`_achieved_tier`, defaults its `optic`
parameter to `UNAIDED_OPTIC`, whose `presence_range_mult`/`class_range_mult`/`type_range_mult` are
all `1.0` (`perception/optics.py` lines 141-143). "The default" in the new sentence meant the
function's own default optic (naked eye), not the neighboring note's illustrative optic
(binoculars), and nothing forced those two readings of "default" to agree.

**Why:** a calibration note that derives a number is documenting *how that number was produced*,
not necessarily *what every later reader of the same constant should assume as "the" value* --
especially when the module defines more than one optic with different multipliers
([[feedback_binocular_not_unaided_eye]] is the companion memory on why this project's
binocular/naked-eye distinction is deliberate, not incidental). Transcribing a neighboring note's
numbers into new prose, without re-deriving them against the actual consuming function's default
parameter, silently carries that note's assumed context into a sentence that no longer states it.

**How to apply:** before writing or editing any pilot-facing range/threshold sentence in this
codebase, (1) identify which optic the constant's consuming function defaults to (grep the
function signature, don't assume from nearby prose), (2) recompute the figure yourself from the
actual default value and that optic's multipliers, and (3) name the optic explicitly in the new
sentence (e.g. `` under `UNAIDED_OPTIC` ``) rather than leaving "the default" ambiguous between
"the function's own default parameter" and "whatever the adjacent note happened to illustrate" --
the ambiguity itself is what let the 4x error through unnoticed in the first pass. Relevant to
Stage 3 (the remaining ~80 body-layer constants), many of which sit next to similar
derivation/calibration notes.
