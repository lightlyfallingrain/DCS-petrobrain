"""Per-`object_type` size/class lookup -- `plans/pb1.5-naked-eye-detection/
plan.md`'s Affected Modules section.

Shared by `perception.visibility` (angular-radius range-threshold numerator)
and `perception.naked_eye_source` (ED coarse-class output quantisation),
replacing what would otherwise be two separate per-type keyword tables --
the concrete duplication this module removes is a second `naked_eye_source.py`
table for class-bucketing alone, which would just be `association.py`'s
keyword-vocabulary problem (see that module's `_type_match_score`) built
twice. Same "unvalidated starting vocabulary" caveat applies here: this is a
hand-authored starting guess, not a validated catalogue of real DCS
unit-type dimensions (see the plan's Risks section).

**Where the size comes from, stated plainly** (plan's Proposed Defaults):
`LoGetWorldObjects`/`WorldObjectSample` carries no physical-dimensions field
(only `object_type`, position, heading, coalition -- confirmed by reading
`aircraft-layer/src/schema/world_objects.py`), and no DCS-exposed
per-unit-type dimension database is known to exist in Lua (untested, not
investigated this round). A hand-authored table is therefore the only
available v1 option without an aircraft-layer schema change.

Lookup is by case-insensitive substring containment against `object_type`,
not word-tokenized keyword overlap (`association.py`'s `_type_match_score`
pattern) -- DCS unit-type identifiers are frequently hyphenated compounds
(`"Ural-4320"`, `"T-72"`, `"ZU-23"`), which a word tokenizer built on
`[a-z0-9]+` would silently split apart, losing the compound. This module
also only needs a single best (first-match) profile per type, not
`association.py`'s "score every candidate and compare" shape, so it reuses
that module's keyword-vocabulary *design pattern* (a hand-authored,
explicitly-unvalidated keyword table with a documented fallback), not its
tokenizer or scoring function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ObjectTypeProfile:
    """One `object_type` keyword's looked-up profile.

    `size_m`: characteristic physical size, metres -- the numerator in
    `visibility.py`'s angular-radius range-threshold formula
    (`range_threshold = size_m / min_angular_radius[tier]`).

    `op_class`: ED's own coarse-class bucket, from `HelperAI_lengths_ng.lua`'s
    ambient-callout vocabulary (`aircraft-layer/research/2026-09-08-pb1-5-
    worldobjects-filter-and-ambient-detection.md`, Session 5 Finding 2) --
    reported verbatim in a naked-eye `Observation`'s `classification_raw`,
    in place of a free-text classification guess.
    """

    size_m: float
    op_class: str


#: Fallback for any `object_type` matching no keyword below. ED's own
#: "unclassified" ground-class bucket (Finding 2), per the plan's Affected
#: Modules section: "using ED's own 'unclassified' bucket for the fallback
#: case rather than inventing one."
DEFAULT_SIZE_M: Final[float] = 5.0
DEFAULT_OP_CLASS: Final[str] = "OP_GROUPSOMETHING"

_DEFAULT_PROFILE: Final[ObjectTypeProfile] = ObjectTypeProfile(
    size_m=DEFAULT_SIZE_M, op_class=DEFAULT_OP_CLASS
)

#: Ordered `(keyword, profile)` pairs -- the first case-insensitive substring
#: match against `object_type` wins, so a more specific keyword (e.g.
#: `"shilka"`, a specific SPAAG hull) must precede a more general one it
#: could also satisfy. None of the keywords below currently overlap, but
#: keep specific-before-general if extending this table.
#:
#: Sizes/classes for infantry, trucks, tanks/IFVs, and the SA-3 launcher
#: match the worked example table in `plans/pb1.5-naked-eye-detection/
#: plan.md`'s Proposed Defaults section verbatim (1.8 m / 6 m / 7 m / 9 m),
#: so those four rows are also this module's regression anchor against that
#: table.
_KEYWORD_PROFILES: Final[tuple[tuple[str, ObjectTypeProfile], ...]] = (
    ("shilka", ObjectTypeProfile(size_m=6.0, op_class="OP_SPAAG")),
    ("zu-23", ObjectTypeProfile(size_m=5.0, op_class="OP_ZU23")),
    ("zu23", ObjectTypeProfile(size_m=5.0, op_class="OP_ZU23")),
    ("infantry", ObjectTypeProfile(size_m=1.8, op_class="OP_INFANTRY")),
    ("soldier", ObjectTypeProfile(size_m=1.8, op_class="OP_INFANTRY")),
    ("sa-3", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("sa-6", ObjectTypeProfile(size_m=9.0, op_class="OP_MRSAM")),
    ("sa-8", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("sa-9", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("sa-13", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("sa-15", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("tank", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-55", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-72", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-80", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-90", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("bmp", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("btr", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("ural", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("kamaz", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("zil", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("truck", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("cruiser", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("frigate", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("corvette", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("destroyer", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("boat", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("ship", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
)


def profile_for(object_type: str) -> ObjectTypeProfile:
    """Look up `object_type`'s size/class profile via case-insensitive
    substring match against `_KEYWORD_PROFILES` (first match wins). Returns
    `_DEFAULT_PROFILE` if nothing matches -- absence of a recognized
    vocabulary entry degrades to a generic profile, matching
    `association.py`'s posture of degrading rather than failing on an
    unfamiliar `object_type` string, never a crash."""
    text = object_type.lower()
    for keyword, profile in _KEYWORD_PROFILES:
        if keyword in text:
            return profile
    return _DEFAULT_PROFILE
