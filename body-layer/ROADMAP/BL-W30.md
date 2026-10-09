# BL-W30 — Radio brevity, and cancel became three commands

- [x] **Radio brevity, and cancel became three commands — 2026-09-23** #status/done (`fix/spoken-vocabulary`,
  user direction from the five-fix transcript).

  **Articles dropped.** *"a couple of contacts"* → *"couple contacts"*, *"Scanning to the left"* →
  *"Scanning left"*, *"Copy, stopping the scan to the left and the watch"* → *"Copy, stop scan left
  and watch"*. The user's reason is the right one and worth keeping: an article carries no
  information in a report and still spends a slice of a channel one person can occupy at a time.

  **An identification line now opens with the contact's class.** *"unit at 11 o'clock, very close
  is BTR-70"* → *"armor 11 o'clock, very close is BTR-70"*: it says what the pilot is being asked
  to look at before it says what it turned out to be. Two guards fell out of trying it — a type
  whose profile lands on the object model's default class (`BM-30`, `SA-10 Flap Lid radar`) keeps
  *"unit"* rather than opening with *"group"*, which reads as a formation; and a lead that would
  repeat the payload (*"truck … is truck"*) falls back to *"unit"*, because that is a stutter
  rather than a report.

  **Cancel is three commands now, reversing this console's own decision from two days earlier.**
  The old reasoning was sound given what existed: there was no vocabulary to say "cancel the watch"
  as opposed to the scan, so cancelling everything and naming each thing stopped beat guessing. The
  user's answer after flying it was to supply the missing vocabulary instead — *"stop watching
  \<unit\>"* and *"stop scan"* are separate actions, and **one cancel must not end the other
  mode**. Scanning while watching a contact is ordinary, and the old reading made it inexpressible.
  `cancel_scan` and `cancel_watch` are narrow; `cancel_task` stays as the explicit all-modes form
  and still names both. The F10 menu grew a `Stop` submenu with all three.

  **Voice caught up the same day** (user, 2026-09-23: *"voice command 'cancel task <task>' should
  work 'cancel <task>'"*). `cancel_scan`/`cancel_watch` are spoken as *"cancel scan"* / *"stop
  scan"* / *"stop scanning"* and their watch equivalents.

  The hesitation had been that these phrasings are **unbenched** — `audio-adapter`'s 99.2% figure
  was measured on a recorded corpus containing no examples of them — and that is still true. The
  user's answer is the right one: a menu-only way to say something the pilot is already saying out
  loud is the wrong side of that trade. The tests prove the phrasings are unambiguous against the
  rest of the vocabulary, which is a different claim from proving whisper hears them; the next
  corpus recording should include them.

  Two decisions inside it:
  - **A bare *"cancel"* stays the all-modes form.** It cannot name which mode it means, and
    guessing is exactly what the narrow tokens were introduced to stop.
  - **`stop scan` does not collide with `stop`** (which silences him), because that rule counts
    only when the single word is the entire transmission — settled in Stage 2 for an unrelated
    reason, and it carries this case for free.
  - **`ACT_FLOOR_CANCEL` now keys on a `CANCEL_TOKENS` set** rather than one name. A mis-heard
    *"stop watch"* destroys standing state exactly as a mis-heard *"cancel task"* does, and the
    narrow tokens would otherwise have inherited the ordinary floor silently.

