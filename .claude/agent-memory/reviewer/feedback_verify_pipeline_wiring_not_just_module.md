---
name: feedback_verify_pipeline_wiring_not_just_module
description: When reviewing a fix to a low-level module, always read the actual call site that wires it into the pipeline/orchestrator, not just the module's own diff.
metadata:
  type: feedback
---

A correct, well-tested fix inside a leaf module (e.g. `osm/pbf.py`'s streaming rewrite) does
nothing for the reported bug if the orchestrator (`build/pipeline.py`) still calls the old
function. This is a distinct failure mode from "the fix is wrong" — the fix can be perfect and
still be a no-op in production because nothing calls it.

**Why**: caught explicitly as the single highest-priority check when reviewing
[[project_osm_streaming_ingest_approved]] — the task instructions called this out by name
("does a real build actually get the fix, or did only pbf.py change"), and it turned out the
pipeline wiring was in fact updated correctly, but it required reading `pipeline.py`'s branch
directly rather than trusting the module docstring's claim that it wires into the streaming path.

**How to apply**: whenever a plan/diff touches a low-level module used by a pipeline/orchestrator,
always grep the orchestrator for the old function name post-fix (it should be gone from the new
code path, or only remain on an explicitly-unrelated branch) and read the new call site in full —
don't infer wiring correctness from the module's own docstring or tests, which can only prove the
module works in isolation, not that anything calls it correctly.
