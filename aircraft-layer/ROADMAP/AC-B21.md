# AC-B21 — `_FLIGHT_CONTROL_LIMITS_BOUNDS` silently drops unknown `limits` keys

- [ ] **`_FLIGHT_CONTROL_LIMITS_BOUNDS` silently drops unknown `limits` keys.** #status/open Filed 2026-11-18 at the BL-16 mode 1 M1+M2 merge. From `plans/flight-control/review-m2.md` (point 4): the `POST /command/flight_control` handler iterates a whitelist and drops any key not in it without error, so a new body-layer limit never reaches Lua until the whitelist is updated — all 8 M2 keys were nearly lost this way. Reject unknown keys (400) or log them loudly.
