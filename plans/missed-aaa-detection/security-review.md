## Security Deep Analysis: fix/los-elevation-tolerance

### Dependency Status
No dependency change.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `world-model/src/query/line_of_sight.py:139` | Sole comparison changed from `terrain_m > sightline_alt_m` to `terrain_m > sightline_alt_m + _TERRAIN_TOLERANCE_M` | This is the entire diff's behavioral change. `_TERRAIN_TOLERANCE_M` is a private module constant with no parameter to override it and no second code path — it applies only to this one comparison, in this one function, which has exactly one caller (`body-layer/perception/geometry.line_of_sight_clear`, an unchanged thin wrapper). It does not bypass the gate, does not leak into any other check, and is not reachable from any other call site. Implements the accepted omniscience trade exactly as decided — no more, no less. | None |
| `world-model/tests/test_query_line_of_sight.py` (two boundary tests, 11.9/12.1) | Boundary pin | Both tests use equal observer/target altitude, making `sightline_alt_m` constant across every sample — the interpolation dilution documented in the first (regression) test's own docstring cannot occur here. Excess is exactly 11.9 and 12.1 at every ridge-band sample. Confirmed by hand: lowering `_TERRAIN_TOLERANCE_M` below 11.9 flips the "just inside" test's assertion to fail; raising it above 12.1 flips the "just outside" test's assertion to fail. The pair genuinely pins the constant in both directions, as claimed. | None |
| `world-model/tests/test_query_line_of_sight.py` (regression + coarse-ridge tests) | Test honesty | Both docstrings explicitly disclose their own limits (the regression test exercises only ~1.5 m of excess despite being framed around 11.5 m grid error; the coarse-ridge test would pass for any tolerance from 0–49 m). No overstated claim in either. | None |
| `body-layer/perception/geometry.py` (unchanged, pre-existing) | Caller of the modified primitive | `observer`/`target` tuples originate from live DCS telemetry (ownship position, contact/unit positions from the sim) via `logger.py`/`visibility.py`/`belief/contacts.py` — never from network input, file parsing, or any other externally-supplied/untrusted source in this single-player, LAN-only deployment. Attacker-controlled geometry into this function is theoretical only; no realistic attack path exists in this project's actual deployment. | None (documented as theoretical, no action) |

### Invariant Check
The only security-relevant property in scope for this change is the project's no-omniscience
invariant. The fix necessarily grants Petrovich sight of units masked by terrain clearing the
sightline by less than 12.0 m — an explicit, user-approved trade with a stated airframe
rationale (Mi-24P attacks in a run, not from a masked pop-up hover) and an explicit lapse
condition (revisit if this primitive is ever asked to model a pop-up-and-shoot airframe such as
Ka-50/Apache). The implementation matches the decision precisely: one constant, one comparison,
one caller, no override surface, no path that reveals more than "terrain within 12 m of the
sightline no longer masks."

### Verdict
APPROVED

No security-relevant risk beyond the accepted invariant trade, which is implemented exactly as
decided.
