# AA-4.5 — Stage 5 — real PTT through DCS

- [x] **Stage 5 — real PTT through DCS. FLOWN AND ACCEPTED 2026-09-23.** #status/done Built the same day on
  `feature/inbound-speech-stage4` (stacked on Stage 4 at user direction, tested as one).

  **The sortie's four verdicts:** the trigger works; a radio call stays out of it; the two-stage
  trigger *"is natural"*; and the audio path is right. The one item not exercised is endurance —
  false-fire and miss rates over a whole flight — which needs a real sortie rather than a systems
  check.

  **One bug was found and fixed between building and flying, and it is the interesting part.**
  `push_ptt_state` was defined above `safe_call` in `Export.lua`, and Lua has no hoisting: a name
  referenced before its `local` declaration compiles as a *global* lookup, nil at call time. Every
  frame called nil, the trigger published nothing, and from the capture process's side that is
  indistinguishable from a talk control nobody pressed. `luac5.1 -p` passes it — the syntax is
  valid — so the syntax check cannot see this class at all. `Export.probe-ptt.lua` was run and arg 738 returned 0.5 held and 0.0 released on the
  user's own bound trigger, a 209 ms press was captured, and the value held across frames rather
  than pulsing. Crucially the *binding* was confirmed too — a DCS binding can be a game action
  that never animates the cockpit control, which would have left the argument right and still
  dead. Full addendum: `aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`.

  **Gate on the intercom stop specifically, not SRS's `>= 0.1`.** The full press is the player
  talking on the radio to someone else, and Petrovich has no business hearing it; the half press
  routes to intercom regardless of the SPU-8 selector, so this is also what the real aircraft does.

  **But `abs(v - 0.5) < 0.1` alone is not enough, and a second probe run proved it.** A full press
  *transits* the half stop for 19–32 ms on its way to 1.0 — it is a two-stage mechanical trigger,
  so it must. That bare gate would therefore open a capture on every radio call. Two mitigations,
  covering different cases: **debounce the 0.5 state by ~100 ms** (three times the observed worst
  transit, still far below any deliberate press-and-speak), and **treat a rise to 1.0 as an abort**
  of any capture in flight, which catches a slow full press that dwells past the debounce. The
  failure this prevents is silent — a discarded sub-threshold clip per radio transmission, which
  presents as an audio problem rather than a trigger one.

  **What was built.** `Export.lua` reads arg 738 every frame and sends `{"t":…,"ptt":…}` **only
  when it changes** — deliberately not on the 5 Hz telemetry line, because a press waiting behind
  that throttle could lose up to 200 ms off the front of an utterance, on top of the ~140 ms the
  audio device already costs to open, and the front of an utterance is where the verb is. A real
  trigger produces two lines per press, not a stream. `PttSample`/`PttCache` carry it,
  `GET /ptt/state` serves it, and `DcsPTT` implements the same `PTTSource` protocol the joystick
  already does. Wire version `2026-09-22b` → **`2026-09-23a`**.

  **The layer boundary is doing real work here.** `Export.lua` and the collector carry the raw
  value and decide nothing; the two thresholds and both mitigations live in `DcsPTT`, where they
  can be tuned and tested without copying a file into Saved Games. The endpoint still serves the
  decided booleans alongside the raw value, so a consumer that wants them need not re-derive two
  thresholds.

  **`discard_if` is a hook on `CaptureLoop`, not a new `PTTSource` method.** Only `DcsPTT` has
  anything to say about radio presses; widening the protocol would have made the joystick and
  keyboard sources carry a method that always answers False.
