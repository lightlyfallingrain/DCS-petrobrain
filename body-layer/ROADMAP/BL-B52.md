# BL-B52 — The wake word strips the slots off a `report` command

- [ ] **BL-B52 — `Petrovich, report left` matches the `report` token with `slots=None`, so the filter is
  silently lost and he answers about the whole scene.** #status/open Found by DoD during [[BL-13]],
  2026-10-10, by running the shipped matcher rather than reading it — no review document held this.

  The command still works; what is lost is the **narrowing**. To the pilot that reads as *"left was
  ignored"*, which is worse than a `say_again`: he gets a plausible answer to a question he did not
  ask, and nothing signals that a word was dropped.

  **Why this is newly worth an entry.** Before [[BL-13]] the wake word prefix cost a whole command,
  which fails loudly. Now it costs a *filter*, which fails quietly — and BL-13's whole product
  argument is that short, narrow questions are the point. The prefix is also the natural thing to say
  to a crewman.

  Fix shape: strip a leading wake word (and its comma) before the verb branch runs, where the verb
  anchoring already happens. Belongs with [[BL-B53]] and [[BL-B54]], which are the other two
  silent-drop findings from the same ten minutes of probing — one round over the slot parser could
  take all three.
