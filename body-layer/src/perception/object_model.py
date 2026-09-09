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

**Keyword vocabulary is checked against real DCS `object_type` strings, not
guessed English/NATO-designation words.** A review pass found the original
OP_SHIP keywords (`cruiser`/`frigate`/`corvette`/...) and the original SA-3/
6/8/9/13/15 keywords (`sa-3`/`sa-6`/...) were both domain-mismatched -- they
read like plausible English/NATO descriptors but do not appear as substrings
of any real DCS ship or SAM `object_type` (ED's real identifiers are hull/
component proper nouns: `"Slava"`, `"5p73 s-125 ln"`, `"Kub 2P25 ln"`,
`"Tor 9A331"`). Both categories were re-derived against ED's own 595-entry
DCS-type -> Petrovich-reporting-name mapping (`HelperAI_reporting_names.lua`)
and coverage numbers recorded in `aircraft-layer/research/
2026-09-09-object-model-keyword-coverage.md`. This does not make the table
exhaustive or validated for every category (armor/truck coverage is still a
thin, unvalidated hand-authored guess, tracked as backlog in that research
doc) -- only OP_SHIP and the SA-3/6/8/9/13/15 OP_SRSAM/OP_MRSAM entries have
been checked against real type strings this way.

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

from perception.reporting_names import reporting_name_for


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
    # SA-3/6/8/9/13/15 keyed on real DCS `object_type` substrings, not the
    # NATO reporting-name shorthand ("sa-3" etc.) the table previously used
    # -- that shorthand is unreachable against real data for the same reason
    # the old OP_SHIP keywords were (see this module's research citation):
    # `LoGetWorldObjects` returns DCS's own component/hull identifiers
    # ("5p73 s-125 ln", "Kub 2P25 ln", "Tor 9A331", ...), which very rarely
    # contain the NATO "SA-N" designation as a literal substring. Verified
    # against 595 real DCS unit type names (research doc below).
    ("s-125", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-3
    ("kub ", ObjectTypeProfile(size_m=9.0, op_class="OP_MRSAM")),  # SA-6
    ("osa", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-8
    # "strela-10" before "strela-1": "Strela-10M3" also contains "strela-1"
    # as a prefix, so the more specific SA-13 keyword must win first-match.
    ("strela-10", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-13
    ("strela-1", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-9
    ("tor 9a331", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-15
    ("chap_torm2", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),  # SA-15
    # No bare "tank" keyword. It was measured against all 595 real DCS type
    # names and scored 8 false positives and zero true positives -- real
    # armour is named T-72/Leopard/Merkava/Challenger2, never "tank", while
    # "tank" matches fuel trailers (ATZ-60_TANK, TZ-22_TANK), fuel trucks
    # (M978 HEMTT Tanker), railway tank cars, and the S-3B Tanker aircraft.
    # Do not re-add it; classify armour by the specific keywords below and
    # by reporting name. See the research doc cited at the top of this file.
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
    # OP_SHIP: real DCS ship-type-name substrings (hull/proper-noun model
    # names -- "Slava", "leander-gun-achilles", "CastleClass_01", ...), not
    # English hull-class words ("cruiser"/"frigate"/...) -- `object_type`
    # never carries the latter, so the previous six-keyword list was
    # unreachable against real data (this fix's primary defect). This list
    # was derived by checking every one of ED's 57 ship-class unit types
    # (research doc below) and choosing a substring per type/family that
    # does not collide with any of the other ~538 non-ship type names.
    ("albatros", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("bdk-775", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("chap_project22160", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("cvn_", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("cv_1143_5", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("castleclass", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("cleveland_class", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("elnya", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("essex", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("forrestal", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("kilo", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("kuznecow", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("lha_tarawa", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("lst_mk2", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("la_combattante", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("molniya", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("moscow", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("mogami", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("neustrash", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("perry", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("piotr", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("rezky", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("ship_tilde", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("stennis", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("ticonderog", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("type_021", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("type_052", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("type_054", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("type_071", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("type_093", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("arleigh_burke", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("samuel_chase", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("uboat", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("ara_vdm", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("hms_invincible", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("leander-gun", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("santafe", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    # Found by broadening the ship-vocabulary search (reporting names using
    # "vessel"/"craft"/"tug"/"landing"/etc., not just "ship"/hull-class
    # words) beyond the 47 initially checked -- see the research doc.
    ("dry-cargo ship", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("handywind", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("harbortug", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("higgins_boat", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("schnellboot", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("seawise_giant", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("zwezdny", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("atconveyor", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
    ("speedboat", ObjectTypeProfile(size_m=100.0, op_class="OP_SHIP")),
)

#: Second keyword pass, run only when `_KEYWORD_PROFILES` (raw `object_type`)
#: finds nothing -- keyed on Petrovich's *reporting* name (via
#: `reporting_names.reporting_name_for`), not the raw DCS type string. This
#: is the mechanism that closes most of the "modern ground units" coverage
#: gap recorded in `aircraft-layer/research/2026-09-09-object-model-keyword-
#: coverage.md`'s Addendum: raw type names for these families are irregular
#: (`CHAP_T90M`, `ATZ-5`, `CHAP_M1130`), but ED's own reporting names for the
#: same types are regular (`T-90M`, `Ural fuel truck`, `Stryker CV`) --
#: derived from the same 595-row `HelperAI_reporting_names.lua` mapping as
#: the OP_SHIP/SA-* fix above, shipped as `data/dcs_type_to_reporting_name.tsv`
#: (see `reporting_names.py` for provenance/regeneration).
#:
#: **Scope of this pass, and why:**
#: - **Modern ground units are the target** -- tanks/IFVs/APCs/recon
#:   vehicles, SPGs, self-propelled AAA, wheeled rocket-artillery/TEL
#:   launchers, fuel/cargo trucks, dismounted troops/MANPAD teams. All
#:   entries below were checked against every one of the 595 real reporting
#:   names (script in the research doc) to confirm no accidental match
#:   against an aircraft, WWII, or unrelated type.
#: - **WWII units are deliberately excluded, not merely un-targeted**: every
#:   `profile_for` lookup through this table first checks the resolved
#:   reporting name does not start with `"Old "` (ED's own WWII-era-unit
#:   naming convention in this table, e.g. `"Old military truck"`,
#:   `"Old car"`) and skips the whole pass if it does. This exists because a
#:   deliberately-broad, useful keyword here (`"truck"`, `"soldier"`) would
#:   otherwise also catch WWII types that happen to share the word (a WWII
#:   truck is still, physically, a truck) -- the plan explicitly calls for
#:   WWII units to keep falling back rather than incidentally getting
#:   classified as a side effect of a broad keyword aimed at modern units.
#: - **Aircraft/helicopters/UAVs are deliberately deferred, not covered**:
#:   ED's own vocabulary does have air-class buckets (`OP_HELI(S)`,
#:   `OP_COMBATHELI(S)`, `OP_TRANSPORTHELI(S)`, `OP_UNMANNED`,
#:   `OP_PROPPLANE(S)`, `OP_JET(S)` -- `aircraft-layer/research/2026-09-08-
#:   pb1-5-worldobjects-filter-and-ambient-detection.md` Session 5 Finding
#:   2), but this channel (`perception.naked_eye_source`) reports ground
#:   contacts, and adding an air branch is a separate, later scope decision
#:   -- no air-class keyword was added here, and none of the ground keywords
#:   below match a real aircraft reporting name (checked).
#: - **Some real ground/support types still have no correct ED bucket and
#:   were deliberately left unclassified rather than force-fit**: towed
#:   (not self-propelled) AA/mortar pieces (`ZPU-4`, `KS-19`, `S-60`,
#:   `Mortar`) aren't `OP_SPAAG` (that class means self-propelled) and
#:   there's no towed-weapon class; standalone SAM-system radars/command
#:   posts beyond the one system named in scope (IRIS-T, below) risk the
#:   same false-positive trap `OP_SHIP`/`"tank"` already hit (see the
#:   research doc) without per-system range-class verification this pass
#:   didn't do; static structures (bunkers, outposts, beacons) and airfield
#:   ground-support equipment (tugs, generators) aren't vehicles at all.
#:   `"ss-26"` and `"scud"` are a deliberate instance of this same care: both
#:   are wheeled TEL trucks for surface-to-*surface* missiles, not SAMs --
#:   despite reporting names ending in `"launcher"`, they are bucketed
#:   `OP_TRUCK`, not `OP_SRSAM`/`OP_MRSAM`, to avoid exactly the "launcher"-
#:   sounds-like-a-SAM domain mismatch the research doc's Finding 1 warned
#:   about for ships.
_REPORTING_NAME_KEYWORD_PROFILES: Final[tuple[tuple[str, ObjectTypeProfile], ...]] = (
    # Modern tanks / IFVs / APCs / recon vehicles / SPGs -- one shared
    # OP_ARMORED/7m bucket, matching the existing raw-table convention of
    # not sub-dividing armor by weight/role.
    ("t-90", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-84", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-64", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-62", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("challenger", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("chieftain", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("bmd", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("brdm", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("stryker", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("scorpion", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("scimitar", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("mrap", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("aav7", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("tos-1a", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("abrams", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("paladin", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("m113", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("bradley", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("patton", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("leclerc", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("leopard", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("warrior", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("merkava", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("lav-25", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("mtlb", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("marder", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("zbd", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("ztz", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("zsu-57", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("type 59", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("t-155", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("dana", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("plz", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("pt-76", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("tpz", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("fuchs", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("tigr", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("vab", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("cobra", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    # "2s1" is a literal substring of "2S19"'s reporting name -- both being
    # OP_ARMORED means this is harmless (first-match wins either way), kept
    # as two explicit entries only for readability against the real names.
    ("2s1", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("2s19", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("2s3", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    ("2s9", ObjectTypeProfile(size_m=7.0, op_class="OP_ARMORED")),
    # Self-propelled AAA / gun-missile hybrids -- same OP_SPAAG/6m bucket as
    # the existing raw "shilka" entry (2S6 Tunguska and Pantsir-S1/SA-22 are
    # both gun+missile SPAAG systems, not pure SAM launchers, so OP_SPAAG is
    # the accurate ED bucket rather than OP_SRSAM).
    ("2s6", ObjectTypeProfile(size_m=6.0, op_class="OP_SPAAG")),
    ("vulcan", ObjectTypeProfile(size_m=6.0, op_class="OP_SPAAG")),
    ("sa-22", ObjectTypeProfile(size_m=6.0, op_class="OP_SPAAG")),
    ("gepard", ObjectTypeProfile(size_m=6.0, op_class="OP_SPAAG")),
    # IRIS-T's launcher, radar, and command post are covered as one group
    # (the plan names all three together) -- "medium" is in the real
    # system's own name (IRIS-T SLM = Surface Launched Medium-range), so
    # OP_MRSAM is a documented reading of the reporting name, not a guess.
    ("iris-t", ObjectTypeProfile(size_m=9.0, op_class="OP_MRSAM")),
    # M48 Chaparral / M6 Linebacker: tracked short-range SAM launchers
    # (MIM-72/Stinger respectively), unlike the gun-based systems above --
    # OP_SRSAM is the accurate bucket, not OP_SPAAG.
    ("chaparral", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    ("linebacker", ObjectTypeProfile(size_m=9.0, op_class="OP_SRSAM")),
    # Wheeled TEL launchers / rocket artillery / fuel-cargo trucks -- one
    # shared OP_TRUCK/6m bucket, matching the existing raw-table convention
    # (ural/kamaz/zil/truck are already one bucket there too).
    ("himars", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("ss-26", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),  # see docstring
    ("scud", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),  # see docstring
    ("mlrs", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("bm-30", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("bm-27", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("truck", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("bus", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    ("insurgent tech", ObjectTypeProfile(size_m=6.0, op_class="OP_TRUCK")),
    # Dismounted troops / MANPAD teams -- same OP_INFANTRY/1.8m bucket as
    # the existing raw "infantry"/"soldier" entries (ED's own reporting
    # names for these are literally "Soldier ..."/"...MANPADS").
    ("soldier", ObjectTypeProfile(size_m=1.8, op_class="OP_INFANTRY")),
    ("manpad", ObjectTypeProfile(size_m=1.8, op_class="OP_INFANTRY")),
)

#: ED's own WWII-era-unit naming convention in `HelperAI_reporting_names.lua`
#: -- every one of these 56+ reporting names starts with this literal
#: prefix (`"Old military truck"`, `"Old car"`, `"Old flak gun"`, ...), which
#: makes it a cheap, general guard rather than an enumerated exclusion list.
_WWII_REPORTING_NAME_PREFIX: Final[str] = "old "


def profile_for(object_type: str) -> ObjectTypeProfile:
    """Look up `object_type`'s size/class profile.

    Two passes, in order:

    1. Case-insensitive substring match against `_KEYWORD_PROFILES` (raw
       `object_type`, first match wins) -- unchanged from before the
       reporting-name mapping existed, so every type this already covered
       (ships, SA-3/6/8/9/13/15, existing armor/truck/infantry) keeps
       working identically regardless of the mapping below.
    2. If that finds nothing, resolve `object_type` to Petrovich's reporting
       name (`reporting_names.reporting_name_for`) and match *that* against
       `_REPORTING_NAME_KEYWORD_PROFILES`, skipping this pass entirely for
       a WWII-era reporting name (`_WWII_REPORTING_NAME_PREFIX`) -- see that
       table's docstring for why.

    Returns `_DEFAULT_PROFILE` if neither pass matches (including when
    `object_type` isn't in the reporting-name mapping at all -- an
    unmapped/new-to-this-DCS-version type still gets pass 1 above, so this
    degrades exactly like it did before this mapping existed, never a
    crash)."""
    text = object_type.lower()
    for keyword, profile in _KEYWORD_PROFILES:
        if keyword in text:
            return profile

    reporting_name = reporting_name_for(object_type)
    if reporting_name is not None and not reporting_name.lower().startswith(
        _WWII_REPORTING_NAME_PREFIX
    ):
        reporting_text = reporting_name.lower()
        for keyword, profile in _REPORTING_NAME_KEYWORD_PROFILES:
            if keyword in reporting_text:
                return profile

    return _DEFAULT_PROFILE
