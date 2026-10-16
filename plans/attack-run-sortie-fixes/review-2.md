### Review Summary

Reviewed the fix commit `571e898` on `feature/attack-run-fixes` against
`plans/attack-run-sortie-fixes/review.md`'s two required findings, the plan
(`plans/attack-run-sortie-fixes/plan.md`, BL-B70), and `implementation.md`'s own account of the
fix. Also re-read the whole BL-B70 change (`5215daa`, `3d964fa`, `571e898` vs `main`) rather than
only the delta, per the dispatch brief.

Worktree started 6 commits behind the named tip (`5015a66`); `git status --porcelain` was clean
and `5015a66` a strict ancestor of `571e898`, so fast-forwarded with `git merge --ff-only
571e898b74acb35bed768616b2d6ed0701588721` before reviewing. No divergence, nothing to report there.

**Both required findings are genuinely fixed, verified against source rather than against the
fix's own claim about itself** (the exact lapse this project's own reviewer memory on this file
names — `claimed-gate-order-mirroring-needs-checking-against-source` — and which produced the
defect in the first place):

- **Gate order.** Read `check_visibility`'s real gate sequence directly
  (`perception/visibility.py:990-1023`): mask → optic FOV → `range_or_size` (gate 3,
  `candidate_range_m > range_threshold_m`) → `live_los_clear` (gate 4) → forest. `_no_look_cause`
  now checks `too_far` (range) before `obstructed` (LOS) — matches. The new test
  (`test_no_look_cause_too_far_wins_over_a_fresh_obstructed_verdict`) constructs exactly the
  previously-unexercised case (fresh `live_los_clear=False` *and* beyond presence range at
  `range_m=2000.0` vs. the default-profile threshold of ~1667 m, `now_sim` inside the 1.5 s
  freshness window) and asserts `"too_far"`. Traced the arithmetic by hand rather than trusting the
  implementer's figure: 2000 m > 1667 m and `1.4 s <= 1.5 s`, so the LOS branch would have fired
  under the old order and is correctly pre-empted under the new one.
- **`<where>` duplication.** `decide`'s losing-sight branch now computes `where = "ahead" if
  alignment_clock_hour(azimuth_deg) is None else None` from the *same* `azimuth_deg` already passed
  to `alignment_phrase(azimuth_deg, ...)` two lines above — same variable, not a parallel
  computation that could drift at the sector boundary, which is the shape of bug this file's own
  gate-order defect was. `render_attack_run_lost_sight`'s `where: str | None` has exactly one call
  site (`attack_run.py:682`), so the type change cannot be forgotten at a second caller. Both
  branches (suppressed outside the 12 o'clock sector, kept as `"ahead"` inside it) are pinned by
  separate tests with the literal rendered strings, not just that `decide` returns non-`None`.

**Nothing the earlier review would have caught had it been in scope.** The fix touches only the two
named branches, their docstrings (now stating the mutation proof and reviewer attribution inline,
which is good practice — the next reader does not have to find `review.md` to know why the order
matters), and the two affected tests. No new `AttackRunState(...)`/`OpticState(...)` construction
site was introduced (grepped both files: the one pre-existing fresh-construction site at
`attack_run.py:595` is untouched by this commit, and `optic_policy.py`'s sites are untouched too —
F4 does not apply to this diff). No new tuning constant was declared (`git diff
main...571e898 -- body-layer/src/tuning.py body-layer/config/defaults.toml` shows only the
`ATTACK_TARGET_LOS_MAX_AGE_S` entry from the *first* implementation pass, already reviewed and
approved in `review.md`'s Optional Refinements — this fix commit adds nothing to `defaults.toml`).

**`Contact.live_los_clear`'s reachability** — the open question the first review flagged rather than
resolved — was traced in this pass (`implementation.md`, "On `Contact.live_los_clear`'s
reachability") and correctly *not* fixed: it is pre-existing machinery outside this plan's Affected
Modules. This is the same finding now filed on `main` as `BL-B76` (narrowed 2026-10-16, per this
branch's dispatch note) — not re-reported here as new, per the brief.

Checks: trusted the dispatcher's clean run (`ruff format --check`, `ruff check`, `mypy src` — 60
files, `pytest -q` — 2016 passed, 4 xfailed) rather than re-running, since nothing in this review
pass changed any file and there is no reason to doubt the figures — they match
`implementation.md`'s own account exactly (+2 tests over the 2014/4 baseline, net of one rewritten
in place). No `TODO`/`FIXME`/debug `print` found in the diff.

---

### Required Fixes

None.

---

### Optional Refinements

- **`body-layer/ROADMAP/BL-B70.md` still reads `[ ]` (open)** and its body still describes the
  pre-fix defects as open problems, not as fixed. Not a reviewer-blocking issue — roadmap
  closure is normally a DoD-time action — but worth DoD confirming the entry is updated (or
  explicitly deferred to merge) before the milestone is called done, since the entry's own
  "trap that is one keystroke away" callout (the `AttackRunState(...)` vs `replace()` note) is
  about a different site than anything touched in this fix and should not be read as still
  outstanding here.
- The module docstring's cause-taxonomy comment and `_no_look_cause`'s own docstring now both
  carry a fairly long inline account of the review/mutation history (reviewer found it, mutation
  confirmed it). This is good practice for *this* defect, given the memory lesson it is guarding
  against, but is worth trimming at some future touch of this function if the comment keeps
  growing with each review round — not asked for now.

---

### Verdict

APPROVED

---

### Review Confidence

Full read of the fix diff (`attack_run.py`, `speech.py`, `test_attack_run.py`) against the real
gate order in `perception/visibility.py` (read from source, lines 990-1023, not from the fix's own
docstring claim about it) and against `speech.py`'s `alignment_clock_hour`/`alignment_phrase`
(read in full to confirm `where`'s suppression condition is the same sector test `phrase` already
uses, not a parallel one). F4 (`replace()` vs fresh construction) and the tuning-constant checklist
item verified by diffing this commit against `main` for new construction sites and new
`tuning.*`/`defaults.toml` entries respectively, rather than re-deriving them from the plan — both
came back empty, i.e. not implicated by this commit. Checks (ruff/mypy/pytest) not re-run; taken on
the dispatcher's report, cross-checked against `implementation.md`'s own figures for consistency
rather than independently re-executed — low risk, since no file changed between that run and this
review and the worktree ended at the identical commit. `BL-B76`'s current state on `main` was
checked (`git log --oneline main`) to confirm the already-known finding is filed where the brief
said, not independently re-audited.
