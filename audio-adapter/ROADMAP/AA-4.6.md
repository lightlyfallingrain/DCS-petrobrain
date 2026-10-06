# AA-4.6 — The ~0.14 s device-open gap — CLOSED

- [x] **The ~0.14 s device-open gap — CLOSED 2026-09-23, not felt, nothing built.** #status/done The sortie
  answered it: press-then-speak *"is the natural, normal way how aviation radios work"*, and
  press-while-speaking *"works surprisingly well"* — the verb survives. So none of the three
  candidate fixes gets built, and the measurement's whole purpose is served: it stopped a fix
  being paid for before there was evidence it was needed.

  The options are kept below rather than deleted, because the gap is real and a different
  microphone or a slower machine could make it matter. **Do not build any of them without a
  fresh observation that it is felt.**

  **A. Open the device speculatively, on any press.** Start recording the moment arg 738 leaves
  0.0, and discard the clip if the trigger never settles at the intercom stop. **This is the
  strongest of the three, and for a reason that is easy to miss: it makes the 100 ms debounce
  free.** Today the two delays *add* — 100 ms of debounce, then ~140 ms of device open, so ~240 ms
  before a word can be captured. Opened speculatively they *overlap*: the device is warming during
  the debounce window, and by the time the trigger is confirmed as intercom the channel is already
  live. The saving is therefore larger than the 0.14 s figure suggests.

  Costs, both real: a sox process is spawned and killed on **every radio call** as well, so a
  device open/close cycle per ATC transmission — worth listening for an audible artefact on the
  user's own hardware, since a device that clicks on open would be trading one annoyance for
  another. And it needs a second signal out of `DcsPTT`: the capture loop currently sees only
  `is_down()`, which is the *decided* state; speculative opening needs "something is happening",
  which means exposing the raw value or adding a `pending()` alongside it.

  **B. A radio click as the cue.** A short click played on the press, timed so that **it ends as
  the channel goes live**. It does not remove the delay, it removes the *uncertainty* — and it
  teaches the press-then-speak gesture rather than asking the pilot to remember it, which is a
  better solution to a human problem than a faster machine would be. Cheap, and in-fiction: real
  PTT systems click.

  The timing property is load-bearing rather than decorative: a click that ends exactly when
  capture starts cannot be recorded by the capture, so it needs no special handling in the gate.
  A click that overlapped would appear at the front of every clip and be handed to whisper.

  **A and B compose**, and the combination is better than either: with the device opened
  speculatively the click can be shorter, because it only has to cover what remains.

  **C. A permanently hot microphone** with the pressed interval trimmed out of a rolling
  recording. Removes the gap completely and costs continuous capture, continuous disk writes and
  file rotation. Listed last deliberately: it is the most thorough and the least proportionate,
  and A gets most of its benefit for none of its running cost.

  **The gate is block 3 of the voice sortie** (`docs/acceptance/2026-09-23-voice-command-sortie.md`):
  press-then-speak versus speaking into the press. If the gap is not felt, none of these gets
  built.
