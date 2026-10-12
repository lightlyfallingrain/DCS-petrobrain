"""`Group`/`GroupStore` -- `plans/group-reporting/plan.md` Stage 2.

**What a `Group` is, and why it is not `belief.callouts.group_candidates`.**
That mechanism buckets *rendered reports* at speech time by whether two
lines would sound the same (`belief.callouts`'s own module docstring,
"Aggregation groups in report space, not world space"). A `Group` answers a
different, prior question -- *do these already-individuated `Contact`s
belong together in the world* -- once, persistently, from belief alone, per
the user's own framing recorded in `plans/group-reporting/explore-notes.md`
("It's really an associative question, 'do these objects belong
together?'"). This module never reads or writes anything speech-shaped; it
only maintains membership.

**Cohesion is a relative gap, not a tuned radius** (explore-notes' figure-
ground cue: a loose line of vehicles reads as one group in an empty desert,
and would not in a cluttered one). Single-link union-find over `Contact.
position` (the fused (x, z) mean, `belief.position_belief.PositionEstimate`
-- world-space and bearing-independent, so a group can span 180 degrees of
bearing, per the user's own convoy-through-ownship refutation of a gaze-
wedge model). Two contacts cohere when their fused-position gap is within
`GROUP_PROXIMITY_GAP_RATIO` times the local median nearest-neighbour gap
among all currently tracked contacts -- the boundary scales with how
densely populated the scene already is, with no absolute constant.

**`GROUP_PROXIMITY_GAP_RATIO` (3.0) is a stated assumption with no data
behind it yet** (`plan.md`'s own "Risks & Unknowns" -- not even backed by
the one flown dataset `perception.group_salience`'s own cohesion constant
had). A one-line change, expected to move after the first sortie flown
under this model -- mechanism and calibration are kept in this one small
file precisely so retuning it later is a single, attributable,
uncalibrated-constant commit, not a mechanism change.

**The relative-gap test is tautological at exactly two tracked contacts**
(the historical reason a backstop exists at all). With two contacts in the
whole store, each is mathematically the other's *sole* candidate nearest
neighbour -- there is no third point to draw a genuinely different
distance from -- so the "local median nearest-neighbour gap" always equals
their own mutual separation exactly, and the cohesion threshold
(`GROUP_PROXIMITY_GAP_RATIO` times that gap) is always some multiple of
the very distance it is being compared against. Left alone, two contacts
cohere regardless of how far apart they actually are (confirmed directly
at 500 km -- `plans/group-reporting/implementation.md`'s Notable
Discoveries, found once `GROUP_REPORTING_MIN_MEMBERS` dropped to 2 and
made this size reachable at all). **The same failure mode is not actually
confined to n=2** -- at three or more tracked contacts spread kilometres
apart with nothing else in the scene, the relative rule alone still merges
dissimilar, unrelated contacts into one `Group` (`plans/group-reporting/
review.md`'s n>=3 finding, pinned by `tests/test_callouts.py::
test_2c_transcript_fixture_renders_four_lines_not_seven` before this
backstop existed). A relative-only rule has no natural floor at any n --
it is answering "is this gap small *for this scene*," never "is this gap
small in any absolute sense a person would recognise as one group" -- so a
bound belongs on every pairwise comparison, not just the tautological
n=2 case.

**The bound is measured in unit widths, not flat metres, and applies at
every scene density.** A flat metre figure ignores what the units
actually are -- 300 m means something different for infantry than for an
S-300 component. `perception.group_salience.GROUP_COHESION_GAP_UNIT_
WIDTHS` (10.0) already solved this currency problem at the perception
layer, for a different question (whether unresolved dots merge into one
*angular*, apparent-size mass at range, at the observer). This module
borrows the *currency* -- unit widths, dimensionless, automatically
range/size-correct -- not that constant or its question:
`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (its own, separate value) caps
a *world-space* metre gap between two already-resolved `Contact`s'
positions, scaled by their own believed physical size (`perception.
object_model.size_m`, via each contact's `last_class_raw` -- no
omniscience, never a DCS object_type). Each pair gets its own bound (the
mean of the two members' sizes), so a backstop between two infantry is
tighter than one between two S-300 components, exactly the currency fix
the angular constant already proved out one layer down. The relative rule
stays primary and can still be *tighter* than the backstop in a dense
scene (the figure-ground behaviour above) -- the bound only ever narrows
the relative threshold, never widens it (`min(relative, backstop)` per
pair), and single-link chaining still lets a long convoy cohere end-to-end
as long as each *neighbour* gap clears the bound, even if the convoy's
full span does not.

`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (20.0) is a stated assumption
(user direction 2026-09-29, *"I have no definitive answer. Pick something,
we'll refine it later"*), not a measurement -- there is no flown data
behind it either, same posture as `GROUP_PROXIMITY_GAP_RATIO`. In world
terms: ~140 m for a 7 m vehicle, ~36 m for 1.8 m infantry. That sits above
typical DCS road-convoy spacing (50-100 m, i.e. ~7-14 unit widths for a
7 m vehicle) with margin, and is ~7x the only real group this project has
flown data for -- the twelve-unit, ~200 m calibration line
(`body-layer/research/2026-09-22-four-column-calibration-ladder.md`),
~18 m spacing, ~2.6 unit widths. It is expected to move once a sortie
actually exercises this path, the same as `GROUP_PROXIMITY_GAP_RATIO`.

**`GROUP_REPORTING_MIN_MEMBERS` (2) is a deliberately different constant
from `perception.group_salience.GROUP_MIN_MEMBERS` (3), not a renamed copy
of it, and the two must never be made to agree by accident.** This module
used to declare its own floor under the same name and value as that
module's, on the reasoning "a pair is a pair, not a formation" -- that
reasoning was overturned by user direction 2026-09-28 (`plans/
group-reporting/plan.md`'s Stage 4 addendum): two already-individuated
`Contact`s belonging together *is* a reportable group, worded as a "pair"
(see `belief.speech.render_group_disclosure`), not withheld until a third
member arrives. Keeping the old name once its value diverged from `group_
salience`'s would have left one identifier meaning two different floors in
two modules -- exactly the collision this rename exists to avoid.
`group_salience.py`'s constant answers an unrelated question -- how many
*unresolved candidates* a distant naked-eye detection needs before it is
salient enough to be admitted at the coarser resolution threshold instead
of the finer one, calibrated against that channel's own dots-off ladder --
and stays at 3, untouched by this decision.

**Similarity and common fate are deliberately not gates here.** Proximity
plus local density is what ships this pass; adding either now would be
exactly the "regularity term fitted to n=1" mistake `group_salience.py`'s
own docstring warns against, with less evidence behind it than that module
had. See the plan's Stage 5 (deferred, gated on a sortie).

**Ground units only, honestly scoped rather than filtered** -- there is no
air/ground domain field anywhere in this codebase today, so nothing here
excludes an airborne contact structurally; this module's tests and the
naked-eye/hybrid channels that feed it are ground-only by construction, and
no claim is made about correctness for aircraft formations.

**Membership is recomputed every `tick()` from the current `Contact` set,
then reconciled against persisted `Group`s by majority-member-overlap** --
the same split/merge pattern `plans/group-contact-model/plan.md` Stage 3
already argued through in full for object-id clusters with no stable
identity, reused here as a *pattern* only (this module's members are
`Contact` ids, which already have real, stable identity, so there is no
ancestry matching or `MemberClaim` to build): no deletion, ever; the
majority child (the new cluster overlapping an old group in the most
members) keeps that group's id; a minority child (a smaller new cluster
that also overlaps the same old group) founds a fresh `Group`; two old
groups whose members now form one cluster is a merge handled by the same
greedy-by-overlap assignment with zero extra code -- only the higher-
overlap old group's id survives, and its own `established_sim`/disclosure
history describes the *merged* group's history from that point on, not any
one contributing group's -- the same "arbitrary survivor" cost `plans/
group-contact-model/plan.md` already accepted for its own clusters.

**Group identity now also survives member-id replacement (BL-12 Stage 1,
`plans/group-contact-identity/plan.md`).** Member-overlap is still tried
first and is still how a split/merge resolves -- the paragraph above is
unchanged. What changes is what happens to a cluster overlap could not
match: a second pass (`group_matches`) matches it against a *remembered*
group's properties (kind, composition, air-defence confirmation,
plausible displacement) instead of founding a fresh `Group` outright, and
a group that matches nothing is *kept*, properties frozen, for
`GROUP_REIDENTIFY_WINDOW_S` before it is actually dropped -- see
`GroupStore.reconcile`'s own docstring for the four phases in full.
`GroupStore.groups` keeps meaning "currently observed" throughout; the
retained-but-unmatched set is `GroupStore.remembered_groups`.

**No omniscience**: `reconcile` takes `Contact` objects (already-folded
belief), never an `Observation` or a DCS object id -- `belief/percept.py`'s
boundary is upstream of this module and untouched by it. Stage 1's
property-match predicate (`group_matches`) reads the same two `Contact`
fields every other computation here already does: `.position` (fused
belief) and `.last_class_raw` (believed classification, via `_profile_for_
contact` and `belief.classification.parent_class_of`) -- never a DCS
`object_type`.

**No spoken split/merge event.** A membership change is only ever visible
as a changed rendered line, once `belief.speech.render_group_disclosure`
exists (Stage 3) -- deferred per the plan's own recommendation and
`plans/group-contact-model/plan.md`'s "no `CONTACT_SPLIT` event kind,
inferred" precedent."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

from belief import classification
from belief.decay import GROUP_REIDENTIFY_WINDOW_S
from belief.position_belief import GATE_GROWTH_RATE_MPS, plausible_speed_mps
from perception import object_model

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Stated assumption, no data behind it yet -- see module docstring.
GROUP_PROXIMITY_GAP_RATIO: Final[float] = 3.0

#: Deliberately not `perception.group_salience.GROUP_MIN_MEMBERS` -- see
#: module docstring for why the two are named differently and free to
#: diverge. Two already-individuated `Contact`s are enough to report as
#: one group, spoken as a "pair".
GROUP_REPORTING_MIN_MEMBERS: Final[int] = 2

#: Absolute cap on member gap, in units of the pair's own mean believed
#: physical size, applied to every pair at every tracked-contact count --
#: not just the tautological n=2 case. Deliberately named and valued apart
#: from `perception.group_salience.GROUP_COHESION_GAP_UNIT_WIDTHS` (10.0,
#: angular, never touched by this module) -- see module docstring for why
#: the two currencies differ and must not be confused. Stated assumption
#: (user direction 2026-09-29), no data behind it yet, same posture as
#: `GROUP_PROXIMITY_GAP_RATIO`.
GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS: Final[float] = 20.0

#: Physical size (metres) used for a contact whose believed classification
#: carries no size `object_model.profile_for` can resolve -- see module
#: docstring. The reference vehicle size `perception.visibility`'s
#: angular-radius tiers are themselves calibrated against, not `object_
#: model.DEFAULT_SIZE_M` (5.0 m, ED's "unclassified" bucket for a
#: different purpose -- see `_representative_size_m`).
GROUP_REPORTING_UNKNOWN_SIZE_M: Final[float] = 7.0


#: Per-class cohesion backstop policy (`plans/group-cohesion-redesign/
#: plan.md` §2) -- `STRICT` is today's unit-widths backstop (the default for
#: every class not named in `_OP_CLASS_COHESION_BACKSTOP`); `EAGER` replaces
#: it with the far looser flat `GROUP_REPORTING_EAGER_COHESION_CAP_M`. Not a
#: bool: a third policy is a plausible future addition, and an enum names
#: the two existing values rather than leaving `eager: bool` to be read as
#: "the only other option."
#:
#: **`EAGER` meant no backstop at all (`math.inf`) until 2026-10-11**
#: (BL-12 Stage 0b). It is now looser-but-bounded, which is the third
#: policy this comment anticipated, arrived at from the other direction.
class CohesionBackstop(Enum):
    STRICT = "strict"
    EAGER = "eager"


#: `OP_INFANTRY` only -- user direction 2026-10-01,
#: *"Ok to merge infantry too eagerly. Infantry is the least detectable and
#: also least important of unit types."* (`plans/group-undermerging/
#: explore-notes.md`). Not extended to any other class. `EAGER` fires for a
#: pair only when **both** members resolve to `OP_INFANTRY` -- the error
#: this policy accepts (over-merging infantry) is asymmetric and cheap;
#: nothing else gets the same latitude, including the *other* member of a
#: pair that happens to contain infantry.
#:
#: **It read `either` member until 2026-10-11, and that was `BL-B48`**
#: (BL-12 Stage 0a). An infantry contact then bridged non-infantry
#: contacts without bound, because the eagerness was being applied to the
#: pair rather than to the infantry: measured on this tree,
#: `armor@1km + truck@3km` correctly stayed two separate things (pair
#: threshold 130 m against a 2,000 m gap) while adding `infantry@7km`
#: merged all three into one group 6,000 m across. A group that wide has no
#: single believable bearing or range, which is the pilot-facing form of
#: the defect. The `both` reading keeps the user's sentence literally true
#: about infantry and nothing else: infantry-to-infantry thresholds and
#: unions were unchanged by Stage 0a (`tests/test_groups.py::test_infantry_
#: only_scene_keeps_identical_thresholds_and_unions`). Stage 0b then moved
#: them deliberately, as a calibration -- see `GROUP_REPORTING_EAGER_
#: COHESION_CAP_M`.
_OP_CLASS_COHESION_BACKSTOP: Final[dict[str, CohesionBackstop]] = {
    "OP_INFANTRY": CohesionBackstop.EAGER,
}
_DEFAULT_COHESION_BACKSTOP: Final[CohesionBackstop] = CohesionBackstop.STRICT

#: `AIR_DEFENSE_OP_CLASSES` was declared here until 2026-10-11 and now
#: lives in `belief.classification`, the one copy (`BL-B51`) -- see that
#: constant's own docstring for why the lattice module is its home.
#:
#: It was never read by this module, which is worth saying because it sat
#: next to the installation cap below and the two ask different questions
#: (`plans/group-cohesion-redesign/plan.md` §1/§4's Correction 2):
#: `_cluster_contacts`'s installation-cap selection asks the narrower
#: "`profile.installation_component is True` on both members" and does not
#: use the class set at all, while `belief.speech.render_group_disclosure`'s
#: delta taxonomy asks the broader "is a newly arrived member's class air
#: defence at all", because "more air defence is always news" applies to a
#: single-vehicle SHORAD system as much as to a fixed site (an Osa joining
#: a group that already has a Shilka is news for exactly this reason).

#: Flat cap, metres, on inter-member spacing for a pair where **both**
#: members are fixed air-defence-installation components (`profile.
#: installation_component is True`) -- `plans/group-cohesion-redesign/
#: plan.md` §1, replacing the first draft's `op_class`-keyed design (which
#: conflated the genuine S-125 fixed site with four single-vehicle systems).
#: 500 m, grounded in `body-layer/research/2026-10-01-sam-site-geometry.md`
#: (real S-75/S-125 launcher spacing is ~60-230 m; this cap carries margin
#: above the best-documented fixed-site figures without reaching far enough
#: to also cover a dispersed mobile-TELAR battery, which is deliberately
#: not this rule's job -- see that research note's §"Possible Approaches").
#: Composed as `min(relative_threshold, GROUP_REPORTING_INSTALLATION_
#: COHESION_CAP_M)`, same as the unit-widths backstop -- the relative test
#: still governs everything, this is not an unconditional "any two
#: installation parts anywhere merge" rule.
GROUP_REPORTING_INSTALLATION_COHESION_CAP_M: Final[float] = 500.0

#: Flat cap, metres, on inter-member spacing for a pair where **both**
#: members' `op_class` has an `EAGER` cohesion policy (today: two infantry)
#: -- BL-12 Stage 0b, `plans/group-contact-identity/plan.md` amendment A2's
#: Q-B, answered by the user 2026-10-11 (*"a group gets a maximum
#: extent"*).
#:
#: **A stated assumption, not a measurement** -- same posture as
#: `GROUP_PROXIMITY_GAP_RATIO` and `GROUP_REPORTING_COHESION_GAP_UNIT_
#: WIDTHS`, and the user judges it in the air. What it replaced was
#: `math.inf`, which is why a finite figure is needed at all: with no
#: absolute backstop the relative test *cannot reject any pair at n = 2*,
#: because both nearest-neighbour gaps are then the pair's own distance, so
#: `GROUP_PROXIMITY_GAP_RATIO * median(gap) >= gap` always. Two infantry
#: therefore formed one group at **any** separation, and infantry is often
#: the only class held at range.
#:
#: **Derived from the resolution of the sentence the group is spoken in.**
#: `belief.speech._format_range_km` rounds a spoken range to the nearest
#: 0.5 km (verified by running it: 2 750 m, 3 000 m and 3 249 m all say
#: *"3 kilometres"*; 3 251 m says *"3.5 kilometres"*), so *"that group, two
#: o'clock, three kilometres"* is a claim with 500 m of resolution. A group
#: wider than that contains members the same renderer would place in
#: different buckets, which is the point at which the sentence stops being
#: true of all of them. This module reads nothing speech-shaped at runtime
#: (module docstring) and does not import `speech` -- the 500 m is
#: transcribed from that renderer's rounding step, not looked up.
#:
#: Cross-checks against figures already in the repo, all of which this cap
#: clears or deliberately does not:
#:
#: - **The clock hour.** One 30-degree clock bucket is `2 * tan(15 deg) * R`
#:   = 0.536 R wide, so a 500 m extent sits inside a single clock hour from
#:   R >= 933 m outward. Below that it can straddle two, which is accepted:
#:   inside a kilometre the pilot can see the thing himself.
#: - **The infantry pair `EAGER` was introduced for** is 260 m apart
#:   (`tests/test_groups.py::test_infantry_pair_merges_eagerly_past_the_
#:   ordinary_backstop`, the geometry the pre-`group-cohesion-redesign`
#:   pinned test forbade). Admitted, with 1.9x margin.
#: - **Measured nearest-neighbour spacing** between distinct objects on the
#:   one flown sortie reduced for this: median 16 m, p75 55 m, p95 342 m
#:   (`plans/post-review-fixes/explore-notes.md` §2). Admitted at p95.
#: - **Measured cluster-to-cluster separation** on that same data is median
#:   236 m at a 100 m single link, p75 378 m (ibid.) -- *under* this cap, so
#:   two clusters a denser rule would keep apart can still merge here. That
#:   is the latitude *"ok to merge infantry too eagerly"* actually granted,
#:   and it is why this cap is only reached by an infantry-infantry pair.
#: - **In this module's own unit-widths currency** it is 500 / 1.8 = 277.8
#:   infantry unit widths, against `GROUP_REPORTING_COHESION_GAP_UNIT_
#:   WIDTHS`'s 20. Stated in metres rather than unit widths because what it
#:   bounds is a *spoken* extent, which is metres, and because the only
#:   class that reaches it has one size.
#:
#: **Every cross-check above that is a *spacing* is true geometry; the cap
#: is applied to *believed* spacing, and that omits the dominant error
#: term.** `_cluster_contacts` compares `contact.position.x`/`.z` -- the
#: fused belief, explicitly not uncertainty-budgeted (its own docstring).
#: Of the five bullets above, **three** are spacings and all three are
#: ground truth -- the p95 342 m nearest-neighbour and the median 236 m
#: cluster-to-cluster are reduced from a belief-truth log **deduplicated
#: by `object_id`** (`plans/post-review-fixes/explore-notes.md` §2), i.e.
#: keyed to distinct real objects, so the per-contact scatter this cap
#: actually sees is deduplicated out of them; and the 260 m pair is a
#: fixture whose two positions are written as literals (0.0 and 260.0),
#: with no noise applied. The remaining **two** (the clock hour, the
#: unit-widths currency) are conversions of the 500 m itself and contain
#: no spacing at all. The omitted term is `perception.estimation`'s
#: `sigma_down_m = RANGE_FRACTIONAL_SIGMA * true_range_m`, with
#: `RANGE_FRACTIONAL_SIGMA = 0.17`. For two independently observed,
#: genuinely co-located contacts the *believed* separation therefore
#: carries `sigma_delta = 0.17 * sqrt(2) * R = 0.2404 R` -- the
#: decomposition, not a lumped figure: **338 m at 1 406 m, 818 m at
#: 3 403 m** (the two ranges below). So a real, tight infantry pair can
#: fail this cap on belief noise alone, in the *under*-merging direction
#: the *"ok to merge infantry too eagerly"* grant exists to avoid. It is
#: bounded rather than permanent: fusion shrinks the error roughly as
#: 1/sqrt(looks), so it is a several-second delay in grouping, which
#: `_cluster_contacts`' own docstring already accepts as *"a human
#: copilot needing a moment"*.
#:
#: **The band where that can actually be reached is binoculars raised,
#: ~1.4-3.4 km** -- not a 2-7 km gradient, because infantry
#: (`ObjectTypeProfile(size_m=1.8)`, `perception.object_model`) cannot be
#: held at longer ranges by any *implemented* optic. Running
#: `perception.visibility.tier_ranges(presence_size_m=1.8,
#: recognition_extent_m=1.8, ...)` against the real constants gives four
#: presence ceilings, each a quotient and a multiplier rather than a
#: quoted number:
#:
#: - **600 m** unaided, as a lone mark: 1.8 / `LOWRES_ANGULAR_RADIUS_RAD`
#:   0.003.
#: - **1 406 m** unaided, once group-admitted: 1.8 /
#:   `RESOLUTION_ANGULAR_RADIUS_RAD` 0.00128.
#: - **1 452 m** and **3 403 m** -- those two times
#:   `optics.BINOCULAR_OPTIC.presence_range_mult` 2.42.
#:
#: (`NAKED_EYE_RANGE_CAP_M` 10 000 m does not bind at any of them.) **The
#: 9K113 is not implemented at all** -- `perception.optics` declares only
#: `UNAIDED_OPTIC` and `BINOCULAR_OPTIC`, the sight having been deferred
#: entirely by the user's scope cut of 2026-09-20 -- so the optic that
#: could see infantry at multiple kilometres does not exist in this code.
#: Below ~1.4 km, `sigma_delta` is <= 338 m, inside this cap.
#:
#: **Accepted by the user's decision of 2026-10-11, not overlooked**
#: (`docs/acceptance/2026-10-11-infantry-detectability-feedback.md`):
#:
#:   > *"infantry is the least important unit type of combat units. It's
#:   > good to have it in, but since it can only be seen at close range,
#:   > we only really need to consider it at close range."*
#:
#: So the cap stays at 500 m and the band is documented rather than tuned
#: for. **It must not be retuned to cover it**: widening it would loosen
#: every close-range infantry pair, where the geometry above is sound, to
#: buy the least important class one band under a deliberately raised
#: optic. The *error model* is what should change -- `[[BL-B55]]`:
#: `perception.estimation.naked_eye_sigma_m(true_range_m)` takes range
#: only, at one call site (`perception/naked_eye_source.py`), so a
#: binocular look already sees 2.42x further while being believed no more
#: precisely than the naked eye. `estimation.py` is optic-blind while
#: `visibility.py` is optic-aware; that asymmetry is the defect, and this
#: cap sits downstream of it.
#:
#: **Equal to `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M` by coincidence,
#: not by derivation, and the two must stay separate constants.** That one
#: is 500 m because real S-75/S-125 launcher spacing is ~60-230 m
#: (`body-layer/research/2026-10-01-sam-site-geometry.md`); this one is
#: 500 m because that is the spoken range bucket. Retuning either must not
#: move the other -- the same reason `GROUP_REPORTING_MIN_MEMBERS` is not
#: `perception.group_salience.GROUP_MIN_MEMBERS` (module docstring).
#:
#: **What would falsify it.** The first two are observable only once a
#: group-identity trace line exists (BL-12 Stage 1, amendment A4): two
#: infantry groups the pilot thinks of separately, under 500 m apart,
#: spoken as one; or a real infantry group more than 500 m across that
#: stops being reported at all.
#:
#: **A third observation is *not* a verdict on this number, and must not
#: be read as one**: infantry at range reported individually for several
#: seconds before pairing, where before this cap existed they paired
#: immediately. That is the believed-separation noise above -- it is
#: attributable to **the range and the raised optic**, not to the cap's
#: value, and it resolves itself as fusion tightens the estimate.
#: Retuning the 500 m in response to it would be treating `[[BL-B55]]`'s
#: optic-blind error model as a cohesion problem.
GROUP_REPORTING_EAGER_COHESION_CAP_M: Final[float] = 500.0

_GROUP_ID_PREFIX: Final[str] = "GROUP"


@dataclass
class Group:
    """One persisted associative belief that a set of `Contact`s belongs
    together -- structurally parallel to `belief.contacts.Contact`, but far
    smaller: no observation log, no per-member position, no per-member
    identity of its own, because membership is a set of ids into a store
    that already has identity for each of them.

    `last_spoken_signature`/`last_spoken_sim` are this dataclass's analogue
    of `Contact.last_emitted_certainty` -- the group-level disclosure
    snapshot `belief.speech.render_group_disclosure`'s progressive-
    disclosure trigger compares against (Stage 3). `None` until this group
    has been spoken for the first time; carried over untouched across a
    reconciliation that keeps this group's id (a split's majority child, or
    an unchanged group), reset to `None` only for a group founded fresh
    (a brand-new cluster, or a split's minority child) -- a fresh group has
    said nothing yet, regardless of what its members individually said
    before they were grouped.

    `last_spoken_member_contact_ids`/`last_spoken_leading_contact_id`/
    `last_spoken_differentiated` are the delta-taxonomy's own disclosure
    snapshot (`plans/group-cohesion-redesign/plan.md` §4) -- what
    `render_group_disclosure` last saw when it actually spoke, read back on
    the next call to decide full/delta/silent. Same carry-over/reset rule as
    `last_spoken_signature` above: untouched across a reconciliation that
    keeps this group's id, reset to the empty/`None`/`False` defaults only
    for a freshly founded group.

    **The seven fields below are BL-12 Stage 1** (`plans/
    group-contact-identity/plan.md`) -- the remembered *properties* a group
    carries so its identity can survive a reconcile where none of its
    members' contact ids are the ones last seen (member-id replacement,
    D4/D5/D7). All additive, all defaulted, so every pre-existing
    construction site (including test fixtures that only ever pass the
    four original fields) keeps compiling. Every one is computed from
    `Contact.position` (fused belief) and `Contact.last_class_raw`
    (believed classification) -- never a DCS `object_type` or an
    `Observation` -- so the no-omniscience boundary this module's own
    docstring states is unchanged by Stage 1.

    `last_observed_sim` is the last reconcile at which a cluster actually
    matched this group -- distinct from `last_reconciled_sim`, which now
    means "the last reconcile call that still knew about this group at
    all," matched or merely retained. The two coincided for every group
    before Stage 1, because an unmatched group was simply dropped; now a
    retained-but-unseen group advances `last_reconciled_sim` every call
    while `last_observed_sim` stays fixed at the reconcile it was last
    actually seen.

    `centroid_x`/`centroid_z` are the mean of the matched cluster's
    `Contact.position.x`/`.z` -- needed because the members may be gone by
    the time a later reconcile attempts to match against this group.
    `centroid_uncertainty_m` is the RMS (quadratic mean) of the matched
    members' own `PositionEstimate.radius_m()` -- the slack term
    `group_matches`'s displacement test budgets against, not a measure of
    the cluster's *extent* (which the Stage 1 amendment's A2/A4 track
    separately, in the sortie trace, precisely because this field cannot
    stand in for it -- a wide, well-observed group has a small per-member
    radius and a large extent at once).

    `composition` is the sorted `(op_class, count)` multiset over members,
    resolved via `_profile_for_contact` (`object_model.profile_for` on each
    member's `last_class_raw`) -- the same resolution `_cluster_contacts`
    already uses for size/backstop, so composition and cohesion never read
    a believed classification through two different paths.

    `installation` is `True` only when every member's resolved profile has
    `installation_component is True` -- the same all-or-nothing question
    `_pair_backstop_m`'s installation cap already asks pairwise, lifted to
    the whole group.

    `air_defence_composition` is the air-defence subset of `composition`,
    **resolved through the classification lattice
    (`belief.classification.parent_class_of`), not through `_profile_for_
    contact`** -- amendment A3's correction. `object_model.profile_for`
    keyword-matches DCS *type* designations; a classification held at
    *class* level (which is what a contact holds before it is identified to
    type, i.e. most of the time at range) carries the `OP_*` string itself
    and matches no keyword, so four of the five air-defence classes would
    silently fail a `profile_for`-based test. This is `BL-B47`'s own
    boundary decision applied to Stage 1's two new consumers (this field,
    and `group_matches`'s test 3). Kept as its own field rather than
    re-derived at match time, because D6 keys the air-defence confirmation
    gate on the *remembered* value -- by the time a match is attempted the
    members producing it may be gone."""

    id: str
    member_contact_ids: frozenset[str]
    established_sim: float
    last_reconciled_sim: float
    last_spoken_signature: str | None = None
    last_spoken_sim: float | None = None
    last_spoken_member_contact_ids: frozenset[str] = frozenset()
    last_spoken_leading_contact_id: str | None = None
    last_spoken_differentiated: bool = False
    last_observed_sim: float = 0.0
    centroid_x: float = 0.0
    centroid_z: float = 0.0
    centroid_uncertainty_m: float = 0.0
    composition: tuple[tuple[str, int], ...] = ()
    installation: bool = False
    air_defence_composition: tuple[tuple[str, int], ...] = ()


def _pairwise_distance(
    positions: Sequence[tuple[float, float]], i: int, j: int
) -> float:
    xi, zi = positions[i]
    xj, zj = positions[j]
    return math.hypot(xi - xj, zi - zj)


def _profile_for_contact(contact: Contact) -> object_model.ObjectTypeProfile:
    """`contact.last_class_raw` (the believed classification string; no
    omniscience, never a DCS `object_type`) run through `object_model.
    profile_for` -- shared by `_representative_size_m` (size) and
    `_cluster_contacts`'s per-pair backstop selection (`installation_
    component`, cohesion policy), so the two never read a believed
    classification through two different paths."""
    return object_model.profile_for(contact.last_class_raw)


def _representative_size_m(profile: object_model.ObjectTypeProfile) -> float:
    """The physical size (metres) used to scale a contact's share of a
    pair's cohesion backstop, given its already-resolved `profile`
    (`_profile_for_contact`).

    Falls back to `GROUP_REPORTING_UNKNOWN_SIZE_M` whenever that lookup
    could not resolve a real type -- detected via `object_model.
    DEFAULT_OP_CLASS`, the same "no real match" signal `belief.
    classification._op_class_of` and `belief.speech._identification_lead`
    already key off, rather than duplicating a `SpecificityLevel` check
    here. This covers both cases that need a default: genuinely no
    classification claim yet (`PRESENCE`/`UNKNOWN`, whose value is the
    `OP_GROUPSOMETHING` placeholder), and a `CLASS`-level value that is
    itself an `OP_*` bucket string (e.g. `"OP_ARMORED"`) rather than a
    keyword-matchable type name -- `profile_for` cannot resolve either, and
    both deserve the same honest default rather than a silently wrong
    size."""
    if profile.op_class == object_model.DEFAULT_OP_CLASS:
        return GROUP_REPORTING_UNKNOWN_SIZE_M
    return profile.size_m


def _pair_backstop_m(
    profile_i: object_model.ObjectTypeProfile,
    profile_j: object_model.ObjectTypeProfile,
    size_i: float,
    size_j: float,
) -> float:
    """The absolute cohesion backstop (metres) for one pair, given both
    members' resolved profiles/sizes -- `plans/group-cohesion-redesign/
    plan.md` §3's composition order, in priority:

    1. **Both** members are fixed-installation components
       (`installation_component is True` on both): the flat
       `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`. A **mixed** pair (one
       installation component, one not) falls through to the ordinary
       rule below -- an installation cap is only meaningful when both
       members are plausibly parts of the same site.
    2. **Both** members' `op_class` have an `EAGER` cohesion policy
       (`_OP_CLASS_COHESION_BACKSTOP`, today only `OP_INFANTRY`): the flat
       `GROUP_REPORTING_EAGER_COHESION_CAP_M`, far looser than the ordinary
       rule but finite (it was `math.inf` until BL-12 Stage 0b -- see that
       constant on why an infinite value made the relative test unable to
       reject anything at n = 2). A **mixed** pair (one eager member, one
       not) falls through
       to the ordinary rule below, for the same reason rule 1 does it: the
       eagerness was granted to a *kind of thing*, and a cap that only one
       member qualifies for is not a statement about the pair. See the
       module docstring's `_OP_CLASS_COHESION_BACKSTOP` note on what the
       `any`-member reading cost (`BL-B48`).
    3. Otherwise, the ordinary unit-widths backstop
       (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * mean(size_i, size_j)`).

    No profile is authored as both `installation_component=True` and
    `EAGER`, so (1) and (2) never compete for the same pair in practice
    (module docstring)."""
    if profile_i.installation_component and profile_j.installation_component:
        return GROUP_REPORTING_INSTALLATION_COHESION_CAP_M
    backstop_i = _OP_CLASS_COHESION_BACKSTOP.get(
        profile_i.op_class, _DEFAULT_COHESION_BACKSTOP
    )
    backstop_j = _OP_CLASS_COHESION_BACKSTOP.get(
        profile_j.op_class, _DEFAULT_COHESION_BACKSTOP
    )
    if backstop_i is CohesionBackstop.EAGER and backstop_j is CohesionBackstop.EAGER:
        return GROUP_REPORTING_EAGER_COHESION_CAP_M
    return GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * (0.5 * (size_i + size_j))


def _cluster_contacts(
    contacts: Sequence[Contact],
    gap_ratio: float,
    min_members: int,
) -> list[frozenset[str]]:
    """Single-link union-find over `contact.position.x`/`.z`. Two contacts
    cohere when their gap clears both of two thresholds: the relative test
    (`gap_ratio * median(nearest-neighbour gap)`, scene-density-scaled, see
    module docstring) and the pair's own absolute backstop
    (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * mean(the pair's own
    believed size)`, `_representative_size_m`) -- `min()` of the two,
    applied to *every* pair regardless of how many contacts are tracked
    (see module docstring for why the old n<3-only gating did not go far
    enough). Clusters smaller than `min_members` are dropped entirely
    (never returned as a pair or a singleton); a total contact count below
    `min_members` short-circuits with no distance computation at all,
    since no cluster meeting the floor is possible either way.

    **Investigated and deliberately not budgeted by position uncertainty**
    (`plans/group-undermerging/debug.md`, 2026-10-01 sortie debug): a
    freshly founded contact's covariance is wide (a single naked-eye look
    is ~300 m of RMS uncertainty even at 500 m range,
    `Contact.position.radius_m()`), and a first attempt at this fix
    subtracted each pair's combined uncertainty from their raw gap before
    comparing it to `pair_threshold`. Replaying the real 2026-10-01 sortie
    trace showed the *unmodified* mechanism already forms the correct
    multi-member group once enough looks accumulate (confirmed against
    the real spoken output, `"Danger, short range SAM. Also three
    armor..."` at the correct composition) -- the few seconds of
    individually-reported members beforehand are this system's equivalent
    of a human copilot needing a moment to resolve a new contact, not a
    defect. The uncertainty-budgeted version, meanwhile, regressed what was
    then a pinned two-infantry-stays-ungrouped test (`OP_INFANTRY` was
    `STRICT` at the time, like every other class): one look's ~300 m
    covariance swallowed a gap nearly 10x the infantry backstop. Budgeting a
    single look's full uncertainty is too blunt an instrument for a strict
    class; a real fix would need something better than a flat subtraction
    (e.g. a proper Mahalanobis-style test, or hysteresis that only favours
    an *already-formed* group's continuity rather than loosening
    first-contact formation) -- out of scope for this debug pass, which
    found no live symptom this mechanism actually needed to fix. **This
    finding does not generalise to `OP_INFANTRY` post-dating this
    investigation** -- `plans/group-cohesion-redesign/plan.md` later made
    exactly that class `EAGER` (then: no backstop at all; since BL-12
    Stage 0b, `GROUP_REPORTING_EAGER_COHESION_CAP_M`) by deliberate user
    direction, not by retuning this uncertainty question; the two are
    unrelated fixes to the same test's old pinned behaviour.

    **Per-pair backstop is `_pair_backstop_m`** (`plans/
    group-cohesion-redesign/plan.md` §3): installation cap, then per-class
    cohesion policy (`EAGER`/`STRICT`), then the ordinary unit-widths
    backstop -- see that function's own docstring for the priority order.

    O(n^2) in the number of currently tracked contacts (same cost shape
    `perception.clustering`/`perception.group_salience` already pay) --
    fine at today's contact counts, the plan's own noted risk if a sortie
    produces materially more simultaneous contacts."""
    if len(contacts) < min_members:
        return []
    ids = [c.id for c in contacts]
    positions = [(c.position.x, c.position.z) for c in contacts]
    profiles = [_profile_for_contact(c) for c in contacts]
    sizes = [_representative_size_m(profile) for profile in profiles]
    n = len(ids)

    nn_gaps: list[float] = []
    for i in range(n):
        best = math.inf
        for j in range(n):
            if i == j:
                continue
            d = _pairwise_distance(positions, i, j)
            best = min(best, d)
        nn_gaps.append(best)
    median_gap = statistics.median(nn_gaps)
    relative_threshold = gap_ratio * median_gap

    parent = list(range(n))

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            pair_backstop = _pair_backstop_m(
                profiles[i], profiles[j], sizes[i], sizes[j]
            )
            pair_threshold = min(relative_threshold, pair_backstop)
            if _pairwise_distance(positions, i, j) <= pair_threshold:
                union(i, j)

    members_by_root: dict[int, list[str]] = {}
    for i in range(n):
        members_by_root.setdefault(find(i), []).append(ids[i])

    return [
        frozenset(members)
        for members in members_by_root.values()
        if len(members) >= min_members
    ]


# --- BL-12 Stage 1: remembered group properties and the matching predicate --
# `plans/group-contact-identity/plan.md`, amendment A2's matching-predicate
# table. Everything below is computed from already-folded `Contact` state
# (`.position`, `.last_class_raw`) -- the same no-omniscience boundary
# `_cluster_contacts` above already keeps.


def _air_defence_op_class_of(contact: Contact) -> str | None:
    """`contact.last_class_raw` resolved to an air-defence `op_class`, or
    `None` if it is not one -- amendment A3's correction. Reads `belief.
    classification.parent_class_of` (the lattice), **not** `object_model.
    profile_for`: a classification held at *class* level (what a contact
    holds before it is identified to type, i.e. most of the time at range)
    carries the `OP_*` bucket string itself, which `profile_for`'s keyword
    match cannot resolve -- four of the five air-defence classes would
    silently fail a `profile_for`-based test at that level. This is `BL-
    B47`'s own boundary decision, applied here to Stage 1's two new
    consumers (`Group.air_defence_composition`, `group_matches` test 3)."""
    op_class = classification.parent_class_of(contact.last_class_raw)
    if op_class is not None and op_class in classification.AIR_DEFENSE_OP_CLASSES:
        return op_class
    return None


def _composition_of(
    members: Sequence[Contact],
) -> tuple[tuple[str, int], ...]:
    """The sorted `(op_class, count)` multiset over `members`, resolved via
    `_profile_for_contact` -- the same resolution `_cluster_contacts`
    already uses for size/backstop. See `Group.composition`'s docstring on
    why this field (unlike `air_defence_composition`) is correct to resolve
    this way: it needs `installation_component`/`size_m`, which only a
    profile carries, not air-defence membership specifically."""
    counts: Counter[str] = Counter(
        _profile_for_contact(member).op_class for member in members
    )
    return tuple(sorted(counts.items()))


def _air_defence_composition_of(
    members: Sequence[Contact],
) -> tuple[tuple[str, int], ...]:
    """The air-defence subset of `_composition_of`, resolved through
    `_air_defence_op_class_of` (the lattice) rather than through
    `_profile_for_contact` -- see that function's docstring and `Group.
    air_defence_composition`."""
    counts: Counter[str] = Counter()
    for member in members:
        op_class = _air_defence_op_class_of(member)
        if op_class is not None:
            counts[op_class] += 1
    return tuple(sorted(counts.items()))


def _installation_of(members: Sequence[Contact]) -> bool:
    """`True` only when every member's resolved profile has `installation_
    component is True` -- see `Group.installation`'s docstring."""
    return all(
        _profile_for_contact(member).installation_component for member in members
    )


def _centroid_of(members: Sequence[Contact]) -> tuple[float, float]:
    """Mean (x, z) of `members`' fused `Contact.position` -- `Group.
    centroid_x`/`.centroid_z`."""
    return (
        statistics.fmean(member.position.x for member in members),
        statistics.fmean(member.position.z for member in members),
    )


def _centroid_uncertainty_of(members: Sequence[Contact]) -> float:
    """RMS (quadratic mean) of `members`' own `PositionEstimate.radius_m()`
    -- `Group.centroid_uncertainty_m`'s docstring: the slack term `group_
    matches`'s displacement test budgets against, not the cluster's
    extent."""
    radii = [member.position.radius_m() for member in members]
    return math.sqrt(statistics.fmean(r * r for r in radii))


def _extent_of(members: Sequence[Contact]) -> float:
    """The cluster's extent, metres -- the maximum pairwise distance among
    `members`' fused positions. This is the figure amendment A2's measured
    table reports (e.g. "one group, extent 6,000 m" for an armour contact
    and an infantry contact 6 km apart) and the field the group-identity
    sortie trace line (A4) carries, because neither `centroid_uncertainty_m`
    above nor any per-member field says anything about how wide the group
    actually is."""
    if len(members) < 2:
        return 0.0
    positions = [(member.position.x, member.position.z) for member in members]
    n = len(positions)
    return max(
        _pairwise_distance(positions, i, j) for i in range(n) for j in range(i + 1, n)
    )


def _cluster_is_stopped(members: Sequence[Contact]) -> bool:
    """`True` only when at least one member reports a motion belief and
    every member that reports one reports `"stopped"` -- the observed side
    of `group_matches` test 5's zero-speed-bound rule. A member with no
    motion belief at all (`Contact.motion is None` -- never observed for
    movement, `belief.motion`'s own module docstring) is silently excluded
    rather than treated as either "moving" or "stopped": it carries no
    evidence either way, and this function must not manufacture some."""
    known = [member.motion.state for member in members if member.motion is not None]
    if not known:
        return False
    return all(state == "stopped" for state in known)


@dataclass(frozen=True, slots=True)
class _ClusterProperties:
    """The same seven remembered properties `Group` carries, computed once
    per observed cluster per `reconcile` call and shared between the
    matching predicate, the newly-founded/re-matched `Group` construction,
    and the trace line -- so none of the three can read a believed
    classification through a different path than the others."""

    centroid_x: float
    centroid_z: float
    centroid_uncertainty_m: float
    composition: tuple[tuple[str, int], ...]
    installation: bool
    air_defence_composition: tuple[tuple[str, int], ...]
    extent_m: float
    stopped: bool


def _cluster_properties(members: Sequence[Contact]) -> _ClusterProperties:
    centroid_x, centroid_z = _centroid_of(members)
    return _ClusterProperties(
        centroid_x=centroid_x,
        centroid_z=centroid_z,
        centroid_uncertainty_m=_centroid_uncertainty_of(members),
        composition=_composition_of(members),
        installation=_installation_of(members),
        air_defence_composition=_air_defence_composition_of(members),
        extent_m=_extent_of(members),
        stopped=_cluster_is_stopped(members),
    )


def _plausible_speed_mps(op_class: str) -> float:
    """How fast a contact of `op_class` could plausibly have moved,
    metres/second -- the bound `group_matches` test 5 budgets displacement
    against.

    **Stage 2: delegates to the one shared table**, `position_belief.
    plausible_speed_mps` -- amendment A2's test 5 row specifies
    `max(plausible_speed_mps(op_class) for op_class in group.composition)`,
    and that table is now `position_belief`'s, not a second copy here
    (`BL-B51`'s own lesson about a set declared more than once). Op-class
    only, deliberately: `Group.composition` does not carry a per-member
    `installation_component` flag (`Group.installation` is the group-level
    analogue, already a hard gate in `group_matches` test 2 -- see that
    test's own docstring), so this call site passes `installation_
    component`'s default (`False`). `group_matches` itself is unchanged by
    Stage 2 landing -- exactly as this function's Stage 1 docstring
    predicted: "this function (or its caller) is what changes"."""
    return plausible_speed_mps(op_class)


def group_match_score(group: Group, observed: _ClusterProperties) -> float:
    """Phase 2's ordering, not a gate: the negative centroid distance, so
    sorting candidates by *descending* score puts the nearest first.
    Deliberately not a composite score weighing multiple factors -- see
    amendment A2's own note that a weighted score here would reintroduce
    the "best-match tiebreak" `pb2-contact-memory` Stage 1 refused to
    build; every candidate this orders has already independently passed
    every hard test in `group_matches`."""
    return -math.hypot(
        group.centroid_x - observed.centroid_x, group.centroid_z - observed.centroid_z
    )


def group_matches(
    group: Group,
    observed: _ClusterProperties,
    elapsed_s: float,
    *,
    window_s: float = GROUP_REIDENTIFY_WINDOW_S,
) -> bool:
    """Whether `observed` (a cluster with no overlap-match this reconcile)
    may inherit `group`'s identity -- amendment A2's six-test matching
    predicate, evaluated cheapest/hardest first, tests 1-5 all required
    (test 6, the ambiguity tiebreak, is the caller's job once more than one
    group passes here for the same cluster -- see `GroupStore.reconcile`).

    `window_s` is keyword-only and defaulted to `GROUP_REIDENTIFY_WINDOW_S`
    specifically so `BL-8` can reuse this exact predicate at its own,
    longer horizon with its own window (`plans/group-contact-identity/
    plan.md`'s "What `BL-8` will need from this design" -- the thresholds
    being parameters is the whole point of the seam).

    No-omniscience: every field this function reads comes from `Contact.
    position` (fused belief) and `Contact.last_class_raw` (believed
    classification), via `Group`'s own stored properties and `_cluster_
    properties`. No `Observation`, no DCS object id."""
    # Test 1 -- elapsed window.
    if elapsed_s > window_s:
        return False
    # Test 2 -- kind coherence (hard). User direction, D4.
    if group.installation != observed.installation:
        return False
    # Test 3 -- air-defence confirmation (hard). User direction, D6; lattice
    # resolution per amendment A3 (both sides already resolved that way --
    # see `Group.air_defence_composition`/`_air_defence_composition_of`).
    if (
        group.air_defence_composition or observed.air_defence_composition
    ) and group.air_defence_composition != observed.air_defence_composition:
        return False
    # Test 4 -- composition compatibility (hard). User direction, D4: a
    # different *kind* of member is evidence of a new group; count is
    # deliberately not gated (more members than memory is new detections of
    # a continuing group; fewer is occlusion -- both normal per the user's
    # own words).
    group_classes = {op_class for op_class, _count in group.composition}
    observed_classes = {op_class for op_class, _count in observed.composition}
    group_non_ad = group_classes - classification.AIR_DEFENSE_OP_CLASSES
    observed_non_ad = observed_classes - classification.AIR_DEFENSE_OP_CLASSES
    if not (group_non_ad <= observed_non_ad or observed_non_ad <= group_non_ad):
        return False
    # Test 5 -- displacement plausibility (hard). The zero-speed-bound rule
    # is one-sided in Stage 1, deliberately: `Group` carries no persisted
    # movement state until Stage 4, so only the *observed* side's motion is
    # known here. This is the conservative direction -- it zeroes the bound
    # only on positive evidence the thing seen right now is stopped, never
    # on an assumption about the (possibly long-gone) remembered members --
    # so it can only ever make this test *stricter* than the full two-sided
    # D4 rule, never more permissive. Stage 4 persists `Group.movement_
    # state` and should widen this to both sides then.
    speed_bound_mps = (
        0.0
        if observed.stopped
        else max(
            (_plausible_speed_mps(op_class) for op_class, _count in group.composition),
            default=GATE_GROWTH_RATE_MPS,
        )
    )
    slack_m = group.centroid_uncertainty_m + observed.centroid_uncertainty_m
    displacement_m = math.hypot(
        group.centroid_x - observed.centroid_x, group.centroid_z - observed.centroid_z
    )
    return displacement_m <= speed_bound_mps * elapsed_s + slack_m


class GroupStore:
    """Holds all currently persisted `Group`s. Structurally parallel to
    `belief.contacts.ContactStore`, deliberately far smaller -- see module
    docstring.

    **BL-12 Stage 1 split what this store holds into two readable sets**
    (`plans/group-contact-identity/plan.md`'s own sharpest-silent-failure
    warning): `_groups` now holds every group this store still remembers,
    whether or not a cluster matched it on the most recent `reconcile`
    call -- a group that matched nothing is *kept*, properties frozen,
    until `GROUP_REIDENTIFY_WINDOW_S` elapses (the expire phase), so that a
    later reconcile's property-match phase has something to match against.
    `groups` (the pre-existing, pilot-facing property) and `group_for_
    contact` must keep meaning exactly what they meant before Stage 1 --
    *currently observed* only -- or every existing consumer (`belief.
    speech.render_group_disclosure`, `tools.py`, `callouts.py`, `crew_
    console.py`) starts rendering or acting on a group nobody can currently
    see. `remembered_groups` is the new, explicit escape hatch for the one
    caller (`reconcile`'s own phase 2) that needs the full set."""

    def __init__(self) -> None:
        self._groups: dict[str, Group] = {}
        self._next_group_number = 0
        #: The `now_sim` of the most recent `reconcile` call, or `None`
        #: before the first one -- what `groups` filters `Group.last_
        #: observed_sim` against to answer "matched *this* reconcile".
        self._last_reconciled_sim: float | None = None
        #: BL-12 Stage 1 test 6's observability requirement (amendment A4 /
        #: A2): how many times a cluster's property-match phase found *more
        #: than one* remembered group passing every hard test, across this
        #: store's whole life. The matching predicate's rarity claim (D5)
        #: is otherwise unmeasurable -- see the module docstring's
        #: `GROUP_REIDENTIFY_WINDOW_S`-adjacent reasoning and amendment A4.
        self.ambiguous_property_matches_count: int = 0

    @property
    def groups(self) -> list[Group]:
        """Currently-observed groups only -- a cluster matched one of them
        on the most recent `reconcile` call. Insertion order. A read-only
        view -- callers must not mutate the returned list.

        **Unchanged meaning since before Stage 1.** A group this store
        merely *remembers* (retained through the expire phase, not yet
        re-matched) is deliberately excluded -- see the class docstring and
        `remembered_groups`."""
        if self._last_reconciled_sim is None:
            return []
        return [
            group
            for group in self._groups.values()
            if group.last_observed_sim == self._last_reconciled_sim
        ]

    @property
    def remembered_groups(self) -> list[Group]:
        """Every group this store still remembers, observed this reconcile
        or not -- BL-12 Stage 1's phase 2 (property match) candidate pool.
        Not for pilot-facing use; see the class docstring."""
        return list(self._groups.values())

    def group_for_contact(self, contact_id: str) -> Group | None:
        """The *currently observed* `Group` `contact_id` belongs to, or
        `None` if it is not a member of one -- deliberately `self.groups`,
        not `self._groups`/`remembered_groups`, for the same reason that
        property is filtered (class docstring): every caller of this method
        (`ContactStore.group_for_contact`, `tools.py`, `crew_console.py`,
        `callouts.py`) is pilot-facing. Linear in the number of currently
        observed groups, which is always far smaller than the number of
        contacts."""
        for group in self.groups:
            if contact_id in group.member_contact_ids:
                return group
        return None

    def mark_spoken(
        self,
        group_id: str,
        signature: str,
        now_sim: float,
        *,
        member_contact_ids: frozenset[str] = frozenset(),
        leading_contact_id: str | None = None,
        differentiated: bool = False,
    ) -> bool:
        """Record that `group_id`'s disclosure line was just spoken as
        `signature` -- the write half of Stage 3's progressive-disclosure
        trigger (`belief.speech.render_group_disclosure`'s caller compares
        a freshly rendered line against `Group.last_spoken_signature`, then
        calls this to update it only when it actually spoke). Returns
        whether `group_id` still exists -- a group can vanish between a
        caller reading it and calling this, if a `reconcile` ran in
        between.

        `member_contact_ids`/`leading_contact_id`/`differentiated`
        (`plans/group-cohesion-redesign/plan.md` §4) are the delta
        taxonomy's own disclosure snapshot -- what `render_group_
        disclosure` saw when it decided to speak this time, read back by
        its own taxonomy decision on the *next* call via `Group.last_
        spoken_member_contact_ids`/`.last_spoken_leading_contact_id`/
        `.last_spoken_differentiated`. Keyword-only with permissive
        defaults (an empty set / `None` / `False`) so a caller that only
        cares about the pre-existing content-signature gate -- or a test
        exercising that gate alone -- is unaffected."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        group.last_spoken_signature = signature
        group.last_spoken_sim = now_sim
        group.last_spoken_member_contact_ids = member_contact_ids
        group.last_spoken_leading_contact_id = leading_contact_id
        group.last_spoken_differentiated = differentiated
        return True

    def _new_group_id(self) -> str:
        self._next_group_number += 1
        return f"{_GROUP_ID_PREFIX}_{self._next_group_number}"

    def reconcile(
        self,
        contacts: Sequence[Contact],
        now_sim: float,
        *,
        trace_sink: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        """Recompute cohesion clusters from `contacts` (the belief store's
        current `Contact` set) and reconcile them against this store's
        persisted `Group`s -- BL-12 Stage 1, four phases in order (amendment
        A6):

        1. **Overlap match** -- unchanged from before Stage 1: greedy,
           highest-member-overlap-first, against every group this store
           still remembers (`remembered_groups`, not only `groups`) -- so a
           group can be reclaimed by overlap even if it was merely
           retained, not currently observed, going into this call.
        2. **Property match** -- for each cluster overlap left unmatched,
           against each group `remembered_groups` still has unclaimed, in
           ascending centroid distance (ties by lowest group id): if
           `group_matches` passes, the cluster claims that group's id,
           `established_sim` and `last_spoken_*` snapshot, the same
           carry-over phase 1 already does. More than one group passing
           for the same cluster increments `ambiguous_property_matches_
           count` (test 6's rarity claim, made observable) before the
           tiebreak is applied.
        3. **Found** -- unchanged: any cluster still unmatched gets a fresh
           `Group`.
        4. **Expire** -- a persisted group that matched no cluster this
           call is *kept*, properties frozen, while `now_sim - group.
           last_observed_sim <= GROUP_REIDENTIFY_WINDOW_S`; past that it is
           dropped. This is what makes phase 2 possible at all -- before
           Stage 1, an unmatched group was dropped on this same call,
           before ever offering a later reconcile anything to match
           against.

        `trace_sink`, when given, is called once per cluster-resolution
        outcome (phase 1/2/3) and once per group that expires this call --
        amendment A4's group-identity sortie trace line, promoted to
        Stage 1's first commit. A `None` default is a true no-op: nothing
        about this method's behaviour changes when no sink is supplied.
        Deliberately **not** file I/O -- this module owns no writer (module
        docstring: "this module never reads or writes anything speech-
        shaped"; the same posture applies to any other kind of I/O) --
        wiring a sink to a file is the caller's job, mirroring `detection_
        trace_writer.py`/`speech_log.py`'s placement outside `belief/`.

        **No omniscience**: every field computed here comes from `Contact.
        position` (fused belief) and `Contact.last_class_raw` (believed
        classification) -- see `_cluster_properties` and `group_matches`."""
        clusters = _cluster_contacts(
            contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS
        )
        contacts_by_id = {contact.id: contact for contact in contacts}
        cluster_props: dict[frozenset[str], _ClusterProperties] = {
            cluster: _cluster_properties([contacts_by_id[cid] for cid in cluster])
            for cluster in clusters
        }

        persisted = dict(self._groups)

        # --- Phase 1: overlap match (unchanged in spirit; candidate set is
        # every remembered group, not only currently-observed ones). ---
        scored: list[tuple[int, frozenset[str], Group]] = []
        for cluster in clusters:
            for group in persisted.values():
                overlap = len(cluster & group.member_contact_ids)
                if overlap > 0:
                    scored.append((overlap, cluster, group))
        # Highest overlap first: a split's majority child claims the old
        # id before its minority sibling gets a chance to, and a merge's
        # two candidate parents resolve to whichever had more members in
        # common with the surviving cluster.
        scored.sort(key=lambda item: -item[0])

        cluster_to_group: dict[frozenset[str], Group] = {}
        claimed_group_ids: set[str] = set()
        resolution_phase: dict[frozenset[str], str] = {}
        for _overlap, cluster, group in scored:
            if cluster in cluster_to_group or group.id in claimed_group_ids:
                continue
            cluster_to_group[cluster] = group
            claimed_group_ids.add(group.id)
            resolution_phase[cluster] = "overlap"

        # --- Phase 2: property match. Clusters in a deterministic order
        # (sorted member ids) so ties/collisions resolve reproducibly. ---
        unmatched_clusters = sorted(
            (cluster for cluster in clusters if cluster not in cluster_to_group),
            key=lambda cluster: sorted(cluster),
        )
        for cluster in unmatched_clusters:
            props = cluster_props[cluster]
            elapsed_candidates = [
                group
                for group in persisted.values()
                if group.id not in claimed_group_ids
                and group_matches(group, props, now_sim - group.last_observed_sim)
            ]
            if len(elapsed_candidates) > 1:
                self.ambiguous_property_matches_count += 1
            if not elapsed_candidates:
                continue
            winner = min(
                elapsed_candidates,
                key=lambda group: (-group_match_score(group, props), group.id),
            )
            cluster_to_group[cluster] = winner
            claimed_group_ids.add(winner.id)
            resolution_phase[cluster] = "property"

        # --- Phase 3: found. ---
        new_groups: dict[str, Group] = {}
        trace_records: list[dict[str, object]] = []
        for cluster in clusters:
            props = cluster_props[cluster]
            old = cluster_to_group.get(cluster)
            if old is not None:
                phase = resolution_phase[cluster]
                new_groups[old.id] = Group(
                    id=old.id,
                    member_contact_ids=cluster,
                    established_sim=old.established_sim,
                    last_reconciled_sim=now_sim,
                    last_spoken_signature=old.last_spoken_signature,
                    last_spoken_sim=old.last_spoken_sim,
                    last_spoken_member_contact_ids=old.last_spoken_member_contact_ids,
                    last_spoken_leading_contact_id=old.last_spoken_leading_contact_id,
                    last_spoken_differentiated=old.last_spoken_differentiated,
                    last_observed_sim=now_sim,
                    centroid_x=props.centroid_x,
                    centroid_z=props.centroid_z,
                    centroid_uncertainty_m=props.centroid_uncertainty_m,
                    composition=props.composition,
                    installation=props.installation,
                    air_defence_composition=props.air_defence_composition,
                )
                group_id = old.id
            else:
                new_id = self._new_group_id()
                new_groups[new_id] = Group(
                    id=new_id,
                    member_contact_ids=cluster,
                    established_sim=now_sim,
                    last_reconciled_sim=now_sim,
                    last_observed_sim=now_sim,
                    centroid_x=props.centroid_x,
                    centroid_z=props.centroid_z,
                    centroid_uncertainty_m=props.centroid_uncertainty_m,
                    composition=props.composition,
                    installation=props.installation,
                    air_defence_composition=props.air_defence_composition,
                )
                group_id = new_id
                phase = "found"
            trace_records.append(
                {
                    "now_sim": now_sim,
                    "phase": phase,
                    "group_id": group_id,
                    "member_contact_ids": sorted(cluster),
                    "centroid_x": props.centroid_x,
                    "centroid_z": props.centroid_z,
                    "extent_m": props.extent_m,
                    "composition": [list(pair) for pair in props.composition],
                }
            )

        # --- Phase 4: expire. ---
        for group in persisted.values():
            if group.id in claimed_group_ids:
                continue
            if now_sim - group.last_observed_sim <= GROUP_REIDENTIFY_WINDOW_S:
                new_groups[group.id] = Group(
                    id=group.id,
                    member_contact_ids=group.member_contact_ids,
                    established_sim=group.established_sim,
                    last_reconciled_sim=now_sim,
                    last_spoken_signature=group.last_spoken_signature,
                    last_spoken_sim=group.last_spoken_sim,
                    last_spoken_member_contact_ids=group.last_spoken_member_contact_ids,
                    last_spoken_leading_contact_id=group.last_spoken_leading_contact_id,
                    last_spoken_differentiated=group.last_spoken_differentiated,
                    last_observed_sim=group.last_observed_sim,
                    centroid_x=group.centroid_x,
                    centroid_z=group.centroid_z,
                    centroid_uncertainty_m=group.centroid_uncertainty_m,
                    composition=group.composition,
                    installation=group.installation,
                    air_defence_composition=group.air_defence_composition,
                )
            else:
                trace_records.append(
                    {
                        "now_sim": now_sim,
                        "phase": "expired",
                        "group_id": group.id,
                        "member_contact_ids": sorted(group.member_contact_ids),
                        "centroid_x": group.centroid_x,
                        "centroid_z": group.centroid_z,
                        "extent_m": None,
                        "composition": [list(pair) for pair in group.composition],
                    }
                )

        self._groups = new_groups
        self._last_reconciled_sim = now_sim
        if trace_sink is not None:
            for record in trace_records:
                trace_sink(record)
