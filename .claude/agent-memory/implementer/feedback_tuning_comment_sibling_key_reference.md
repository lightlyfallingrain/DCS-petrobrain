---
name: tuning_comment_sibling_key_reference
description: body-layer's test_tuning_comment_renders.py fails if a tuning constant's #: comment names a sibling tuning key anywhere after its first sentence -- only the first sentence renders into config/defaults.toml, so a real cross-key reasoning stated later is silently invisible to the pilot reading that file
metadata:
  type: feedback
---

Hit on `BL-B124` Stage 2: `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`'s `#:` comment's *second* sentence said
"...for the same reconciliation reason as `SIGHT_FULL_DARK_SUN_ELEV_DEG`'s `hi` bound above." The
generator (`tools/generate_defaults.py`) only ever renders a tunable's **first** sentence into
`config/defaults.toml`; `tests/test_tuning_comment_renders.py::
test_no_cross_key_constraint_hides_after_the_first_sentence` scans every `#:` block and fails if a
sibling tuning-key name appears anywhere after the first sentence (deliberately, not an accident --
it is catching exactly this: a constraint on how two keys relate that would otherwise be invisible
to anyone reading only the rendered file).

**The fix is not always "move it into the first sentence."** First check whether the two keys
actually have a *real* coupling needing a shared explanation, or whether each key's own `lo`/`hi`
bound already independently guarantees the relationship (as was the case here: `SIGHT_FULL_DARK_
SUN_ELEV_DEG`'s `hi=-6.0` and `EYE_FULL_DAYLIGHT_SUN_ELEV_DEG`'s `lo=1.0` each individually keep
that key away from the fixed measured anchors, and transitively from each other, with no
cross-key enforcement code needed at all, unlike `tuning._check_scan_decay_coupling`'s genuine
cross-key case). If there's no real coupling, just reword the later sentence to restate the
reasoning on its own terms rather than naming the sibling key by identifier -- the test only flags
the *name*, not the general shape of the sentence.

**How to apply:** before adding a new `tuning.real`/`whole`/etc. declaration whose comment mentions
another tunable by name anywhere past the first sentence, run
`pytest tests/test_tuning_comment_renders.py` (part of the full suite, not the fast/targeted one a
narrow `pytest tests/test_light_level.py`-shaped run would miss) before considering the stage done.
