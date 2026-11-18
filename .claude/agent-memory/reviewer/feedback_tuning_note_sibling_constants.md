---
name: tuning-note-sibling-constants
description: When a Lua file already has the "no tuning.py outside body-layer" note on one constant, check every new sibling constant in the same diff for the same note -- it gets added inconsistently.
metadata:
  type: feedback
---

On BL-16 mode 1's M0-J capture-fix round (`fb9df20f`, `plans/flight-control/review-m1b.md`),
`flight_control.lua` already carried the correct "outside body-layer the loader does not exist --
would want the X-T26 mechanism if one existed here" note on `FLIGHT_WOBBLE`. The same round added
two new behaviour-affecting constants a few lines below it (`STOWED_THRESHOLD`,
`LIVE_SEAT_ZERO_EPS`) with thorough mechanism comments but **no tuning note at all** -- an easy
miss because each constant's own comment reads complete on its own (cites the measured flight,
explains the threshold choice) and nothing about it screams "missing".

**Why:** the tuning-mechanism check (reviewer.md's "Verifying the tuning pattern") is phrased
around `body-layer/config/defaults.toml`, which makes it easy to treat as a body-layer-only check
and skip entirely when reviewing aircraft-layer/other-subproject Lua or Python. The rule explicitly
also applies outside body-layer, just with a different required artifact (a note, not a loader
entry) -- and the fastest way to catch a missing one is to grep the *same file* for whether this
convention already exists on an older constant, then diff that against every constant the current
round adds.

**How to apply:** whenever a diff adds a new module-level constant anywhere outside
`body-layer/src/tuning.py`'s own tree, first check whether that file already has at least one
constant carrying the "no tuning.py-equivalent loader... would want the mechanism" note (grep the
file for "tuning.py-equivalent" or similar). If it does, every new behaviour-affecting constant in
the same diff needs the same note or an explicit, stated reason it does not apply (e.g. "not
behaviour-affecting, kept as a plain local" -- this file's own `ENV_IAS_MARGIN_KMH` et al. show
that pattern too). Treat the file's own existing convention as the baseline to hold new siblings to,
not just the general checklist item in the abstract.
