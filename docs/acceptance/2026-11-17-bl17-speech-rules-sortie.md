# BL-17 Stages 0/1b/2 (spoken commands as Lua rules): acceptance sortie

**Artifact (cockpit-readable card):** https://claude.ai/artifact/UaZdz1eas5M5DEME4bdZu4
**Card source:** `docs/acceptance/2026-11-17-bl17-speech-rules-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, from `plans/speech-rules/plan.md` (Stages 0, 1b, 2) and
`body-layer/ROADMAP/BL-17.md`:

- The rule engine itself: `config/rules/*.lua` loads at startup and reloads at mission restart,
  pushes its patterns to `audio-adapter` over `PUT /rules`, and a loaded rule behaves identically
  from the pilot's seat to a static Python-handled command.
- The one ported command, `turn_heading_relative` ("turn left/right NN"), on AI-overlay (parked,
  mode 2) flight, player in the operator seat.
- The edit-and-reload loop: a rule-file change is picked up on a mission restart, not a
  body-layer restart.
- The two failure modes the user specifically asked be audible: a rule-file clash (two rules
  claiming the same wording) and a Lua syntax error — both spoken as one fixed phrase, "Action
  file error," with the real cause only in the stderr log.

**Deliberately not re-tested here**: Stage 1a (the bearing/heading rename) — paused mid-build by
user direction, parked on `wip/bl17-stage1a-rename`, not in this merge at all. No existing scan/
report/heading command's meaning has changed. Stages 4–10 (the remaining ~80 commands) are not
built; this flight is only "turn left/right NN."

**Already verified without a flight** (DoD, from the Mac, no DCS needed):
`python -m body --print-rules --audio-adapter-url http://127.0.0.1:<port>` against a real running
`audio-adapter` loads `turn_heading_relative` and the adapter answers it accepted, nothing
rejected. Run it again before you fly if you want to see it yourself — it's the card's first step.

Results go to `body-layer/ROADMAP/BL-17.md`, not into the card.
