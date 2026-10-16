### Review Summary

Reviewed `feature/bl-b76-tripwire-rejected` @ `d742ce57232b36b06bb85959f3196930d8df2bbb`, one
commit ahead of `main` @ `95ef798213c46a6de91a488de63eeb4c131dabf7`. Scope is exactly what the
roadmap entry (`body-layer/ROADMAP/BL-B76.md`) asked for: widen
`BeliefTruthLogWriter._write_attack_run_tripwire` to split `"rejected"` from `"absent"` for the
attack-run target, logging only. Touches `body-layer/src/belief_truth_log.py`,
`body-layer/tests/test_belief_truth_log.py`, and `plans/bl-b76-tripwire/implementation.md` — no
other file changed (`git diff main..HEAD --stat`). No change to `perception/visibility.py`,
admission, `Contact`, `belief/attack_run.py`'s fail-open arm, or anything Petrovich says — verified
by diff, not assertion. No new tuning constant (`body-layer/config/defaults.toml` diff is empty;
the change reuses `belief.decay.OBJECT_ID_MEMORY_S`).

Re-ran the implementer's own checks from this tip: `ruff format --check` passes (the one
reformat hit, `research/2026-10-05-security-audit.md`, predates this branch — `git log` shows it
introduced by `f9cc3119`, already on `main`, untouched by this diff), `ruff check` clean,
`mypy --strict` clean (60 source files), `pytest -q` → 2060 passed / 4 xfailed, matching the
reported baseline delta (+3 new test functions).

**Verified by mutation, not by reading.** Replaced the rejected-entry membership test
(`entry.object_id not in target_object_ids`) with `entry.object_id not in frozenset()` — the
reported counterfactual — and reran the three affected tests: all three failed for the stated
reason (`'rejected'` not found, outcome falls through to `'absent'`). Restored with
`git checkout -- body-layer/src/belief_truth_log.py`; full module suite back to 32/32 passing,
clean tree.

One real soundness gap found in the join's own reasoning (below) — not severe enough to block a
logging-only change whose output is read by a human deciding whether to build cockpit behaviour,
but severe enough that the code's own claim of impossibility needs correcting before anyone trusts
these numbers at face value.

### Required Fixes

- **The docstring's soundness claim overstates what the cache actually guarantees.**
  `_write_attack_run_tripwire`'s docstring states a stale/wrong cache entry "can only ever cause a
  **miss**... never a wrong contact's rejection being attributed to this one." This is not true in
  general. The cache (`_object_id_to_contact_id`) is populated only from `GateOutcome.ADMITTED`
  rows, which pass through `NakedEyePerceptionSource`'s clustering/emission step
  (`perception/naked_eye_source.py`, module docstring point 6) — and that step explicitly performs
  **majority-overlap voting across cluster splits**: "a cluster that just absorbed a neighbour, or
  just split off from one... a cluster that splits into several children never lets more than one
  of them claim the parent's continuity" (same file, `_build_observation`'s own docstring). So when
  a group the attack target belongs to splits, the *other* child's `object_id`s get a **new**
  observation/contact identity this same poll — but only if that child's candidate is **admitted**
  this poll. If it is instead **rejected** at a gate the same poll the split would otherwise have
  happened, `_update_object_id_contact_cache` never sees it (the cache update loop only reads
  `ADMITTED` entries), so the stale mapping from the *previous* poll — when that `object_id` was
  still part of the target's cluster — survives into `_object_ids_for_contact(target)`. The
  rejected row for what is now, or would be, a *different* real-world contact gets logged as a
  `"rejected"` observation of the attack target.

  This is not a hypothetical: splitting under fire (a group scattering) is exactly the scenario an
  attack run is likely to encounter, and the mechanism that makes it possible
  (`_object_id_to_last_observation_id`'s majority-overlap vote) is the same one the implementer's
  own "Notable Discoveries" section names as the more-robust alternative this change chose not to
  reach for, scope reasons stated. The implementer's "Notable Discoveries" paragraph is honest about
  this as a *future* risk ("if the cache's simpler rule starts mis-attributing object_ids across
  group splits in practice") — but the docstring's own soundness claim, in the code itself, asserts
  the thing that paragraph says might happen cannot happen. One of the two is wrong, and it is the
  stronger, in-code claim that needs to give way: a reader of the module six months from now has
  only the docstring, not the implementation notes.

  **Fix is cheap and stays in scope** (no design change needed for Step 1, which is explicitly
  measure-first): soften the docstring's claim to name this residual risk — misattribution across a
  same-poll split-and-reject is possible, bounded by `OBJECT_ID_MEMORY_S` same as the already-
  accepted object_id-reuse risk — rather than asserting it away. Because this is a measurement
  feature whose entire purpose is informing a future decision (how often LOS-none happens for the
  target), an inflated `"rejected"` count from occasional split misattribution is exactly the kind
  of bias the user flying the mountainous acceptance sortie should be told about before reading the
  numbers, not discover later.

### Optional Refinements

- **No test exercises the one additional bug the implementer found and fixed while building this**
  (moving `_update_object_id_contact_cache`'s call to the top of `write_poll`, unconditional on
  whether a run is active, so a newly-started run's first poll isn't forced to read `"absent"` for
  a target that was already being observed). Every new/extended test passes
  `attack_run_target_contact_id="CONTACT_1"` on *both* the seeding and the rejecting poll, so the
  "run becomes active only on the second poll" path this fix specifically addresses is never
  exercised. A future refactor that moved the cache update back inside the `if
  attack_run_target_contact_id is not None` guard would pass the full suite untouched. Worth a
  fourth small test: seed with `attack_run_target_contact_id=None`, then reject on the next poll
  with the target now set, asserting `outcome == "rejected"` rather than `"absent"`.
- **No test exercises the `OBJECT_ID_MEMORY_S` expiry boundary** for this new cache — every test
  uses a fixed `t_sim=10.0` across polls (via `_ownship()`/`_trace_entry`'s defaults), so elapsed
  time between seeding and rejection is always `0`. `_object_ids_for_contact`'s own exclusion logic
  (`now_sim - last_seen_sim <= OBJECT_ID_MEMORY_S`) is exercised nowhere in this diff. Low risk
  since the comparison is a one-line reuse of an already-tested pattern
  (`belief.decay.object_id_continuity_valid`), but it is new code in a new location.
- **Backward-compatibility judgment**: keeping `present_in_snapshot`'s name while widening its
  meaning (`outcome != "absent"`, was `outcome == "admitted"`) is defensible for a logging-only
  change with no live consumer found — grepped `.claude/skills/`, `plans/`, `docs/`, and
  `body-layer/` for `present_in_snapshot`/`attack_run_los_tripwire`; the only hits are this
  change's own files, `BL-B76.md`'s entry, and the two `attack-run-sortie-fixes` plan documents
  that *describe* the field rather than parse it. `sortie-log-triage`'s `SKILL.md` has no reference
  to either name. So the implementer's flagged concern turns out to be moot, and no action is
  needed — noting it here only because the implementer asked for it to be checked, and it was.
  A renamed field would have been marginally safer for a human eyeballing old-vs-new JSONL side by
  side, but is not worth a second pass for a measurement log with a single reader (the user,
  manually, per the roadmap entry's own "fly it mountainous and read the rate" instruction).

### Verdict
APPROVED WITH MINOR FIXES

The join is logging-only, correctly scoped, well-tested for the three states it exists to
distinguish, and the one soundness gap found does not touch admission, belief, or anything spoken
in the cockpit — it only risks mislabelling some `"rejected"` rows that should have been
`"absent"` (or attributed to a different contact) in a rare, specific window (same-poll
split-and-reject). Fix the docstring's overclaim before the user reads the mountainous-sortie
numbers as ground truth; the optional refinements can wait.

### On the implementer's counterfactual-restore note

The implementer's report describes restoring a counterfactual mutation with `git checkout --
<file>` while the real work was still uncommitted, wiping its own implementation, and recovering
only because it had taken a `shasum`-verified file copy first. This is a generalisable hazard
(`git checkout --` discards *all* uncommitted changes to that path, not just the injected bug), but
the fix the implementer used — commit-or-copy before mutating, verify byte-identity after
restoring — is already this project's standing counterfactual procedure (`implementer.md`'s "Show
the red"), just applied carefully. Judged this as **not warranting a new memory entry**: the
general rule ("commit real work before mutating for a counterfactual, or you can lose it to the
same command that undoes the mutation") is better left where it already lives, as a sharpened
example inside `implementation.md`/`implementer.md`'s existing counterfactual guidance, rather than
duplicated into reviewer memory, which did not do the mutation and has nothing role-specific to add
about avoiding it.

### Review Confidence

Full read. Read the diff in full, the roadmap entry's full `/explore`d history, the implementer's
own account, the relevant upstream code (`perception/naked_eye_source.py`,
`belief/groups.py`, `belief/contacts.py`, `belief/decay.py`) rather than accepting the
implementation note's framing, re-ran all stated checks from this tip, and independently verified
the mutation claim rather than trusting the report.
