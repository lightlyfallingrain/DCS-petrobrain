## Security Deep Analysis: expected-area-check (BL-B110), batch: Stages 0a, 0, 1

Scope per root `CLAUDE.md`: single-user, LAN-only hobby project, one security pass per batch,
before DoD. Branch `feature/expected-area-check`, tip `20de6ab1` (fast-forwarded into this
worktree from `c588a88d`, clean tree, no conflicts). Diff base `6b2b8296a`.

### Dependency Status

**No dependency change.** `body-layer/pyproject.toml` is untouched in this diff; the full
`git diff --stat` carries no `pyproject.toml`/lockfile entry. Confirmed directly, not taken from
the implementer's or reviewer's report.

### What this batch actually is, for this pass's purpose

Every file in "Files Changed" (`position_belief.py`, `optic_policy.py`, `geometry.py`, `gaze.py`,
`naked_eye_source.py`, `decay.py`, `tuning.py`, `body.py`) is pure in-process belief/geometry
logic over DCS telemetry already received through the existing aircraft-layer HTTP client — no
new listening socket, no new HTTP endpoint, no new file read/write path, no new process spawn, no
new serialization format. The attacker-relevant question for this threat model (malicious
dependency, or an infected LAN host scanning/talking to a listener) has nothing new to attack
here: there is no new attack surface, only new arithmetic over data that was already trusted
(ownship telemetry from the player's own aircraft-layer process) under the existing no-omniscience
and belief-state invariants, which are `[[Reviewer's / goal-aligner's domain]]`, not this role's.

Grepped the diff for every category this role's checklist covers — `eval(`/`exec(`/
`subprocess`/`os.system`/`pickle`/`yaml.load`/`socket`/`open(`/`urllib`/`requests.`/`__import__` —
zero hits in the added/changed lines of `body-layer/src/`. No shell-outs, no deserialization of
untrusted data, no new file I/O, no new network code.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/tuning.py:356-452` (`_check_scan_decay_coupling`) | cross-key coupling-check bypass via local override file (`PETROBRAIN_TUNING`) | This is exactly the hazard class this project's own memory flags (`.claude/agent-memory/reviewer/project_configurable_constants_crosskey_assert_gap.md`, `.claude/agent-memory/security/project_bearing_line_search_divisor_floor.md`): a module-level `assert` coupling tunables that per-key `lo`/`hi` bounds cannot see, reachable by an in-bounds override. This batch extends the *existing, already-fixed* mechanism from 3 keys/I1 to 5 keys/I1+I2, rather than introducing a fresh unguarded assert. Traced directly: `real()`/`sequence()` call `_check_scan_decay_coupling` for every key in the now-5-member `_COUPLED_KEYS` (tuning.py:460-461, 532-533) before binding; a violated invariant marks every file-mentioned coupled key `cross_key_rejected`, and `real()`'s own rejection path (tuning.py:481-484) forces that key back to its code default rather than the bad value. `decay.py`'s new `assert WORST_REVISIT_S < min(...)` (line 296) is the backstop for a *code-default* violation only (a genuine programming error), reached only once the loader has already rejected every override contribution — confirmed by reading `real()`'s control flow, not by trusting the docstring. Not an attacker-reachable path in this threat model either way: `PETROBRAIN_TUNING` is a local file the player hand-edits on their own machine, never data arriving over the LAN. | None |
| `body-layer/src/tuning.py` new import `from perception.geometry import n_sectors_for_legs` | new intra-subproject import | `perception/geometry.py` has no dependency on `tuning`/`gaze` per its own module docstring — confirmed, no import cycle, no new external surface. | None |
| `body-layer/config/defaults.toml` new/changed tunables (`EXACT_LOCATION_MIN_GAIN_M`, `GLASS_STALL_COOLDOWN_S`, `GLASS_BUDGET_PER_CYCLE_S`) | new behaviour-affecting constants | All three carry `lo`/`hi` bounds and a `status`, per this project's "Behaviour-affecting constants are tunable" convention. All resolve through `tuning.real`, so type/range are checked at the accessor, not trusted from the TOML. No unbounded numeric field reachable from the override file. | None |
| `body-layer/src/body.py` (`_resolve_sector_scan`, new fields `_last_scan_command_t_sim`) | new per-runner state, reset logic | Purely in-process dataclass fields over already-trusted ownship/telemetry data; no new input boundary. | None |

### Reviewed and not re-litigated

Reviewer's `review.md` (APPROVED, no required fixes) already verified the cross-key coupling
mechanism's correctness in depth (budget/stall/priority mechanics, Co-moving Fields table
coverage) — this pass does not re-derive that behavioural correctness, only the security-relevant
question of whether the mechanism can be made to silently accept an out-of-invariant combination.
It cannot, by the trace above.

### Passed to Reviewer

(Correctness/behaviour findings noted in passing, not given a security verdict, per this role's
scope — root `CLAUDE.md`'s security-review-agent scoping direction, 2026-10-21.)

- None beyond what Reviewer already covered in `review.md` (Deviation 2's interrupt-while-
  `GLASSING` sector-restart behaviour, the look-follow comment duplication, the "pilot-driven and
  rare" wording nit) — all already reviewed and dispositioned there.

### Verdict

**APPROVED.**

No exploitable vulnerability, no new attack surface reachable by this project's threat model
(malicious dependency / infected LAN host), no dependency change, and the one new cross-key
tunable-coupling mechanism extension is a correctly-traced closure of a known hazard class rather
than a new instance of it.

### Required Fixes

None.
