# AC-B2 — Regenerate the command-surface reference with a raw-table parser

- [ ] **AC-B2 — Regenerate `research/mi24p-command-surface.md` with a parser that handles raw table
  literals.** #status/open Found 2026-09-20 on the Windows box: the dump enumerates the
  `default_2_position_tumb(…)`-style helper forms only, so **13 of `clickabledata.lua`'s 749
  elements are missing** — and the missing set is biased, because a control needs the raw form
  precisely when it has more than one action. Both push-to-talk triggers (args 738 and 856), both
  collectives, the ASP-17V sight reflector handle and the PKI control are all absent. This is what
  made arg 738 look untraceable in `2026-09-19-ptt-gate-feasibility.md` when it was sitting in the
  source file all along. The 13 are now listed by hand in a warning box at the top of that
  reference, which stops the gap misleading a reader but does not survive the next DCS update —
  the generator is the real fix. Full detail:
  `research/2026-09-20-dcs-install-detection-deep-read.md` finding 11.
