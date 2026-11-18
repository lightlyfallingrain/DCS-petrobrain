# AC-B20 — `arm_lease_s` 10 s ceiling is declared in three places with no parity test

- [ ] **`arm_lease_s` 10 s ceiling is declared in three places with no parity test.** #status/open Filed 2026-11-18 at the BL-16 mode 1 M1+M2 merge. From the BL-16 M1+M2 change-request round (`plans/flight-control/review-cr-m1-m2.md`, DoD): `Export.lua` `FC_LIMIT_BOUNDS`, aircraft-layer `_FLIGHT_CONTROL_LIMITS_BOUNDS`, and body-layer `ARM_LEASE_S`'s tuning `hi` all say 10.0. Add a parity test like `test_export_lua_constants_parity.py`, or one source of truth.
