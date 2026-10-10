# BL-B54 — `report six o'clock` answers about eight o'clock

- [ ] **BL-B54 — `report six o'clock` resolves to `report_clock_8`**, on [[BL-13]]'s tip and on its base
  alike. #status/open Found by DoD during BL-13, 2026-10-10, measured on the shipped matcher.

  **This is the same silent-wrong-direction shape as `BL-B28`**, which [[BL-13]] Stage 1 was built to
  close — `report left` matching *report east* at 0.75. That one was closed for the left/right axis;
  hours **5, 6 and 7** were not, because the clock slot covers only the nine forward hours (1–4,
  8–12) and a rear hour fuzzy-matches to the nearest supported one instead of being rejected.

  **Why it matters more than a missing hour.** A rejected command earns a *"say again"* and the pilot
  asks again. A command that silently answers about a different direction gets believed — and the
  rear hemisphere is exactly where a pilot asks because he cannot look himself.

  There are two defensible answers and they are not the same:

  - **Reject it**, as the two-*where*-slots case already does (`token=None`, `verb_anchored=True`),
    earning a "say again".
  - **Answer it**, since `render_no_view` already exists for the rear hemisphere and says he has not
    looked there — arguably the more useful reply, and the honest one.

  The second is probably right and is a small design question rather than a bug fix, which is why
  this is filed rather than patched. Note that `render_no_view` already fires today for a
  rear-hemisphere `sector`, so the machinery for the honest answer exists; what is missing is the
  parse admitting hours 5–7 at all.

  Pairs with [[BL-B52]] and [[BL-B53]] — all three are silent-drop or silent-substitution findings
  from the same probing pass, and one round over the slot parser could take them together.
