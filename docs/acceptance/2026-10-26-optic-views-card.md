# Acceptance: fix/optic-views-actual-look -- optic views agree

Card: https://claude.ai/artifact/HRxMuu4JiSfrwvZmYE38pW

**Branch:** `fix/optic-views-actual-look`, DoD-passed at tip
`9d8908e2782c18d27e221a9af94b8cb426a56848`. Not yet merged to `main`.

**What this is.** Fixes the defect reported in `docs/acceptance/2026-10-26-sortie-feedback.md`:
`--eyesight-view` and `--pov-view` disagreed on where Petrovich was actually looking, because
`--eyesight-view` (and `--pov-view`'s non-sight branch) read the *commanded* scan plan rather than
the gaze actually applied once a fixed look (sight aim or a binocular glass phase) overrode it.
Fixed with one shared `_resolve_active_gaze(runner)` in `body-layer/src/body.py`, read by both
debug views and by `_speech_log_sink`'s belief-truth log.

**Run command** (same pattern as the prior POV-view card,
`docs/acceptance/2026-10-25-bl-b99-pov-view.md`):

```sh
cd run-scripts
./run-body-layer-debug-view.sh --pov-view
```

**Verified:** `python -m body --help` against this branch lists `--eyesight-view` and `--pov-view`
unchanged. **Unverified:** the actual live render -- needs the Windows box, a live DCS session,
and the user's own `petrobrain.env`, none of which exist in this worktree.

## Acceptance boundary

All 13 new automated tests (`body-layer/tests/test_body.py`) exercise the fixed resolver against a
fabricated `runner`, proving the per-case logic is correct given those inputs -- not that a real
sortie's poll loop produces exactly those inputs, and not that the rendered text reads right to a
pilot watching it. That is exactly what this card checks for.

## Test cases (full detail on the card)

1. **Sight case** -- the one the original screenshot showed disagreeing. Both views should now
   agree on direction and optic name.
2. **Binoculars** -- the case the original sortie did not happen to exercise (the "second, narrower
   finding" in `plans/optic-views-actual-look/debug.md`). Both views should agree during a fixed
   binocular look.
3. **Naked-eye free scan** -- regression check only; this path is unchanged by the fix.

## Pass criteria

All three cases agree between the two views, and the free-scan case shows no regression from
before this branch. Clears `#needs-flight` on `body-layer/ROADMAP/BL-B99.md` once confirmed --
name the sortie that cleared it.
