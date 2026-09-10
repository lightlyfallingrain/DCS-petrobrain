---
name: contact-dup-continuity-of-track
description: Resolution of the BL-2.6 gate-widening vs never-guess-merge tradeoff via continuity-of-track
metadata:
  type: project
---

`plans/contact-duplication-ambiguity-runaway/plan.md` (2026-09-10) resolves a genuine
architectural tradeoff: BL-2.6's symmetric spatial-gate fix (7581928) necessarily widened
`spatial_gate_radius_m` enough that two real, moderately-separated objects (~874m) now overlap
gates, and `ContactStore.ingest`'s deliberate "two-or-more candidates → always new contact,
never guess-merge" policy (`plans/pb2-contact-memory/plan.md` Stage 1) has no self-limiting
mechanism once that fires — runaway one-contact-per-poll duplication.

**Revised 2026-09-10 (same day, second pass): scope widened from zero-gap continuity to full
object permanence**, per explicit user direction — "sensor(y) data should be treated as
factual... even if I close my eyes for a minute... I make the logical conclusion it is the same
unit." A `continues_observation_id: str | None` field on `Observation`/`Percept`, unchanged in
*shape* from the first pass, now gets populated from a **persistent** (never-cleared,
session-lifetime) `object_id -> last Observation.id` map inside each `PerceptionSource`, not a
previous-poll-only comparison. `ContactStore.ingest` needed **no change** to support this — its
`observation_id -> contact_id` index was already gap-agnostic; only `perception/`'s own map
needed to remember longer. Key insight: the broader "object permanence" reading does not need a
bigger `belief/` boundary crossing than the zero-gap reading already had — `perception/` just
remembers longer, `belief/` doesn't need to know more.

**Boundary precedent, reaffirmed and unchanged**: `object_id` itself never leaves `perception/`;
only the already-legitimate `observation_id`-shaped field crosses, same as the first pass. This
still holds even for correlation across a multi-minute gap.

**Scope change: `hybrid_source.py` is now IN scope**, reversing the first pass's exclusion. The
first pass excluded it worrying about "matching leaf text across polls" — a real problem. But
correlation keyed on `object_id` (which `associate()` already resolves via `AssociationResult.
candidate.object_id`) sidesteps that problem entirely; no leaf-text matching is needed. Lesson:
re-examine an early scope exclusion when its stated reason turns out to be avoidable by keying
on a different join column than the one that made the problem hard.

**The "different unit moved into the same spot" edge case (explicitly waived by the user, not to
be specially handled) turned out to be structurally self-excluding**: a genuinely different real
object always has a genuinely different `object_id`, so it can never produce a false continuity
match — it always falls through to the untouched gate path, same as any first sighting. Nothing
needed to be built to decline handling it. This is a reusable architecture pattern worth
remembering: sometimes a waived edge case doesn't need a guard because the correlation key you
already chose (a real, unique identifier) naturally excludes it.

**Residual, accepted risk — now materially more exposed, not new**: `object_id` *reuse* by DCS
itself (kill/respawn or similar) during a real gap is the risk that still matters (distinct from
the waived "different unit" case above, which needs no id reuse to occur). The class-
compatibility defense-in-depth check is unchanged in mechanism but now does far more real work,
since gap-spanning correlation is the common case, not a rare edge case. `hybrid_source.py`'s
class-compatibility is documented as weaker than naked-eye's (free text often fails to resolve
to an `OP_*` bucket) — so this channel's safety margin is thinner than naked-eye's for the same
risk. Also newly flagged: `Contact._extend_or_open_span` (`belief/contacts.py`) has never been
gap-aware (splits spans only on source change, never on a time gap) — a pre-existing
simplification that is now exercised far more often, since gap-spanning merges are the norm, not
the exception. Not fixed (matches the user's own "hairy details, not worth it now" framing), but
will surprise a future reader of `sighting_spans` if not remembered.

See also [[project_bl2_contact_memory_design]] (the original Stage 1 invariant) and
[[project_bl26_classification_refinement]] (the 7581928 gate-widening fix this resolves the
fallout from).
