## Security Deep Analysis: same-optic-gate-indefinite

Branch `fix/same-optic-gate-indefinite` at `259ea5733408f06ba546fd4c738e2d5389219655`, reviewed
against `main`. Single-batch bug fix (Reviewer already approved — `plans/same-optic-gate-indefinite/review.md`).

### Dependency Status

No dependency change. `body-layer/pyproject.toml` is untouched in this diff. Both new dev tools
(`tools/measure_gate_calibration.py`, `tools/measure_same_group_fold.py`) import stdlib
(`argparse`, `math`, `statistics`, `sys`, `time`, `dataclasses`) plus this subproject's own
`belief.*`/`perception.*` modules only — no new third-party package anywhere in the diff.

### Scope note

The changed code is a closed-form numerical fix inside `belief/position_belief.py`'s
`correlated_innovation`/`_max_c_down_for_psd` (covariance-fusion math: a PSD cap and a
determinant-ratio margin) plus its test fences, and two offline measurement scripts. There is no
untrusted input anywhere in this diff: no network boundary, no file parsing of externally-produced
data, no new listening socket, no new DCS-facing surface, no LLM-readable text. The entire change
operates on values already inside the belief-computation pipeline (covariances, bearings, ranges)
that were already trusted by the pre-existing code; the fix only changes how those values are
combined.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/position_belief.py` (`_max_c_down_for_psd`, `correlated_innovation`) | numerical/arithmetic change only | Pure float math over already-internal values (two `Covariance2D`s, two bearings). No external input reaches this function; nothing here is a new deserialization, file, or network path. Out of security scope — this is a correctness/numerical-stability change, which Reviewer already verified (`plans/same-optic-gate-indefinite/review.md`). | None |
| `body-layer/tools/measure_gate_calibration.py`, `measure_same_group_fold.py` — `argparse` + `open(args.out, "w")` | file write sized by a CLI flag | `--out PATH` is an ordinary local-operator CLI argument on a dev-only offline measurement script (synthetic simulation data, no DCS/network connection, no user-facing deployment). Not reachable from any untrusted source; the "LAN scanner" and "malicious dependency" threat model do not apply to a script a local developer invokes by hand. False positive as a security finding. | None |
| `measure_gate_calibration.py` reading `pb_module._down_axis_unit`/`_max_c_down_for_psd` and a ground-truth probe (`correlated_innovation_true_axis`) | test/ground-truth access | Confined to `tools/`, excluded from `mypy src` scope, explicitly documented "test-only, can never ship — no-omniscience." Not a new exception to the no-omniscience boundary in shipped code (`belief/percept.py`); Reviewer already confirmed this. No security implication — mentioned for completeness only. | None |
| Security-grep sweep (full baseline, all subprojects) | — | No hit lands inside any file this feature touches (`position_belief.py`, the two new `tools/` scripts, the three test files). All grep hits are pre-existing, in unrelated files (audio-adapter subprocess use, the aircraft-layer/brain-layer/world-model/audio-adapter HTTP `Content-Length` handling, the DCS `net.dostring_in` bridge, etc.) and are the project's known, already-reviewed steady state. | None — pre-existing, not this feature's |

### LLM prompt injection / arbitrary code execution / LAN surface

Not applicable to this diff. No speech transcript, mission text, or any other model-readable
string is touched. No `eval`/`exec`/`loadstring`/`net.dostring_in` appears in the diff. No socket,
HTTP server, or `Content-Length` handling is touched. No new file path is built from received
data.

### Verdict

APPROVED

### Required Fixes (if any)

None.

### Backlog / findings tracking

No finding in this analysis met the bar for a backlog item — every item above is either a
non-issue (pure internal math) or an explicit false positive (local dev-only CLI tool, test-only
ground-truth probe already fenced and documented). Nothing to file; no `(A)/(B)/(C)/(D)` risk
matrix was raised, so this section is intentionally empty rather than silently empty.
