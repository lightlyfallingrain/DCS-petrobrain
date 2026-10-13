# Probes for `plan.md` (BL-B59)

Throwaway measurement scripts, kept because the plan's design rests on their output. **Not
tests** and not importable by anything in `src/`.

Run each with cwd inside `body-layer` (no `.venv` exists in an agent worktree, so the main
checkout's interpreter is resolved explicitly):

```sh
cd body-layer
/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
    ../plans/group-retention-hysteresis/scratchpad/probe_b59_trace.py
```

| probe | what it establishes |
|---|---|
| `probe_b59_axes.py` | **Which observation axis drives what.** `ownship_x` drives `Contact.position` (identity `project_terrain_aware`: `position.x = ownship_x + 1000`); `dwp_x`/`dwp_z` drive gate matching **only** and do not move the fused position — so `test_callouts._observation`'s own docstring claim that dwp drives `last_position` is **stale**. Also shows two tracks 200 m apart found a new contact every tick in this harness, because each percept has ≥2 passing gate candidates at the 300 m fallback uncertainty. Written because probe 3's first draft was invalidated by exactly this. |
| `probe_b59_mechanism.py` | **§2a** — decomposes the eviction into its two terms: the relative threshold tightens 13.6 % (195.6 → 169.0 m) while the `CONTACT_1–CONTACT_2` gap grows 170 % (72.1 → 194.6 m), with `fold_displacement_m` = 132.7 / 143.3 m on the two folded-onto contacts. The fold's displacement is the major cause; the threshold shift is the minor one, reversing `BL-B59`'s own framing. **Its `co=` column for the post-fold snapshot is circular** (it reads the roster *after* reconcile already evicted) — kept as written, because that circularity is what exposed the eviction's latching behaviour. |
| `probe_b59_candidates.py` | Runs the real pipeline with each candidate monkeypatched into `groups._cluster_contacts` (which `reconcile` calls by module-global name, so rebinding swaps the mechanism for real). **All four candidates fix the incident**, which is why the incident alone cannot choose between them. |
| `probe_b59_discriminate.py` | The first attempt at discriminating cases. **Both D2 and D3 are degenerate** and are kept only so the next reader does not repeat them: D2 founds a new contact every tick (the axes problem above), and D3's random scenes are so sparse that the backstop always binds, so the relative term — the only term in question — is never exercised. D1 is sound for its first 18 ticks and shows the fold-budget discount byte-identical to baseline on a genuine departure. |
| `probe_b59_lifetime.py` | **§2c, §2e, §2f** — 60 ticks past the fold. The unbounded fold-budget discount gives **0 membership transitions**; `watch-reporting` §4e's 1.5× factor **loses the member again at t=25**. And the decisive one: `fold_displacement_m` **never retires** in this geometry, growing 132.7 → 239.0 m (C3: 259.8 m), because every re-observation in a scene dense enough for the relative term to bind is itself ambiguous and folds again. That is a measurement about **merged Stage 3.5 code**, whose own Risks section had recorded `+=` as an untested assumption. |
| `probe_b59_bounded.py` | **§2e** — rules out covariance as a retiring bound: `position.radius_m()` floors at **120.0 m** and never drops below it, so `min(fold, radius_m())` is insufficient and evicts at t=30 (11 transitions). |
| `probe_b59_recommended.py` | **§2d** — sweeps the bound as a fraction `f` of the pair threshold. `f ≤ 0.1` does not fix the fold tick at all; `f ≥ 0.2` does. |
| `probe_b59_trace.py` | **§2d's decisive table** — traces `CONTACT_1`'s group for 60 ticks per bound. `f = 0.25 / 0.5 / 1.0` all clear the fold tick and all **lose the member at t=25**; only the unbounded discount holds 60/60. This is why the sweep is not a calibration curve with a good value in it, and why the whole bounded-factor family is ruled out. |

Geometry note that makes these readable, carried over from
`plans/group-cohesion-admission-gate/scratchpad/README.md` and re-confirmed by
`probe_b59_axes.py`: with `test_callouts._enrichment_context`'s identity
`project_terrain_aware` stub, a contact's fused position is `(ownship_x + 1000, ownship_z)`,
so `_observation`'s `ownship_x`/`ownship_z` place contacts exactly, and `dwp_x`/`dwp_z` keep
them from gate-merging.
