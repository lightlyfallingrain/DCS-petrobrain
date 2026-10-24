# Definition of Done — BL-B90 Stages 1-2 batch

**Scope**: registry + loader (Stage 1), engine + wiring (Stage 2), the main merge of
`fix/guidance-ready-edge`, the review fixes, the security deep analysis, and the performance
change request. **Not in scope**: Stage 0 (already DoD-passed separately,
`dod-check-stage0.md`), Stage 3 (this re-flight card — tested by this same pass but not itself a
prior DoD subject), Stage 4 (not built).

**Verdict scoped to**: tip `5cac1bee0bd3ddc4f234ae81e93ceca6582388a6`, branch
`feature/effector-sequences`. Reached by `git merge --ff-only` from this worktree's prior tip
`f4e552c1` (a strict ancestor) — confirmed clean fast-forward, no cherry-pick, no rebase.

## Acceptance boundary — what fixtures structurally cannot reach

Every check below ran against fakes and synthetic fixtures — a real `EffectorDef`/`SwitchRow`
registry resolved in-process, a fake `AircraftLayerClient` that returns scripted writes/failures,
a poll loop driven by advancing simulated time by hand. **None of it touches a real DCS cockpit.**
Two classes of defect are structurally invisible to this pass, the same shape the worked example
in this role's own brief names:

1. **Whether the real `performClickableAction` writes actually move the real switches** in the
   real cockpit, in the real order, with the real ~1 s spacing that matters for the animation. The
   fake client only records what it was asked to write; it has no opinion on DCS's own behaviour.
2. **Whether the readback (`GET /cockpit_switch/latest`'s new `"args"` map) reports what the
   cockpit actually shows**, especially for `cplr_distr` (arg 761), which is carried as
   `unverified = true` precisely because this cannot be settled from a test.

The re-flight card below exists to close exactly these two gaps, not as a formality after a
passing test suite — it is where this feature's real pass/fail lives.

## Mechanical checks

All commands run in this worktree, tip `5cac1bee`, tools resolved from the main checkout's
`.venv`s (no `.venv` in this worktree) per the task's instruction.

**body-layer:**
- `ruff format --check src tests tools` — pass (180 files)
- `ruff check src tests tools` — pass
- `cd body-layer && .venv/bin/mypy src` — pass (74 source files)
- `.venv/bin/mypy tools` — pass (9 source files)
- `pytest tests -q` — **2550 passed, 4 xfailed** — matches `review-stage2.md`'s own re-review
  numbers exactly
- `pytest tests/test_render_switch_reference.py -q` (switch-reference staleness test) — pass
- `tools/generate_defaults.py` (no `--write`, check mode) — "config/defaults.toml is up to date"
- Rendered `config/defaults.toml`'s `[belief.effector_engine]` section read directly (not the
  source `#:` comment): `EFFECTOR_CONDITION_READBACK_WAIT_S = 5.0` (1.0–30.0) and
  `EFFECTOR_SEQUENCE_STEP_DELAY_S = 1.0` (0.5–5.0) both render correctly, with the correct
  first-sentence comment each. `GUIDANCE_UNIT_SWITCH_DELAY_S` is gone except as the explanatory
  "renamed from" comment attached to its replacement — confirmed by grep.
- `pip show pytest-randomly` — not installed, confirmed not reinstalled.

**aircraft-layer:**
- `ruff format --check src tests` — pass (75 files)
- `ruff check src tests` — pass
- `cd aircraft-layer && .venv/bin/mypy src` — pass (27 source files)
- `pytest tests -q` — **533 passed** — matches `review-stage2.md`'s numbers exactly

No unhandled errors/panics on a data path: `effector_engine.advance`'s write-failure handling
catches `AircraftLayerError`, logs, retries next poll (D9), never propagates; both loaders'
documented contract ("never raises on bad content," `security-stage1-2.md`) is implemented, not
just asserted. No debug `print`/leftover TODO introduced by this batch — grepped the diff for
`print(`/`TODO`/`FIXME` in `body-layer/src`/`aircraft-layer/src`: the two `print(` hits found are
intentional (`CONFIG_ERROR_LINE`'s `_print` call, the startup banner's `print(banner, file=sys.stderr)`),
not debug leftovers.

## Code quality / scope / invariants

- **Implementation matches `plan.md`**, including three revisions (R12, R13, the performance
  guard) made live during the batch — `plan.md`'s own text has been brought in line with what was
  built in this pass (D5's collision wording corrected to point at R13's actual rule; D6 now
  states the performance guard). No unplanned scope found beyond what `implementation.md` already
  names and justifies (the `cmd2` field, `crew`/`crew_explicit`, the per-aircraft directory
  layout) — all of these are Stage 0/1 decisions already reviewed, not new in this batch.
- **No invariants violated**: DCS stays authoritative (conditions read observed readback, not
  commanded); the write channel stays registry-resolved only (security-stage1-2.md's finding,
  re-confirmed by reading `effector_engine.advance` directly — a sequence file cannot name an
  arbitrary device/cmd/arg); no GPL dependency, no ED source committed; module independence
  unaffected (aircraft-layer↔body-layer stays HTTP/JSON).
- **All new/modified files staged**: confirmed via the fast-forward merge bringing in a complete,
  already-committed set of commits; `git status --porcelain` in this worktree shows only the
  plan.md edit made in this pass, which is committed below.

## Testing

- Core logic (registry resolution, sequence parsing, engine transitions D1/D3/D4/D8/D9, the R12
  self-check, R13's per-aircraft isolation and first-wins collision rule) is covered by real,
  mutation-verified tests per `review-stage1.md`/`review-stage2.md` — not decorative; both reviews
  independently confirmed this by deleting guard lines and watching the right tests fail.
- No existing tests broken: aircraft-layer and body-layer counts both match the prior review's
  own numbers exactly, and both subprojects' full suites are green.

## Documentation

- **Reviewer findings addressed**: review-stage1's one flagged item (collision-rule confirmation)
  was resolved by R13 (first-wins) and is reflected in the plan text. review-stage2's one required
  fix (SPU-8 intercom-gate test coverage) was closed and the closure independently mutation-
  verified in the same review's own fix re-review — confirmed again here by reading
  `review-stage2.md`'s "Fix re-review" section rather than taking the headline APPROVED at face
  value.
- **Non-obvious behaviour explained**: `body-layer/CLAUDE.md`'s module map now documents
  `effector_registry.py`/`effector_sequences.py`/`effector_engine.py`/`sight_effector.py`'s slimmed
  role, the per-aircraft directory layout, the bad-file-is-not-fatal posture, how to add a new
  effector from `switch-reference.md`, and the two tunables — this was a real gap (these modules
  had no CLAUDE.md entry before this pass) and is now closed.

## Security

- `plans/effector-sequences/security-stage1-2.md` — **APPROVED**, no findings. Explicitly checked:
  arbitrary-write surface (none — registry-resolved only), D5 raise-path (none found), new
  aircraft-layer field bind/auth (no change), new dependency (none), secrets (none). One
  forward-looking note (the `petrovich_says` field's prompt-injection re-check) restates an
  already-filed Stage-0 caveat rather than raising a new finding.
- A Stage 0 plan-review and security pass already exist and are unaffected
  (`security-stage0.md`, APPROVED, and the `BL-B91` TOML-escaping fix filed and closed from that
  pass).

## Milestone-completion question

Stages 1-2's completion does not change what Stage 3 (this card) or Stage 4 (the low-rate
readback) should be — both were already fully specified in the plan before this batch started.
It does sharpen one thing for Stage 4: the performance review's own note
(`performance-stage1-2.md`, "cockpit_switch readback via the per-frame args map") found that
`effector_engine` reads readback only through an opaque `Mapping[str, float] | None`, with no
idea whether it came from the per-frame push or an on-demand low-rate query — so Stage 4's planned
move should not require touching `effector_engine.py` at all, only what `logger.py` passes in.
That was true before this batch (by the code's own existing shape) but is now a confirmed fact
about the actual shipped code, not a plan assumption.

## Verdict

**PASSED.** Proceeding to the re-flight card (Stage 3) as requested — no merge this pass; the
user decides when, after at least this card's flight.
