### Goal

Stop the reproduced runaway duplication where two distinct, moderately-separated real objects
(the BL-2.6 gate-widening fix legitimately overlapping their gates) trigger `ContactStore.
ingest`'s "two-or-more candidates → always new contact" policy repeatedly, spawning roughly one
new contact per poll for the rest of the session — by giving `ContactStore` a cheap,
non-omniscient way to recognise "this is the same real object I've seen before" and skip the
gate entirely whenever that recognition is available, rather than by re-tuning gate width
(which cannot be made correct for every unit/range combination) or by relaxing the
never-guess-merge invariant.

**Revision 2026-09-10**: the original plan (37007a3) scoped this to the *zero-gap* case only —
same-`object_id` match between one poll and the very next. The user's confirmed intent is
broader: **object permanence, not merely frame-to-frame continuity**. A `Contact` whose
`object_id` is later re-observed — after any real gap (masked by terrain, out of FOV, a
multi-poll aircraft-layer hiccup, minutes of no sighting at all) — should fold back onto the
same contact directly, without re-running the spatial/class gate. This revision reworks the
Design/Affected-Modules/Risks sections below accordingly; the Goal, Decision framing, and
`observation_id`-not-`object_id` boundary principle from the original plan still hold and are
carried forward, generalized rather than replaced.

**Revision 2026-09-10 (second pass, same day)**: object permanence must itself decay — trusting
an `object_id` match forever, no matter how much time has passed, is not what the user asked for
("when enough time passes that location becomes uncertain, the contact could be 'forgotten',
object_id nullified"). This pass adds that expiry, worked out against `belief/decay.py`'s
existing half-life table rather than as a new ad hoc timeout — see the new "Decay: object_id
continuity must expire" subsection below, and the corresponding Affected Modules / Implementation
Plan / Risks updates.

### Decision

**Primary fix, generalized: object-permanence correlation via `object_id`, for both perception
channels**, with the class-compatibility check as defense-in-depth doing real, load-bearing work
now (not just a rare backstop). Still not gate re-tuning, still not relaxing the ambiguity
policy — the spatial/class gate is untouched as a mechanism; what changes is how *often* a
percept actually reaches it.

**What "continuity" now means.** For any incoming percept whose channel resolved a DCS
`object_id` this poll, check whether that `object_id` has ever been seen before by that
channel's `PerceptionSource` instance, however long ago, however far the position may have
drifted in between. If yes, fold the percept directly onto the contact that earlier sighting
belongs to and **skip `passes_gate` entirely**. If no — first-ever sighting of this `object_id`,
or the channel didn't resolve one this poll at all — fall through to the existing spatial/class
gate, exactly as it works today (zero-or-one-or-many-candidates → the Stage 1 decision rule,
unchanged).

**Where the correlation state actually lives — this is the concrete answer to "where does the
most-recently-known `object_id` get stored," and it turns out to need *less* new surface than
the zero-gap design already had, not more:**

- No new field on `Contact`. `object_id` still never crosses into `belief/` — the boundary
  principle from the original plan holds exactly as stated, just applied over a longer window.
- What crosses the `perception/` → `belief/` boundary is unchanged in *shape*:
  `continues_observation_id: str | None` on `Observation`/`Percept`, carrying a previously
  emitted `Observation.id` — still "this report continues that earlier report," still not a DCS
  truth field, still the same kind of bookkeeping `Percept.observation_id` already legitimately
  carries. What changes is only that the earlier `Observation.id` it names may now be many polls
  old rather than always the immediately preceding one.
- `belief/contacts.py`'s `ContactStore` already needs (per the original plan) an
  `_observation_id_to_contact_id: dict[str, str]` index to resolve that field to a contact.
  That index, once populated, is *already* gap-agnostic — an `observation_id` minted 50 polls ago
  still resolves to its contact, because nothing in `ContactStore` ever expires or re-keys a
  contact's contributed observation ids. **No change is needed in `belief/contacts.py` to
  support gaps** — the zero-gap design's own index already supports arbitrary-age lookups; the
  only thing that was artificially narrow was *when `perception/` chose to populate the field*.
- The actual change is entirely inside `perception/`: each channel keeps a **persistent**
  `object_id -> last-emitted-Observation.id` map (not the zero-gap design's
  previous-poll-only comparison), consulted and updated on every poll for as long as that
  `PerceptionSource` instance lives (i.e., for the session). This is a strictly smaller
  architectural change than it might sound — it is the same map the zero-gap design already
  proposed, just not cleared between polls.

**Interaction with the waived "different unit moved into the same spot" edge case** (user's own
framing, explicitly not to be specially handled): this case is architecturally self-excluding
from the correlation path, not something that needs a guard. A genuinely different real object
has a genuinely different DCS `object_id` — it can never produce a same-`object_id` continuity
match. So it always falls through to the existing spatial/class gate, exactly as any first
sighting or non-continuity reacquisition already does today. The user's waiver ("that's getting
into fairly hairy details... do not bring further value") is therefore already honored by
construction: nothing new needs to be built to decline handling it, and nothing in this design
accidentally handles it either. What *does* change is that this gate path is now reached in
exactly the same circumstances as before (first sighting, or a genuinely different object)
— it is not reached *more* by the "different unit" scenario specifically, only by real gaps in
general, most of which *do* correlate correctly and skip the gate.

**Interaction with the class-compatibility defense-in-depth.** With gaps in scope generally
(not just the rare simultaneous-gap edge case the original plan flagged as residual), the
correlation path is now reached far more often — most of a session's re-observations, not just
adjacent-poll ones. This means the defense-in-depth check is no longer a rarely-exercised
backstop; it is now doing real, frequent work; **the check itself is unchanged**
(`class_compatibility` between the incoming percept and `contact.last_class_raw`, same
incompatible → fall back to gate rule), but its practical importance is higher, and the one gap
it does not close — an `object_id` that is somehow reused for a *different, same-class* real
object during a gap — is correspondingly more exposed than before, purely because gaps are now
common instead of rare. This is the specific residual risk the user named as "stays a known
residual risk per the plan's existing framing" (kill/respawn id reuse); it is not a new risk
this revision introduces, but it is a risk this revision makes more consequential by exercising
the gap path far more often. See Risks.

**Interaction with the scope/HelperAI channel (`hybrid_source.py`) — now in scope, reversing the
original plan's exclusion.** The original plan excluded this channel because it read the
exclusion as needing to solve "which of last poll's resolved leaves does this poll's leaf-text
refer to" — a real text-matching problem. That framing no longer applies: `hybrid_source.
associate()` already resolves each leaf to a `WorldObjectCandidate`, which already carries a
real `object_id` (`perception/association.py`'s `WorldObjectCandidate.object_id`). Correlation
can be keyed on that resolved `object_id`, exactly like naked-eye, without ever comparing leaf
text across polls — the harder problem the original plan was avoiding simply isn't the problem
that needs solving here. Given the user's own framing ("the scope channel's whole nature is
intermittent/gappy relative to the target's continuous existence"), this channel is exactly
where object permanence matters most, not least — it is now in scope for this fix (see Affected
Modules). Flagged as a genuine scope addition beyond the original naked-eye-only plan, not a
quiet extension — see Risks for what's untested about it.

**Decay: object_id continuity must expire, not persist indefinitely — a genuine addition, not a
restatement of the persistent-map design above.** The persistent `object_id -> last Observation.
id` map inside each `PerceptionSource` (see above) has no size or time bound on its own — that's
fine for *memory* (it's small, bounded by the count of distinct objects ever seen this session),
but wrong for *trust*: nothing should keep treating a same-`object_id` percept from an hour ago as
automatically the same contact forever. Checked against `belief/decay.py`'s existing "one table"
of half-lives (`IDENTITY_HALF_LIFE_S` = 600s, `POSITION_HALF_LIFE_S` = 30s, `MOTION_HALF_LIFE_S` =
60s / `GENERAL_AREA_HALF_LIFE_S` = 180s declared-not-yet-consumed, `LOST_THRESHOLD_S` = 120s
derived as 4x `POSITION_HALF_LIFE_S`) rather than a fourth parallel mechanism, per that module's
own stated intent ("what matters structurally is that they live in one table").

- **Not `LOST_THRESHOLD_S`.** That threshold governs `certainty_of`'s position/tracking
  narrative — when the crew would say "I lost him," 120s after `last_seen_sim`. Object_id
  correlation is an *identity* claim ("I still believe this is the same vehicle"), not a position
  claim — and `decay.py`'s own docstring names identity as the slowest-decaying attribute,
  explicitly *because* "a crew member does not forget 'that was a BMP' on the timescale it takes
  the BMP to drive out of sight." Tying object_id memory to `LOST_THRESHOLD_S` would nullify the
  identity claim at exactly the moment the concept doc says it should still be trusted most.
- **Recommendation: anchor to `IDENTITY_HALF_LIFE_S` (600s), reused directly, not multiplied.**
  Add `OBJECT_ID_MEMORY_S: Final[float] = IDENTITY_HALF_LIFE_S` to `belief/decay.py`'s existing
  table — declared in terms of the existing constant, not a new independently-chosen number, so
  the two cannot silently drift apart — plus one pure function,
  `object_id_continuity_valid(contact: Contact, now_sim: float) -> bool`
  (`now_sim - contact.last_seen_sim <= OBJECT_ID_MEMORY_S`), in the same style as `certainty_of`/
  `position_confidence`/`classification_confidence_at`. Reused as a straight equality rather than
  a derived multiple (unlike `LOST_THRESHOLD_S`'s 4x) because this is a binary trust/no-trust
  gate, not a ladder needing room for an intermediate state the way `certainty_of` does — the
  point at which `classification_confidence_at` would already call *this same contact's*
  identity claim "50% decayed" is the natural place to also stop trusting a second identity claim
  (object_id continuity) built on the same premise.
- **Where the check lives, and why not in `perception/`.** In `belief/contacts.py`, not inside
  each `PerceptionSource`'s own persistent map. Two reasons: (1) `perception/` must not depend on
  `belief/` — the existing layering only ever runs the other way (`belief/association_over_time.
  py` already imports from `perception/`, never the reverse) — so a decay check reading `belief.
  decay.IDENTITY_HALF_LIFE_S` cannot live in `naked_eye_source.py`/`hybrid_source.py` without
  inverting that dependency. (2) `Contact.last_seen_sim` is the *right* anchor anyway, and only
  `belief/` has it: it reflects the most recent observation from *any* channel, not just the
  channel whose map entry is being checked — a contact kept fresh by the hybrid channel while
  naked-eye lost sight of the object for 550s should still honor naked-eye's own stale-looking map
  entry, because the contact's identity was never actually in doubt. Anchoring in `perception/`
  against each channel's own last-touched time would get this case wrong; anchoring in `belief/`
  against `contact.last_seen_sim` gets it right for free.
- **`ContactStore.ingest`'s consumption changes accordingly.** Resolving `continues_observation_
  id` through the `observation_id -> contact_id` index is necessary but no longer sufficient —
  `object_id_continuity_valid(contact, now_sim)` must also hold. Failing either check (unresolved
  id, or resolved-but-expired) falls through to the ordinary gate/ambiguity path identically —
  there is no third code path, only "continuity trusted" vs. "continuity not available for this
  percept, use the gate."
- **The persistent per-channel map itself needs no pruning or active nullification.** It stays
  exactly as designed above (never cleared, bounded by distinct-object count). A stale entry that
  fails the `belief/`-side freshness check simply isn't honored this poll; the moment the same
  `object_id` is genuinely re-observed, that channel's map entry is overwritten with a fresh
  `Observation.id` and (if still within the window) resumes working normally. No feedback channel
  from `belief/` back into `perception/` is needed to "nullify" anything.
- **Consequence, traced explicitly** (per the user's request, not left implicit): once a
  contact's identity claim has expired (`now_sim - contact.last_seen_sim > OBJECT_ID_MEMORY_S`),
  the *next* percept carrying that same DCS `object_id` — which the aircraft itself still
  considers the same object — does **not** silently reattach to the old contact. It is treated
  exactly like a percept with no `object_id` match at all: it goes through `passes_gate` against
  every existing contact, and merges, ambiguously spawns a duplicate, or founds a new contact
  under the Stage 1 policy, same as any other reacquisition. This is the correct behavior, not an
  accepted gap — "forgotten" should mean genuinely re-derived from scratch via the gate, not a
  silent reattachment the crew has no way to have independently verified after that much elapsed
  time. This does **not** delete or replace the `Contact` record itself — `ContactStore` has no
  contact-deletion mechanism at all, lost or not; what expires is only the *shortcut*, never the
  record.
- **Interaction with `LOST_THRESHOLD_S` is intentional, not coincidental.** `OBJECT_ID_MEMORY_S`
  (600s) is deliberately larger than `LOST_THRESHOLD_S` (120s), so a contact can pass through the
  full "observed → tracked → estimated → lost" ladder and still be validly reacquired via
  object_id continuity any time in the 120s-600s window after `last_seen_sim` — exactly the
  "I lost him... it's the same guy" scenario the user's own framing describes. Past 600s, the
  crew's `CONTACT_LOST` narrative and the object_id continuity mechanism agree: re-derive from
  scratch.

**Whether the gate's own tuning still matters.** Yes, materially, just less frequently. Every
contact's *founding* percept (first-ever sighting of an `object_id`, by either channel) still
goes through the gate/ambiguity path unchanged — correlation has nothing to found onto yet. So
does any reacquisition where correlation genuinely doesn't apply (no `object_id` resolved that
poll, or a truly different object at the old position). The debugger's own reproduction (below)
confirms the *runaway* shape is what correlation eliminates — the steady-state
one-contact-per-poll cascade from repeated re-observation — not the gate's role at first
contact. **Do not deprioritize the widened (7581928) gate's correctness on the theory that
correlation "handles it now."** It handles the common case; the gate is still what stands
between "two real, nearby, newly-appearing objects" and a spurious extra contact on their very
first shared poll, and it is still the entire mechanism for the explicitly-waived edge case
above.

**Rejected as primary fix, for the record** (unchanged from the original plan; both alternatives
were evaluated against the zero-gap case and neither is improved by broadening the scope):

- *Bound/self-limit the ambiguity rule* — needs a tiebreak, which is the best-match guess
  Stage 1 deliberately refused to build.
- *Narrow the gate back down, handle bucket-requantisation specially* — converges with
  continuity anyway; no independent surgical fix worth building alongside it.

### Boundary reading (confirmed by the user, scope now broader per above)

- `object_id` itself still never leaves `perception/` — it is consumed only inside each
  `PerceptionSource`'s own persistent correlation map, never serialised onto `Observation`,
  `Percept`, or `Contact`.
- What crosses is still only `continues_observation_id: str | None`, unchanged in shape from the
  original plan — an already-legitimate `observation_id`-shaped reference, not a truth field.
  The only thing that changed is how long `perception/` is willing to remember a prior mapping
  before offering that reference.
- `belief/contacts.py` and `belief/percept.py` change exactly as much as the original plan said
  they would (see Affected Modules) — no additional boundary-crossing is needed to support
  gaps, because the `observation_id -> contact_id` index the original plan already specified is
  already gap-agnostic. This is worth stating plainly since it was the open question: **the
  broader "object permanence" reading does not require a bigger boundary crossing than the
  zero-gap reading already had** — it requires `perception/` to remember longer, not `belief/`
  to know more.

### Affected Modules / Files

- `body-layer/src/perception/naked_eye_source.py` — replace the zero-gap design's
  previous-poll-only comparison with a **persistent** `_object_id_to_last_observation_id:
  dict[int, str]` field, updated whenever `_build_observation` emits for a given `object_id` (in
  both `emit_mode`s), and **never cleared** — including across a `world_objects is None` gap
  (an aircraft-layer/collector hiccup is not evidence the real object stopped existing; only the
  existing `_previously_visible_ids`/`_acquired_ids` *emission-debounce* state still resets on
  that gap, unchanged from today — this map is deliberately a third, independent piece of state
  from those two). For each object being emitted this poll: look up its `object_id` in the map;
  if present, tag `continues_observation_id` with that prior `Observation.id`; either way,
  overwrite the map entry with this poll's new `Observation.id` afterward.
- `body-layer/src/perception/hybrid_source.py` — **new scope**. Add the same persistent
  `_object_id_to_last_observation_id: dict[int, str]` mechanism, keyed on
  `AssociationResult.candidate.object_id`, populated after every successful `associate()` call
  (both confident and ambiguous results — the existing class-compatibility check is the guard
  against an ambiguous association's `object_id` being wrong, same as it already guards
  confident ones). Independent of `emit_mode`, same as naked-eye. This channel currently has no
  per-poll persistent state at all; this is a new `@dataclass` field plus a few lines in `poll`'s
  per-leaf loop, not a redesign of `associate()`/`WorldObjectCandidate` themselves.
- `body-layer/src/perception/source.py` — `continues_observation_id: str | None = None` on
  `Observation`, as originally planned. Docstring note updated: "may reference an observation
  from an arbitrary number of polls ago, not necessarily the immediately preceding one."
- `body-layer/src/belief/percept.py` — thread the field through unchanged, as originally
  planned. No further change needed for the broadened scope (see Boundary reading).
- `body-layer/src/belief/decay.py` — **new**, per the "Decay" subsection above: add
  `OBJECT_ID_MEMORY_S: Final[float] = IDENTITY_HALF_LIFE_S` to the existing constant table, and a
  pure `object_id_continuity_valid(contact: Contact, now_sim: float) -> bool` function alongside
  `certainty_of`/`position_confidence`/`classification_confidence_at`.
- `body-layer/src/belief/contacts.py` — `_observation_id_to_contact_id: dict[str, str]` index, as
  originally planned (still gap-agnostic, no change needed there). `ingest`'s consumption does
  change from the original plan: skipping `passes_gate` on a resolved `continues_observation_id`
  now additionally requires `decay.object_id_continuity_valid(contact, now_sim)` to hold, not just
  index resolution — an expired-but-resolved id falls through to the gate identically to an
  unresolved one. The class-compatibility fallback is unchanged.
- `body-layer/src/belief/association_over_time.py` — no formula change, as originally planned.
  Docstring update: state plainly that the gate is now the *exception* path (founding
  observations, and reacquisitions where `object_id` correlation didn't resolve), not merely the
  "genuine re-acquisition after a gap" path the original plan described — that description is
  now only accurate for the subset of gaps where correlation fails.
- Tests:
  - `body-layer/tests/test_naked_eye_source.py` — extend the original plan's continuity test to
    a genuine multi-poll gap (object drops out of the visible set for several polls, including
    across a `world_objects is None` poll, then reappears with the same `object_id`) →
    `continues_observation_id` still resolves to the last observation before the gap, not
    `None`. Keep the original never-cross-tag-different-objects test.
  - `body-layer/tests/test_hybrid_source.py` — new: same `object_id` resolved by `associate()`
    across a gap (leaf text absent for several polls, then a leaf resolves to the same
    `object_id` again) → continuity resolves; two different leaves/objects never cross-tag.
  - `body-layer/tests/test_contacts.py` — extend the debugger's many-poll two-object regression
    scenario (874m separation, 60 polls) to include a mid-session gap for one of the two objects,
    confirming it still stays at 2 contacts after reacquisition (see re-trace below). Add an
    explicit test for the waived edge case's *mechanics*, not special-casing it: a different
    `object_id` reported at a position matching a since-gapped contact's last-known position,
    same class → correctly falls through to the gate/ambiguity path (produces a new contact via
    the existing policy, not a forced merge) — this confirms the exclusion is structural, not
    coded, per the Decision section above.
  - Keep the existing class-incompatible-continuity-claim fallback test from the original plan,
    unchanged.
  - `body-layer/tests/test_decay.py` — new: `object_id_continuity_valid` true at exactly
    `OBJECT_ID_MEMORY_S` elapsed (boundary inclusive, matching `certainty_of`'s own `<=`
    convention), false just past it.
  - `body-layer/tests/test_contacts.py` — new: a resolved `continues_observation_id` whose
    contact's `last_seen_sim` is more than `OBJECT_ID_MEMORY_S` in the past falls through to the
    gate/ambiguity path (not a forced merge) — the expiry case. A second test confirms the
    120s-600s window: a contact well past `LOST_THRESHOLD_S` (so `certainty_of` already returns
    `"lost"`) but still within `OBJECT_ID_MEMORY_S` still merges via continuity, skipping the
    gate — the "I lost him, but it's the same guy" case the decay ordering is meant to preserve.

**No longer out of scope**: `hybrid_source.py` is now included (see above) — this is the one
substantive scope change from the original plan's Affected Modules list, beyond the gap-handling
itself.

### Implementation Plan

1. **Live verification of the one unconfirmed fact — confirmed by the user to run before the
   next live acceptance pass, not before this merge** ("I'd trust TacView implementation, it's
   widely used" — matches this plan's own lean). One addition given the broadened scope: when
   that probe is eventually run, it should specifically include a masked/out-of-FOV gap in the
   watched unit's visibility, not only continuous visibility — the desk research
   (`aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`)
   supports `object_id` stability generally, but the multi-minute-gap case (where DCS AI
   despawn/respawn or group regeneration could plausibly reuse an id) is exactly the case this
   revision leans on more heavily than the zero-gap version did. Not a blocker for this plan's
   own completion — recorded here so the eventual probe's scope isn't silently narrower than
   what the shipped code now assumes.
2. **Minimal working version.** `continues_observation_id` plumbing on `Observation`/`Percept`,
   always `None` until Stage 3 populates it — unchanged from the original plan.
3. **Naked-eye persistent correlation.** Implement the persistent
   `_object_id_to_last_observation_id` map in `naked_eye_source.py` (replacing the zero-gap
   design's previous-poll-only comparison before it's ever built, since the persistent version
   subsumes it — no need to implement the narrower version first). Test in isolation, including
   the multi-poll-gap and `world_objects is None`-survives-the-gap cases.
4. **`decay.py` addition, then `ContactStore.ingest` consumption, with defense-in-depth class
   check and the expiry check.** Add `OBJECT_ID_MEMORY_S`/`object_id_continuity_valid` to
   `decay.py` first (small, independently testable — Stage 4's own test in `test_decay.py`), then
   wire `ingest` to require both index resolution and `object_id_continuity_valid` before skipping
   `passes_gate`. This differs from the original plan, which specified only index resolution —
   the expiry check is this revision's addition.
5. **Hybrid-channel correlation.** New stage, not in the original plan: same persistent-map
   mechanism in `hybrid_source.py`, keyed on `AssociationResult.candidate.object_id`. Test in
   isolation before relying on it in any `ContactStore`-level test.
6. **Validate correctness against the exact reproduction, re-traced for the broadened design.**
   Re-run the debugger's two-object, 874m-separation, 60-poll scenario, now with a deliberate
   mid-session gap inserted for one object (it drops from the visible set for several polls,
   then reappears). Confirm it still stays at 2 contacts. This is expected to hold *more*
   robustly than under the zero-gap design, not just as robustly — under the zero-gap design,
   correlation only applied on the immediate zero-gap polls surrounding the reproduction, and
   any real gap would have fallen back to the (still-widened) gate, which is exactly the
   overlapping-gate condition that caused the original bug; under the broadened design,
   correlation applies on *every* poll, gap or not, so the gate is never re-exercised for either
   object after its founding poll. Verify this explicitly with the added `test_contacts.py`
   extension (Affected Modules), not by assumption — the reasoning above is the hypothesis the
   test needs to confirm, not a substitute for running it. The gap inserted for this scenario
   should stay well inside `OBJECT_ID_MEMORY_S` (e.g. a few tens of seconds, not minutes) — this
   stage is re-tracing the debugger's own reproduction, not re-testing the expiry boundary, which
   Stage 4's tests already cover separately.
7. **Refine — docstring/module-boundary write-up.** Update `naked_eye_source.py`'s,
   `hybrid_source.py`'s, `association_over_time.py`'s, and `contacts.py`'s module docstrings to
   state the new division of labor: `object_id` correlation (both channels) is the primary
   contact-identity mechanism for any re-observation of a previously-seen object, regardless of
   gap length; the spatial/class gate is now the exception path — founding observations and
   non-correlating reacquisitions only.

### Risks & Unknowns

- **This is a larger-consequence change than the original zero-gap plan, not merely a bigger
  version of the same one.** Object-permanence correlation is now the primary path for the
  overwhelming majority of a live session's percepts on both channels, not a shortcut for the
  zero-gap subset. A defect in the correlation or class-compatibility logic now has session-wide
  reach (silently wrong or silently missed merges across the whole session), where the original
  plan's defect surface was bounded to adjacent-poll pairs. Treat this plan's own defense-in-depth
  check and test coverage (Stage 6 especially) as correspondingly higher-stakes to get right, not
  carry over the original's confidence level unchanged.
- **`object_id` stability across a real, multi-minute gap is a weaker desk-research claim than
  stability across one skipped poll**, even though the same source material (ED's doc comment,
  Tacview's shipped implementation) is cited for both. Neither piece of evidence specifically
  exercises the "object goes out of scope for minutes, is it still the same id on return"
  question — it's a reasonable extrapolation, not a separately confirmed fact. The
  class-compatibility fallback bounds the damage (a false continuity claim degrades to the
  existing gate path) *except* when the reused/incorrect id also carries a compatible class —
  the same residual gap the original plan named, now reached far more often because gaps of this
  kind are the common case this revision is built for, not a rare edge case. This is the
  strongest argument for actually running the Stage 1 live probe with a real masked-gap scenario
  before trusting this in a long live session, even though it's not required before merging.
- **The waived "different unit occupies the same spot" edge case is structurally excluded from
  the correlation path** (different real object → different `object_id` → no continuity match →
  falls to the gate, same as before) — this is a design property, verified by the new Stage 6
  test, not an assumption. What is *not* excluded, and remains exactly the residual the previous
  bullet describes, is `object_id` *reuse* by DCS itself for a genuinely different object
  (kill/respawn or similar) — a different failure mode from the waived one, and the one that
  still matters.
- **`hybrid_source.py` correlation is new, untested-in-production scope.** The mechanism is
  structurally identical to naked-eye's, but this channel's class-compatibility check is already
  documented as weaker (`association_over_time.py`'s own docstring: free descriptive text like
  `"Slava cruiser"` often fails to resolve to an `OP_*` bucket at all, degrading to "unknown"
  rather than a real check) — so for this channel specifically, the defense-in-depth layer that
  bounds the id-reuse risk elsewhere is itself weaker. This is a real, not hypothetical, gap in
  this channel's safety margin relative to naked-eye's, worth flagging rather than assuming
  parity.
- **`SightingSpan`'s existing gap-blindness becomes materially more exercised, not newly
  introduced.** `Contact._extend_or_open_span` has never split a span on a time gap — only on a
  source change (Stage 1's own documented simplification: "this stage does not define what
  counts as a gap"). Under the original zero-gap plan this was rarely consequential, because most
  continuity-driven merges genuinely had no gap. Under this broadened design, a contact reacquired
  after a multi-minute gap silently extends its *existing* span's `end_sim` rather than opening a
  new one — the record will look like continuous observation when it wasn't. This is not a new
  defect this plan introduces (the gate-fallback path already had this exact property before any
  of this work), but it is now reached far more often, and any future feature that reads
  `sighting_spans` to answer "was this contact continuously tracked" will get a wrong answer more
  often than it would have under the original narrower plan. Out of scope to fix here (matches
  the user's own "hairy details, not worth it at this stage" framing for the adjacent edge case),
  but flagged explicitly so it isn't rediscovered as a surprise later.
- **`OBJECT_ID_MEMORY_S` (600s, reused from `IDENTITY_HALF_LIFE_S`) is a placeholder-by-inheritance,
  not a newly-calibrated figure.** It's principled relative to the existing table (identity
  outlives position, per the module's own stated ordering) but `IDENTITY_HALF_LIFE_S` itself is
  already documented as "a placeholder judgment call... revisit" — this reuse inherits that
  uncertainty rather than resolving it. If live sessions show object_id continuity being trusted
  too long (a stale reattachment) or not long enough (unnecessary duplicate spawning inside a
  window that should still have worked), revisit `OBJECT_ID_MEMORY_S` specifically rather than
  `IDENTITY_HALF_LIFE_S` itself first — the two now share a value but are conceptually distinct
  claims (classification confidence vs. correlation trust) and could legitimately decouple later
  if evidence points that way; this plan does not decouple them now for lack of any such evidence.
- **Gate tuning still matters, just less frequently** — see Decision section. Not a risk to fix
  now, but a risk to *remember*: do not read this plan as license to stop caring about
  `spatial_gate_radius_m`'s correctness.
- **New coupling in `Observation`/persistent per-source state**: unchanged in kind from the
  original plan (a field only some sources populate), now doubled (both channels carry their own
  persistent map). Acceptable for the same reasons the original plan gave; revisit if a third
  source is ever added.

### Second-Order Effect

This sets a materially stronger precedent than the original zero-gap version: object permanence
(not merely frame-to-frame continuity) becomes the base contact-identity model for both
perception channels, not an optimization for the common case. Two concrete downstream
consequences: (1) any future track-quality or staleness-surfacing feature (e.g. distinguishing
"continuously observed" from "reacquired after N minutes out of sight" in crew dialogue or the
tools/console output) can no longer infer that from contact-merge behavior itself — correlation
now succeeds across gaps of any length, so that distinction must be built as an explicit signal
on top of this (and `SightingSpan`'s current gap-blindness, above, means it isn't free from the
data already being recorded either); (2) it unblocks BL-5a's live acceptance testing more
robustly than the original plan did, since the fix now covers the realistic "masked by terrain
then reappears" scenario that live flight will actually produce, not only the narrower
continuous-visibility case the original plan's reproduction happened to hit first.
