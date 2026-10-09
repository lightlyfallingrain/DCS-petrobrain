# BL-W5 — Confirm-band affirmatives

- [x] **`fix/confirm-band-affirmatives` — the confirm band was unanswerable in the air; fixed and
  merged 2026-09-28 (`583d786`), unflown.** #status/done #needs-flight **Merged before its acceptance flight at user
  direction** — *"so many things at this stage are intertwined that it's better to test to current
  HEAD"* — so the card
  (`docs/acceptance/2026-09-28-confirm-band-sortie.md`) is now flown from `main` alongside
  everything else outstanding, not from a branch. Same posture as the 2026-09-24 binocular-optic
  merge: a correction the flight produces lands on `main` rather than on a branch that has drifted. The 2026-09-26 sortie: `"cancel"` → *"Cancel everything, confirm?"* →
  `"yes"`/`"confirm"` → *"Unable, no such command."* Three defects behind one symptom, and
  `cancel` always routes through the confirm band whatever its match ratio, so all three hit
  every cancel: `"confirm"` — the word the question itself asks for — was not an affirmative;
  `CONFIRM_WINDOW_S` was 8.0 s timed from when the question was *decided* rather than heard,
  against a ~6.5–7.5 s round trip; and a late answer escalated to the brain, whose
  `NO_SUCH_COMMAND` is literally where that wording came from. Now 15.0 s, a 20 s late-answer
  grace that says "Say again?" instead, and a widened answer vocabulary.

  **What the sortie has to settle, because static review cannot**: whether 15 s and 20 s are
  right (both are reasoned budgets, not measurements), and whether `cancel` → `"confirm"` → the
  task actually stopping works in the cockpit.

  **Worth recording separately: this took five review rounds, and each round's fix broke
  something the previous round had right.** First word is an answer word → swallowed a real
  instruction opening "okay". Every word an answer word → rejected "yes do it", and inside the
  window a rejected answer *silently discards the pending command*, so the cancel just would not
  happen. `verb_anchored` → broke bare `"roger"` and `"negative"`, which had worked before the
  branch existed (`VERB_FLOOR` is 0.5 fuzzy; `roger` scores 0.55 against `report`, `disregard`
  *is* `cancel_nevermind` at 1.00). The anchor for multi-word utterances → still broke
  `"roger wilco"`, because the anchor is computed from the **first word alone**. What shipped is
  the union of all of them, ordered. **Every round was found the same way** — by running the real
  `command_matcher` end to end rather than trusting a test that supplied its own default for the
  parameter under scrutiny — and that is the transferable lesson, not the word list. The
  cross-subproject coupling is now pinned from both sides (`audio-adapter` asserts those words do
  anchor; body-layer asserts the classifier answers them anyway), since neither may import the
  other. Full five-round log: `plans/confirm-band-affirmatives/review.md`.

