# Definition of Done — `fix/callout-observability-gate`

**Date:** 2026-10-06 · **Branch tip verified:** `304a367` · **Fork point from `main`:** `5a656ad`
**Verdict: PASSED.** Live acceptance deferred, not waived — tracked in `body-layer/ROADMAP.md`'s
"Live acceptance debt" list. **Not merged; the merge is the user's.**

## Branch contract

| check | result |
|---|---|
| worktree `git rev-parse HEAD` on arrival | `19143fa` on `worktree-agent-ab16c0e980d937198` — **not** the named tip |
| correction applied | explicit `git checkout fix/callout-observability-gate` (the branch is not checked out in the main checkout, so this was available and is strictly better than `--ff-only` onto a detached head) |
| HEAD after correction | `304a367` — matches the dispatched sha exactly |
| working tree | clean (`git status --porcelain` empty) before and after every probe |

Recorded because `AGENTS.md` rule 4 exists for it: a DoD run on this project once reported
`1177/4` — exactly `main`'s baseline — against a branch's own `1192/4`. The worktree did land on a
stale commit again here (eleven-plus commits behind), as it has for several agents this session.

## Checks — run in this worktree, not quoted from the implementation log

`body-layer/` only; the diff touches no other subproject (`git diff --name-only 5a656ad HEAD`
returns `body-layer/src/belief/{callouts,contacts}.py`,
`body-layer/src/perception/motion.py`, `body-layer/tests/test_callouts.py`, the four plan files and
three roles' agent-memory files — nothing under `world-model/`, `aircraft-layer/`, `audio-adapter/`,
`brain-layer/` or `mission-interpreter/`).

The worktree has no `.venv`. The main checkout's `body-layer/.venv` binaries were used by absolute
path with `cwd` inside the worktree's `body-layer/`, **after proving imports resolve to the
worktree's own tree**:

```
belief/callouts.py → …/worktrees/agent-ab16c0e980d937198/body-layer/src/belief/callouts.py
belief/contacts.py → …/worktrees/agent-ab16c0e980d937198/body-layer/src/belief/contacts.py
query/describe.py  → …/worktrees/agent-ab16c0e980d937198/body-layer/../world-model/src/query/describe.py
```

`pyproject.toml`'s `[tool.pytest.ini_options] pythonpath = ["src", "../world-model/src"]` is
relative to pytest's rootdir, which `--collect-only` confirmed as the worktree's `body-layer/`.

| check | command | result |
|---|---|---|
| format | `ruff format --check src tests` | **PASS** — 115 files already formatted |
| lint | `ruff check src tests` | **PASS** — all checks passed |
| type | `mypy src` (cwd `body-layer/`, CWD-only discovery) | **PASS** — no issues in 53 source files |
| test | `pytest tests -q` | **PASS** — **1475 passed, 4 xfailed** in 12.09s (`main` baseline 1466/4; +9 net) |

## Criteria

**Code quality**

- [x] Every subproject the branch touches had its own commands run — one subproject, derived from the diff.
- [x] No unhandled errors or panics in data paths. The diff adds **no** `except`, bare `pass` or `contextlib.suppress`; `ContactStore.callout_observable` is a pure read of bookkeeping `_callout_may_speak` already maintains, and returns `True` when that bookkeeping has never run, which is what keeps every `tick()` caller that omits `ownship` a true no-op.
- [x] No debug output left in committed code. `grep` for `print(`/`breakpoint`/`pdb`/`TEMP-PREFIX-PROBE` over the three touched `src` files is empty.
- [x] No leftover TODO/FIXME/XXX introduced by this feature — `grep` over the three touched `src` files is empty.

**Scope & correctness**

- [x] There is no `plans/callout-observability-gate/plan.md`: this is the bug-fix path (Debugger → Reviewer ×2 → DoD), so `debug.md` is the plan of record. Checked against it and against `plans/post-review-fixes/explore-notes.md` decision 11.
- [x] No unplanned scope added. `perception/motion.py` is **comment-only** (15 lines, provenance for `BL-B34`'s rates) and is explicitly argued in `debug.md` as the cheaper alternative to a third re-derivation; the implementation log records that no `ROADMAP.md`/`BACKLOG.md`/`todo/` file was touched on the branch, per the dispatch constraint.
- [x] **No invariants violated — this change *restores* one.** body-layer's "no omniscience is structural, not a convention" was being broken out loud 17 times in one sortie. The gate reads only belief-side bookkeeping, adds no second ground-truth exception, and the `belief/percept.py` boundary is untouched. Mechanism and calibration do not share this commit: no threshold value changed.
- [x] All files staged and committed; working tree clean.

**Testing**

- [x] Core logic covered. 9 tests over the gate, 2 added in the review-fix pass.
- [x] **Tests are meaningful, and that was checked by running the counterfactual rather than reading it.** The one that matters most — the exemption — re-verified here independently: emptying `_OBSERVABILITY_EXEMPT_KINDS` fails `test_engagement_change_speaks_about_a_cockpit_masked_bearing` with `assert [] == ['Danger, ZU-23-3 Sergey.']`; the edit was reverted and the tree confirmed clean. Round 3's own correction of a counterfactual that **failed open** (`CALLOUT_MAX_AGE_S` raised to `1e9` passes, because the test derives its clock from that constant) is the strongest evidence the suite is being held to this standard.
- [x] No existing tests broken; zero existing tests changed behaviour. `grep -rln "callout_observable\|last_observable_sim\|OBSERVABILITY" tests/ src/` bounded the impact surface to two test files, and `test_contacts.py`'s references are to the emission-site gate which the engagement block never used.
- [x] Breadth claims verified **by import, not by reading prose**: `len(_TEMPLATED_KINDS) == 6`, `len(_OBSERVABILITY_EXEMPT_KINDS) == 1`, `len(_TEMPLATED_KINDS - _OBSERVABILITY_EXEMPT_KINDS) == 5`; `CALLOUT_OBSERVABILITY_GRACE_S == CALLOUT_MAX_AGE_S == 10.0` confirmed from `belief/decay.py:143` and `belief/callouts.py:376`.

**Documentation**

- [x] Reviewer findings addressed. Round 1 (`review.md`) APPROVED with one documentation fix; round 2 (`review-round2.md`) **APPROVED WITH REQUIRED FIXES** R1–R3, all documentation, all landed in `304a367`. Round 2's own confidence line: **"Full read"**, with the load-bearing claims re-run rather than read.
- [x] Round 3 is documentation-only, and that was established mechanically rather than asserted: the dispatcher AST-diffed `belief/callouts.py` against its parent with docstrings blanked and the trees are identical; the only test change is one added `assert`.
- [x] Non-obvious behaviour explained in code structure — `_OBSERVABILITY_EXEMPT_KINDS` is a named, documented set rather than an inline `!=`, carrying a two-property admission bar that names the kind it must exclude (`CONTACT_RANGE_CROSSED`) and which clause does it. Four insights harvested to `NOTES.md`.

**Security**

- [ ] `plans/callout-observability-gate/security-plan-review.md` — **absent, and correctly so.** Under the cadence root `CLAUDE.md` set on 2026-09-24, `security` runs **once per whole feature, immediately before DoD**; there is no per-plan review pass, and this is additionally a bug-fix path with no `plan.md` to review.
- [ ] `plans/callout-observability-gate/security-review.md` — **absent.** This is the one gap. The deep-analysis pass in the bug-fix sequence (`Debugger → Reviewer → Security → DoD`) was not run on this branch. **Assessed as not blocking**, on the specific facts rather than by waiving the rule: the change adds no input surface, no network or filesystem path, no parsing, no new dependency and no state that crosses a trust boundary — it *removes* disclosure, which is the direction security review exists to push. `debug.md` records that a security pass independently reached the same 17/3 conclusion while sizing the defect, so the branch is not unexamined. Flagged here so the user decides, rather than discovering the omission later.

## The acceptance boundary — what these fixtures structurally cannot reach

**A fixture pass here is weaker than usual, because the observable is an absence.** Three gaps,
named so a green suite is not mistaken for a flown feature:

1. **A fixture cannot distinguish "silent because the gate worked" from "silent because something
   upstream stopped producing the event."** Every test asserts `scheduler.tick(...) == []` against
   a hand-built store. If founding, association or the event derivation broke, the assertion would
   still pass. Only a flight with units genuinely behind the aircraft, and `report` still answering
   about them, separates the two.
2. **The exemption's correctness is a judgement a test cannot hold.** The engagement test proves
   the line is *spoken*; whether speaking *"Danger, ZU-23-3, six o'clock, 1.0 km"* about something
   Petrovich cannot see is right behaviour or the same omniscience the user asked to be fixed is
   his call, and he has not made it. This is the F10-vocabulary failure shape exactly: code doing
   precisely what it says, possibly against the wrong intent, which no fixture detects.
3. **Ten seconds is a fixture constant, not a measured one.** `CALLOUT_OBSERVABILITY_GRACE_S` and
   `CALLOUT_MAX_AGE_S` are both untuned 10.0 by their own docstrings; the tests supply their own
   clock derived from them, so they pin the *mechanism* and say nothing about whether the number
   suits real flying. This fix makes it load-bearing for three more paths than before.

**Live acceptance is deferred, not waived, and does not gate the merge** (user direction,
2026-09-19). The user is asleep; the card is written rather than conducted. Entry added to
`body-layer/ROADMAP.md`'s "Live acceptance debt" list, **batched with `fix/contact-report-flood`,
`fix/redundant-group-disclosure` and `feature/terrain-callout-stages-345`** — all four change what
is spoken about the same contact stream, and each one's observable is distinct enough that a single
sortie can score them separately.

Acceptance card: `docs/acceptance/2026-10-06-callout-observability-sortie.md`, published at
https://claude.ai/artifact/N4CGoNx5xaMdXW8QD3PwMw.

## Process signals for the user

- **The branch's documentation count was wrong three times before it was right**, and each time a
  review caught it rather than the author. It was only settled once the tally was taken by
  *import* (`len(_TEMPLATED_KINDS)`) instead of by counting prose. That is the fourth-plus
  instance of this repo's own documented enumeration defect — root `CLAUDE.md` names three
  subprojects-while-six-existed recurrences and one in the commit gate that warns about it. The
  signal is process debt, not code debt: a prose count of a set that lives in code should be
  derived by import at the point it is written, and that belongs at Architect/Implementer rather
  than being caught at Reviewer each time.
- **A skill on `main` documents behaviour that only exists on an unmerged branch.**
  `.claude/skills/sortie-log-triage/SKILL.md` (commit `6d819de`) states that the three sortie logs
  are run-stamped "since 2026-10-06". The stamping is `BL-11` Stage 5 and lives on
  `feature/bl11-tick-cost`, which is not merged — nothing in `body-layer/src` on `main` or on this
  branch writes a timestamp into a log path. The acceptance card says so explicitly, because the
  user noting file sizes before the flight depends on it. Worth reconciling at `BL-11`'s merge.

## Not done here, deliberately

- **Nothing marked merged.** The user merges, with their own approval.
- `body-layer/BACKLOG.md` left untouched: `BL-B34` is already resolved on `main` (2026-10-06) and
  `BL-B30` does not carry the masked-hour count, so there is nothing to correct — and the branch's
  copy of that file is behind `main`'s, so editing it here would create a conflict for no gain.
- **Round 2's Optional 2 is still outstanding** (a test pinning the enriched exempt line, so
  "does the exemption speak a position?" becomes an assertion rather than a reviewer's note). It is
  the one refinement with real value and is recorded in `implementation.md` as worth its own small
  commit.
