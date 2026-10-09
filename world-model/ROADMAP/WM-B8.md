# WM-B8 — A fixture-scale fine elevation grid for offline LOS tests

- [ ] **WM-B8 — A fixture-scale fine elevation grid for offline LOS tests. LOW PRIORITY.** #status/open
  User direction, 2026-10-05, replacing [[WM-B7]]: *"If we build a fine grid for a very small area,
  we can use that for test scenarios."* **Unblocked 2026-10-05, [[X-B29]] DoD gate**: [[WM-B7]]'s "do
  not start before [[X-B29]] lands" gate is cleared now that `feature/dcs-driven-los` has passed DoD
  on fixtures (merge still pending, which does not block starting this). Still low priority in
  ordering, not in importance.

  **Note the inversion** — [[WM-B7]] was coarse-everywhere; this is **fine-but-tiny**. The offline
  LOS primitive is no longer trying to stand in for DCS over a theatre. It serves fixtures, so it
  needs to be *small, fine and deterministic*, and agreement with what DCS would say is an explicit
  **non-goal** (see `plans/dcs-driven-los/plan.md` §3): the two answer different questions.

  Open: how small an area, what resolution, and whether it is generated into the test fixtures or
  built once and committed. The [[WM-B7]] entry above carries design questions that transfer —
  particularly what it reports where there are no landform control points at all, which must be
  "unknown" rather than an invented height.
