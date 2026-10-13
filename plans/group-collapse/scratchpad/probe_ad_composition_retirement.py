"""Probe 3 -- can `air_defence_composition` be retired into
`collapse(group, ...)["air defense"]`?

Open question 3 from `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`
Part 4: *"Whether `air_defence_composition` can then be retired (it would become
`collapse(group, ...)['air defense']`) or whether `D6`'s gate needs it
materialised for a reason the derivation cannot serve."*

The capture calls the field *"a symptom of the tree being flattened"*. This probe
tests whether it is instead load-bearing, by exercising the one path that reads
it: `group_matches` test 3, during `reconcile`'s phase 2 (property match), where
the group being matched is a REMEMBERED group whose members may be gone from the
`ContactStore` entirely.

If the derivation cannot produce the field for a group with no live members, the
field cannot be retired -- regardless of how redundant it looks.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402
from belief.contacts import Contact, ContactStore  # noqa: E402
from belief.decay import GROUP_REIDENTIFY_WINDOW_S  # noqa: E402
from belief.groups import GroupStore  # noqa: E402
from belief.position_belief import Covariance2D, PositionEstimate  # noqa: E402


def _contact(cid: str, x: float, z: float, class_raw: str) -> Contact:
    half = 0.5 * 40.0 * 40.0
    cov = Covariance2D(xx=half, zz=half, xz=0.0)
    return Contact(
        id=cid,
        position=PositionEstimate(
            x=x, z=z, covariance=cov, as_of_sim=0.0, fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw=class_raw,
        classification=new_classification_belief(
            value=class_raw, level=SpecificityLevel.CLASS, established_sim=0.0
        ),
    )


def main() -> None:
    print("probe 3 -- is air_defence_composition retirable?")
    print()

    store = GroupStore()

    # Tick 1: a SAM site and a truck, close together. One group forms.
    members = [
        _contact("AD1", 0.0, 0.0, "OP_LRSAM"),
        _contact("AD2", 30.0, 10.0, "OP_LRSAM"),
    ]
    store.reconcile(members, now_sim=0.0)
    observed = store.groups
    print(f"   tick 0: groups formed = {len(observed)}")
    g = observed[0]
    print(f"           id={g.id}")
    print(f"           member_contact_ids={sorted(g.member_contact_ids)}")
    print(f"           composition={g.composition}")
    print(f"           air_defence_composition={g.air_defence_composition}")
    print()
    print(
        "   Note already: `composition` says OP_GROUPSOMETHING for a\n"
        "   class-level LRSAM belief (probe 2b), while\n"
        "   `air_defence_composition` says OP_LRSAM. The lattice-resolved\n"
        "   field is the only one that can see what this group is."
    )
    print()

    # Tick 2: every member gone from the contact store (occlusion, fold,
    # whatever) -- reconcile with NO contacts. The group is retained, frozen.
    store.reconcile([], now_sim=1.0)
    print(f"   tick 1 (no contacts at all): store.groups = {len(store.groups)}")
    remembered = store.remembered_groups
    print(f"                                remembered_groups = {len(remembered)}")
    r = remembered[0]
    print(f"           id={r.id}  last_observed_sim={r.last_observed_sim}")
    print(f"           member_contact_ids={sorted(r.member_contact_ids)}")
    print(f"           air_defence_composition={r.air_defence_composition}  <-- STILL HELD")
    print()

    # The decisive test: can a derivation reproduce that field now?
    contact_store = ContactStore()  # deliberately empty -- the members are gone
    resolvable = [
        mid for mid in r.member_contact_ids if contact_store.contact(mid) is not None
    ]
    print("   Can `collapse(group, ...)` derive the air-defence branch now?")
    print(f"           members resolvable from ContactStore: {len(resolvable)} of "
          f"{len(r.member_contact_ids)}")
    print(
        "           => NO. A derivation reads members; this group has none\n"
        "              resolvable. A collapse would return an empty tree, so\n"
        "              `collapse(group, ...)['air defense']` would be absent\n"
        "              exactly when test 3 needs it."
    )
    print()

    # And this is not a hypothetical window -- it is 60 s wide.
    print(f"   GROUP_REIDENTIFY_WINDOW_S = {GROUP_REIDENTIFY_WINDOW_S} s")
    print(
        "   Phase 2 (property match) runs against `remembered_groups` for this\n"
        "   whole window. `Group.air_defence_composition`'s own docstring\n"
        "   already states the reason it is a field: *'Kept as its own field\n"
        "   rather than re-derived at match time, because D6 keys the\n"
        "   air-defence confirmation gate on the remembered value -- by the\n"
        "   time a match is attempted the members producing it may be gone.'*\n"
        "   This probe confirms that sentence rather than taking its word."
    )
    print()

    # Now show the match actually working off the remembered value.
    from belief.groups import _cluster_properties, group_matches  # noqa: PLC0415

    fresh = [
        _contact("NEW1", 5.0, 5.0, "OP_LRSAM"),
        _contact("NEW2", 35.0, 15.0, "OP_LRSAM"),
    ]
    props = _cluster_properties(fresh)
    matched = group_matches(r, props, elapsed_s=1.0)
    print(f"   a fresh LRSAM cluster re-matches the remembered group: {matched}")
    mismatched_props = _cluster_properties(
        [_contact("NEW3", 5.0, 5.0, "OP_TRUCK"), _contact("NEW4", 35.0, 15.0, "OP_TRUCK")]
    )
    mismatched = group_matches(r, mismatched_props, elapsed_s=1.0)
    print(f"   a fresh TRUCK cluster re-matches it:                    {mismatched}")
    print()
    if matched and not mismatched:
        print(
            "   => test 3 is doing real work off the remembered field, and it is\n"
            "      the ONLY test that can distinguish these two cases: test 4\n"
            "      compares `composition`, which is OP_GROUPSOMETHING for the\n"
            "      LRSAM side (probe 2b), so it cannot tell a SAM site from a\n"
            "      truck park at class level."
        )
    else:
        print("   => UNEXPECTED -- re-examine before concluding.")

    print()
    print("   VERDICT: air_defence_composition CANNOT be retired by this plan.")
    print(
        "   It is not a symptom of flattening; it is a MEMORY of a derivation,\n"
        "   held for a window in which the inputs to that derivation no longer\n"
        "   exist. The collapse and the field answer different questions:\n"
        "     collapse  -- what is this group, now, from live members (reporting)\n"
        "     the field -- what was this group, then, for re-identification\n"
        "   Retiring it would silently weaken BL-12's D6 gate to nothing."
    )


if __name__ == "__main__":
    main()
