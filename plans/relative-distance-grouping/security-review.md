## Security Deep Analysis: relative-distance-grouping (BL-B108)

One pass for the whole batch — Stages 0-5 plus the 2026-10-31/2026-11-01 cross-optic amendment —
on `feature/relative-distance-grouping` at tip `f8629e468e567d1129cc65292d6a4b5b886d9a4a`
(fast-forwarded cleanly from `d299dd52`, origin/main ancestor). Scope per dispatch: body-layer only
(estimation, belief, association, mission memory, tuning keys, config/defaults.toml). Threat model
per root `CLAUDE.md`/user direction (2026-10-21): single-user, LAN-only; the realistic attackers are
malicious code in a dependency and an infected LAN machine scanning ports. Player-experience
correctness (does the model fold/split groups the way the pilot expects) is Reviewer's job, already
covered across three review rounds in `review.md` (verdict: APPROVED WITH MINOR FIXES) — not
re-litigated here.

### Dependency Status

No dependency change. Confirmed: `git diff origin/main...HEAD` touches no `pyproject.toml`,
lockfile or requirements file in any subproject. The entire diff is body-layer source/tests/config/
plans. Nothing to CVE-check.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `perception/estimation.py` (whole diff) | New math: RFF noise fields, tiered-optic correlation, hash-based deterministic draws | No `eval`/`exec`/`pickle`/`yaml.load`/subprocess/network/file-write. `_field_frequencies` is `functools.cache`-keyed on `(field_name, optic_class, length_scales, salt)` — all four are from a small fixed set resolved at import time in production (`salt` is always `""` outside tests), so the cache is bounded (a handful of entries), not an unbounded-memory vector from attacker-controlled input. | None |
| `perception/estimation.py:483-497` | `_deterministic_unit_gaussian_pair`/`_deterministic_uniform`: `math.log(u1)` with `u1` mapped onto `(0, 1]` (never exactly 0) | Guards `log(0)` explicitly (`u1_int + 1`). No NaN path found. | None |
| `belief/position_belief.py:639-641` | `hi = max(...)`, `lo = max(1.0, min(...))`, `range_ratio_value = hi / lo` | Division denominator floored at `1.0`, so `range_ratio_value` is always finite and `>= 1`; feeds `log(range_ratio_value)` downstream (`RANGE_DECORRELATION_RANGE_RATIO`'s own kernel), never `log(0)` or `log(negative)`. | None |
| `belief/association_over_time.py:494` | `hypothesis_range_m / percept.range_m if percept.range_m > 0.0 else 1.0` | Explicit zero-guard on a value that could in principle be 0 (a percept at the observer's own position). | None |
| `belief/position_belief.py:370-377` | `determinant = self.xx * self.zz - self.xz * self.xz`; `determinant = max(determinant, floor)` before `1/determinant` divisions (matrix inverse) | Floored before use as a divisor — degenerate/near-singular covariance cannot divide by (near-)zero. Consistent with the new `_is_valid_covariance` guard (Stage 5 discovery) that routes a non-PSD fusion result to the existing "hold" branch instead of propagating a bad covariance. | None |
| `perception/estimation.py` (tiered-field ladder) / all `_RANGE_SIGMA_SCALE_BY_OPTIC` entries | `optic_range_correlation` divides by `max(k_a, k_b)` | Every optic's range-sigma-scale tunable has a `lo` bound strictly `> 0` in `config/defaults.toml` (checked: narrow 0.05, wide/binocular ≥0.1, unaided fixed 1.0), and the tuning loader (`src/tuning.py`) rejects an out-of-bounds override and falls back to the code default rather than clamping to or accepting 0 — so this denominator cannot reach 0 through a malformed `tuning.toml`. | None |
| `src/tuning.py` (pre-existing, re-verified for the new keys) | Bad/out-of-range override handling | Confirmed (not re-derived from the docstring): a bad value for any key — including the five new `BL-B108` tunables — warns and falls back to the code default; the loader never crashes or clamps to an invented value (Decision 4 REVISED). The new `RANGE_LOOK_SHARE`/`RANGE_RELATIVE_SHARE` pair's cross-key coupling (`f² + a² < 1`) is closed by choosing per-key bounds (`hi=0.6` each, so max `0.72 < 1`) rather than a runtime assertion — confirmed in the rendered `defaults.toml` comment, not just the plan text. Since `tuning.toml` is a local file read via `PETROBRAIN_TUNING` (no network path to it), this is not LAN-reachable input anyway, but the defence-in-depth is real and correctly applied to the new keys. | None |
| `mission_memory/admission.py` | `_maybe_write_entry_for_contact`'s `nameable` gate dropped — every founded contact (including single-glimpse presence-only ones, once confidence clears `GROUP_ENTRY_CONFIDENCE_FLOOR`) now gets a memory entry | More entries written per sortie than before. This is **not** an unbounded-memory vulnerability: entry count is bounded by the number of distinct contacts a single-player DCS mission can ever produce (bounded by the mission, not by attacker-controlled input), there is no network path into this admission logic, and the growth is an explicit, user-approved design tradeoff already stated in `plan.md`'s "Risks & Unknowns" ("Mission-memory volume... no guard is added, per the user's 'keep all'. Watch the sortie's memory log."). A player-experience/volume concern, not a security one — no action needed from this role. | None |
| grep across the full diff | hardcoded credentials / secrets pattern | None found. | None |
| grep across the full diff | `subprocess`/`os.system`/`shell=True`/`socket`/`http.server`/`urllib`/`requests.`/file writes (`open(..., "w"/"a")`, `shutil.`, `os.remove`, `os.rename`) | None found anywhere in the nine touched `src/` files. This feature adds zero new listening sockets, zero new HTTP endpoints, and zero new filesystem write paths — it is pure in-process numerical/belief code. | None |
| `mission_memory/admission.py:471`, `belief/contacts.py:908` | `self.__init__()  # type: ignore[misc]` | Pre-existing (confirmed via `git diff origin/main...HEAD` on both files — neither line is new or touched by this diff). Not this feature's finding. | None |

### No new attack surface

Under the stated threat model (malicious dependency; infected LAN machine port-scanning), this
feature changes **nothing reachable from the network or from a dependency boundary**: no new
package, no new socket, no new HTTP route, no new file write, no deserialization of anything, no
`eval`/`exec`. It is entirely in-process arithmetic over already-trusted, already-bounded
perception/belief data, gated by the existing tuning loader's reject-not-crash posture for config
values. The one place a crafted/out-of-range input could matter (a hostile `tuning.toml`) is local,
not LAN-reachable, and is already defended by pre-existing loader behaviour that this feature's new
keys correctly inherit.

### Passed to Reviewer

(Already Reviewer's own territory and already resolved there — noted only for completeness, no
verdict given here.) The memory-only cross-optic fold-rate figure (round 3's finding) and the E1
same-optic/in-view guarantee's scope are player-experience/correctness matters, fully covered by
`review.md` rounds 1-3 (APPROVED WITH MINOR FIXES) and the user's answered decision in
`explore-notes.md`.

### Verdict

APPROVED

### Required Fixes

None.
