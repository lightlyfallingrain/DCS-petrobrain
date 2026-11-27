---
name: mock-position-gap-silently-changes-regime
description: test_flight_control_lua.py's LoGetSelfData mock never modelled Position -- a new regime-deriving field (lambda, from ground speed) silently read as "hover" everywhere once added, regardless of the mocked IAS
metadata:
  type: feedback
---

While implementing BL-16 LV-3 (`plans/flight-lift-vector/plan.md`), discovered that
`aircraft-layer/tests/test_flight_control_lua.py`'s mock `LoGetSelfData()` returned only
`{ Heading = heading_rad }` -- no `Position` field at all, ever, across ~60 tests. `est_sample`'s
`velocity_source = "position"` path (this harness's own default) differentiates `Position` to get
`v`/`v_g`/`v_g_f`/`v_g_r`; with no `Position`, `pos_valid` is always `false` and those fields never
move off their reset value (0) regardless of the separately-mocked `ias_mps`.

This was invisible until LV-3 added `lambda = law_lambda(est.v_g, profile)` (the hover/forward
blend) -- at that point every test in the file was silently running the law at `lambda = 0` (hover),
no matter what speed the test *thought* it was testing. Four tests with tight numeric assertions
failed outright; the rest likely tolerated the wrong regime by luck of loose assertions, which is
the more worrying half -- a silent regime mismatch a tighter test elsewhere could miss entirely.

**Fix**: made the mock `Position` advance by `ias_mps` along `heading_rad` for real elapsed sim
time, via a `_mock_t` global set by a one-time wrap of `flight_control.run_flight_control` inserted
in `_run`'s own script assembly (not by editing every individual driver's call site). The wrap:
```lua
local _real_run_flight_control = flight_control.run_flight_control
flight_control.run_flight_control = function(t)
    _mock_t = t
    return _real_run_flight_control(t)
end
```

**How to apply**: when a mock DCS harness is missing a field that a *new* derived quantity will
start reading, grep every test file's mock for that field before assuming "no test uses it, so it's
safe" -- a field silently absent from a mock can read as a specific wrong value (here, always
hover) rather than erroring, and only num tests tight enough to notice will fail. If a harness mocks
one channel (IAS) but not a physically-related one (ground-speed-via-Position) that a new feature
now correlates against both, check whether the two mocks are actually consistent with each other.
