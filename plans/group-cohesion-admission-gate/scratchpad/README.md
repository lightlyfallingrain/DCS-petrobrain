# Probes for `plan.md`

Throwaway measurement scripts, kept because the plan's design rests on their output. **Not tests**
and not importable by anything in `src/`.

Run each with cwd inside `body-layer` (no `.venv` exists in an agent worktree, so the main
checkout's interpreter is resolved explicitly):

```sh
cd body-layer
/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
    ../plans/group-cohesion-admission-gate/scratchpad/probe_b58_geometry.py
```

| probe | what it establishes |
|---|---|
| `probe_b58_geometry.py` | Replays the 2C fixture and dumps every pair's gap / backstop / threshold / verdict at t=8, t=12 and t=15. **§1**: the absorbing edge is 81.9 m against an 88.0 m backstop — it already passes — and the corrupted position persists unchanged to t=15. |
| `probe_b58_second_incident.py` | A clean second incident, independent of the 2C fixture. **§2a/§2b**: absorption of a ZSU-23-4 (`air_defence_composition` `[]` → `[('OP_SPAAG', 1)]`) **and** simultaneous eviction of a real infantry member (`BL-B59`). |
| `probe_b58_candidate.py` | The candidate admission gate beside the current rule, six rows, three of them invariant. **§4**: both incidents resolve, rows C/D/E byte-identical. Reimplements only the predicate; every threshold comes from the real module's `Final` constants. |

Geometry note that makes these readable: with `test_callouts._enrichment_context`'s identity
`project_terrain_aware` stub, a contact's fused position is `(ownship_x + 1000, ownship_z)` —
measured, not assumed — so `_observation`'s `ownship_x`/`ownship_z` place contacts exactly, and
`dwp_x`/`dwp_z` keep them from gate-merging.
