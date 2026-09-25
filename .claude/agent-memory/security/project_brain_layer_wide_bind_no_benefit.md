---
name: project_brain_layer_wide_bind_no_benefit
description: brain-layer's run script binds 0.0.0.0 though both ends of that seam are same-box; server.py's own default is loopback
metadata:
  type: project
---

BR-1 Stage 1 (`feature/brain-layer`, reviewed 2026-09-25): `brain-layer/src/server.py` sets
`DEFAULT_HOST = "127.0.0.1"` with a docstring explaining why (brain-layer and Ollama both run on
the Mac; only aircraft-layer↔body-layer genuinely crosses the LAN to Windows, per root `CLAUDE.md`'s
compute-topology memory). `run-scripts/run-brain.sh` nonetheless passes `--host 0.0.0.0`
unconditionally, with no comment recording why the default was overridden.

**Why:** a wide bind on a same-box seam has no offsetting benefit and is exactly the kind of
low-probability/low-impact-but-free-to-fix exposure this role should flag rather than wave through
just because it doesn't rise to "block DoD." Reported to the user as a non-blocking recommended fix
rather than silently accepted or silently ignored.

**How to apply:** next brain-layer security pass (Stage 2/3), check whether `--host 0.0.0.0` was
removed or whether an actual LAN topology reason has since appeared and been documented — don't
re-litigate from scratch, just confirm the state. If a *future* subsystem genuinely needs
brain-layer reachable from another box, that's a real reason and the fix here should be "gate wide
bind behind an explicit flag," not "never allow it."

See also [[project_wire_boundary_type_check_not_range_check]] for a related class of gap
(type-checked but not further validated) that this pass re-confirmed is *not* present here —
`brain_client.py`'s `_reply_from_dict` type-checks reply fields, and the two call sites that act on
`contact_id`/`token` (`crew_console._handle_brain_pick`/`_handle_brain_confirm`) independently
re-validate against live state/an allowlist before acting, which is sufficient defense in depth for
Stage 1 (the far end is still trusted `StubDecider` code; D10's full semantic validator is correctly
deferred to Stage 2).
