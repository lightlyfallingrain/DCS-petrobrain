---
name: br1-confirm-asymmetry-fix-review
description: Review of d51a25b (Security/Performance change-request fold on BR-1 Stage 2) — the drift-direction check technique and what it found
metadata:
  type: project
---

Reviewed `d51a25b` on `feature/brain-layer-stage2`: security asked `_validate_confirm` to check a
narrower "what the classify prompt actually offered" set (`OFFERED_CONFIRM_VOCABULARY`, mirroring
`brain-layer/src/prompts.py`'s `CLASSIFY_COMMAND_VOCABULARY`) instead of body's whole
`DISPATCHED_COMMAND_TOKENS` (~30). Implementer duplicated the constant (module independence
forbids the import) and documented the drift risk in the new constant's own docstring, claiming
"never unsafe" for a stricter validator.

**That claim only covers one drift direction.** When a task brief says "verify a safe-degradation
claim holds in both directions," actually construct both: (1) body's copy stale-narrow relative to
brain's current vocabulary → validator gets stricter → fails safe, true. (2) body's copy
stale-**wide** — brain *removes* a token from `CLASSIFY_COMMAND_VOCABULARY` without the matching
edit landing in body's mirror, and that token is still a real dispatchable command
(`DISPATCHED_COMMAND_TOKENS`) → the validator's `AND`-of-two-membership-checks still passes it,
because body's stale copy still lists it — reopening the exact asymmetry this stage patched, scoped
to the removed token(s). This is a real code path (`_validate_confirm` degrades on failing *either*
check, i.e. requires membership in *both* to pass), not a theoretical one. Filed as a required fix
(docstring-only, low urgency per [[feedback_bounded_magnitude_isnt_optional_severity]]): a safety
claim that's only half-proven and stated as absolute will mislead whoever next edits
`prompts.CLASSIFY_COMMAND_VOCABULARY`.

**Technique for verifying an "X is never reached" claim in a test docstring**: don't trust the test
alone if it only calls the pure validator function — trace the actual caller
(`crew_console.py::_handle_brain_reply`) to confirm the *returned* `reply.kind` (post-degrade)
is what dispatch branches on, not the original reply. Here it held: `validate_brain_reply` runs
first and its output kind drives the `if/elif` chain, so a degraded `"confirm"`→`"ask"` never
reaches `_handle_brain_confirm`.

**Technique for verifying a performance-tool scenario "can surface pattern X"**: read the actual
concurrency mechanism it depends on, don't take the tool's own docstring at face value.
`live_stage2_decider_check.py`'s scenario 5 claims firing utterances 0.3s apart creates real
concurrent decode calls against Ollama (not requests pre-empted by `JobSlot` before ever reaching
the model). Verified by reading `brain-layer/src/server.py`'s `_handle_escalate`/`_run_job`: each
POST spawns its own worker thread immediately and calls `decide()` right away; `JobSlot.is_current`
is checked only once, right before publishing — never before starting the decode. So the premise
was real.
