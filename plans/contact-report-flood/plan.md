### Goal

When the naked-eye gaze sweep merges several already-identified contacts into one supercluster,
stop the discarded identities' eventual re-founding from re-announcing ground the pilot has
already been told about — without building per-member identity tracking, which this project has
twice already decided against.

### Context this plan rests on (read before changing anything below)

- `plans/contact-report-flood/debug.md` (today): the defect, live evidence, the regression test
  (`test_merging_previously_separate_contacts_abandons_the_minority_identities`), escalated rather
  than patched.
- `plans/group-contact-model/plan.md`, "Splitting" and "Merging into an existing group" sections:
  **the merge case was analysed, not missed.** "The other contact is not deleted — it stops being
  observed and decays `tracked → estimated → lost` on the existing ladder. That is exactly right
  epistemically: the crew did not watch it vanish, they stopped seeing it separately." That
  verdict stands for the *belief* side and this plan does not revisit it. What that plan did not
  separately analyse is the callout layer's reaction to the same event — nothing there was ever
  checked against "the discarded contact's objects later redetect as a brand-new id nearby."
  That gap is what produces the re-announcement.
- `plans/contact-fragmentation-at-range/debug.md` and `2026-09-28-log-analysis.md`,
  `plans/contact-duplication-ambiguity-runaway/`, `body-layer/BACKLOG.md` BL-B24: three prior
  passes on the same underlying engine (`ContactStore.ingest`'s "2+ candidates → always a new
  contact" anti-guessing rule, reached through `association_over_time`'s generous, range/time-
  scaled spatial gate). See "Why the fourth occurrence" below for how this one relates.
- Knowledge graph: not queried — `graphify-out/` does not exist in this worktree (`gq.sh` reports
  "No graph yet"). Everything above was found by reading plans directly; flagging this as a gap
  rather than silently skipping the step the process requires.

### Decision

**Primary fix: suppress the spoken `CONTACT_DETECTED` callout for a freshly-founded contact when
an existing, not-yet-`lost` contact is spatially and classification-plausibly the same real
thing** — reusing `association_over_time`'s already-calibrated spatial/class gate math, not a new
radius constant, and scoped to `CONTACT_DETECTED` only (never `CONTACT_REACQUIRED`, never
`CONTACT_CARDINALITY_CHANGED`, which already has no speech template). The contact record, its
classification, its position, and its cardinality are untouched — only whether its founding is
*spoken* changes. Nothing in `belief/contacts.py`'s identity model changes.

**Why not the other two shapes the debugger offered:**

- **Reconcile discarded identities into the survivor (full `Contact`-to-`Contact` merge).** This
  is new territory the project has already priced once, in the Splitting section's rejected
  "Option A" (delete-and-respawn): five surfaces dangle on any scheme that moves a contact's
  identity after the fact — `_events[].contact_id`, `_observation_id_to_contact_id`,
  `PendingIntent.result_contact_ids`, `WorldEnrichmentCache`, `PartialParse.
  referenced_contact_id`. A *merge-forward* alias (rather than delete-and-respawn) sidesteps the
  dangling-reference problem, but does not solve the actual re-announcement case this debug
  found: the abandoned contact's objects resurface **under a brand-new id with no link back to
  the alias at all** (a later re-split founds fresh, `continues_observation_id=None`, by the same
  mechanism an ordinary, never-merged split uses). An alias from the old id to the survivor cannot
  catch a *third*, not-yet-existing id. Reconciliation would need to solve the same problem this
  plan already solves (position-plausibility at founding time) before it could even apply — so it
  is strictly more code for no additional coverage.
- **Let one cluster carry multiple contact identities (the user's "group" framing from
  `group-contact-model/plan.md`'s rejected Option B).** Already argued and rejected there by name:
  "a second contact kind that all thirteen consumers must handle, a parallel shape on the tool
  surface... compatible, and remains buildable later as a view over contacts (BL-8/brain), but
  building it now would answer the wrong question at permanent structural cost." Nothing about
  today's evidence changes that argument; re-raising it here would be re-deciding a settled
  question rather than resolving a new one. **Effort/value: this is the "technically challenging"
  option, and the two prior passes already found its cost is categorically the same as per-member
  identity tracking** — which both group-contact-model and contact-duplication-ambiguity-runaway's
  plans independently concluded should never be built.

### Whether the merge should happen at all (requirement 2 from the task)

No design question survives here either. Clustering is deliberately position-only and carries no
persistent per-member identity (`perception/clustering.py`'s own docstring) — that is the same
decision that makes the merge possible in the first place, made and re-affirmed across
`group-contact-model/plan.md` and the two decay-anchored revisions in
`contact-duplication-ambiguity-runaway/plan.md`. Giving clustering "authority" to not overrule an
existing separate contact would require it to know about existing contacts at all, which inverts
the `perception/` → `belief/` layering (`perception/` must never depend on `belief/`, stated
repeatedly, enforced by import direction). The fallout is what belief does with a cluster the
gaze sweep legitimately produced, and that is what this plan answers.

### The honest cost of the chosen fix, stated plainly

**The suppression check cannot distinguish "this founding is a re-echo of a merge I already
absorbed" from "this founding is a genuine split — the scene just resolved into two things."**
Both produce an identical shape at `_build_observations` time once a merge has happened: every
absorbed member's `_object_id_to_last_observation_id` entry is overwritten to the survivor's
observation id (`naked_eye_source.py` module docstring, point 6 — "every member's entry is then
overwritten... regardless of whether it was the winning vote"), so a later re-split off that
survivor looks, to the perception layer, exactly like an ordinary split of a group that was never
touched by a merge. This is not a gap in this plan's design; it is a structural consequence of
the already-made, twice-reaffirmed decision not to track per-member identity. Suppressing the
merge-echo case necessarily also suppresses the occasional genuine split's own `CONTACT_DETECTED`
line.

**Taking that cost anyway, because it is bounded and the alternative is worse, measured.** A
suppressed split is not a suppressed *fact* — the new contact record, its classification, and the
survivor's cardinality/composition belief (which already told the pilot "there's a group of about
N here" at founding or merge time) all still exist and are reachable via `report`/console. What is
lost is only the incremental "actually that's two things" refinement, not the original
disclosure. Against that: the measured cost of not suppressing is the user's own stated
complaint — a near-constant stream, much of it about units already reported. The user's framing
("it also feels like many of those reports were about the same units") says which failure mode he
already finds worse. This can be revisited if live flying shows legitimate splits going silent
often enough to matter — nothing here is a one-way door, since no belief state is deleted or
rewritten, only a speech decision.

### Mechanism

1. **New pure function, `belief/association_over_time.py`: `contacts_plausibly_same(a: Contact, b:
   Contact, now_sim: float) -> bool`.** Generalises `passes_gate`'s existing math (class
   compatibility, then the Mahalanobis test against the *sum* of both sides' covariances, each
   inflated by its own elapsed time since its own `last_seen_sim`) to two `Contact`s instead of a
   `Percept` and a `Contact` — `_contact_covariance(contact, elapsed_s)` already takes exactly the
   shape needed for both sides; `GATE_SIGMA_THRESHOLD` is reused unchanged. **No new constant.**
   This is the same calibrated gate the ambiguity rule already trusts to mean "plausibly one real
   thing," applied symmetrically.
2. **`belief/contacts.py`: add `ContactStore.contact(contact_id: str) -> Contact | None`**, a
   small named lookup alongside the existing `group_for_contact` — currently nothing outside
   `ingest`/`_resolve_continuity` can resolve an id back to a `Contact` from outside the module.
3. **`belief/callouts.py`: in `_render_event`'s existing `CONTACT_DETECTED, CONTACT_REACQUIRED`
   branch, split the two kinds.** Add, for `CONTACT_DETECTED` only, a check before rendering: does
   any *other* contact in `store.contacts` satisfy `certainty_of(other, now_sim) != "lost"` and
   `contacts_plausibly_same(this_contact, other, now_sim)`? If so, treat exactly like the existing
   "vanished candidate" case — return `None` without acknowledging, so the event is retried on a
   later `tick()` rather than lost outright (the same "lost, not deferred" pattern the module
   already documents for a stale signature match). `CONTACT_REACQUIRED` is untouched — it only
   ever fires for a contact id that already existed and had gone `lost` (`events.
   lifecycle_event_kind`: `CONTACT_DETECTED` fires only on a contact's first-ever tick,
   `CONTACT_REACQUIRED` only when `previous_certainty == "lost"` for that *same* id) — so the "the
   same guy is back" story this project built object-permanence correlation for in the first place
   is never affected.

**Why this needs no new time-window constant.** `CALLOUT_MAX_AGE_S` (10s) already bounds how long
any retried, unspoken candidate can wait before `tick()` drops it unacknowledged. `LOST_THRESHOLD_S`
(120s) is far longer than that, so in practice a candidate suppressed by an actively-tracked
nearby survivor stays suppressed for its entire retry window and is then quietly dropped — which
is the intended effect (a merge survivor under continuous tracking should permanently absorb the
redundant announcement, not eventually blurt it out stale). No separate suppression-duration
constant is needed; `CALLOUT_MAX_AGE_S` already is one, doing exactly the right job for a
different reason than it was built for.

### Interaction with BL-B23 / group-cohesion-redesign (requirement 3)

**No interaction with the belief-side mechanisms those touched.** BL-B23's "exclude `lost`
contacts from clustering" is about `belief.groups`' report-space grouping of currently-believed
contacts for disclosure — unrelated to `ContactStore.ingest`'s gate or to this plan's speech-time
check, which never consults `belief.groups` at all.

**What this plan's reading of the code confirms, though, and flags rather than fixes:**
`ContactStore.ingest`'s gate-candidate loop (`passing = [candidate for candidate in self.
_contacts.values() if ... and passes_gate(...)]`) **never excludes `lost` contacts.** A
merge-abandoned contact is not pruned (nothing in `contacts.py` prunes any contact, by design) and
remains a permanently-live gate candidate forever. This means a later re-split near a dense,
merge-churned cluster can face *multiple* stale, lost, mutually-close candidates simultaneously —
which is exactly BL-B24's and `contact-duplication-ambiguity-runaway`'s still-undecided "2+ close
candidates → always new contact" shape, now fed by merge-driven zombies rather than range-scaled
sigma or elapsed-time growth. **This plan does not touch that** — it is the same open architectural
question already escalated twice (BL-B24, `contact-duplication-ambiguity-runaway`), and blanket-
excluding `lost` contacts from the gate (the obvious-looking fix) would break the deliberately-
built "reacquire the same lost contact after a long gap" story that `contact-duplication-
ambiguity-runaway`'s own decay anchoring exists for. Recorded here as a confirmed amplifier, not
resolved — see "Why the fourth occurrence" below.

### Why the fourth occurrence (requirement 4)

**These are genuinely distinct triggers feeding one undecided root policy, not duplicate work.**
`ContactStore.ingest`'s "2+ passing candidates → always a new contact, never a guessed merge" rule
has had no self-limiting mechanism since it was written (`plans/pb2-contact-memory/plan.md` Stage
1), and every occurrence has been a different way of pushing the system into the regime where
that rule fires on candidates that are plausibly the same thing:

1. `contact-fragmentation-at-range`: range-scaled `naked_eye_sigma_m` widening the gate faster
   than real position error grows, plus per-poll admission caps spreading one group's founding
   across enough polls to break continuity's majority vote.
2. `contact-duplication-ambiguity-runaway`: the BL-2.6 symmetric-gate fix mechanically doubling
   the effective gate radius.
3. `BL-B24`: the gate's own elapsed-time growth term inflating the radius after a long
   reacquisition gap.
4. This one: the merge-direction mirror of continuity's majority vote, discarding minority
   identities that then remain as permanent, un-excluded gate candidates — feeding the same rule
   from the *stale-candidate* side rather than the *gate-width* side.

The common thread is real and worth naming plainly: **nobody has yet decided what the ambiguity
rule should do when its 2+ candidates are themselves close to each other or recently stale**,
and three debug passes have each correctly declined to patch that decision locally. This plan does
not resolve it either — it resolves the pilot-audible symptom (noise) at the speech layer, which is
available precisely because speech is not identity. If the root policy is ever to be resolved
properly, it needs real DCS mission-object spacing data neither prior pass had, which is a
separate, larger investigation and not bundled here per the effort/value read above.

### Staging

1. **`contacts_plausibly_same` + `ContactStore.contact`, with unit tests.** Pure function, cheap
   to test in isolation against the existing gate's own calibration (same inputs that would pass
   `passes_gate` between a percept and a contact should pass this between two contacts at zero
   elapsed time). Acceptance: new tests pass; no existing test touches these two additions.
2. **Wire the `CalloutScheduler` suppression check, with regression tests in
   `test_callouts.py`.** Build the exact shape from `debug.md`'s evidence table as a fixture:
   several independently-founded contacts whose objects later merge into one supercluster, then
   (separately) a later poll re-splitting one of the absorbed objects off on its own. Acceptance,
   stated as the numbers the fix must hit:
   - The six-vehicle cluster shape from the live trace (`t_sim` 699–751, `CONTACT_3/4/5/7/8`)
     reduced to **at most 2 spoken `CONTACT_DETECTED` lines** for that cluster in that window, not
     6 — the two genuine first-sightings before any merge, with every merge-echo re-founding
     suppressed.
   - A control case proves `CONTACT_REACQUIRED` is untouched: a contact goes fully `lost`, then
     reacquires under its own id with no other contact nearby — still speaks.
   - A control case proves ordinary, well-separated foundings are untouched: two contacts founded
     2 km apart (`test_two_well_separated_objects_produce_two_contacts`'s existing separation)
     both speak.
3. **Replay-harness integration check against the sortie shape, not the raw 266k-row trace.**
   Driving the full `detection-trace.jsonl` isn't worth building a harness for one measurement;
   instead construct a `replay.py`-driven fixture reproducing the six-vehicle merge sequence
   through the real `NakedEyePerceptionSource` → `ContactStore` → `CalloutScheduler` chain
   end-to-end, confirming the object-id-level reproduction in `debug.md`'s regression test still
   happens (the belief-layer abandonment is unchanged by design) while the audible line count
   drops as above.
4. **Note, do not close, BL-B24 and `contact-duplication-ambiguity-runaway`.** Add one line to
   each noting that this fix mutes the audible symptom of a merge-driven instance of their shape
   but does not touch the underlying candidate-ambiguity policy, which remains open.

### Risks & Unknowns

- **The split-vs-echo indistinguishability above** — accepted, not resolved; see that section.
- **`ContactStore.contacts` is a full list copy per call** (`list(self._contacts.values())`); the
  suppression check only runs when a `CONTACT_DETECTED` candidate is actually chosen to render
  (at most one per `tick()`, with a bounded retry list on misses), so this is O(scene size) per
  tick, not per candidate scored — negligible at the contact counts this project runs with (tens,
  not thousands). Not worth a Performance Reviewer pass on its own; flagged for the record since
  the brief asked about cost explicitly.
- **No new dependency.** Everything above is stdlib-only, reusing existing `belief/` modules.
- **Lost-contact accumulation in `_contacts` is pre-existing and unaffected.** `contacts.py`
  states outright that nothing is ever pruned; this plan neither worsens nor fixes that — flagged
  so it isn't mistaken for a new leak this change introduces.

### Second-order effect

Narrows, slightly, what a future resolution of the ambiguity-rule root policy (BL-B24 /
`contact-duplication-ambiguity-runaway`) needs to additionally consider: once this suppression
ships, the *audible* symptom of that unresolved policy question goes quiet for the merge-driven
case specifically, which could make the underlying belief-store duplication easier to leave
unaddressed for longer simply because nobody hears it anymore. Worth a line in whichever plan
eventually resolves that policy, noting the noise went away before the cause did.

### Decisions requiring user input

**Genuinely his, per the task's own framing — what the pilot should hear, not a mechanism
question:** this plan's default is **silence** — a suppressed merge-echo produces no callout at
all, exactly like the existing "unchanged, don't re-speak" precedent
(`group-cohesion-redesign`'s delta-suppression, `_last_spoken_signature`'s duplicate-text
suppression). The richer alternative — an explicit acknowledgement such as "same group as before,
11 o'clock" when a merge-echo is suppressed — was not built here because it requires deciding what
a crew member would actually say about a cluster re-forming, which is exactly the kind of cockpit
behaviour call this project's process reserves for the user, not the architect. Recommend shipping
silence first (cheapest, reversible, matches the existing precedent) and revisiting only if live
flying shows the silence itself reads as wrong.
