---
name: project_effector_sequence_config_files_are_local_not_a_wire_boundary
description: body-layer's config/sequences/<aircraft-dir>/*.md files (effector_sequences.load_sequences) are read once at startup, local-file-only, no network/brain/voice path writes or re-reads them -- not a wire boundary, don't apply isfinite/NaN-boundary-style scrutiny to text parsed from them.
metadata:
  type: project
---

`belief.effector_sequences.load_sequences` has exactly one call site (`body.py`, process startup),
reading `config/sequences/<aircraft-dir>/*.md`. Confirmed on BL-B119 (effector-says,
`plans/effector-says/security.md`) by grepping every reader of `petrovich_says`/
`EffectorRunState.spoken` across `src/`: no network handler, no brain-layer tool
(`tool_api.py`/`brain_client.py`/`brain_reply.py`), no escalation payload, no mission-memory path
touches this data. It is edited only by the user (pilot) themselves, same trust level as any other
project source file.

**Why this matters for future security passes**: this project's recurring real finding is
unguarded `isfinite`/`NaN` conversion *at a wire boundary* (`GET /world_objects/latest` and
similar) — see `project_nan_infinity_int_conversion_at_lan_boundary.md`. The effector-sequence
config files are not that boundary, and treating them as one (demanding bounds/sanitisation
proportional to a LAN-facing endpoint) would be mis-scoped effort. The real checks that *do* apply
here are: (1) confirm no new call site has made the directory reachable from the network (grep
`load_sequences(` on every pass that touches this module), and (2) crash-safety of whatever string
processing runs on the parsed cells (indexing, regex) — ordinary code-quality scrutiny, not a
security-hardening budget.

**If a future change makes `config/sequences/` writable or reloadable from a remote/brain/voice
path**, this memory is stale the moment that lands — re-trace the call graph, don't assume it's
still local-only.

See also [[project_bl_b90_stage4_readback_by_need]] for the companion one-shot-readback design this
module's sibling (`effector_engine`) uses, and [[project_cockpit_write_vocabulary_invariant]] for
the write-side vocabulary constraint this read-side module has no analogue of (it only reads local
config, never writes cockpit state itself).
