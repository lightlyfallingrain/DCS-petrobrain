### Debug Report

### Observed Issue

Live sortie 2026-09-18, flat desert, the twelve-unit ground calibration complex (SA-3 launcher +
SA-3 TR radar, ZU-23 on a Ural, ZSU-23-4, BMP-1, BTR-70, T-72B, Ural, BM-21, three AK infantry —
twelve genuinely distinct DCS objects, each with its own `object_id`) produced roughly five
`Contact`s in body-layer's belief store, not twelve — and the merged contacts never split apart
even as the aircraft closed to 500 m and the units became plainly distinct in the narrated log.
`body-layer/ROADMAP.md` already carried an open entry for a two-object version of this
("False contact merge at first sighting, kept alive by `object_id` continuity"), pinned by a
strict `xfail`, `tests/test_mock_flight_chain.py::test_two_real_objects_stay_two_contacts`.

**Mid-investigation scope change.** The user's own framing of what they actually want reframed
this from "should two nearby objects stay separate" to "cardinality and composition are
themselves beliefs that refine over time" — `"there is something"` → `"many somethings"` →
`"3 tanks and something else"` → `"not ifvs, but shilka and two MLRS"` → `"3 T-72, 1 BMP-2, 2
GRAD"`. That is a materially larger requirement than the original bug report. Per that
redirection: this report finishes the root-cause analysis and the data-model feasibility
question, evaluates one candidate localised fix (reverted, not applied), and does **not** build
the group model — that is now recommended as Architect work.

### Hypothesis

Two independent, compounding mechanisms, both confirmed by reading the code (not assumed):

**1. `object_id` correlation is reached and works correctly — the bug is entirely at founding
time, not in continuity.** Each concrete `PerceptionSource` (`naked_eye_source.py`,
`hybrid_source.py`) keeps its own persistent `object_id -> last Observation.id` map, keyed by the
real DCS `object_id`, never cleared mid-session. A genuinely different real object has a
genuinely different `object_id`, so it can never produce a same-`object_id` continuity match —
its very first observation always carries `continues_observation_id=None` and therefore always
falls through to `belief.association_over_time.passes_gate` (`belief.contacts.
ContactStore._resolve_continuity` returns `None` for it). This is by design
(`plans/contact-duplication-ambiguity-runaway/plan.md`'s own text: *"a genuinely different real
object has a genuinely different DCS `object_id` — it can never produce a same-`object_id`
continuity match... this gate path is now reached in exactly the same circumstances as before
(first sighting, or a genuinely different object)"*). So the question "why did the spatial gate
get consulted at all" has a simple answer: it always does, for every founding observation, by
design — that is not itself a bug. The bug is what happens once it's consulted.

**2. Founding-time gate: presence-tier percepts are structurally class-blind, so an honestly-wide
spatial gate is the *only* thing deciding merge-vs-new, and one false merge permanently disables
the ambiguity safety net for the rest of that cluster.**

- Naked-eye's `lowres` tier (`visibility.check_visibility`'s coarsest achieved tier, reached at
  long range) emits `classification_raw = object_model.DEFAULT_OP_CLASS` (`"OP_GROUPSOMETHING"`)
  at `classification_level = SpecificityLevel.PRESENCE` (`naked_eye_source._classification_
  for_tier`). `belief.classification._op_class_of` always resolves `DEFAULT_OP_CLASS` to `None`
  (it is explicitly excluded by the `!= object_model.DEFAULT_OP_CLASS` check), so `class_
  compatibility` between any two presence-tier percepts — or a presence-tier percept and an
  already-classified contact — is always `"unknown"`, never `"incompatible"`. `association_over_
  time.py`'s own docstring documents `"unknown"` as deliberately neutral ("neither confirms nor
  blocks a merge... deliberately weak on the scope channel... the plan accepts this as a known
  risk (under-merging into duplicate contacts, **never a bad merge**)"). That accepted trade is
  false for naked-eye's presence tier specifically: it is not a rare unresolvable-free-text edge
  case, it is the *systematic, every-time* output at long range — exactly when two different real
  objects are most likely to be spatially indistinguishable too. So at long range, class provides
  zero discriminating power precisely when it is needed most, and the entire merge decision falls
  on the spatial gate.
- The spatial gate (`spatial_gate_radius_m`) sums both sides' `uncertainty_radius_m` plus a
  growth term. At ~9 km, naked-eye's own quantisation implies real uncertainty: cross-range =
  `range_m * sin(15°) ≈ 2330 m`, down-range = the ~1000 m `OP_D9_10k` bucket width, combined via
  `math.hypot` to ≈2500 m *per side* — several kilometres of combined gate radius, honestly
  derived from the channel's own bucket widths (this formula is correct and was not the subject
  of this investigation; it is BL-2.6's fix, confirmed by reading `plans/classification-
  refinement/debug.md`'s history and left untouched). A twelve-vehicle calibration complex
  spanning a few hundred metres sits entirely inside that radius for every pairing.
- **The cascade mechanism** (confirmed by direct reproduction, see Evidence): `ContactStore.
  ingest`'s Stage 1 decision rule — "exactly one candidate passing → merge; zero → new; two or
  more → new" — is a real, working safety net, but it can only fire when *two or more* existing
  contacts already exist for a new percept to be ambiguous between. The very first two objects in
  the cluster: object A founds contact 1 (zero candidates). Object B's founding percept sees
  exactly one candidate (contact 1) and merges into it — the false merge; the safety net never
  triggers because there was only ever one contact to check against. From then on, *every
  subsequent* object in the cluster of the same broad situation sees the same single, already-
  merged contact as its only candidate and merges into it too — the false merge from step 2
  permanently prevents the ambiguity check from ever having two contacts to be ambiguous between,
  for this cluster, for the rest of the session (subject to `OBJECT_ID_MEMORY_S` continuity
  keeping every subsequent re-sighting of each already-merged object pinned to that same contact
  regardless of how far its position later diverges, since continuity skips the gate entirely).
  This is the same *shape* of runaway `plans/contact-duplication-ambiguity-runaway/plan.md` fixed
  in the opposite direction (that one was one real object spawning many contacts; this is many
  real objects collapsing into one) — and that plan's own text flagged this exact residual risk
  and left it unaddressed: *"the gate is still what stands between two real, nearby, newly-
  appearing objects and a spurious extra contact on their very first shared poll."*

### Evidence

- Read `src/perception/naked_eye_source.py` (`_object_id_to_last_observation_id`, `_build_
  observation`) and `src/perception/hybrid_source.py` — confirmed each channel's correlation map
  is keyed by the real `object_id`, persistent, one entry per distinct real object; a new
  `object_id` always starts with `continues_observation_id=None`.
- Read `src/belief/classification.py` (`_op_class_of`, `PRESENCE_CLASS`) — confirmed `DEFAULT_OP_
  CLASS`/`OP_GROUPSOMETHING` always resolves to `None` class, therefore always `"unknown"`
  compatibility, never blocking a merge.
- Read `src/belief/association_over_time.py` (`spatial_gate_radius_m`, `uncertainty_radius_m`,
  `_naked_eye_uncertainty_m`) and computed the ~9 km gate radius (~2.5 km per side) by hand from
  the real constants (`_CLOCK_BUCKET_DEG`, `_RANGE_BUCKETS_M`).
- Read `src/belief/contacts.py`'s `ingest` — confirmed the "one candidate → merge, else new"
  decision rule operates purely on the *current* contact list, with no batch-level or historical
  awareness of prior false merges.
- **Direct reproduction** (`body-layer/tests/test_calibration_cluster_merge_undercount.py`,
  committed as a permanent characterisation test): twelve synthetic `Observation`s, one per real
  unit, each with its own private `continues_observation_id` chain (mirroring what each real
  `object_id`'s correlation map would produce), founding sightings all quantised to an identical
  long-range presence-tier reading (`OP_GROUPSOMETHING`, `PRESENCE`, bearing 0°, range 9000 m —
  what a real cluster this tight would genuinely quantise to at that range), then two more polls
  of refinement toward each unit's real class and well-separated final position. Run against the
  real, **unmodified** `ContactStore`/`association_over_time` code: **twelve distinct real
  objects produced six `Contact`s**, matching the live sortie's "roughly five" — and the merged
  contacts never separate, because every non-founding percept in the test reaches its contact via
  `continues_observation_id` continuity, which never re-runs the spatial/class gate at all.
- Ran the existing suite unmodified (`pytest body-layer/tests -q`): 601 passed, 1 xfailed
  (`test_two_real_objects_stay_two_contacts`) — confirmed this is still the documented, still-open
  defect; nothing in this investigation changed that baseline.

### Fix Applied

**None merged.** One candidate fix was designed, implemented, and empirically verified to work
for the narrow two-object mock scenario, then **reverted** per the user's redirection — see
"Candidate fix evaluated (not applied)" below for what it was and why it doesn't answer the
actual question anymore. `tests/test_mock_flight_chain.py::test_two_real_objects_stay_two_
contacts` remains a strict `xfail`; its `reason=` string was updated to point future readers at
this report and explicitly warn against flipping it green with a narrow gate-tuning patch that
doesn't address cardinality/composition (see the diff, already on this branch).
`tests/test_calibration_cluster_merge_undercount.py` (new) is committed as a permanent
characterisation test of the twelve-object collapse, asserting the *current* (still defective)
count — its own docstring says explicitly that its assertions should be replaced once a real
group/composite model lands, not treated as a target to preserve.

### Can the current data model carry the desired behaviour? No — concretely, here is the gap.

`belief.contacts.Contact` holds exactly **one** `classification: ClassificationBelief` field and
one `last_position`/`last_position_uncertainty_m` pair — a single-entity belief record by
construction. The desired progression (`"there is something"` → `"many somethings"` → `"3 tanks
and something else"` → `"not ifvs, but shilka and two MLRS"` → `"3 T-72, 1 BMP-2, 2 GRAD"`)
requires all of:

1. **A cardinality belief, itself uncertain and refining** — `unknown` → `"many"` (a count lower
   bound / rough estimate) → a specific integer, independent of any single member's
   classification specificity. Nothing in `Contact`, `ClassificationBelief`, or `SpecificityLevel`
   represents "how many of these am I looking at" at all today — `SpecificityLevel` is a totally
   ordered ladder over *one* entity's identity, not a count.
2. **A composition belief: a multiset of sub-claims at mixed specificity, not one value.** "3
   tanks and something else" is three `CLASS`-level members plus one unresolved remainder, held
   *simultaneously* inside what is presented as one contact. `Contact.classification` is a single
   `ClassificationBelief`; there is no member list, no per-member specificity, and no notion of "N
   of the M members are resolved, M−N are not."
3. **Contradiction and retraction at the *member* level, not the whole contact.** "Not IFVs, but
   Shilka and two MLRS" retracts a claim about part of the group while leaving the rest (e.g. the
   tank count) untouched. `belief.classification.fold_classification` already implements exactly
   this *shape* of reasoning for a single entity — level-ordered refinement, contradiction
   collapsing to the deepest common ancestor, a re-promotion lockout
   (`CLASSIFICATION_CONTRADICTION_LOCKOUT_S`) — and that mechanism generalises naturally to "one
   fold per member, plus a fold over the member-count/roster claim itself" rather than needing an
   unrelated parallel mechanism invented from scratch. This is worth stating plainly: **the
   *fusion logic* mostly exists and would extend; what's missing is the *shape holding multiple
   folds at once*, not the folding rule.**
4. **Per-member refinement, independent of the group's own founding/last-seen timestamps and
   position.** `Contact.last_position`/`last_seen_sim`/`sighting_spans` are single-entity fields.
   A group contact plausibly needs a position (or spatial extent) for the group as a whole *and*
   optionally per-member offsets once resolved — not designed for at all today.
5. **Splitting.** Nothing in `ContactStore` can ever turn one `Contact` into two — there is no
   contact-deletion mechanism (per `contacts.py`'s own docstring, correlation state is "never
   pruned or re-keyed"), no mechanism to re-key a subset of `contributing_observation_ids` onto a
   new contact, and every downstream consumer (`events.py`'s lifecycle events, `speech.py`'s
   contact-report rendering, `tools.py`'s brain-facing API, the F10/crew-console command surface)
   assumes a stable 1:1 `contact_id` for a physical thing's whole session. This is likely the
   single largest piece of net-new surface: BL-4's `AttentionArea`/event-cooldown machinery,
   BL-5a's speech templates, and BL-7's mission-phase relevance scoring would all need to decide
   what "the same contact split into two" means for their own state (does the split child inherit
   attention? cooldown state? an in-flight `PendingIntent`?).

**Is `OP_GROUPSOMETHING`/the presence tier a usable starting point, or a dead end?** A genuinely
useful *hook*, not a dead end, but presently a one-way one: it is already exactly the vocabulary
value ED gives Petrovich for "a group of something, unresolved" — precisely what the cardinality
ladder's `unknown`/`"many"` rung would want to key off of. But nothing today treats it specially:
it folds through `fold_classification` as an ordinary `PRESENCE`-level claim like any other,
carries no count, and (per the root cause above) actively contributes to the bug by providing zero
class-gate resistance to founding-time merges. Using it as the actual entry point into a group
model is plausible; using it as-is, unmodified, is not — the fold/gate machinery around it treats
"unresolved" and "known to be exactly one thing, just not identified" identically today, and a
group model needs to tell those apart.

**Bottom line for the Architect:** this is a genuine extension to `belief.contacts.Contact` and
`belief.classification`'s data model (a `Contact` needs either a `members: list[...]` +
cardinality belief field, or a new sibling type for group contacts with its own fold rules), plus
a `ContactStore` splitting mechanism with defined semantics for every existing per-contact
subsystem (events, attention, tasks, speech). Not a localised gate/threshold fix by any framing.

### Candidate fix evaluated (not applied)

Before the scope redirection, a narrow fix was designed and verified against the existing
two-object mock fixture: add a hard veto to `association_over_time.passes_gate` refusing to treat
a `PRESENCE`-level (`classification_level <= SpecificityLevel.PRESENCE`) percept as a merge
candidate at all — it always founds a new contact instead (continuity, being unconditional on
tier, still reattaches it correctly on the next poll once the object's own chain exists). This
made `test_two_real_objects_stay_two_contacts` pass outright (verified: 2 contacts, correct
classifications) without touching `uncertainty_radius_m`'s formulas or BL-2.6's symmetric
budgeting, so it did not reopen the single-object-splits-into-many bug that fix addressed. Diff
kept for reference at `/private/tmp/claude-501/.../scratchpad/candidate-presence-tier-veto.patch`
(session-local, not part of this branch).

**Why it was reverted rather than merged:** it answers "should these two stay separate" with a
binary yes, which is real progress for the two-object degenerate case, but it is not the answer
the user actually wants. It has no notion of cardinality ("many somethings"), no composition, and
no splitting — applied to the twelve-object reproduction, it would very likely reduce the
over-merge (presence-tier percepts would no longer collapse across classes) but would still
collapse same-class, closely-spaced objects (three AK infantry within ~50 m of each other, all
resolving to the identical `CLASS`-level `OP_INFANTRY`, are genuinely indistinguishable by class
*and* still within each other's spatial gate — this veto does nothing for that case, confirmed by
re-reading the reproduction's `INFANTRY_1..3` entries, which share a class and would still pass
the gate against each other's contact even with the veto in place).

**Is it wasted work, or a stepping stone?** Likely a real stepping stone, not wasted: whatever
group model the Architect designs will still need *some* founding-time decision about "is this
sighting evidence for an existing group, a new member of it, or a new group entirely," and
"a percept with zero class evidence should not make a confident 1:1 identity claim" is a
component of that decision that survives the redesign — it would plausibly become "a presence-
tier percept can grow an existing group's cardinality estimate, but should not resolve which
specific member it is." The veto as written (outright refuse to merge) is very likely too blunt
for the group model's actual founding rule, but the underlying observation it encodes is not
wasted.

### Verification

- `cd body-layer && ruff format --check src tests && ruff check src tests && mypy src && PYTHONPATH=src:../world-model/src:tests pytest tests -q` — 601 passed, 1 xfailed (unchanged from
  the pre-investigation baseline; the new characterisation test is counted in the 601).
- Confirmed by hand that `git diff` against `main` for `src/belief/association_over_time.py` is
  empty (candidate fix fully reverted) and that `tests/test_mock_flight_chain.py`'s only change is
  the `xfail` reason string (no assertion or behaviour changes).
- No debug instrumentation left in the tree; the reproduction in `test_calibration_cluster_
  merge_undercount.py` is the permanent artifact, not throwaway instrumentation.

### Recommendation

Bring in the Architect to design a group/composite contact model: cardinality as a refining
belief, composition as a multiset of member sub-claims at mixed specificity (generalising `belief.
classification.fold_classification`'s existing per-entity fold rule rather than inventing a
parallel mechanism), and a `ContactStore` splitting mechanism with defined semantics for BL-4
attention/events, BL-5a speech, and BL-7 mission-phase relevance. `OP_GROUPSOMETHING`/`SpecificityLevel.PRESENCE` is a usable entry point for the "unresolved group" state but needs the
surrounding fold/gate logic redesigned to distinguish "known group, unresolved membership" from
"unknown whether this is one thing or many." The reproduction test and this report's root-cause
section are the starting evidence base for that plan.
