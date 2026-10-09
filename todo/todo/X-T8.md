# X-T8 — The confirm band asks a question nothing can answer

- [~] **The confirm band asks a question nothing can answer.** #status/in-progress *me "cancel" -> P "cancel everything,
  confirm?" -> me "yes"/"confirm" -> P "no such command".*

  **The diagnosis written here on 2026-09-26 was wrong and is kept for the record**: it said "the
  vocabulary has no affirmative token at all — so the confirm band is unreachable by design". It
  is not. `belief/voice_commands.py` already had `_AFFIRM_WORDS = {affirm, affirmative, yes,
  roger}`, `PendingConfirmation` already held the command between turns, and
  `handle_transcript` already checked both before anything else. Writing that from reading the
  symptom rather than the code cost a day of the item reading as bigger than it was — the
  project's own "verify state, not the account of it" rule, applied to a defect report.

  What was actually wrong (fixed on `fix/confirm-band-affirmatives`, 2026-09-28, unflown):

  1. **The question asks for a word the answer set rejected.** `render_confirm_request` renders
     "<X>, confirm?" and `"confirm"` was not an affirmative — the pilot's own report is
     *"yes"/"confirm"*, and echoing the operative word back is the most natural answer there is.
     Widened to include `confirm`/`confirmed`/`correct`/`yeah`/`yep`/`ok`/`okay`, and the
     negatives to include `nope`/`belay`. **Widening the set took four review rounds to make
     safe, and the lesson is worth more than the fix.** Each round produced one plausible rule
     that was right about the case motivating it and broke something the previous one had right:

     - *first word is an answer word* → swallowed `"okay watch that truck at three o'clock"`;
     - *every word is an answer word* → rejected `"yes do it"`, and a rejected answer inside the
       window does not say "say again", it **silently discards the pending command** — so the
       cancel simply would not happen, worse than the original defect;
     - *`verb_anchored`* (the matcher's verdict) → broke bare `"roger"` and `"negative"`, which
       had worked before this branch existed: `VERB_FLOOR` is 0.5 fuzzy, so `roger` anchors
       against `report` at 0.55, and `disregard` *is* the `cancel_nevermind` phrasing at 1.00;
     - *the anchor for multi-word utterances* → still broke `"roger wilco"` and `"negative hold
       off"`, because the anchor is computed from the **first word alone**, so an answer word
       that anchors intercepts the whole utterance whatever follows it.

     What is in the code is the union, ordered: (1) whole transcript is answer words → that
     answer, consulting nothing else; (2) else the matcher resolved a real command **token** →
     not an answer; (3) else first word is an answer word and ≤ 4 words → that answer. Every
     round was found the same way — by running the real matcher end to end rather than trusting
     a test that supplied its own default for the parameter under scrutiny.
  2. **`CONFIRM_WINDOW_S` was 8.0 s, measured from when the question was *decided*, not heard.**
     The round trip it has to cover is TTS synthesis + playback of the question + the pilot
     hearing, deciding, holding PTT and speaking + Whisper `small.en` (p90 1.46 s) + one 1.0 s
     body poll ≈ 6.5–7.5 s with nothing going wrong. Raised to 15.0 s. Still not measured end to
     end — a sortie should set it.
  3. **A late yes/no escalated to the brain**, which is literally where *"Unable, no such
     command."* came from (`decider.py`'s `NO_SUCH_COMMAND`). That wording says the *command* was
     rejected when in fact the *answer* was late. A yes/no word within `CONFIRM_LATE_ANSWER_
     GRACE_S` (20 s) of expiry now draws "Say again?" instead, which prompts the retry that works.

  `cancel` always routes to the confirm band whatever its match ratio, so this hit every single
  cancel. **Merged to `main` 2026-09-28 (`583d786`) before its acceptance flight, at user
  direction** — the card is flown from `main` now. Leave this open until a sortie confirms
  "cancel" → "confirm" → the task actually stops.
