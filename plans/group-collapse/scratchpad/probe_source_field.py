"""Probe 5 -- which `Contact` field must `collapse` read?

There are two candidates and they are not the same field:

  * `Contact.last_class_raw` -- the most recent percept's raw string.
    `belief.groups._profile_for_contact`/`_composition_of` read this.
  * `Contact.classification.value`/`.level` -- the FOLDED best claim.
    `belief.tools._classification_facts` and therefore
    `belief.speech._group_composition_clause` read this, and
    `plans/classification-refinement/plan.md` states the rule:
    *"everything user-facing ... reads `Contact.classification` instead"*.

`collapse` is a reporting derivation, i.e. user-facing. This probe confirms the
two fields really can disagree -- so that picking one is a decision with
consequences rather than a style choice -- by driving the lattice's `hold`
outcome, which is the oscillation fix that makes them diverge on purpose.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief import classification  # noqa: E402
from belief.classification import SpecificityLevel, new_classification_belief  # noqa: E402


def main() -> None:
    print("probe 5 -- last_class_raw vs classification.value")
    print()

    # A contact identified to TYPE, then re-observed only at CLASS level.
    held = new_classification_belief(
        value="ZSU-23-4 Shilka", level=SpecificityLevel.TYPE, established_sim=0.0
    )
    print(f"   held claim:      value={held.value!r} level={held.level.name}")

    incoming_raw = "OP_SPAAG"  # a coarser, class-level re-observation
    incoming = new_classification_belief(
        value=incoming_raw, level=SpecificityLevel.CLASS, established_sim=5.0
    )
    outcome = classification.fold_classification(
        held, incoming, now_sim=5.0, lockout_until_sim=None
    )
    print(f"   incoming percept: {incoming_raw!r} at CLASS")
    print(f"   fold outcome:     {outcome}")
    print()
    print(
        "   After this fold `Contact.last_class_raw` is the incoming\n"
        f"   {incoming_raw!r} (it is always the most recent percept -- see\n"
        "   `Contact`'s own docstring), while `Contact.classification` still\n"
        f"   holds {outcome.classification.value!r} at {outcome.classification.level.name}.\n"
        "   That is the lattice's `hold` rule and it is deliberate: the held,\n"
        "   more specific claim survives a coarser re-observation."
    )
    print()
    print("   So the two fields answer different questions:")
    print(f"     last_class_raw        -> {incoming_raw!r}        (latest evidence)")
    print(
        f"     classification.value  -> {outcome.classification.value!r}  (best belief)"
    )
    print()
    agree = outcome.classification.value == incoming_raw
    print(f"   do they agree here: {agree}")
    print()
    print(
        "   CONSEQUENCE for the plan: `collapse` must read\n"
        "   `Contact.classification` (value + level), NOT `last_class_raw`.\n"
        "   Reading `last_class_raw` would make a group's reported tree lose a\n"
        "   type identification the moment a coarser percept arrived -- the\n"
        "   exact oscillation `fold_classification` exists to prevent, and it\n"
        "   would contradict `_group_composition_clause`, which already reads\n"
        "   the folded claim through the facts path.\n"
        "\n"
        "   This also means `collapse` is NOT a reshaping of\n"
        "   `Group.composition`: that field reads `last_class_raw` through\n"
        "   `profile_for` (probe 2b), i.e. the other field AND the other\n"
        "   resolver. Two independent reasons it cannot be the tree's source."
    )
    print()
    print(
        "   Decay: `level` and `value` never decay by design\n"
        "   (`_classification_facts`' own docstring); only `confidence` does,\n"
        "   through `belief.decay.classification_confidence_at` over\n"
        "   IDENTITY_HALF_LIFE_S. So the collapse's GROUPING is decay-free and\n"
        "   matches the facts path exactly -- but if a node exposes confidence,\n"
        "   it must route through `classification_confidence_at`, never read\n"
        "   `ClassificationBelief.confidence` raw."
    )


if __name__ == "__main__":
    main()
