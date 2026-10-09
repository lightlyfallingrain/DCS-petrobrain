# X-T6 — Crossings are announced for contacts he cannot see

- [~] **Crossings are announced for contacts he cannot see.** #status/in-progress *"Crossings say which way -> yes, but
  also says it for contacts outside FOV also contacts masked by cockpit."* This is a
  **no-omniscience violation**, the project's core invariant, not a wording bug: the direction-of-
  crossing callout fires off belief state without re-checking that the contact is currently visible
  (in FOV and not cockpit-masked). Highest priority of the four. **Fix merged (`fix/sortie-2026-
  09-26`, Fix A) — an observability gate with a grace window, DoD PASSED on fixtures/console.
  Awaiting the sortie that clears it**, tracked on `body-layer/ROADMAP.md`'s live-acceptance-debt
  list; leave this checkbox open until that flight confirms it.
