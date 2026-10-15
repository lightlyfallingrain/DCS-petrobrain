---
name: claimed-gate-order-mirroring-needs-checking-against-source
description: When a new function claims to compute causes "in X's own gate order", read X's actual gate sequence from source before trusting the claim -- BL-B70's cause taxonomy got it backwards and no test caught it.
metadata:
  type: feedback
---

A pure-function cause taxonomy (`belief.attack_run._no_look_cause`, `BL-B70`) claimed, in its own
docstring and in two test docstrings, to be "computed in `check_visibility`'s own gate order, so the
two cannot disagree about precedence." It was not: `check_visibility`'s real gate sequence
(`perception/visibility.py`) is mask → optic FOV → **range/size** → **terrain LOS** → forest, but
the new function checked LOS (`"obstructed"`) before range (`"too_far"`) — inverted.

**Why this is worth a standing habit, not a one-off:** the claim appeared three times (module
docstring, function docstring, two test docstrings) and was never checked against the actual gate
order in `check_visibility`'s body — only read as asserted. Mutation proved the gap instantly:
swapping the two branches left all 2018 tests passing, because nothing constructs a contact that is
simultaneously fresh-LOS-blocked *and* beyond range. That combination is exactly the kind of
diverged state `[[verify-by-mutation-per-entry-not-per-set]]` already names as the class of defect
reading alone misses.

**How to apply:** whenever a plan or implementation claims a new code path "mirrors" or "matches"
an existing pipeline's order/precedence (gate order, priority list, fallback chain), read the
referenced pipeline's actual control flow from source -- not its docstring, not the new code's own
claim about it -- before accepting the claim. If the two can jointly be true (e.g. a contact that is
both too-far and LOS-blocked), construct that case by hand and check which branch wins, then verify
a test exists pinning it. A docstring repeating a false claim three times does not make it true, and
a full green test suite does not confirm an ordering claim that nothing exercises both halves of.

Also worth remembering from the same review: a losing-sight sentence template
(`render_attack_run_lost_sight`) combined a word-form clock phrase (`alignment_phrase`, which
itself renders "three o'clock" whenever azimuth is outside the 12 o'clock sector) with a
separately-computed digit-form clock position (`where = f"{where_hour} o'clock"`, bypassing the
module's own `_ALIGNMENT_CLOCK_WORDS` table one function away) -- producing, and the project's own
test pinning, "Three o'clock armor 3 o'clock, last seen a moment ago." A test asserting an exact
string is not evidence the string is *good* -- read what it pins, not just that it passes.
