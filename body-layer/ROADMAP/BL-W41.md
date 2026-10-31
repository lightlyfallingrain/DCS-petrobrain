# BL-W41 — Voice latency instrumentation + positional readback freshness

- [~] **A shared `correlation_id` and per-stage `time.monotonic()` timings now ride the whole voice
  round trip (PTT release → STT → body-layer dispatch → TTS → playback), across audio-adapter,
  aircraft-layer and body-layer, plus a reducer that joins the logs into one timeline per
  utterance — and every positional readback (`select_target`, `mark_target`, `step`, `follow`,
  `watch_nearest`/`watch_nearest_air_defence`, the whole `report` family) is now re-rendered
  against current belief at the moment it is actually spoken, instead of the moment it was
  commanded, when the channel is modeled busy.** #status/in-progress #needs-flight
  `feature/voice-latency-instrumentation`, DoD reviewed at tip `47952413`
  (`plans/voice-latency-instrumentation/{plan,implementation,review,security-plan-review,
  security-review,performance-review,dod-check}.md`). Built from `docs/acceptance/
  2026-10-20-sortie-feedback.md`'s F1 ("readback latency of several seconds") and F8 ("set target"
  acknowledged several seconds late, with the pilot already turned away from a now-stale position).

  **User decisions (2026-10-20, plan.md's own override block)**: defer-and-redraw every positional
  readback, not just `select_target` ("all of them"); log the dispatched command token as a cheap
  substitute for the full `OutgoingSpeech.template` ("cheap"); no playback-start feedback seam yet
  — measure first, revisit only if a real timeline shows the channel-modeled-clear case dominates
  ("measure first"); `--latency-log` records failed STT/synthesis attempts too ("yes").

  **Merged to `main` 2026-10-20 (`9a5da6a4`)**, after `feature/9k113-narrow-search`. Stays
  `#status/in-progress` until flown: `#needs-flight` is the open part. `feature/async-speech`
  (F8, plan only) builds on this branch; the plan merged to `main` 2026-10-31 and is tracked as
  `[[BL-B106]]`.

  **DoD mechanical checks, all three touched subprojects (audio-adapter, aircraft-layer,
  body-layer — the only ones this diff touches, confirmed from `git diff` against the branch's
  own fork point, not assumed): `ruff format --check` / `ruff check` / `mypy --strict` / `pytest`
  all pass.** audio-adapter 343 passed/2 skipped; aircraft-layer 377 passed/2 deselected; body-layer
  2269 passed/4 xfailed. The 2 deselected aircraft-layer tests
  (`test_collector_server_accept_errors.py`) are a sandbox artifact confirmed unrelated to this
  diff (`git diff` against that file and the collector code it exercises is empty) — reproduced
  directly in this DoD pass as a `thread.is_alive()` race on a fixed-port bind, the same symptom
  the Reviewer found and distinct from (but equally sandbox-shaped as) the `OSError: Address
  already in use` the Implementer originally reported; worth knowing the exact symptom is
  sandbox-dependent, not the conclusion that it's unrelated.

  **Reviewer**: three rounds, all on real exercised behaviour, not inferred from the diff — an
  initial full read built a synthetic round trip through real code (`CaptureLoop` → `TranscribeClient`
  → a real `TTSAdapterServer` → body-layer's `CrewConsole` → `push_speech` → the same server's
  `/speak`) and fed the resulting logs into the reducer, confirming the pipeline-ordered timeline
  works; found one real defect by running it, not reading it — `mark_target`'s deferred *write*
  (not just its spoken echo) could be silently dropped by a refusal or mission restart before the
  channel cleared, a correctness regression against this project's "code owns truth" posture.
  **Required Fix 1** (APPROVE after re-review, mutation-tested by the Reviewer): the write now
  happens unconditionally at command time, same as every other positional-readback handler's side
  effect; only the position-free acknowledgment text is deferred. **Security's deep analysis**
  then found two further low-risk gaps — `_pending_positional_replies`'s missing size cap
  (`BL-B87`) and the reducer aborting whole on one malformed JSONL line (`BL-B88`) — both fixed and
  Reviewer-approved in the same batch (both entries already `#status/done` in this same directory).
  **Security plan review**: APPROVED (no new dependency, `correlation_id`/`t_ptt_release_wall`
  validation-and-cap precedent flagged for the Implementer, confirmed applied). **Performance**:
  APPROVED — MONITOR, no required mitigation; two items flagged for a future pass if real-flight
  evidence warrants it (the same `_pending_positional_replies` list, self-limiting today because
  its producer is human-paced; `push_speech`'s pre-existing, not newly-introduced, blocking call on
  the poll thread).

  **Acceptance boundary — what fixtures structurally cannot reach.** Every check above runs
  against a synthetic round trip or unit-level fixtures. That proves the instrumentation mechanism
  works end to end and that Stage 6's defer-and-redraw fires correctly — it does **not** show where
  the real multi-second F8 delay actually is. Two things only a live flight can settle:
  1. **Stage 6 only fixes the *modeled-busy* case** — a readback queued in sim-time terms behind
     another already-spoken utterance. The user's own read of F8 ("the real problem here is the
     many second delay") is more consistent with raw STT/network/TTS latency while the channel was
     modeled *clear*, which this milestone does not touch (Decision 2: no playback-start feedback
     seam yet, by design, pending exactly this evidence).
  2. **The audio-adapter queue dwell time** (a recognised transcript sitting in the queue before
     body-layer's ~1s poll drains it) has no measured field anywhere in this chain — only the poll
     interval as a known upper bound.
  The very next flight should run with `--latency-log` on both audio-adapter processes and
  `--belief-truth-log` on body-layer's logger, then reduce them with
  `tools/join_voice_latency.py` — see "How to turn the logs on and read them" in
  `plans/voice-latency-instrumentation/dod-check.md`. That single flight is what clears
  `#needs-flight` here, and what decides whether Decision 2 needs reopening.

  **Milestone completion question**: yes, conditionally. This does not add a new milestone to the
  BL-x sequence by itself, but its own outcome gates the next piece of work — if the first real
  timeline shows the channel-modeled-clear case dominating, Decision 2 (no playback-start feedback
  seam) is the thing to revisit, per the plan's own stated condition, not a fresh architecture pass.
  **Separately, not part of this entry's own scope**: the branch's own history has already picked
  up one further sortie-feedback note after this DoD's reviewed tip (`feature/voice-latency-
  instrumentation`'s current head, one commit past `47952413` as of this write-up) — "speech async,
  one mouth; layers don't wait on each other" — captured per this project's capture-then-explore
  rule, not yet explored or planned. This entry's own verdict is scoped to `47952413` only.
