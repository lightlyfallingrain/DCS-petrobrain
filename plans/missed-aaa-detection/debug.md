### Debug Report

### Observed Issue

2026-09-28 flight, mountainous region (Syria theatre). The pilot flew close past an insurgent
AAA position, saw it plainly with his own eyes, attacked it, and Petrovich never called it out —
across the whole engagement, not just one look. The pilot's own account of the geometry: the
target was **boresight on an attack run, `scan ahead` commanded** — i.e. dead ahead in azimuth,
diving.

### Investigation base

Checked out `264bba3` (tip of `main` at dispatch time; the group-reporting branch the worktree was
on, `570dccc`, is unrelated to this bug). Working tree clean throughout.

Knowledge graph queried before reading code (`.claude/scripts/gq.sh`, three queries — naked-eye gate
failure in mountains, LOS elevation sampling, and a targeted read of `plans/cockpit-visibility/` and
`plans/world-model-los-generalization/`). No prior debug report covers this specific mechanism.
`plans/world-model-los-generalization/` is a pure refactor (algorithm moved from body-layer into
world-model byte-for-byte, DoD-verified identical) and carries no relevant finding.
`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md` covers a *different* defect from
the same day's log file (noisy singular callouts, not a miss) — noted so it isn't re-attributed here.

### Hypothesis ruled out first (per pilot's own account)

**Cockpit occlusion mask, per-optic FOV, and gaze/scan-ahead azimuth are not the cause.** Confirmed
by reading the mechanism, not just taking the pilot's word for it:

- `perception/geometry.py::body_relative_direction` computes azimuth/elevation from the **airframe's
  own axes** (`heading_true_deg`/`pitch_deg`/`bank_deg` all applied, read from `OwnshipState` — lines
  737-739 of `visibility.py`). A target that is genuinely boresight, on any dive angle, resolves to
  `azimuth_deg≈0, elevation_deg≈0` in body frame by construction — the pitch of the dive is exactly
  what keeps it there.
- `perception/cockpit_mask.py::is_visible`: `depression_deg = -elevation_deg ≈ 0`, well inside the
  co-pilot mask's 22° nose allowance (`_CO_PILOT_MASK`, `az 0-60 → 22°`).
- `perception/gaze.py::within_gaze` is azimuth-only by design (no elevation term at all — "hard part
  3"), and `scan ahead` is a wide-enough wedge that a boresight target is trivially inside it.
- `perception/optics.py::within_optic_fov` is a circular cone about boresight (elevation and azimuth
  combined via the spherical-law-of-cosines separation angle); for a target at `(0,0)` the separation
  is 0° regardless of the optic's half-angle.

So every gate whose job is "is Petrovich looking the right way" passes trivially for this geometry.
That leaves the two gates that don't care about attitude or gaze at all: the angular-radius
size/range threshold, and terrain LOS.

**Angular-radius threshold also does not explain it.** The AAA-family entries in `object_model.py`
(`"zu-23"`/`"zu23"` → `size_m=5.0`, `"shilka"` → `size_m=6.0`) give a presence-tier range threshold
of `size_m / LOWRES_ANGULAR_RADIUS_RAD (0.003) ≈ 1660-2000 m`, far beyond a close attack-run range.
The truth log also shows both types were detected repeatedly on other occasions this session
(`Ural-375 ZU-23` 18 rows, `ZSU-23-4 Shilka` 26 rows) — this is not a type that is systematically
invisible to the size gate.

### Hypothesis confirmed: world-model's elevation grid can place a real, visible unit "underground"

**This is `check_visibility`'s gate 4 (terrain LOS), and it is not gaze- or attitude-dependent — it
is purely a function of the unit's fixed `(x, z)` position in the world-model store.** That property
is exactly what matches "never detected, from a close pass, boresight, in mountains": a permanent,
location-pinned false verdict, not an intermittent one.

**Mechanism.** `world-model/src/query/line_of_sight.py::line_of_sight_clear` samples 19 interior
points (`range(1, samples)`, `samples=20` fixed regardless of range) along the observer→target
ground track, and blocks if any sampled terrain height exceeds the straight-sightline altitude at
that point:

```python
terrain_m = sample_grid(conn, "elevation", sample_x, sample_z)
...
if terrain_m > sightline_alt_m:
    return False
```

`sample_grid` (`store/reader.py`) bilinearly interpolates the **stored** elevation grid — it has no
access to DCS's actual terrain, only to world-model's approximation of it. Two facts about that
approximation, both confirmed by inspecting the live store:

1. **`syria-full.sqlite`'s elevation grid is SRTM-sourced at 1000 m spacing**, not a DCS-native
   probe grid:
   ```
   sqlite> SELECT id, kind, spacing_m, provenance FROM grid;
   1|elevation|1000.0|srtm
   ```
   (per M7's own roadmap entry, this was a deliberate scope decision — "SRTM-primary elevation, not
   a full-grid DCS probe" — not an oversight.)
2. **M7's own theatre-wide validation already measured this grid's error against DCS ground truth**:
   `DCS-probe spot-check vs. SRTM: mean delta -7.19 m, stddev 11.52 m` (`world-model/ROADMAP.md`,
   M7 entry). That is a theatre-wide average; mountainous relief is exactly where SRTM-vs-DCS error
   is largest, not smallest.
3. **`line_of_sight_clear` also never falls back to the finer M8 probe-store grid** the way
   `query/describe.py::describe_position` does (ATTACH + `sample_probe_grid`-before-`sample_grid`,
   `store/reader.py` lines ~535-605). It imports `sample_grid` directly, by design (avoiding
   `describe_position`'s road/settlement joins) — but that also drops the probe-fallback it never
   meant to drop. **Confirmed not to matter for tonight's flight specifically**: no `-probe.sqlite`
   exists for `syria-full` (`ls world-model/data/world-model/` shows none), and `body-layer/src/
   logger.py` has no probe-store wiring at all — so both code paths were reading the same coarse
   base grid regardless. Worth closing later (see Fix options), but it is not what produced tonight's
   miss.

**A real unit's altitude is DCS ground truth** (`WorldObjectCandidate.alt_m`, from
`LoGetWorldObjects`'s `altitude_m` — code owns fact, per invariant). If the SRTM grid at that exact
`(x, z)` reads even a little **higher** than the real terrain the unit is standing on, the straight
sightline arriving at the unit's true altitude will read as passing *below* the model's terrain in
the unit's own neighbourhood — "underground" relative to the model, exactly as the pilot suspected —
and every sample near the target inherits that same wrong reading, for every observer position, at
every range and angle. It is not a per-look coin flip; it is baked into the store at that location.

### Reproduction (offline, no sortie needed)

Built directly against `query.line_of_sight.line_of_sight_clear`, monkeypatching `sample_grid` the
same way the module's own test suite does (`test_query_line_of_sight.py`'s established pattern), so
the mechanism is isolated from real-data noise and the exact error margin that flips the verdict is
visible:

```python
TARGET_X = 10000.0
TARGET_TRUE_ALT = 500.0  # DCS ground truth

def make_sample_grid(margin_m, window_m=500.0):   # window ~= one 1 km grid cell
    def fake(conn, kind, x, z):
        return TARGET_TRUE_ALT + margin_m if abs(x - TARGET_X) < window_m else 0.0
    return fake

# observers: 10 km shallow approach / 2 km diving pass / 1 km close attack pass
```

Result, `margin_m` = how much the model's terrain estimate at the target's own `(x, z)` overstates
DCS ground truth (target itself is always placed at the correct DCS altitude, never moved):

| grid overestimate | 10 km shallow | 2 km dive | 1 km close pass |
|---|---|---|---|
| −2 m / 0 m / +2 m / +5 m | clear | clear | clear |
| **+11.5 m** (M7's own recorded SRTM stddev) | clear | clear | **blocked** |
| +20 m | clear | **blocked** | **blocked** |

The close-range attack-pass geometry flips to a false "blocked" verdict at **exactly the grid error
M7 already measured and accepted as normal for this store** — not an extreme outlier. The far,
shallow-approach geometry stays clear at the same margin because its sightline sits far above local
terrain everywhere along the track; only the close/steep geometry has a small enough margin for a
one-cell error to matter. That is the same shape as "he saw it plainly, from close range, on a dive"
being the exact case that misses, while the same unit might be called out correctly from a longer,
shallower approach — consistent with the AAA types being detected elsewhere in tonight's log at
other ranges/geometries, and never at this one.

### Evidence this is not merely plausible

- Confirmed live-store facts (spacing, provenance, no probe-store override) rather than assumed.
- Confirmed the exact "no probe-store data currently exists" caveat, so the ATTACH-fallback gap,
  while real, is ruled out as *this* flight's cause rather than left ambiguous.
- Reproduced the verdict flip with a synthetic grid at the theatre's own recorded accuracy figure,
  not an invented worst case.
- Ruled out cockpit mask / gaze / optic FOV / angular-radius threshold by reading the mechanism
  against the pilot's own stated geometry (boresight, scan ahead), not by assumption.

### What the evidence cannot settle

- **Whether this exact mechanism, at this exact location, is what happened tonight.** No
  `--detection-trace` was enabled on this flight (confirmed against the working tree's
  `run-scripts/run-crew-text.sh` / `run-crew-text-debug-view.sh` — neither passes the flag), and
  `~/dcs-belief-truth.jsonl` structurally cannot show a rejected candidate (`write_poll` only emits
  rows for `GateOutcome.ADMITTED` entries joined to a live contact). Absence from that log is not
  evidence either way.
- Residual, lower-probability alternatives not excluded by anything above: the unit never arriving
  from `LoGetWorldObjects` at all, and `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` (5) starving admission in
  a dense scene. Both are unfalsifiable without a trace; both are also weaker fits to "boresight,
  close, mountainous, permanent" than the terrain-LOS mechanism above.

### Re-fly recipe to settle it definitively

Add `--detection-trace <path>.jsonl` to the run-crew-text invocation (BL-9; `logger.py`'s
`_build_sources`/`_run_crew_text_poll_loop` already wire it, additive, no other behaviour change) on
the next sortie, and fly a similar close, boresight attack pass on a known AAA position. Then check
`DetectionTraceCollector`'s records for that object id at the miss:

- **Terrain-LOS hypothesis confirmed** if the deciding gate for every rejected candidate at that
  position is the LOS gate, at every recorded range/angle for that id — i.e. it never once passes,
  regardless of geometry. Cross-check with `sample_grid(conn, "elevation", x, z)` read directly
  against the unit's real `(x, z)` from that position's briefing/mission data, compared to its known
  DCS altitude — a positive difference confirms the mechanism directly, no inference needed.
- **Ruled out in favour of something else** if the trace shows the candidate passing gate 4
  (terrain LOS clear) and being rejected by a different gate instead, or never appearing as a
  candidate at all (points at `LoGetWorldObjects`/intake instead).

This is a single targeted sortie, not a rebuild — it can ride along with an already-planned flight.

### Fix options (not applied — architectural decision, per Debugger's own escalation rule)

This is a genuine, reproduced defect, but every fix trades directly against the no-omniscience
invariant: loosening the terrain-LOS check anywhere also loosens it for units genuinely masked by a
real ridge at similar margins. Laid out for Architect rather than picked silently:

1. **Global tolerance on the terrain check** (`terrain_m > sightline_alt_m + TOLERANCE_M`), sized to
   the grid's own recorded error budget (~12-15 m for SRTM per M7's stddev). Cheapest, matches this
   project's "absence of data is not evidence" posture extended to *imprecise* data — but it is a
   single constant applied everywhere, including where the grid is actually accurate, so it also
   unmasks some genuinely-hidden targets at small margins.
2. **Exclude a short final stretch of the track nearest the target** from the terrain check (the
   last sample is already excluded; widen that exclusion to roughly one grid cell). Cheaper to reason
   about than a global tolerance, but changes behaviour only near the target, not along a ridge
   genuinely between observer and target that this mechanism would still get wrong the same way.
3. **Wire the M8 probe-store ATTACH fallback into `line_of_sight_clear`**, mirroring
   `describe_position`'s existing pattern. Does not fix tonight's case (no probe data exists yet for
   Syria, and `logger.py` has no live probe-population channel — M8 is explicitly "deferred to
   Runtime" per its own roadmap entry) but closes a real, unrelated gap: once a probe store exists
   for a theatre, this gate should see it exactly as `describe_position` already does. Smallest,
   most mechanical option; does not address the SRTM-baseline accuracy problem by itself.
4. **Per-cell uncertainty-aware LOS** — propagate `grid.provenance` (and a per-cell error estimate,
   which the schema does not currently store) into the check, blocking only when terrain exceeds the
   sightline by more than that cell's own recorded uncertainty. Most correct, most aligned with this
   project's provenance/uncertainty invariant, but needs a schema addition (no per-cell error field
   exists today) and is real design work, not a patch.
5. **Denser/more accurate elevation for mountainous theatres** — the actual root-cause fix at the
   data layer, already the direction recorded for future world-model work (a full-grid DCS probe or
   synced external DEM, not the current sparse SRTM store). A build-pipeline project, not a code
   change; out of scope for this pass.

None of these were applied. Recommend Architect pick from 1-4 for a near-term mitigation (1 and 3
are independent and could both land cheaply; 2 is redundant with 1 if 1 is chosen), with 5 tracked as
the standing follow-up it already is.

### Verification

No source files were changed — this pass produced a diagnosis and a reproduction script (run
ad hoc, not committed as code), not a fix, per the escalation rule ("if the fix requires
architectural change, stop and escalate to the Architect") and the coordinator's explicit direction
to lay out options rather than pick one. `world-model`'s and `body-layer`'s test suites were not
re-run because nothing in either subproject was modified.
