# Review round 2 — the two review change-request fixes

**Branch:** `feature/sortie-refinements` · **Tip reviewed:** `f955a73`, verified by
`git rev-parse HEAD`.

The worktree was created at `19143fa` — a `main` commit, **not an ancestor of the tip** (16 commits
unique to each side). That is the AGENTS.md rule 4 trap for the seventh agent in a row. `19143fa` is
contained in `main`, so nothing was at risk; the agent branch was reset to `f955a73`
(`git checkout -B worktree-agent-<id> f955a73`) and every command below ran against that tree, with
imports proven worktree-local (`belief.crew_console.__file__`,
`belief.speech.__file__`, `belief.callouts.__file__`, `query.describe.__file__` all under
`.claude/worktrees/agent-a54556cd70ac3624c/`) and pytest `rootdir` =
`<worktree>/body-layer`, `configfile: pyproject.toml`.

**Scope:** the two fixes (`41e7495`, `726af61`) and the log commit (`f955a73`), against
`security-review.md` finding 1 (REQUIRED FIX) and `performance-review.md` finding 1
(NEEDS MITIGATION). Not a re-review of the feature.

## Checks (body-layer; `audio-adapter` is not in this diff)

Borrowed the main checkout's binaries by absolute path, `cwd` inside the worktree's `body-layer/`:

| check | result |
|---|---|
| `ruff format --check src tests` | 115 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` | Success: no issues found in 53 source files |
| `pytest tests -q` | **1475 passed, 4 xfailed** — matches the expected count exactly |

## The test trap — verified empirically, not read

This was the single most valuable check available and it passes.

With the suppression's condition forced false
(`if False and keeper_id is not None and ...`), `test_a_watched_group_that_starts_moving_speaks_
one_line_not_one_per_member` fails with exactly what the implementer reported:

```
E       AssertionError: assert 3 == 1
E        +  where 3 = len(['ground, moving.', 'ground, moving.', 'ground, moving.'])
```

The three sibling tests still pass with it disabled, correctly — they test
`group_callout_member_id` directly, not the filter. Condition restored afterwards.

The same disable-and-rerun on fix 1 (`return found, len(member_ids)` in place of
`return found, marked`): `test_watch_nearest_group_readback_counts_only_members_actually_marked`
fails with `assert ['Watching two.'] != ['Watching two.']`. Both tests have teeth.

The implementer's account of *why* the first version of the flood test was vacuous — one line per
`tick` call, and a second tick past `busy_until_sim` is also past `CALLOUT_MAX_AGE_S`, so expiry
produces the same observable as suppression — is correct, and the final version pins that premise
with its own assertion rather than relying on the reader. Good practice; worth keeping.

## Fix 1 (`41e7495`) — correct, and the call-site claim holds

The claim that `if group_size > 1` / `if not found` absorb the change with no structural edit was
checked by reading the two call sites, not by the suite passing:

- `marked == 0` ⟹ the resolved contact itself failed ⟹ `found is False` ⟹ the pre-existing
  `if not found or result is None` branch returns the error. Reachable only via that branch.
- `marked == 1` ⟹ single-contact readback. Correct for the ungrouped case and for a group that has
  shrunk to one live member — which is the fallback the security review asked for.
- `marked > 1` with `found is False` is unreachable (the `not found` return precedes it).

Docstring now states the fallback and why, and no longer promises "the real member count". Asked
for, delivered.

**Pre-existing, not a regression, noted for completeness:** when the *resolved* contact fails but
peers succeed, the console returns `no such contact: <id>` while having just set those peers to
`watch` and minted their tasks. That asymmetry predates this commit and the fix does not widen it.

## Fix 2 (`726af61`) — the performance finding is genuinely fixed; one new silence path is not

### Zero `describe_contact` on the suppression path — confirmed

Traced, not assumed. `group_callout_member_id` calls only `store.contact` (a `dict.get`) and
`_leading_index` → `belief.threat.envelope_for`, which is pure table lookup
(`SpecificityLevel` test, `_match_type_row` substring scan, `_CLASS_ENVELOPES.get`). No
`describe_contact`, no `describe_position`, no enrichment. The call site adds `store.
group_for_contact` (delegates to a dict lookup) and memoises per group per tick.

Placement is correct: the `_consumed.add` / `continue` is at `callouts.py:837-838`, **before** the
filter's `describe_contact` at `:839`, and a consumed peer never reaches `live`, so the scoring
`describe_contact` at `:864` is skipped too. 2N describes → 2. The finding's mechanism is removed.

### Same member set and same ordering — re-derived

The implementer's load-bearing claim is that `describe_contact(store, id, …) is None` ⟺
`store.contact(id) is None`. Re-derived rather than taken:

- `describe_contact` → `_find_contact`, which linearly scans `store.contacts` matching `.id`.
- `store.contacts` is `list(self._contacts.values())`; `store.contact(id)` is
  `self._contacts.get(id)`.
- `self._contacts` has exactly one assignment site in the module, `self._contacts[contact.id] =
  contact` (`contacts.py:970`), so it is keyed by `Contact.id` with no aliasing.
- `describe_contact` returns `_contact_result(...)`, whose return type is non-optional, so `None`
  arises *only* from the `_find_contact` miss.

So the sets are identical. Ordering is identical too: both iterate `sorted(group.
member_contact_ids)`, and `_member_contacts_for` preserves `_group_member_facts`' order, so
`_leading_index` is handed the same sequence and returns the same index. The fewer-than-two guard
matches (`len(member_facts) < 2` vs `len(member_contacts) < 2`). The claim is sound and
`_leading_index` stays the single definition of "the leader".

### REQUIRED FIX — an unwatched keeper silences its watched peers entirely

This is new behaviour introduced by this commit, and it turns a flood into total silence.

The keeper is chosen with no regard for whether the keeper is itself *watched*. The filter's
not-watched check (`attention not in ("watch", "priority")` → `continue` **without** consuming)
then drops the keeper's own event, while every peer's event has already been `_consumed`. Net
result: **nothing is spoken for that group's watched-only kinds at all.**

Demonstrated by running the code, with the branch's own test helper — three cohering members, the
keeper left unwatched, the other two watched, all three starting to move:

```
with the fix:            keeper=CONTACT_1  watched=[CONTACT_2, CONTACT_3]  spoken=[]
suppression disabled:    keeper=CONTACT_1  watched=[CONTACT_2, CONTACT_3]  spoken=['ground, moving.', 'ground, moving.']
```

Two lines before, zero after. The watched contacts' range-crossing / motion / engagement callouts
are lost for as long as the keeper stays unwatched — which is indefinitely, because nothing re-runs
`_mark_watched_with_group`.

**Mixed-watched groups are not exotic; they are this feature's own accepted design.** Item 3's
settled scope is *"Tag once, static"*, and the branch already carries a test asserting it:
`test_a_unit_that_joins_the_group_later_is_not_retroactively_watched`. `GroupStore.reconcile`
re-clusters every call and rebuilds `member_contact_ids` while keeping the group's id
(`groups.py:586-600`), so a watched group gains unwatched members as contacts are founded,
re-founded after a loss, or drift into cohesion. Two concrete routes to an unwatched keeper:

1. **Envelope path, the high-stakes one.** `envelope_for` gives ground armour and trucks no
   envelope, and air-defence classes an envelope. So an air-defence contact clustering into a
   watched truck convoy immediately becomes the keeper by widest envelope — and it is unwatched,
   because it joined after the command. The convoy goes silent.
2. **Fallback path, the common one.** With no envelope anywhere the keeper is
   `min(member_contact_ids)` — a *lexicographic* min over ids of the form `CONTACT_<n>` with no
   zero-padding (`contacts.py:1442`), so past nine contacts `CONTACT_10 < CONTACT_2` and a
   later-joined, unwatched member sorts first.

Going quiet is also the worse failure direction for this project (`project_ed_petrovich_failures`:
*"says too little"*), and it is unobservable to the pilot — the same argument the security review
used to make fix 1 required.

**The fix is cheap and needs no `describe_contact`:** choose the keeper among members whose
*effective* attention is `("watch", "priority")`, and return `None` (suppress nothing) when none
is. `belief.attention.effective_attention(contact.attention, contact.last_position, store.areas)`
is pure arithmetic over `AttentionArea`s, `store.areas` is already public (`contacts.py:693`), and
it is the same value `describe_contact` puts in `facts["attention"]` (`tools.py:303`), so the
filter's own gate and the keeper choice would agree by construction. Keep the existing
all-resolving-members `< 2` guard for group coherence; apply `_leading_index` to the eligible
subset. With all members watched — the single-command case — the answer is unchanged, so the
measured 2N→2 result is preserved.

Do **not** instead gate on "suppress only if the keeper is watched": that reverts to the flood in
exactly the mixed case.

### REQUIRED FIX — two docstring assertions the change makes false

The new paragraph on `_WATCHED_ONLY_KINDS` is good (see the wording question below), but it is
contradicted by text four lines above it and by the module docstring a reader meets first:

- `callouts.py:224-225` — *"Never filtered by group membership either (see module docstring's
  'Group disclosure now speaks for its members')"*. It now **is** filtered by group membership.
- `callouts.py:51-52` — *"every other kind still competes and speaks exactly as it does today,
  grouped contact or not."* No longer true of `_WATCHED_ONLY_KINDS`.

The new paragraph's *"That is the paragraph above, unchanged"* reads as endorsing a sentence the
commit falsifies. This repo has already been burned by docs asserting behaviour the code lacks
(`project_bl26_stage10_docs_confidence_decay_gap`); both lines need correcting, and the correction
is one sentence each.

## Cross-branch independence vs `fix/callout-observability-gate` — confirmed for `src`, with a caveat

Trial-merged (`git merge-tree --write-tree f955a73 fix/callout-observability-gate`):
**`body-layer/src/belief/callouts.py` auto-merges cleanly**, and the merged result is semantically
coherent — the suppression sits inside the `_WATCHED_ONLY_KINDS` branch (merged `:888`), the
observability gate sits just before `live.append(event)` (merged `:989`), separated by the
`WATCH_REPORT_MIN_GAP_S` and `CALLOUT_MAX_AGE_S` blocks. No `callout_observable` call is added or
moved by this branch. The independence claim holds where it matters.

**But the log's "should merge without conflict beyond adjacent-line context" is too strong** — six
files conflict, and the merger should not resolve them blind:

```
body-layer/tests/test_callouts.py          body-layer/BACKLOG.md
docs/acceptance/2026-10-05-sortie-feedback.md (add/add)
.claude/agent-memory/{implementer,performance-reviewer,security}/MEMORY.md
```

All look append-shaped, but `test_callouts.py` is where both branches add test blocks and is the
one to read rather than take either side of.

**And there is a semantic interaction worth recording, which the required fix above also closes.**
Once both land, an *unobservable* keeper is dropped by the observability gate while its peers are
already `_consumed` — the identical silence mode, with a second trigger. The sibling branch solved
exactly this for the group-disclosure path and said so in-code: *"Any one member observable is
enough, not all of them … requiring every member would silence a visibly-present group for the
sake of one straggler behind the doorframe."* The suppression block has no equivalent. Choosing the
keeper among *eligible* members (rather than among all members) is the shape that generalises to
both gates; whoever merges second should extend the eligibility predicate rather than add a second
special case. (`CONTACT_ENGAGEMENT_CHANGED` is exempt from the observability gate, so that kind
survives this particular route — the other two do not.)

## The wording tension — the docstring is clear enough, once the stale lines go

Asked: does the docstring now state the cardinality-vs-wording tension clearly enough that the next
reader will not "finish" the job by folding these kinds into `render_group_disclosure` and silently
dropping the affix?

**Yes — the new paragraph does its job.** It names the outcome (*"the surviving line is the leading
member's, affix and all, not a group-level 'the group is moving'"*), gives the mechanism
(`event_clause`/`lead` affixes), and gives the consequence of ignoring it (*"inventing one would
drop the affix, which is the fact the event exists to report"*). A reader who reaches it will not
fold these kinds in by accident.

The qualifier is the one in the required docs fix: it is undercut by *"Never filtered by group
membership either"* immediately above, and a skimmer who reads only that sentence gets the opposite
answer. Fix those two lines and the answer is unqualified yes.

## Test coverage judgement

- **The fallback is the common path in flight, not only in tests.** `envelope_for` returns `None`
  for ground armour and trucks by design, so for the convoy case Item 3 exists to serve the keeper
  *is* `min(member_contact_ids)`. Coverage is therefore aimed at the right path, which is better
  than the implementation log implies.
- **The envelope path is untested in this function** and is the air-defence case — the one where
  getting the leader wrong matters most. `_leading_index` itself is shared and covered through
  `group_membership_state`, so the risk is thin; a test is an **optional** addition, not a blocker.
- **No test covers the mixed-watched group.** That is the gap the required fix above closes, and
  the fix needs a test pinning it: a watched peer whose group's keeper is unwatched must still
  speak.
- `test_an_ungrouped_watched_contacts_motion_callout_is_untouched` and the shrunken-group guard are
  real regression value, not decoration. Verified by the disable-and-rerun above that the flood
  test is the one carrying the fix.

## Invariants

No omniscience boundary touched: `group_callout_member_id` reads `Contact.classification` (believed)
and `Contact.id`; `envelope_for` is explicitly the no-omniscience line and unchanged. No DCS write,
no coordinate math added, no provenance/confidence field involved, no `world-model/data/` path, no
new dependency, no debug leftovers or TODOs in the diff. The implementer's agent-memory file is at
the repo-root path (`.claude/agent-memory/implementer/`), not under `body-layer/`. Mechanism and
calibration are in separate commits, as the body-layer convention requires. Working tree clean.

---

### Verdict

**NEEDS FIXES**

### Required Fixes

1. **`speech.py::group_callout_member_id` must choose the keeper among members whose effective
   attention is `("watch", "priority")`, returning `None` when none is.** As written, an unwatched
   keeper silences every watched peer's `_WATCHED_ONLY_KINDS` callout — demonstrated above, two
   lines before the change, zero after. Mixed-watched groups are guaranteed by Item 3's own
   "tag once, static" design plus `GroupStore.reconcile`. Needs a test pinning it. The fix costs no
   `describe_contact` and leaves the measured 2N→2 result intact.
2. **Correct the two docstring assertions the change falsifies:** `callouts.py:224-225`
   ("Never filtered by group membership either") and `callouts.py:51-52` ("every other kind still
   competes and speaks exactly as it does today, grouped contact or not").

### Optional Refinements

- A test for `group_callout_member_id`'s envelope path (one member with an air-defence
  classification that resolves an envelope), since the fixtures only exercise the fallback —
  optional, because `_leading_index` is shared and already covered.
- The fallback's "first in id order" could be "nearest member", which is this module's existing
  convention for speaking about a cluster (`_nearest_clock_position`). It would need ownship in the
  signature for no real gain — members are co-located — so this is a note, not a recommendation.
- Correct the implementation log's "should merge without conflict" line to name the six conflicting
  files, so whoever merges second does not take it as licence to resolve blind.

### Review Confidence

**Full read.** Both fixes read in full against both review documents; the two new tests verified
non-vacuous by disabling each fix and re-running; the zero-`describe_contact` claim and the
`describe_contact`/`ContactStore.contact` equivalence re-derived from source rather than accepted;
the new silence path reproduced by executing the code; cross-branch independence established by a
trial merge and by reading the auto-merged result. All four body-layer checks run in the worktree
with imports and rootdir proven worktree-local.
