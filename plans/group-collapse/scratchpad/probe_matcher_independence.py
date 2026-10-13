"""Probe 2 -- does `group_matches` keep working off the flat tuple once a
derived tree exists, or does something in it quietly want the deeper structure?

Open question 2 from `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`
Part 4. The capture states flat-for-matching as a *recommendation*, explicitly
not measured against the matcher. This measures it three ways:

1. **By AST** -- every `Group`/`_ClusterProperties` attribute `group_matches`
   actually reads, enumerated from the source rather than read off by eye.
2. **By round trip** -- whether a depth<=2 collapse and the flat
   `composition` tuple carry the same information, i.e. whether a tree could
   ever distinguish two rosters the tuple cannot (if not, the tree adds nothing
   a matcher could use).
3. **By partition identity** -- whether test 4's inline
   `classes - AIR_DEFENSE_OP_CLASSES` carve-out is the same partition the
   collapse's level-1 ("class") step produces. If it is, the two should share
   one vocabulary instead of spelling it twice.
"""

from __future__ import annotations

import ast
import inspect
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief import classification, groups  # noqa: E402

# --------------------------------------------------------------------------
# 1. By AST.
# --------------------------------------------------------------------------


def attributes_read_by(func: object) -> dict[str, set[str]]:
    """`{base_name: {attribute, ...}}` for every `x.y` load in `func`."""
    src = inspect.getsource(func)  # type: ignore[arg-type]
    tree = ast.parse(inspect.cleandoc(src))
    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found.setdefault(node.value.id, set()).add(node.attr)
    return found


def report_ast() -> None:
    print("1. BY AST -- what group_matches actually reads")
    print()
    reads = attributes_read_by(groups.group_matches)
    for base in sorted(reads):
        if base in {"math", "classification", "groups"}:
            continue
        print(f"   {base}.*  ->  {sorted(reads[base])}")
    print()
    tree_only = {"members", "member_contact_ids", "branches", "types", "units"}
    leaked = {
        f"{b}.{a}" for b, attrs in reads.items() for a in attrs if a in tree_only
    }
    print(f"   roster/tree-shaped attributes read: {sorted(leaked) or 'NONE'}")
    print(
        "   => group_matches reads only remembered scalars and the two flat\n"
        "      tuples. It never touches a roster, so it cannot want a tree."
    )
    print()


# --------------------------------------------------------------------------
# 2. By round trip.
# --------------------------------------------------------------------------


def collapse_to_class_level(class_raws: list[str]) -> dict[str, dict[str, int]]:
    """The depth<=2 collapse: class -> sub-class -> count. Level 1's only
    vocabulary in code today is AIR_DEFENSE_OP_CLASSES (see partition test
    below); everything else stands as its own class."""
    out: dict[str, Counter[str]] = {}
    for raw in class_raws:
        op = classification.parent_class_of(raw)
        sub = op if op is not None else "unknown"
        label = "air defense" if op in classification.AIR_DEFENSE_OP_CLASSES else sub
        out.setdefault(label, Counter())[sub] += 1
    return {k: dict(v) for k, v in out.items()}


def flat_composition(class_raws: list[str]) -> tuple[tuple[str, int], ...]:
    """`_composition_of`'s shape -- but note it resolves through
    `_profile_for_contact` (`object_model.profile_for`), NOT the lattice, so
    this reproduction uses the lattice and is therefore the *generous* case for
    the tree. See the note printed below."""
    counts = Counter(
        classification.parent_class_of(raw) or "unknown" for raw in class_raws
    )
    return tuple(sorted(counts.items()))


def report_round_trip() -> None:
    print("2. BY ROUND TRIP -- can a depth<=2 tree distinguish rosters the flat")
    print("   tuple cannot?")
    print()
    rosters = [
        ["OP_ARMORED", "OP_TRUCK"],
        ["OP_ARMORED", "OP_ARMORED", "OP_TRUCK"],
        ["T-72B", "Ural-375"],  # type level, same parents as roster 0
        ["OP_SPAAG", "OP_LRSAM"],
        ["OP_LRSAM", "OP_SPAAG"],  # same multiset, different order
        ["OP_SPAAG", "OP_SPAAG"],
        ["OP_GROUPSOMETHING", "OP_GROUPSOMETHING"],
    ]
    def _naive_key(roster: list[str]) -> str:
        """`repr` of the dict as built. Looks canonical; is not."""
        return repr(sorted(collapse_to_class_level(roster).items()))

    def _canonical_key(roster: list[str]) -> str:
        """Every level sorted, so insertion order cannot leak into the key."""
        tree = collapse_to_class_level(roster)
        return repr(
            sorted((label, sorted(subs.items())) for label, subs in tree.items())
        )

    by_flat: dict[tuple[tuple[str, int], ...], list[int]] = {}
    by_naive: dict[str, list[int]] = {}
    by_tree: dict[str, list[int]] = {}
    for i, roster in enumerate(rosters):
        by_flat.setdefault(flat_composition(roster), []).append(i)
        by_naive.setdefault(_naive_key(roster), []).append(i)
        by_tree.setdefault(_canonical_key(roster), []).append(i)
    print(f"   distinct flat compositions:        {len(by_flat)}")
    print(f"   distinct trees, naive repr key:    {len(by_naive)}  <-- see below")
    print(f"   distinct trees, every level sorted:{len(by_tree)}")
    naive_partition = sorted(sorted(v) for v in by_naive.values())
    print(f"   naive-key partition: {naive_partition}")
    print(
        "   The naive key splits rosters 3 and 4 -- ['OP_SPAAG','OP_LRSAM'] and\n"
        "   ['OP_LRSAM','OP_SPAAG'], the SAME multiset in a different order.\n"
        "   This probe's first draft had that bug, and the bug is the finding:\n"
        "   a nested dict built by insertion is NOT canonical, so comparing two\n"
        "   derived trees needs every level sorted deliberately. That is the\n"
        "   capture's 'a nested structure would need its own comparison\n"
        "   semantics', demonstrated rather than asserted -- and it is the\n"
        "   concrete reason not to make a tree the match key.\n"
    )
    flat_partition = sorted(sorted(v) for v in by_flat.values())
    tree_partition = sorted(sorted(v) for v in by_tree.values())
    print(f"   flat partition of rosters: {flat_partition}")
    print(f"   tree partition of rosters: {tree_partition}")
    same = flat_partition == tree_partition
    print(f"   identical partition: {same}")
    print(
        "   => a depth<=2 tree is an exact relabelling of the flat multiset: it\n"
        "      groups and nests, it never adds a distinction. Only depth>=3\n"
        "      (type) or depth 4 (per contact) adds information, and no\n"
        "      group_matches test reads either (see 1)."
        if same
        else "   => DIVERGENT -- investigate before trusting flat-for-matching."
    )
    print()
    print(
        "   NOTE, and it matters: `_composition_of` resolves through\n"
        "   `object_model.profile_for`, not the lattice. This probe used the\n"
        "   lattice. So `Group.composition` is a *coarser* key than even the\n"
        "   depth<=2 tree -- see probe 2b below."
    )
    print()


def report_resolver_divergence() -> None:
    print("2b. THE RESOLVER SPLIT -- composition and the tree do not agree")
    print()
    from perception import object_model  # noqa: PLC0415

    raws = [
        "OP_ARMORED",
        "OP_TRUCK",
        "OP_INFANTRY",
        "OP_SPAAG",
        "OP_LRSAM",
        "OP_SRSAM",
        "OP_MRSAM",
        "OP_ZU23",
        "T-72B",
        "Ural-375",
        "ZSU-23-4 Shilka",
        object_model.DEFAULT_OP_CLASS,
    ]
    print("   class_raw                  profile_for      parent_class_of   agree?")
    print("   ---------                  -----------      ---------------   ------")
    disagreements = 0
    for raw in raws:
        p = object_model.profile_for(raw).op_class
        lattice = classification.parent_class_of(raw)
        agree = p == lattice
        disagreements += 0 if agree else 1
        print(f"   {raw:<26} {p:<16} {str(lattice):<17} {'yes' if agree else 'NO'}")
    print()
    print(
        f"   {disagreements} of {len(raws)} disagree. Every disagreement is a\n"
        "   CLASS-level belief -- the common case at range. `Group.composition`\n"
        "   buckets all of them into OP_GROUPSOMETHING; the lattice resolves\n"
        "   them. This is the BL-B47 family (see the dod agent's own memory,\n"
        "   `project_recurring_air_defence_vocabulary_resolution_gap.md`,\n"
        "   4 prior occurrences).\n"
        "\n"
        "   Consequence for this plan: `collapse` MUST resolve through the\n"
        "   lattice, and must NOT be built by reshaping `Group.composition` --\n"
        "   that field cannot see most class-level beliefs. It is a match key,\n"
        "   and it is correct as one (both sides of every comparison resolve\n"
        "   the same way, so it is self-consistent), but it is not a\n"
        "   projection of the tree the user described."
    )
    print()


# --------------------------------------------------------------------------
# 3. By partition identity.
# --------------------------------------------------------------------------


def report_partition() -> None:
    print("3. BY PARTITION IDENTITY -- is test 4's carve-out the collapse's")
    print("   level-1 step?")
    print()
    src = inspect.getsource(groups.group_matches)
    inline = "AIR_DEFENSE_OP_CLASSES" in src
    print(f"   group_matches references AIR_DEFENSE_OP_CLASSES inline: {inline}")
    all_classes = sorted(
        {
            "OP_ARMORED",
            "OP_TRUCK",
            "OP_INFANTRY",
            "OP_SPAAG",
            "OP_LRSAM",
            "OP_SRSAM",
            "OP_MRSAM",
            "OP_ZU23",
            "OP_HELI",
            "OP_JET",
            "OP_SHIP",
        }
    )
    matcher_view = {
        c: ("<excluded from test 4>" if c in classification.AIR_DEFENSE_OP_CLASSES else c)
        for c in all_classes
    }
    collapse_view = {
        c: ("air defense" if c in classification.AIR_DEFENSE_OP_CLASSES else c)
        for c in all_classes
    }
    same_grouping = [
        c for c in all_classes if (matcher_view[c] != c) == (collapse_view[c] != c)
    ]
    print(
        f"   classes the two treat the same way: {len(same_grouping)}/{len(all_classes)}"
    )
    print(
        "   => test 4 partitions op_classes into {air defence} and {everything\n"
        "      else} and handles the two differently. That is exactly the\n"
        "      user's level-1 'class' step, with one branch named and the rest\n"
        "      left flat. So the collapse's level-1 vocabulary is not new\n"
        "      invention -- it is the generalisation of a partition the matcher\n"
        "      already relies on, and the two should read one table."
    )
    print()
    print(
        "   This is also why `air_defence_composition` exists as its own field\n"
        "   rather than being derived: see probe 3."
    )


if __name__ == "__main__":
    report_ast()
    report_round_trip()
    report_resolver_divergence()
    report_partition()
