### Performance Review

Batch reviewed: `fix/optic-views-actual-look` (tip `332f4a9c`), both commits (`_resolve_active_gaze`
introduction + `_render_eyesight_frame`/`_render_pov_frame` call-site swap, and the follow-on
`_speech_log_sink` call-site swap). No hard real-time budget applies in this phase (`CLAUDE.md`);
assessed against "no per-request allocations on hot paths" and "offload heavy work asynchronously"
since this touches the body-layer poll loop.

### Context established before judging cost

- The poll loop runs at ~0.7 Hz in practice against a specified 5 Hz target (knowledge graph:
  "body-layer poll loop runs at ~0.7Hz against a specified 5Hz",
  `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`) — the loop already has
  headroom relative to its own target, so a few extra float comparisons and one dataclass
  construction per poll is not competing with a tight budget.
- `--eyesight-view` and `--pov-view` both default off (`body-layer/CLAUDE.md`: "Both default off, a
  true no-op when absent") — `_resolve_active_gaze` only runs from these two call sites when a
  developer/calibration flag is explicitly set, not on every player's ordinary sortie.
- `_speech_log_sink`'s `sink` closure runs once per spoken line (`CrewConsole.speech_log_sink`), not
  once per poll — speech is "a handful of rows per sortie" (`body-layer/CLAUDE.md`, describing the
  sibling `--speech-log`), several orders below poll frequency.

### Findings

#### `_resolve_active_gaze` call cost

- **Location:** `body-layer/src/body.py:1742-1814`, called from `_render_eyesight_frame` (debug
  view, opt-in), `_render_pov_frame` (debug view, opt-in), and `_speech_log_sink`'s `sink` closure
  (per spoken line).
- **Risk:** none credible. The function body is a handful of attribute reads, up to one
  `relative_bearing_deg` call (plain trig on floats, no allocation beyond the return value), and one
  `Gaze` dataclass construction (two floats, two primitives) per call. No loop, no query, no I/O,
  no collection iteration. Even if a future change made the eyesight/POV views default-on, two such
  calls per poll at 0.7-5 Hz is immaterial next to the rest of the poll (contact store tick,
  association, world-model LOS queries).
- **Action:** MONITOR — only worth re-checking if `_resolve_active_gaze` is later given its own
  heavier per-call work (e.g. a world-model query), since today's version sets the expectation that
  callers can call it freely.

#### Redundant computation across two debug views in the same poll

- **Location:** `_render_eyesight_frame`/`_render_pov_frame`, both called from the same poll-loop
  block (`body.py` ~L3297-3320) when both `--eyesight-view` and `--pov-view` are on.
- **Risk:** `_resolve_active_gaze(runner)` is now computed twice per poll in that combined mode
  (once per view) instead of once — a pre-existing pattern (the two views already duplicated
  per-optic resolution before this fix; now they duplicate a call to the shared function instead of
  duplicating the logic itself). The duplicated call is the same trivial cost assessed above, and
  both flags are opt-in debug/calibration tooling, not the default path.
- **Action:** LATER (not now) — if someone wants to tidy this, the poll-loop block could resolve
  gaze once and pass it into both render calls, but doing so now would be refactoring working debug
  code for a cost too small to matter at today's call frequency and optic-count scale.

#### No batching, allocation, or query-frequency regressions introduced

- Confirmed no new per-poll collection iteration, no new query against `ContactStore`/world-model,
  and no new allocation pattern beyond the one `Gaze` object already produced before this fix (the
  old code also built a `Gaze` via `gaze_at(...)` on every call — this fix changes *which* branch
  builds it, not how many are built per caller).
- `_speech_log_sink` was already reading `runner` live per spoken line before this change (by
  design, per its own docstring: "Reads `runner` live rather than capturing values... for the same
  reason: `scan_plan`/`optic` are reassigned every poll"); swapping its one `gaze_at(...)` call for
  `_resolve_active_gaze(runner)` does not change its call frequency, only which fields it reads.

### Verdict
APPROVED
