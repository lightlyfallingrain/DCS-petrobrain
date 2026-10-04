# Definition of Done: contact-report-flood

Branch `fix/contact-report-flood`, tip `4cb5b214bdfda3562d8297fb66f027bd7c41d1f9` (confirmed via
`git rev-parse HEAD` as the first action; matched the tip named in the dispatch). Implementation
commit: `c3bf79b`.

## Code Quality

- `ruff format --check src tests` (from `body-layer/`, fresh `.venv` built against this branch's
  own `pyproject.toml`) — **PASS**: "114 files already formatted"
- `ruff check src tests` — **PASS**: "All checks passed!"
- `mypy src` (run from inside `body-layer/`, per the CWD-only config-discovery rule) — **PASS**:
  "Success: no issues found in 53 source files"
- `pytest tests -q` — **PASS**: "1399 passed, 4 xfailed in 14.27s" — matches the figure both
  Reviewer and Security independently reported against this same tip, and matches this branch's
  own stated baseline of 1389/4 plus this feature's 10 new tests. Confirmed **not** the wrong-code
  trap this project has hit before (`main`'s 1398/4, from `silence` merging after this branch was
  cut, is a different number from this branch's own 1389/4 baseline and from the 1399/4 this
  branch reaches with its own tests added).
- No unhandled errors/panics introduced: `contacts_plausibly_same` and the new `CONTACT_DETECTED`
  check are pure functions over existing belief-layer types; no new I/O, no new exception path.
- No debug output or TODO/FIXME introduced: `git diff c3bf79b~1 c3bf79b -- body-layer/src | grep
  -nE "TODO|FIXME|print\(|pdb"` — no matches.
- `git status --porcelain` — clean, nothing untracked or unstaged.

## Scope & Correctness

- Implementation matches `plans/contact-report-flood/plan.md` Stages 1-3. The one deviation
  (`other.first_seen_sim < this_contact.first_seen_sim`, excluding same-poll peers) is documented
  in the implementation commit and Reviewer's trace as a conformance fix, not a design change —
  tested against real sortie data, the plan's literal check mutually silenced every same-poll
  contact, which is worse than the flood it exists to fix. Reviewer traced the mechanism and
  confirmed no design surface was reopened.
- No unplanned scope added: Reviewer's diff read found "one extra boolean clause in a generator
  expression, no new function, no new field" beyond the planned mechanism.
- No CLAUDE.md invariants violated: `contacts_plausibly_same` reads only
  `Contact.last_class_raw`/`last_position`/`last_seen_sim` on both sides — confirmed by Security
  against the no-omniscience boundary (`belief/percept.py`), no ground-truth field crosses it.
- All new files staged (`git add`) — confirmed via `git status --porcelain` on this commit.

## Testing

- Core logic covered: `test_association_over_time.py` (new `contacts_plausibly_same` tests,
  mirroring `passes_gate`'s own calibration), `test_callouts.py` (the merge-echo suppression
  fixture built from `debug.md`'s six-vehicle cluster, the `CONTACT_REACQUIRED`-untouched control,
  the well-separated-contacts control), `test_contacts.py` (`ContactStore.contact` lookup).
- Tests are meaningful, not decorative: Reviewer confirmed the `CONTACT_REACQUIRED` control
  exercises the real `store.ingest`/`store.tick`/`scheduler.tick` path end-to-end, not a
  directly-constructed `Event`.
- No existing tests broken: 1399/4 against a clean `main`-equivalent baseline of 1389/4 (this
  branch's own, predating `silence`'s later merge to `main`).

## Documentation

- Reviewer's one required fix (Staging step 4: note, don't close, `BL-B24` and
  `contact-duplication-ambiguity-runaway`) is applied — confirmed directly:
  `grep -n "contact-report-flood" body-layer/BACKLOG.md` and
  `plans/contact-duplication-ambiguity-runaway/plan.md` both return a 2026-10-04 note pointing at
  this fix and stating plainly that the root candidate-ambiguity policy remains open.
- Non-obvious behaviour (one-shot permanent suppression, the split-vs-echo indistinguishability,
  the same-poll exclusion's rationale) is explained in the plan's "honest cost" section, the
  module docstrings Reviewer traced, and the roadmap entries added by this DoD pass.

## Security

- `plans/contact-report-flood/security-plan-review.md` does not exist — **expected**, not a gap.
  This feature took the bug-fix path (Debugger → Implementer → Reviewer → Security deep analysis
  → DoD), which has no Architect-plan stage and therefore no plan-review step, consistent with
  this project's current once-per-feature security cadence (root `CLAUDE.md` "Agents";
  `.claude/agent-memory/dod/project_current_cadence_one_security_pass_per_feature.md`).
- `plans/contact-report-flood/security-review.md` exists and is **APPROVED**, with one non-blocking
  risk note (timing-dependent suppression of a genuine new sighting near a long-tracked contact)
  recommended to accept-as-is — same accepted tradeoff the plan itself already names, not a new
  one.
- No performance-reviewer pass, and this is correctly a non-gap, not an omission: Security
  examined the cost directly in its deep analysis (`association_over_time.py` / per-event cost
  row) — `any(... for other in store.contacts)` is O(n) over the contact store, but runs only on a
  `CONTACT_DETECTED` event (a new-contact founding), not per tick and not per percept. The real
  sortie this plan measures against produced 34 such events across a whole flight, and `n` is the
  same small, sortie-bounded contact count `BL-B23` already established is not a growth risk.
  Security's own verdict: "Not quadratic in any meaningful sense for this workload; no separate
  performance pass is warranted for this change." Recording that reasoning here rather than
  treating the absent Performance pass as a gap, per this DoD run's own dispatch.

## Verdict

**PASS.**

## Acceptance boundary — what fixtures structurally cannot reach

Every number above (1399/4, the ruff/mypy results, the reviewed suppression-mechanism trace) is a
fixture/static-analysis result. **None of it can tell us what the cockpit actually sounds like.**
The 17-of-34-foundings figure is a retrospective reconstruction run against `belief-truth.jsonl`'s
*recorded per-tick believed states* from a real sortie — not a byte-for-byte replay of the raw
observation stream, because no such stream exists in that snapshot. It is the best approximation
available, and it is honestly labelled as such in the implementation log and the commit message,
but it is still an approximation: the real pipeline, run live, could suppress a different count,
and the one thing no fixture or reconstruction can test is whether a suppressed genuine split is
ever actually missed by a pilot flying the aircraft. That is exactly the F10-vocabulary-precedent
class of gap this role exists to name rather than paper over: a fixture pass is not a flight pass.

A live sortie is owed, and per this project's live-acceptance-debt practice it is **debt, not
waived** — recorded in `body-layer/ROADMAP.md`'s "Live acceptance debt" list, not merely as a line
in this file.
