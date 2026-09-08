## Review: PB-1 stages 4-9 (HybridPerceptionSource) — 2026-09-08

Reviewed commits `598945f`..`1bade06` on `feature/pb1-perception-logger` against
`plans/pb1-perception-logger/plan.md`'s redesigned stages 4-9 ("Association design", "Invariant
Check", "Implementation Plan") and `aircraft-layer/research/2026-09-08-pb1-live-spike-results.md`.
Stages 2-3 (BL-0 scaffolding) were reviewed previously (`pb1-stage2-3-review.md`) and are not
re-litigated here except where stage 4-9 code touches them.

### Review Summary

The hybrid redesign is implemented faithfully to the plan: `association.py`'s algorithm matches
the "Association design" section step-for-step (candidate pool, plausibility filter, type-match
scoring, three-way decision), `HybridPerceptionSource`'s detection gate is structurally real (not
synthetic — verified by tracing every early-return path in `poll()`), `Observation.bearing_deg`/
`range_m` stay non-optional with a genuine drop-and-emit-nothing path for zero candidates, the new
`petrovich_indication.py` parser is a from-scratch recursive-descent implementation with no trace
of `asherao/DCS-ExportScripts`, `GET /petrovich_indication/latest` mirrors `/world_objects/latest`
exactly with zero interpretation logic, `Export.lua`'s new push reuses the existing throttle/
socket/debug-log mechanism with no bypass, and `test_logger.py`'s fake-source test passes
unmodified. No scope creep — no `petrovich_feed.py`/`proxy.py` materialized. All four
format/lint/type/test commands were re-run directly (not trusted from implementer notes) and pass
clean: `ruff format --check`, `ruff check`, `mypy --strict` (both subprojects, body-layer via the
documented `cd body-layer && mypy src` CWD workaround), `pytest` (52 passed aircraft-layer, 47
passed body-layer).

`TYPE_MATCH_TIE_MARGIN=0` is a reasonable reading of the plan's ambiguous "one is unambiguously
top-scored (score margin above a threshold)" phrasing — strict-tie-only-counts-as-ambiguous is the
conservative choice (it treats *more* scenes as ambiguous, i.e. lower-confidence, rather than
fewer), consistent with the plan's own "prefer a new contact over a bad merge"-style caution
elsewhere. Named as a tunable constant, not a hardcoded literal — acceptable as shipped.

### Required Fixes

None.

### Optional Refinements

- **Debounce keys only on classification text, not position or a stable ID** — if HelperAI
  switches its selected target between two same-type objects (e.g. two different "Ural truck"s)
  *without* an intervening empty-text frame, `hybrid_source.py`'s debounce will suppress the
  second detection as "unchanged." The plan's own debounce requirement only specifies "clearing
  then reappearing with the same text still re-emits" — implemented and tested
  (`test_detection_clearing_then_reappearing_with_same_text_re_emits`) — not "two consecutive
  same-classification detections without a gap." This is an inherent limitation of a
  classification-text-only signal (no stable ID exists to distinguish the two), already implicitly
  covered by the plan's "Debounce/re-emission tuning is unspecified" risk note, so not a required
  fix. Worth a one-line comment in `hybrid_source.py` acknowledging the gap explicitly (it's
  currently only visible by reading the debounce logic closely), and worth flagging for the live
  acceptance test in stage 7 (a same-text back-to-back target switch is exactly the scenario a
  live decoy-target test should probe, alongside the ambiguous-association path already called
  out in the plan).
- **HelperAI wire-format parser was built from prose only, no literal example dump** — the
  implementer's own memory note (`project_pb1_stage4_9_hybrid_source.md`) flags this transparently.
  `parse_indication_text`'s graceful-degradation posture (skip malformed structure rather than
  raise) mitigates the risk of a wrong assumption crashing the pipeline, and this is exactly the
  kind of thing stage 7's live acceptance run against a real Mi-24P sortie will validate for real.
  No action needed before merge; just don't let this parser's test coverage be mistaken for live
  validation.
- **Type-match vocabulary and plausibility thresholds remain unvalidated against a real
  multi-object scene** — explicitly flagged as a known risk in the plan itself (Risks & Unknowns),
  not new. Restating only because stage 7's acceptance criterion (a live sortie with a decoy
  target to exercise the ambiguous path) is the actual validation step and hasn't happened yet per
  the implementation log — make sure that step isn't skipped before this is trusted operationally.

### Verdict

APPROVED

### Review Confidence

Full read — plan (`plans/pb1-perception-logger/plan.md` in full), research note, all touched
source files (`association.py`, `source.py`, `hybrid_source.py`, `petrovich_indication.py`,
`Export.lua` diff, `server.py` diff, `PETROBRAIN_RUNTIME.md` diff) and their test files read in
full, not sampled. Verification commands (ruff format/check, mypy --strict, pytest) re-run
directly by the reviewer for both `aircraft-layer` and `body-layer`, not trusted from the
implementer's session notes. One process note: found the implementer's stage-4-9 agent-memory
files unstaged (sixth recurrence of this pattern per reviewer memory) — staged them as part of
this review rather than treating it as a blocking required fix, since the content itself was
sound.
