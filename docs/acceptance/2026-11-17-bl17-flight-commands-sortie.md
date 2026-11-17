# BL-17 Stages 3a/3b/3d/4 (fuzzy matching, category gates, effector-write surface, flight-control port): acceptance sortie

**Artifact (cockpit-readable card):** published by the main loop at merge time.
**Card source:** `docs/acceptance/2026-11-17-bl17-flight-commands-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, from `plans/speech-rules/plan.md` Revision 2 (D13-D20) and
`body-layer/ROADMAP/BL-17.md`:

- Fuzzy near-miss tolerance on a rule's directive words (D13 + the Stage 3a review's E12
  correction) — the value itself (a number, left/right) is never fuzzy, only the command words
  around it.
- The number-word grammar reaching the `angle` slot, so "turn left thirty" actually parses as a
  number, not just digits.
- Six gate categories (D16): every flight-control rule refuses "unable, not flying" before its
  handler ever runs when Petrovich has no controls, and the four finer categories hold briefly
  (never refuse) during the takeover-settle window until their own needed held value arrives.
- 18 of the 19 originally planned flight-control commands, ported from their pre-rule Python
  handlers to `config/rules/flight.lua`, each kept differentially equivalent to what it replaced
  ("straight" dropped per the user's own decision — it collided with the bare hover word "right").
- A flight-category readback now cuts ahead of an in-flight routine callout (U22) — the one
  genuine, user-confirmed behaviour change in this batch that a fixture cannot judge.
- The rule action surface can write cockpit effectors through the existing registry/engine
  (D20), but no shipped rule in this batch actually calls it — nothing to fly for that yet.

**Deliberately not re-tested here**: the bearing/heading rename (still paused), Stage 3c (the
narrowed speech-to-text hint — not built; its test corpus can be recorded in this same session,
see the card's last section, but there is nothing live to fly for it), and the five wording
collisions a mid-build check once found among these 18 rules — all resolved before this merge
(verified below), so nothing to check for them specifically, though any strange command behaviour
is still worth reporting.

**Already verified without a flight** (DoD, from the Mac, no DCS needed):

- Full suites, both subprojects: `fast-tests.sh --full body-layer` (3548 passed, 0 failed, 4
  xfailed) and `fast-tests.sh --full audio-adapter` (526 passed, 0 failed, 2 skipped).
- `python -m body --print-rules --audio-adapter-url http://127.0.0.1:<port>` against a real
  running `audio_adapter` and the real shipped 18-rule `config/rules/flight.lua`: all 18 load,
  all 18 pushed, **all 18 accepted, zero rejected** — the five wording collisions
  `implementation.md` once found mid-build are confirmed gone, not just claimed gone (the D9
  collision-check recalibration rescued three, dropping "straight" removed the last pair's own
  colliding side).
- `/invariant-check` clean (no new violations from this batch); `command-map-check.py` fails for
  the known, named reason (it does not understand rule-file commands yet, so every ported id
  reads as "on the map but no longer in TOKENS" — not a regression, not redrawn this pass).

Full DoD report: `plans/speech-rules/dod-check-stage3-4.md` — its "Acceptance boundary" section
states plainly what none of the above can reach: whether any of this reads right to a pilot in
real time, in a real cockpit, against DCS's own state machine rather than a test double.

Results go to `body-layer/ROADMAP/BL-17.md`, not into the card.
