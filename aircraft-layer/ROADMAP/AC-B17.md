# AC-B17 — `law_update` copies the whole ~25-key law state with `pairs()` every active frame

- [ ] **`law_update` copies the whole ~25-key law state with `pairs()` every active frame.** #status/open Filed 2026-11-18 at the BL-16 mode 1 M1+M2 merge. Perf MONITOR from `plans/flight-control/perf-m1-m2.md` (BL-16 mode 1 M1+M2): one table allocation per active frame in `flight_control.lua`. No measured symptom; fix when next touched with an explicit field-by-field return (`law_init_at_take`'s style). Escalate only on a live stutter/jitter report.
