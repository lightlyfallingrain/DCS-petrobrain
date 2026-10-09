# BL-W22 — Cones slice 2C — the o'clock scan loop

- [x] **Cones slice 2C — the o'clock scan loop. DONE, merged 2026-09-22** #status/done (`4f89fc8`). The
  default gaze stops being "everywhere" and becomes a scan: 12, then 11/10/9, then 12 again, then
  1/2/3 — 30° cones, two seconds each, a 16-second cycle that covers the forward arc twice. The
  numbers are the user's (*"scan per o'clock cone"*, 2 s per sector), not fitted.

  **`gaze_at(t_sim, plan)` is a pure function of sim time**, so replay determinism falls out of
  purity rather than being managed — nothing holds a scan phase that could drift from the clock.
  Two consequences followed rather than being designed: `decay.OBSERVED_WINDOW_S` moved 5.0 → 16.0,
  derived from the cycle and bounded on both sides, and acquisition state became time-based,
  because poll-indexed sets break the moment the cone moves.

  **Two fixes rode in from the sortie that followed, and both came from the pilot flying it.**

  - **The overlay now names the cone he is looking at.** Two of the test card's four blocks were
    unevaluable without it — *"very difficult to judge when I don't visually see where Petrovich is
    looking"*. A perception model that steers attention is invisible from the cockpit unless it
    says where it is pointed.
  - **Scan and Watch became standing modes rather than one-shot tasks.** `tasks.py` marked a task
    succeeded on first contact and `_active_gaze` honoured only pending tasks, so a commanded scan
    silently reverted to free scan the moment it found anything — which is why *"scan left"* still
    produced 12 o'clock reports. The same assumption sat in three places, so fixing only
    `_active_gaze` would have left cancel hollow.

  **Left open at merge and closed afterwards:** `watch_nearest` created no `PendingIntent` at all,
  so `Cancel Task` had nothing to find regardless of the above. Fixed in `32346a0` (watch as a
  standing mode), where cancel now ends every governing kind and names each.

