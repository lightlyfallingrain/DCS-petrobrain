### Review Summary

Reviewed `fix/contact-report-flood` at `d8be11e` (confirmed via `git rev-parse HEAD`) against
`plans/contact-report-flood/plan.md`, `debug.md`, `implementation.md`. Implementation commit is
`c3bf79b`.

The core mechanism — `contacts_plausibly_same` generalising `passes_gate`'s calibrated
percept-vs-contact gate to contact-vs-contact, and `CalloutScheduler._render_event`'s
`CONTACT_DETECTED`-only suppression — matches the plan's Stage 1-3 design, reuses
`GATE_SIGMA_THRESHOLD` and `_contact_covariance` unchanged (no new constant), and is correctly
scoped to never touch `CONTACT_REACQUIRED`.

**The implementer's deviation (the `other.first_seen_sim < this_contact.first_seen_sim`
condition) is sound and correctly classified as a conformance fix, not a design change.**

- **Mechanism check**: traced through `naked_eye_source.py`'s merge/continuity logic. A
  merge-echo's suppressing survivor is, by construction, an identity that already existed
  before the merge poll that abandoned the echo's sibling — the survivor cannot be founded in
  the same poll as the later re-split that produces the echo, because clustering runs once per
  poll and a merge and a subsequent re-split of the same objects are necessarily different
  poll ticks. The claim "a merge-echo is always strictly later-founded than the identity it
  echoes" holds for every path through that code, including the degenerate case where the
  merge survivor itself has no prior continuity link (freshly founded at the merge poll) — the
  later re-split is still founded at a strictly later `t_sim`.
- **No design surface reopened**: verified directly — the change only narrows which *other*
  contact can suppress a founding (excludes same-poll peers); it does not touch
  `contacts_plausibly_same`, does not add a cross-contact merge, does not add a second contact
  kind. Confirmed by reading the diff: one extra boolean clause in a generator expression, no
  new function, no new field.
  reproduction: `test_merge_echo_refounding_near_a_live_contact_is_not_spoken` and
  `test_simultaneously_founded_mutually_close_contacts_both_speak` reuse the already-proven
  overlapping-gate geometry from `test_contacts.py`'s own ambiguous-candidate test rather than
  inventing new numbers, and `test_contact_reacquired_is_never_suppressed_by_a_nearby_contact`
  exercises the real `store.ingest`/`store.tick`/`scheduler.tick` path end-to-end (not a
  directly-constructed `Event`), so it genuinely proves `CONTACT_REACQUIRED` survives the real
  dispatcher, not just the isolated predicate.
- **Edge case probed**: two contacts founded at *exactly* identical `first_seen_sim` suppress
  neither (strict `<`), which is correct for the ordinary case — a merge and the re-split it
  later causes are always different poll ticks, since clustering runs once per poll. The one
  way identical timestamps could occur for two *otherwise-unrelated* polls is the frozen-`t_sim`
  pause anomaly `debug.md`'s "second, unrelated density anomaly" section already found and ruled
  harmless (no speech produced during or after it). If a genuine merge and its echo ever did
  collide on a frozen timestamp, the failure mode is under-suppression (the echo speaks), which
  is the safe direction relative to this fix's purpose — not a correctness bug, and not worth a
  fix given the anomaly's own documented scope. Flagged as an observation, not a required fix.

**`contacts_plausibly_same` composition verified correct.** It sums `_contact_covariance(a,
elapsed_a) + _contact_covariance(b, elapsed_b)` — both sides read through the same function
`passes_gate` uses for its contact side, not a reuse of `_percept_covariance`'s differently-shaped
look-ellipse. This is the right generalisation, not percept-vs-contact asymmetry smuggled in.
No new constant: `GATE_SIGMA_THRESHOLD` is imported, not redeclared. `class_compatibility`'s
three-valued return means a pairing where either side is still `OP_GROUPSOMETHING` (`_op_class_
of` maps it to `None`) resolves to `"unknown"`, not `"incompatible"`, so the spatial test alone
decides — this is inherited unchanged from `passes_gate`'s own existing semantics (the function
being generalised was never changed), so the 1524/1529 `OP_GROUPSOMETHING` rows in the real
sortie get exactly the same class-gate behaviour the already-calibrated percept-vs-contact gate
already gives them. Not a new risk introduced by this change.

**Scoping to `CONTACT_DETECTED` confirmed correct and real-path tested.** `CONTACT_REACQUIRED`
only ever fires for a contact id that already existed and had gone `lost`
(`belief.events.lifecycle_event_kind`), so the new check's placement in a separate `if event.kind
== CONTACT_DETECTED` block (not merged into the pre-existing `if event.kind in (CONTACT_DETECTED,
CONTACT_REACQUIRED)` signature-dedup block above it) is correct and minimal.

**One-shot permanence confirmed, and the docstring correction is accurate.** `tick()`'s loop adds
any `_render_event`-`None` result straight to `self._consumed`, which is checked before scoring on
every subsequent `tick()` call — a suppressed merge-echo is never retried by this scheduler
instance, matching the pre-existing vanished-candidate/duplicate-signature behaviour exactly, not
a new pattern. The implementer's docstring correction (the plan's prose read as time-windowed
retry; the code is permanent) is a real, accurate fix to stale documentation, not a behaviour
change.

**Replay measurement**: the retrospective reconstruction (running the real `contacts_plausibly_
same`/`certainty_of` functions against `belief-truth.jsonl`'s recorded per-tick believed states,
since no raw observation/percept stream exists in the snapshot to replay byte-for-byte) is a
reasonable substitute given the data available, and is honestly scoped as such in both the
implementation log and the commit message — it is not presented as an exact pipeline
reproduction. The one place to note plainly: the measured outcome for the named six-vehicle
cluster (4 spoken, 1 suppressed) misses the plan's own "at most 2" acceptance bound, and the
implementer's explanation (the plan's number was a narrative estimate made before this per-object
data existed) is accurate but means the plan's stated acceptance criterion, taken literally, is
not met. The actual outcome — every genuinely distinct simultaneous sighting heard once, the one
genuine echo suppressed — is the right behaviour and a better outcome than the plan's own
number implies; this is a plan-estimate miss, not an implementation defect.

**BL-B24 / `contact-duplication-ambiguity-runaway` are untouched in substance** — no change to
`ContactStore.ingest`'s "2+ candidates → always new contact" policy anywhere in the diff.

### Required Fixes

- **Plan's own Staging step 4 ("Note, do not close, BL-B24 and `contact-duplication-ambiguity-
  runaway`. Add one line to each...") was not done.** `git diff main...HEAD` shows no change to
  `body-layer/BACKLOG.md` or `plans/contact-duplication-ambiguity-runaway/plan.md`; `grep -rn
  "contact-report-flood"` against both returns nothing. `implementation.md` states the right
  conclusion in prose, but the plan explicitly scoped this as a staging deliverable, not merely
  an implementation-log remark — the two files most likely to be read by whoever next picks up
  the ambiguity-rule root policy don't yet point at this fix. Cheap to add (one line each);
  should land before merge.

### Optional Refinements

- The frozen-`t_sim` pause anomaly as a theoretical (never observed, never audible) way for the
  strict-inequality edge case to under-suppress — not worth defending against given `debug.md`'s
  own finding that the anomaly produces no speech. Worth a one-line comment only if it recurs.
- The plan's "at most 2, not 6" acceptance number for the named cluster is superseded by the
  more precise 4-spoken/1-suppressed measurement; worth a one-line note in `plan.md` or
  `implementation.md` so a future reader doesn't take the plan's narrative number as the actual
  acceptance bound hit. Not required since `implementation.md` already explains the discrepancy
  honestly.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read — plan, debug, implementation docs, both touched source files' full diffs, all new/
changed tests read in full, mechanism traced against `naked_eye_source.py`'s continuity logic for
the central "always strictly later-founded" claim, and `ruff format --check`, `ruff check`, `mypy
src`, `pytest tests -q` all run directly against this branch's own worktree (not trusted from the
implementation log): 1399 passed, 4 xfailed, matching the branch's own stated baseline.
