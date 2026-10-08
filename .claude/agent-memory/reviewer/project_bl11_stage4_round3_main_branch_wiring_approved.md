---
name: bl11-stage4-round3-main-branch-wiring-approved
description: round 3 of BL-11 Stage 4 (wiring coverage logging into main()'s bare else: branch) reviewed APPROVED clean.
metadata:
  type: project
---

`c6f196e` (feature/bl11-stage4-fail-closed) wired `_warn_live_los_coverage_gap_once`/
`_log_live_los_coverage_summary` (approved round 2) into `main()`'s third, previously-dark branch
— the bare `else:` with neither `--console` nor `--crew-text` — answering Security's advisory
finding that this branch shared the fail-closed gate 4 but had no coverage signal at all.

Three things worth remembering about how this was verified:

1. **The `sources` hoist** (`sources: list[PerceptionSource] = []` before `try:`, reassigned
   inside) is the right shape for "finally always has a valid list even if construction raised" —
   and does not mask a construction failure, because that failure still propagates past
   `except KeyboardInterrupt: pass` (which doesn't catch it) through `finally:` and out, loud via
   its own traceback. The summary's silence on an empty list is "nothing to report," not a
   swallowed error.
2. **`main()` can be driven past argparse and into a loop body via `sys.argv` + a real
   `MockAircraftLayerServer` + a controlled `KeyboardInterrupt`, with `main()` itself untouched.**
   This is sound when the thing under test is specifically "is this branch's production code
   wired correctly" — the only way to prove that is a real invocation — but it is a precedent to
   keep narrow, not the new default way to add `logger.py` coverage (implementer's own framing,
   confirmed correct).
3. **The cross-test `time.sleep` pollution (leftover `BrainLayerClient` daemon thread catching an
   unrelated `KeyboardInterrupt`) reproduces exactly as described** — reverting the fix's own fix
   (`monkeypatch.setattr(mod.time, "sleep", fake)` instead of rebinding `mod.time` itself) brings
   back 6 `PytestUnhandledThreadExceptionWarning`s on a full suite run. See
   `[[feedback_monkeypatch_module_attr_not_shared_stdlib]]` in the implementer's memory — flagged
   as worth a home in `body-layer/CLAUDE.md`'s `## Testing` section too (optional, not required;
   not yet done as of this round).

Verdict: APPROVED, ready for DoD. Full review: `plans/bl11-stage4-fail-closed/review.md`, "Round
3".
