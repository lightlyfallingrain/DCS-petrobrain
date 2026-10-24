# BL-B9 — F10 Watch Nearest reply in contact-report format

- [x] **BL-B9 — F10 Watch Nearest reply in contact-report format — done, merged 2026-09-13 (merge
  `a4e8704`, `fix/f10-watch-nearest-readback`).** #status/done Live
  2026-09-13 it replied "Watching CONTACT_1."; now `"Watching <unit type>, <clock> o'clock, <range>
  km[ <semantic fact>]."` via `speech.render_watch_nearest_readback` / `_contact_report_text`, no
  spoken id. Typed `watch <id>` readback unchanged.

**Obsolete note, 2026-10-24 (`BL-B96`, `plans/default-crew-pipeline/plan.md`):** the F10 transport
that triggered this readback was removed entirely. The readback format itself
(`render_watch_nearest_readback`/`_contact_report_text`) and the typed/voice `watch <id>` path it
describes are unaffected -- only the F10 menu's own "Watch Nearest" entry point is gone. This entry
stays `[x]` done and its ID is not reused, per root `CLAUDE.md`'s "Numbers are never reused" rule;
it records what was true and merged on 2026-09-13.
