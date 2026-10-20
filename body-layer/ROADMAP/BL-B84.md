# BL-B84 — 9K113 search depth adapts to terrain

- [>] **BL-B84 — With `observ on`, the sight's search could concentrate on the near band when
  terrain in the search direction closes the far band.** #status/deferred User, 2026-10-20
  (`docs/acceptance/2026-10-20-sortie-feedback.md`, F4/F5 "as needed" settled): *"B would be a
  natural consequence of angles. Wherever the 9K113 happens to be pointing, if terrain blocks
  there's no LOS. However if there's something nearside on that terrain it can be seen. B can be
  left till later."*

  Perception already behaves this way look by look: live LOS rejects whatever is behind terrain,
  and a nearside unit stays visible. What is deferred is only the *search pattern* choosing its
  depth from terrain. Mind the 2026-10-05 direction that world-model's offline LOS is testing-only
  (`docs/acceptance/2026-10-05-sortie-feedback.md`): any terrain input here must not become an
  offline LOS verdict in the live path. Sibling: weather/light in `[[BL-B22]]`'s "Detection under
  real world conditions" section.
