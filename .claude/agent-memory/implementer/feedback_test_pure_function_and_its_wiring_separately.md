---
name: test-pure-function-and-its-wiring-separately
description: a well-tested pure function can still have an untested call site; test the wiring too
metadata:
  type: feedback
---

On `feature/terrain-callout-stages-345`, `terrain_divide_qualifier` (`body-layer/src/belief/
enrichment.py`) had five solid direct-call unit tests in `test_enrichment.py`. Review round 1 found
that the two lines that actually deliver it to the pilot -- `tools.py`'s
`facts["terrain_qualifier"] = terrain_qualifier` and `speech.py`'s
`if isinstance(terrain_qualifier, str): ... replaces semantic selection` -- had zero coverage.
Disabling either with `if False and ...` left the full 1430-test suite passing unchanged.

**Why:** five existing fixtures across `test_tools.py`/`test_console.py`/`test_crew_console.py`/
`test_callouts.py`/`test_speech.py` all stub `divides_between` to return `0` unconditionally (added
only to stop an unrelated `sqlite3.OperationalError` against a schema-less fake connection), so none
of them ever reach the new branch. A pure function's own tests prove it's *correct*; they don't prove
anything *calls* it with a value that exercises the interesting branch.

**How to apply:** when a plan's last stage is "wire X's result into Y" (a write into a shared
`facts`/context dict, then a read elsewhere that branches on it), write at minimum one test that
drives the writer with the condition true and asserts the dict key lands, and one that drives the
reader with that key present and asserts it changes the output (not just "appears somewhere" --
assert what it *displaces*, e.g. the semantic fragment it was designed to outrank). Then prove
each with the reviewer's own method: wrap the line in `if False and ...`, confirm the specific new
test (and only that test) fails, revert. See [[project_terrain_feature_probing_rev3_stages345]] for
the original feature this applied to.
