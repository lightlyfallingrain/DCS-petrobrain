# Definition of Done — `feature/bl-b76-tripwire-rejected` (BL-B76, Step 1)

**Scoped to tip `9616235af070372fb17826cd0f412af70fa7bb37`.** Confirmed via
`git rev-parse feature/bl-b76-tripwire-rejected` at the time of this check. If the branch has
moved since, this verdict no longer covers it.

**Verification route: isolated snapshot, not merge.** This DoD agent's own worktree HEAD
(`a5082adf`) is not an ancestor of the tip — `git merge-base --is-ancestor HEAD <tip>` returned
false — because `origin/HEAD` in this clone is ~100 commits behind local `main`, so the worktree
was created off an unrelated line of history. No merge was attempted. Instead: `git archive
feature/bl-b76-tripwire-rejected | tar -x -C <scratch>`, then every check below ran with `cwd`
inside that snapshot's `body-layer/`, tools resolved to
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/<tool>`.

## Mechanical checks — PASS, all run, all match expectation

| check | result |
|---|---|
| `ruff format --check src tests` | 133 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy --strict src` (cwd inside snapshot's `body-layer/`) | Success, 60 source files |
| `pytest -q` | **2061 passed, 4 xfailed** |

All four match the numbers stated in the dispatch prompt exactly.

**Diff scope confirmed independently** (`git diff --name-only 95ef7982 <tip>`): only
`body-layer/src/belief_truth_log.py`, `body-layer/tests/test_belief_truth_log.py`, two
`.claude/agent-memory/` files, and four `plans/bl-b76-tripwire/*.md` files. No other subproject
touched — single-subproject verification is sufficient.

## Does it deliver what the user asked for?

> *"Before acting on LOS none, we should know how often that happens. As it stands now, log it and
> then ignore in cockpit behaviour."*

**Half 1 — can the log now answer "how often"?** Yes. `_write_attack_run_tripwire` now writes
`outcome` (`"admitted"`/`"rejected"`/`"absent"`) and, for a rejection, `gate_outcome` and the
existing `live_los_clear` (`False` = blocked this poll, `None` = no fresh verdict this poll) for
the attack-run target specifically. That is exactly the three-way split §9 needed and the old
`present_in_snapshot` boolean could not express — `"rejected"` and `"absent"` both used to read as
`present_in_snapshot: false`.

**Half 2 — did cockpit behaviour change?** No, verified by diff, not assertion.
`git diff 95ef7982..<tip> -- body-layer/src` touches only `belief_truth_log.py`.
`perception/visibility.py` (the admission gate), `belief/attack_run.py` (the fail-open `"unknown"`
arm), `Contact`, and anything that reaches speech are all untouched. The new
`_object_id_to_contact_id`/`_object_id_last_seen_sim` cache lives entirely inside
`BeliefTruthLogWriter`, a log writer only constructed when `--belief-truth-log` is passed, and
nothing it computes is read back by belief/perception/attack-run code — confirmed independently by
both Reviewer (`review.md`) and Security (`security.md`).

## The honest caveat — present in the docstring, not yet in the thing the user reads

The docstring (`_write_attack_run_tripwire`, "One residual case is not a miss...") correctly states
the known upward bias: if the target's `NakedEyePerceptionSource` cluster splits and the minority
child is rejected on the same poll it splits, `_update_object_id_contact_cache` — which only reads
`ADMITTED` rows — still holds the previous poll's object_id→contact_id mapping, so that rejection
gets attributed to the target even though it is, or is about to become, a different real contact.
This can only inflate `"rejected"`, never deflate it, and fires exactly when a group scatters under
fire — i.e. plausibly during the acceptance sortie itself.

**This caveat is currently discoverable only by a reader of `belief_truth_log.py`'s source.** The
user reads `BL-B76.md`, the roadmap entry, not the module. Per the DoD role's standing instruction
to name the acceptance boundary explicitly when a fixture pass could be mistaken for the real
answer (and per `.claude/agent-memory/dod/feedback_name_the_acceptance_boundary_when_the_observable_is_an_absence.md`,
same shape: a result that looks like a clean count is weaker evidence than it looks), **the
roadmap entry should carry this caveat in the user's own words**, not just the source. See
"Roadmap — recommended edit, not applied" below for exact text, and why it was not applied
directly.

## Acceptance boundary — what this step's fixtures cannot reach

**Stated explicitly, per role instruction.** All 2061 passing tests are unit-level, built against
hand-constructed `DetectionTraceCollector`/`Contact`/`GateOutcome` fixtures. They prove the
three-way split computes correctly for the cases those fixtures construct — admitted, rejected
during the same poll with a warm cache, absent, cache-warm-before-run-active — and that the join is
bounded and inert outside the log writer. **No fixture can show the actual rate of `"rejected"`
with `live_los_clear is None` for a real attack target over real DCS terrain**, which is the whole
number the user asked for. That requires a live, mountainous sortie: both 2026-10-15 sorties were
flat desert, where terrain-LOS rejection barely fires — this feature exists because that terrain
structurally could not answer the question. A fixture pass here is evidence the *instrument* works,
not evidence of what it will read.

## Reviewer findings addressed

`review.md` (first pass, `7f31b1f4`, reviewing implementation commit `d742ce57`): **APPROVED WITH
MINOR FIXES**, one required fix — the docstring's soundness claim overstated the cache's guarantee
("can only ever cause a miss... never a wrong contact's rejection being attributed"), which
review.md's own mutation testing and reading of `naked_eye_source.py`'s majority-overlap voting
showed was false for the same-poll split case. Fixed in `01480698`; `review-2.md` (second pass,
`e6a77d8e`) re-verified the corrected docstring, re-ran all four checks (2061/4, matching),
re-verified the cache-warm-before-run-active test by mutation (reverted the fix, confirmed the
test fails for the stated reason, restored), and returned **APPROVED**, no further required fixes,
no optional refinements outstanding.

## Scope & correctness

- Matches `plans/bl-b76-tripwire/implementation.md` and the roadmap entry's own "Scope for this
  entry, as it now stands" paragraph: a logging-only widening of
  `BeliefTruthLogWriter._write_attack_run_tripwire`, no change to admission, no change to what
  belief holds, no new cockpit word. Confirmed by diff.
- No unplanned scope added. No new tuning constant (`body-layer/config/defaults.toml` untouched —
  the change reuses the existing `belief.decay.OBJECT_ID_MEMORY_S`).
- No invariant violated: no-omniscience is unaffected — `Contact` still carries no DCS `object_id`;
  the new cache lives only inside the log writer and is never read by belief.
- All new files staged on the feature branch (confirmed via `git show --stat` on the commits;
  nothing outside the five commits' own diffs).

## Testing

- Core logic (the three-way outcome split, the cache-warm-before-run-active ordering, the rejected
  join, `present_in_snapshot`'s backward-compatible redefinition) is covered — `+3` test functions
  over the prior baseline at first review, confirmed present and passing at this tip.
- Tests are meaningful: `review-2.md` independently verified the cache-warm test's bite by mutation
  (moved the cache-update call back inside the run-active guard — the exact regression the test
  exists to catch — and confirmed it fails for the stated reason), and `review.md` did the same for
  the rejected-entry membership test.
- No existing tests broken: 2061 passed / 4 xfailed matches the full suite, no regressions.

## Security

`plans/bl-b76-tripwire/security.md` — **APPROVED**, no required fixes. Confirmed scope by diff
(same untouched-files list as above); the two structural observations raised (unbounded-looking but
census-bounded cache growth; sim-time-monotonicity assumption) were both judged pre-existing,
systemic patterns already accepted elsewhere in this codebase (`belief.decay`), not new risk, and
not blocking. No plan-review document exists for this entry because `BL-B76` originated from an
`/explore` on an existing roadmap entry rather than a fresh Architect plan — the deep-analysis
security pass is the one that ran, matching this project's "one security pass per feature,
immediately before DoD" cadence.

## Performance

`plans/bl-b76-tripwire/performance.md` — **APPROVED, MONITOR**. No material per-poll cost: the new
unconditional cache-update pass and the conditional rejected-entry scan are both single O(records)
passes over an already-small `collector.records` set, and the rejected-branch membership test is a
set lookup, not a scan. MONITOR flags are for future stages stacking more unconditional per-poll
work onto this writer, or reusing the never-evicted cache pattern with an unbounded (not
census-bounded) key space — neither applies to what shipped here.

## Roadmap — recommended edit, not applied directly

`body-layer/ROADMAP/BL-B76.md` does not exist in this agent's own worktree checkout (same
divergence as above — the worktree's line of history predates this entry's creation on `main`).
Editing it blind, from a snapshot I cannot verify is the entry's current state on `main`, risks
silently clobbering content I cannot see. **Recommending the edit here instead of applying it**:

The entry's top-level checkbox should **stay `[ ]` open** — this is Step 1 of three (fly it
mountainous and read the rate is Step 2; deciding whether the attack run should read the live gate
outcome is Step 3) — per the convention `BL-11.md` and similar multi-stage entries use: sub-steps
get their own `[x]`/DONE marker inline in prose while the top-level box stays open until the whole
entry closes.

Append, after the "Scope for this entry, as it now stands" paragraph:

> **Step 1 — [x] DONE, `9616235a` (`feature/bl-b76-tripwire-rejected`).** Shipped exactly the
> scope above: `outcome` (`"admitted"`/`"rejected"`/`"absent"`) and, for a rejection,
> `gate_outcome` and `live_los_clear` (`False`/`None`), for the attack-run target specifically.
> DoD PASSED on fixtures; mountainous live acceptance outstanding — see Step 2. #needs-flight
>
> **One caveat the mountainous reading must account for**: if the target's perception cluster
> splits and the minority child is rejected on the same poll it splits, the join can attribute that
> rejection to the target even though it belongs to a different, newly-separate contact —
> `_write_attack_run_tripwire`'s own docstring names the mechanism. This can only inflate the
> `"rejected"` count, never deflate it, and a group scattering under fire is exactly when it fires —
> read the Step 2 rate as an upper bound on true LOS-blocked, not an exact count.

## Milestone-completion question

**Does Step 1 landing change what Step 2 should be, or invalidate a downstream assumption?** No —
if anything it sharpens Step 2: the mountainous sortie should specifically watch for cluster-split
moments near the attack target (a group scattering under fire) when reading the `"rejected"` rate,
because that is exactly where the one known soundness gap inflates the count. Step 2 as scoped
("fly it mountainous and read the rate") remains correct; it should just be read as an upper bound
rather than a precise measurement.

## NOTES.md harvest

Two candidates from this feature, assessed against the duplicate-detection and obviousness filters:

1. **"An implementer destroyed its own uncommitted work with `git checkout -- <file>` while
   restoring a counterfactual mutation."** — **Not added.** `NOTES.md` line 103 already carries
   this exact lesson, from the binocular-optic Stage 3b incident (2026-09-23): "`git checkout --`
   on a file with unstaged edits silently discards everything back to `HEAD`... Use a scratch copy
   instead." This feature's implementer recovered via a `shasum`-verified file copy taken before
   mutating, which is the same prescribed fix already applied carefully — a duplicate, not a new
   insight.
2. **`Contact` deliberately holds no DCS `object_id` field (the no-omniscience boundary), which is
   why this feature had to invent its own `object_id -> contact_id` cache rather than reading the
   id off `Contact` directly.** — **Recommended for addition** (not applied, same divergence
   reason as the roadmap edit above — `NOTES.md` as it exists in this worktree is not provably the
   current `main` state). Not a duplicate: `NOTES.md` mentions no-omniscience in passing (line 505)
   but not this specific consequence. Not obvious from `CLAUDE.md` alone — the invariant there is
   "Petrovich must never be omniscient," which does not by itself predict that `Contact` has no
   `object_id` *field at all*, or that this forces any future code needing object_id→contact_id
   correlation to reinvent the same kind of cache this feature built. Proposed bullet, in the
   project's existing style:

   > **`Contact` deliberately carries no DCS `object_id` field — the no-omniscience boundary means
   > belief retains only what was observed, not ground-truth identity — so any later code that
   > needs to correlate a raw DCS `object_id` back to a `contact_id` (as `BL-B76`'s rejected-
   > candidate join needed) has to build its own admitted-row cache rather than reading the id off
   > `Contact`. Expect this gap to recur whenever new code needs that correlation outside of a
   > normal admission.**

## Environment problem — flagged, not acted on

`origin/HEAD` in this clone is ~100 commits behind local `main` (local `main` is never pushed), so
every isolated-agent worktree in this session has been created off an unrelated line of history.
This is the second time today an agent landed diverged on this exact branch — `git merge --ff-only`
was simply unavailable both times, and this DoD pass had to fall back to the isolated-snapshot
route rather than a direct checkout. This is the user's call (push `main`, or accept the snapshot
workaround as standing procedure); recorded here as the environment cost of not pushing, not acted
on.

## Verdict

**DoD: PASSED**, scoped to tip `9616235af070372fb17826cd0f412af70fa7bb37`. All mechanical checks
pass, Reviewer's required fix was addressed and re-reviewed APPROVED, Security APPROVED, Performance
APPROVED-MONITOR, scope matches the plan exactly, no invariant violated, logging-only confirmed by
diff. Two items are recommended but not applied (roadmap entry edit, NOTES.md bullet) because this
agent's own worktree diverged from `main` before this entry existed — apply them from a checkout
that actually has `BL-B76.md` and current `NOTES.md` (e.g. the already-checked-out
`/Users/sg/Code/DCS-petrobrain-bl-b76-tripwire` worktree, or the feature branch directly).

**What the user must do to validate this**: nothing on the ground is ready to validate yet — this
is logging-only and changes nothing Petrovich says or does. The mountainous acceptance sortie (Step
2) is the next live-validation point, against branch `feature/bl-b76-tripwire-rejected`
(`git checkout feature/bl-b76-tripwire-rejected` once merged, or fly it pre-merge from
`/Users/sg/Code/DCS-petrobrain-bl-b76-tripwire`), and must be flown over mountainous terrain, not
the flat desert both 2026-10-15 sorties used — that terrain is structurally why the rate is
currently unknown.

Do not merge this branch on the strength of this document alone — the roadmap/NOTES.md edits above
still need applying from a non-diverged checkout.
