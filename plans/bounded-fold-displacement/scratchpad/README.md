# Probes for `plan.md` (BL-B58 option 2)

Throwaway measurement scripts, kept because the plan's design rests on their output. **Not tests**
and not importable by anything in `src/`. Each installs the proposed bound by monkeypatching
`ContactStore._fold_target_for_ambiguous_candidates` (to record which contact is about to be the
fold target) and `Contact.record` (to clamp immediately after), which is exactly `ingest`'s own
fold branch and nothing else. **The probes assign `contact.position` directly; merged code must
not** — see `plan.md` §1 on why the real seam is `Contact.record`.

Run each with cwd inside `body-layer` (no `.venv` exists in an agent worktree):

```sh
cd body-layer
/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python \
    ../plans/bounded-fold-displacement/scratchpad/probe_o2_bound.py
```

| probe | what it establishes |
|---|---|
| `probe_o2_bound.py` | **§2a** — every candidate bound against the incident, with residual position error against truth. Rules out the `group_matches` test-5 slack analogue (**552.1 m bound, a no-op**) and the whole `radius_m()` family (prior radius is **300 m** at the fold, not the 120 m floor the previous pass measured). Settles the clamped remainder's covariance by measurement: accepting the fuse's covariance gives **0 transitions / 160 m**, holding the prior's gives **10 / 208 m**, because holding keeps `fused_at_sim` back and so *grows* the next fold's bound. |
| `probe_o2_accuracy.py` | **§3, §4** — scores the incident against **all six real units**, not the four with contacts. k=1 takes the held positions from 72–95 m to **40 m (2.29° at 1 km, inside the channel's own 3.0° bearing σ)**; and shows **two real units have no record at all**, before or after, which no bound can fix. Also measures `B6`, "found instead of fold" (reverses `D5` at contact grain): per-unit error 0.0 m, **18 contacts for 6 units**. |
| `probe_o2_motion.py` | **§2b, the discriminator** — two contacts genuinely translating, every look ambiguous. `speed × elapsed` is **byte-identical to baseline** at the class speed (12.5 m at t=40), which is the property that makes it safe to apply to every fold. A **zero** bound *freezes* (80 m and growing), so `probe_o2_accuracy`'s perfect 0.0 m for bound-0 is an artifact of a scene whose truth is that nothing moved. At 4× the class speed the bound is **worse than baseline** (104.2 vs 49.8 m) — the plan's one measured regression. `B6` reaches **82 contacts for 2 real units**. |
| `probe_o2_stage35.py` | **§2d, §5** — re-measures Stage 3.5's row B with the admission term neutralised, so "is the gate still load-bearing?" is answered by comparison rather than argument. At **k=1 and k=2 the gate is a no-op**; at **k=3 it is load-bearing again** (the absorbing edge returns to 75.5 m against its 78.0 m backstop), which is why the gate stays as the safety net for an uncalibrated speed table. |
| `probe_o2_motion_keyed.py` | **§6** — the user's 2026-10-13 motion-keyed direction, assessed not designed. The incident's `Contact.motion` is **`None`** (the fixture's default), so a motion-keyed rate leaves every number in the plan unchanged. Refutes both hypotheses sent with the direction: at **0.0 m/s growth the fresh percepts still have 3 passing gate candidates** (the gate is dominated by the 300 m declared-uncertainty fallback, so removing a 40 m inflation term un-ambiguates nothing), and **`BL-B24`'s 17 m pair still passes both gates** at 0.0 m/s. |
| `clamp_plugin.py` | **§5** — a pytest plugin that installs the bound for a whole suite run, so `src/` stays untouched. `PB_CLAMP_K=off` is the control (**1697 passed / 4 xfailed**); `PB_CLAMP_K=1.0` and `2.0` both give **1 failed / 1696 passed**, the one failure being Stage 3.5's provenance test whose fold is entirely at `t_sim=0.0` (elapsed 0 ⇒ bound 0). Both pinned invariants — the eager-cap chaining test and the 2C fixture — pass unchanged. |

Geometry note carried over from `plans/group-retention-hysteresis/scratchpad/README.md`: with
`test_callouts._enrichment_context`'s identity `project_terrain_aware` stub a contact's fused
position is `(ownship_x + 1000, ownship_z)`, so `_observation`'s `ownship_x`/`ownship_z` place
contacts exactly and `dwp_x`/`dwp_z` keep them from gate-merging.

**One trap, met and recorded:** `probe_o2_motion_keyed.py` holds the infantry observed for six
extra ticks so a `False` motion claim can confirm past `MOTION_STOP_CONFIRM_S = 5.0`. That
shortens the unobserved interval from 20 s to 14 s and so shrinks the fold to 39.3/42.4 m **and
removes the eviction entirely**. Its rosters are therefore *not* the incident's, and its numbers
must not be quoted as the canonical 132.7 m. It measures the motion questions only.
