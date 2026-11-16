# BL-16 Stage P2a/P2b (voice goals + HVRT translate): acceptance sortie (2026-11-17)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/K2vYdNY8d4kVaf2Eom56V8
**Card source:** `docs/acceptance/2026-11-17-bl16-p2-voice-goals-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, from `plans/flight-control/plan.md` ("Stage P2 ready to build", "Stages" —
Flight P2a/P2b) and `plans/flight-control/review-p2.md`'s re-review:

- **P2a**: spoken heading/altitude/speed goals, the readbacks, rotation when more than one goal
  is outstanding (one parameter moves at a time), "unable, not ready" with a retry about 3 s
  later when a mode-cycle gets stuck.
- **P2b**: HVRT translate (left/right/forward/back/up/down) from a hover, the automatic switch
  into HVRT, "Hold" always cancelling even if the aircraft has left hover.
- **The arbitration decision** (`plans/flight-control/implementation.md`, "Review-fix round,
  2026-11-16", Required fix 2) — a main-loop judgement call on the pilot's behalf, not something
  the pilot asked for in these words: a translate pauses the goal channel, "Hold" resumes it, a
  new goal clears an outstanding translate. Needs the pilot's confirm or overrule.
- **The seat gate**: switching to the pilot seat mid-goal must stop every press, inherited from
  Stage P1's seat-gate fix, confirmed by Reviewer for this stage's new press paths structurally
  rather than by a new check.

**Deliberately not re-tested here**: Stage P1's takeover/stabilisation (own card, 2026-11-16,
already flown separately) and the 700 m radar cap probe (Stage P0-rad) — flown as part of this
stage's own "alt ... radar" block below, since no dedicated probe exists yet. Stage P3 (align,
break turns) and P4 (recovery) are not built.

**Known limitation, not a regression if seen**: `[[BL-B122]]`, filed at this DoD pass — a goal
write that fails over the LAN (collector hiccup) is marked sent and not retried until a new or
repeated command. Only reachable by a transient network failure, not normal flight; worth a note
if a spoken goal appears to do nothing at all.

Results go to `body-layer/ROADMAP/BL-16.md`, not into the card.
