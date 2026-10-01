### Review Summary

Reviewed `fix/contact-store-pruning` (tip `90057c4`, checked out directly — confirmed via
`git rev-parse HEAD` before anything else) against `body-layer/BACKLOG.md`'s `BL-B23` entry,
`plans/contact-store-pruning/implementation.md`, and `plans/group-cohesion-redesign/performance.md`.

The fix is exactly what the Backlog item asked for and nothing more: `ContactStore.tick`'s eighth
block now filters `self._contacts.values()` to `certainty_of(contact, now_sim) != "lost"` before
calling `GroupStore.reconcile`. `_contacts` itself is untouched.

Verified directly, not just read:

- **Memory invariant holds.** `describe_contact`/`get_contact_history` read `ContactStore.contacts`
  (the `_contacts.values()` property, `contacts.py:699`), never the filtered list local to `tick`'s
  eighth block — a `lost` contact stays fully answerable. `test_lost_contact_still_answerable_by_
  describe_contact` confirms this by calling `describe_contact` directly and checking
  `certainty == "lost"`. No other block in `tick` consumes the filtered list; it is a local
  comprehension passed inline to `reconcile`, not a reassignment of any shared variable, so nothing
  downstream in the same `tick` call sees a shortened sequence it doesn't expect.
- **Re-admission ordering holds at the one real call site.** `src/logger.py:500` (`ingest`) runs
  before `:516` (`tick`) in `Runner.run_once` — the only production caller. No test harness or
  replay path calls them in the other order (checked every `.ingest(`/`.tick(` call site in `src/`).
- **Predicate choice is coherent.** `tracked`/`estimated` stay in clustering, `lost` alone is
  excluded. No incoherence between what is grouped and what is reported: `GroupStore.reconcile`
  fully recomputes `member_contact_ids` every call from whatever list it's handed, so there's no
  stale "spoken-about but not clustered" or "clustered but not reportable" state — a `lost` contact
  is simply absent from the next cluster, same as any other contact that left the live set.
- **Group coherence across a lost leader, specifically.** Read `belief/groups.py` and `belief/
  speech.py`. `leading_contact_id` is *not* a field read off persisted `Group` state when deciding
  what to say next — `render_group_disclosure`/`group_membership_state` recompute it fresh each call
  from `member_contacts` (`_leading_index`), and compare against the *persisted*
  `last_spoken_leading_contact_id` only to decide whether a "leader changed" delta should fire
  (`speech.py:1591-1594`). So when a leader goes `lost` and `reconcile` drops it from the cluster,
  the next disclosure naturally recomputes a new leader from the survivors and the existing
  leader-changed delta path fires — this is the same mechanism that already handles a leader lost to
  a spatial split, not a new code path and not a gap. `groups.py` genuinely needed no change.
- **Measurements independently reproduced**, by a different script than the implementer's own
  benchmark (built from scratch against `test_contacts._observation`, not reusing their fixture
  code): unfiltered `GroupStore.reconcile` on 500/1200 contacts measured 70.16 ms / 405.98 ms here
  against their claimed 69.15 ms / 402.99 ms; `ContactStore.tick()` with 20 live + up to 1200 total
  measured 1.26 ms at n=1200 here against their claimed 1.40 ms. Both within noise — the "before"
  column is a real reproduction of the original Performance Reviewer numbers, not a cherry-pick.
- **The `association_over_time` gap** (two close contacts ambiguous reacquisition candidates for
  each other after a long gap) is correctly left unfixed — it's pre-existing, orthogonal to this
  fix's scope, and both new tests that hit it route around it via `continues_observation_id`
  exactly as the implementation log says. It is recorded in `implementation.md`'s "Notable
  Discoveries" and in two test docstrings, which is enough to not mislead a future reader, but it
  is not in `BACKLOG.md` under its own ID — see Optional Refinements.

Checks (`body-layer/`, fresh `.venv` built from `pyproject.toml`, Python 3.14 — no 3.11 available
in this environment but nothing in the diff is version-sensitive):
- `ruff format --check src tests` — pass (114 files already formatted)
- `ruff check src tests` — pass
- `mypy src` — pass ("Success: no issues found in 53 source files")
- `pytest tests -q` — **1384 passed, 4 xfailed** (matches claimed, matches 1379/4 baseline + 5 new)

### Required Fixes

None.

### Optional Refinements

- **File the `association_over_time` long-gap ambiguity as its own Backlog item (`BL-B24`, next
  free id).** It's correctly out of scope for this fix and adequately recorded in the plan's
  implementation log, but a plan-folder note is easy to lose track of, and this project's own
  convention is that discovered defects get a tracked id rather than living only in a decision log.
  Not a blocker — optional housekeeping.

### Verdict
APPROVED

### Review Confidence
Full read — plan, Backlog entry, implementation log, the full diff (`contacts.py` + all 5 new
tests), and the two downstream files (`groups.py`, `speech.py`) the leader-coherence question
depends on. Measurements independently reproduced with a separate script, not re-run of theirs.
