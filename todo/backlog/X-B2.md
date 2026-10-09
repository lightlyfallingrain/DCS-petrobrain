# X-B2 — `CollectorServer.open()` never resets `_shutting_down`

- [ ] **X-B2 — `CollectorServer.open()` never resets `self._shutting_down` to `False`.** #status/open Latent, not
  live: `__main__.py` opens once and closes once at exit, and no test reuses an instance
  across a cycle, so nothing exercises it today. But if an instance is ever reopened it would
  **permanently swallow real `accept()` failures** — turning the loud-failure guard back into
  the silent death it was built to prevent. One line in `open()`. Flagged non-blocking by the
  reviewer on 2026-09-26; worth taking the next time that file is touched.
