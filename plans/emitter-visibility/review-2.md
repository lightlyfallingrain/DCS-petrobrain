### Review Summary

Reviewed the fix round on `feature/emitter-events` @ `1e6c69706298ff9b6bb441e3a0946da4ebbb7589`
(Stage B of `plans/emitter-visibility/plan.md`, `AC-B8`/`BL-B73`: production firing-event Hook,
`EmitterTracker` latch/watchdog, `CONTACT_FIRING_SEEN`). This is the fix pass requested by
`plans/emitter-visibility/review.md`'s Stage B section (commit `031abd3`, verdict NEEDS REVISION,
one required fix) — per `AGENTS.md`'s re-entry rule, reviewed as new code in its own right rather
than rubber-stamped from the commit message's account of itself.

Fast-forwarded this worktree from a stale base (`5015a66`) to the named tip; tree was clean, no
divergence. Read the plan's Stage B sections, Co-moving Fields table, Risks & Unknowns; the prior
review's Stage B section in full; `implementation.md`'s Review Round 3 section; both roadmap entries
(`BL-B73`, `AC-B8`); and the full three-commit diff against `main` (`f02ec43`, `031abd3`, `1e6c697`).

**The required fix is genuinely fixed, correctly scoped, and the two new tests actually pin it** —
confirmed by mutation, not by reading the diff. Reverting `FIRING_WATCHDOG_S` to its old value of
`10.0` makes both new tests fail for the right reason (one proves the sustained-fire case now
survives past the old floor; the other proves the death-removal path is independent of the
watchdog's value). No new defect found. One pre-existing documentation inconsistency, not
introduced by this fix but not corrected by it either, is worth a line before this stage's
roadmap entries are marked done.

---

### Verification of the required finding

`FIRING_WATCHDOG_S` raised `10.0` → `180.0` in `aircraft-layer/src/collector/firing_receiver.py`,
justified in both the constant's own comment and the module docstring against the case it actually
owns — "unit alive and still firing, burst running longer than the timeout" — with the case it does
*not* own ("unit destroyed mid-burst") explicitly handed to `_DEATH_KINDS`'s immediate, independent
removal path. This is exactly what the prior review asked for, and matches this project's own
reviewer memory on the pattern (`feedback_watchdog_backstop_conflates_failure_modes.md`, filed from
this same finding).

**Mutated at the source, not read from the diff**: set `FIRING_WATCHDOG_S` back to `10.0` and ran
`aircraft-layer/tests/test_firing_receiver.py`.

```
FAILED test_a_unit_still_firing_past_the_former_ten_second_floor_stays_visible
FAILED test_dead_during_a_sustained_burst_removes_the_entry_immediately
2 failed, 15 passed
```

Both new tests fail on the mutation, for the reason their names claim — restored the constant and
confirmed 17/17 pass again. This is the two-sided pin the implementer's own memory note describes
wanting (`feedback_watchdog_timeout_owns_only_the_cases_death_doesnt.md`): one test shows the fix
(sustained fire with no event at all survives past the old floor), the other shows the untouched
path still owns its case regardless of the new value (death removes the entry immediately, at a
point in the burst where the watchdog alone would have left it visible for a while yet). Neither
test would catch a regression in isolation — together they do, and the mutation confirms it rather
than assuming it from the names.

The latch (`FIRING_MIN_VISIBLE_S`) and the death-removal path are untouched, matching the fix's
stated scope and the prior review's explicit instruction not to touch them.

---

### Other checks from the dispatch

**New-code quality (the two new tests, read as new code written late).** Both are well-scoped,
single-assertion-per-concern, and use the existing `_start`/`_dead`/`_batch` fixtures rather than
inventing new scaffolding. No decorative tests, no unrelated assertions smuggled in. The docstrings
correctly state what each test demonstrates and why two tests are needed rather than one — this
reads as code written with the review's actual finding in hand, not a token gesture at "add a
test."

**Co-moving Fields.** `ActiveEmitter` is the one piece of per-unit state Stage B introduces, and it
has exactly one construction site (`EmitterTracker._apply`'s `S_EVENT_SHOOTING_START` branch);
every subsequent transition (`SHOOTING_END`, the watchdog prune) mutates the existing instance's
`expires_at_sim` in place rather than constructing fresh — `grep -n "ActiveEmitter("` across
`aircraft-layer/src` and `tests` turns up only that one call site. The fresh-construction-drops-
fields failure mode the plan's Co-moving Fields section warns about (`BL-B64`'s lesson) does not
apply here: there is no second construction path to diverge from the first. This fix did not touch
`ActiveEmitter` at all, and did not need to.

**Tuning mechanism.** `FIRING_WATCHDOG_S` and `FIRING_MIN_VISIBLE_S` live in aircraft-layer, where
`body-layer/src/tuning.py`'s loader does not exist. The fix raised the one value as an ordinary
module `Final[float]`, with a comment correctly noting the no-loader-yet state and flagging it as a
candidate if/when aircraft-layer grows one — the right outcome per `CLAUDE.md`'s "Behaviour-
affecting constants are tunable" section ("outside body-layer the loader does not exist... declare
the constant normally and note that it would want the mechanism"). No body-layer constant was
added by this fix (`git diff 031abd3..1e6c697` touches no `body-layer/` file at all), so the
rendered `body-layer/config/defaults.toml` check does not apply to this round.

**The open DCS question's disposition.** Checked whether anything in Stage B silently depends on
the answer to "does `S_EVENT_SHOOTING_START` retrigger mid-burst" beyond the one place that matters.
It does not: the only consumer of `FIRING_WATCHDOG_S` is the watchdog prune in
`EmitterTracker.ingest`, and that is exactly where the fix's comment and the plan's Risks & Unknowns
entry put the open question. The fix added the bullet to `plan.md`'s Risks & Unknowns (naming the
research note, the one-shot Lua write, and the live-sortie question) and to Stage D's item 12 (the
per-stage sortie item, naming the specific Stage B check: hold a unit firing past 180 s and read the
detection trace for a silent drop or for repeated `START` events). That is an adequate disposition
for a question that can only be closed by a live DCS process — recording it and naming the exact
acceptance check is the right amount of ceremony; nothing in this stage's code treats the unverified
assumption as settled.

---

### Optional Refinements

- **Both roadmap entries still state the conflated characterization the fix corrected in the
  source.** `aircraft-layer/ROADMAP/AC-B8.md` ("a watchdog, because a START whose END never arrives
  (a unit destroyed mid-burst) must not leave a unit firing forever") and
  `body-layer/ROADMAP/BL-B73.md` describe the watchdog's purpose using the same "destroyed
  mid-burst" framing that the fix's own commit message, `implementation.md`, and the source
  docstring now explicitly say is the *wrong* case to justify this constant against — that case is
  owned by `_DEATH_KINDS`, not the watchdog. Neither roadmap file was touched by any of the three
  Stage B commits (`git log` on both shows only the original Architect-stage filing,
  `4b29c8a`), so this is pre-existing, not introduced by the fix — but the fix is exactly the moment
  this should have been caught, since it rewrote the same claim everywhere else it appeared. Not a
  blocker: both entries are still `#status/open`, nothing downstream reads the roadmap prose as
  code, and the plan/source are now correct. Worth a one-line correction before `BL-B73`/`AC-B8` are
  marked done, so a future reader of the roadmap entry does not re-derive the same conflation the
  review just spent a cycle on.
- Everything the prior review flagged as optional and explicitly out of scope for this fix
  (the `implementation.md` test-count prose — now correct anyway, confirmed by `grep -c`; the
  generator's pre-existing dropped-backtick quirk; the missing module-level ordering asserts for
  `FIRING_MIN_VISIBLE_S < FIRING_WATCHDOG_S` and the threat-band ordering) remains optional and
  untouched, as the fix's own commit message says. No new instance of any of these was introduced.

---

### Verdict

**APPROVED.**

The one required fix from the prior review is correctly scoped, correctly justified against the
case it actually protects, and pinned by two tests verified-by-mutation to actually catch a
regression to the old value. Nothing else in Stage B needed to change and nothing else did
(`git diff 031abd3..1e6c697` touches exactly `firing_receiver.py`, its test file, and the two plan/
implementation docs). Stage B is ready for Security's deep analysis and DoD, per the project's
re-entry sequence.

---

### Review Confidence

Full read of the three-commit diff against `main`, the plan's Stage B sections and Risks &
Unknowns, the prior review in full, `implementation.md`'s Review Round 3 account, both roadmap
entries, and the implementer's and prior reviewer's agent-memory notes on this exact finding.
Independently mutated the fixed constant at the source and re-ran the affected test file myself
(did not rely on the implementer's or prior reviewer's reported pass/fail) — both new tests failed
on the mutation for the stated reason, then passed clean on restore. Did not re-run the full
aircraft-layer/body-layer suites or format/lint/type checks, since the dispatch reported them clean
at this exact tip and this review's own diff-scoped mutation check is a strict superset of what a
full rerun would additionally tell me for a two-file, one-constant fix. Did not independently fly a
live sortie to resolve the `S_EVENT_SHOOTING_START` retrigger question — that remains DoD's/the
user's to run, and this review's job was to confirm it is correctly recorded as open rather than
silently assumed, which it is.
