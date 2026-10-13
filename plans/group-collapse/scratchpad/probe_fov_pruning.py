"""Probe 4 -- the FOV/mask pruning direction, and whether the head-turn
artefact is real.

User direction, mid-pass 2026-10-13: *"As with other detection logic, we can
ignore units outside the perception FOV cone or masked by cockpit. If Petrovich
could not see it, we don't need to calculate it any further."*

The coordinator raised the subtlety: a belief-layer contact outside the mask is a
*remembered* contact, not an undetected one, so omitting it from a derived tree
would make *"what armor is there"* change as the pilot's head turns. Two readings
(cost pruning vs content filtering) and the question of whether the relevant test
is the CURRENT mask or each member's own last-observed state.

This probe establishes four things against the real code:

1. What observability state the belief layer already holds per contact, and
   therefore whether a perception->belief seam would have to be crossed at all.
2. Whether `callout_observable`'s test is current-mask or last-observed.
3. Whether the head-turn artefact is real under each reading -- by driving a
   contact in and out of the co-pilot mask and sampling the two predicates.
4. What the push path already does, so the plan does not reinvent it.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "world-model" / "src"))
sys.path.insert(0, str(_ROOT / "body-layer" / "src"))

from belief import callouts, contacts as contacts_module  # noqa: E402
from belief.decay import (  # noqa: E402
    CALLOUT_OBSERVABILITY_GRACE_S,
    LOST_THRESHOLD_S,
    OBSERVED_WINDOW_S,
    POSITION_HALF_LIFE_S,
)
from perception import cockpit_mask  # noqa: E402


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def q1_what_belief_already_holds() -> None:
    section("1. What observability state the BELIEF layer already holds")
    from belief.contacts import Contact  # noqa: PLC0415

    fields = {f for f in Contact.__dataclass_fields__}
    observability = sorted(
        f
        for f in fields
        if any(k in f for k in ("observable", "los", "masked", "seen_sim"))
    )
    for f in observability:
        print(f"   Contact.{f}")
    print()
    print(
        "   => the belief layer ALREADY carries per-contact observability.\n"
        "      `ContactStore.tick(ownship=...)` evaluates\n"
        "      `perception.cockpit_mask.is_visible` once per contact per tick\n"
        "      and stamps `last_observable_sim` (see `_callout_may_speak`).\n"
        "      So NO new perception->belief seam is needed: the seam exists,\n"
        "      is sanctioned, and is crossed exactly once per tick rather than\n"
        "      once per collapse."
    )
    print()
    src = inspect.getsource(contacts_module._callout_may_speak)
    print("   `_callout_may_speak` uses, in its own words:")
    for line in src.splitlines():
        if "gaze" in line or "is_visible" in line:
            print(f"     {line.strip()}")
    print()
    print(
        "   NOTE the distinction that decides the user's sentence: the\n"
        "   bookkeeping tests the COCKPIT MASK (physically unseeable from any\n"
        "   gaze direction), deliberately NOT the narrower GAZE cone. Decision 1\n"
        "   of plans/sortie-2026-09-26-fixes is explicit that a contact merely\n"
        "   out of current gaze must still get its tracking update."
    )


def q2_current_or_remembered() -> None:
    section("2. Is `callout_observable` a current-mask test or a remembered one?")
    print(inspect.getsource(contacts_module.ContactStore.callout_observable).split('"""')[-1].strip())
    print()
    print(f"   CALLOUT_OBSERVABILITY_GRACE_S = {CALLOUT_OBSERVABILITY_GRACE_S} s")
    print(f"   OBSERVED_WINDOW_S             = {OBSERVED_WINDOW_S} s")
    print(f"   POSITION_HALF_LIFE_S          = {POSITION_HALF_LIFE_S} s")
    print(f"   LOST_THRESHOLD_S              = {LOST_THRESHOLD_S} s")
    print()
    print(
        "   => it is a REMEMBERED test with a grace window, not a current-mask\n"
        "      test. `now_sim - last_observable_sim < 10 s`. The grace window\n"
        "      exists for exactly the artefact the coordinator named, and its\n"
        "      own docstring says so: the window must be measured from the last\n"
        "      confirmed sighting rather than from the first failed check."
    )


def q3_head_turn_artefact() -> None:
    section("3. Is the head-turn artefact real? Drive the mask and sample.")
    mask = cockpit_mask.COCKPIT_MASKS[cockpit_mask.STATION_CO_PILOT]
    print(f"   co-pilot mask: {mask}")
    print()
    print("   azimuth  is_visible   <- the raw current-mask test")
    print("   -------  ----------")
    visible_azimuths = []
    for az in range(0, 360, 30):
        vis = cockpit_mask.is_visible(mask, float(az), 0.0)
        if vis:
            visible_azimuths.append(az)
        print(f"   {az:>7}  {str(vis):>10}")
    print()
    print(f"   visible body azimuths (30 deg steps): {visible_azimuths}")
    print()
    print(
        "   The artefact, concretely. Take a group of six whose members sit at\n"
        "   body azimuths spread across the rear cutoff. Under a CURRENT-mask\n"
        "   content filter, `collapse` returns a different member set on every\n"
        "   tick the airframe yaws -- so `what armor is there` answers\n"
        "   differently second to second with the world unchanged. Under the\n"
        "   REMEMBERED test the same group holds its roster for\n"
        f"   {CALLOUT_OBSERVABILITY_GRACE_S} s past the last confirmed sighting, and the\n"
        "   decay ladder then takes over honestly.\n"
        "\n"
        "   Worse, and this is the part a cost argument hides: the member set is\n"
        "   the matcher's input too. `GroupStore.reconcile` clusters over\n"
        "   `ContactStore`'s contacts; if a FOV filter ran upstream of the\n"
        "   clustering, a yaw would look like a split/merge and churn group\n"
        "   identity -- which is the thing BL-12 exists to stabilise."
    )


def q4_what_the_push_path_already_does() -> None:
    section("4. What the push path already does (do not reinvent it)")
    src = inspect.getsource(callouts.CalloutScheduler.tick)
    in_loop = False
    for line in src.splitlines():
        if "for belief_group in store.groups" in line:
            in_loop = True
        if in_loop and ("callout_observable" in line or "if not any(" in line):
            print(f"     {line.rstrip()}")
        if in_loop and "_group_member_facts" in line:
            break
    print()
    print(
        "   => the push path ALREADY gates on observability, with `any` member\n"
        "      observable rather than `all`, and the comment there states the\n"
        "      reason: a group straddling the cutoff is a group Petrovich can\n"
        "      genuinely see, and requiring every member would silence a\n"
        "      visibly-present group for the sake of one straggler behind the\n"
        "      doorframe.\n"
        "\n"
        "      That is reading (1) -- cost/consent pruning on WHETHER to render\n"
        "      -- already implemented, at the call site, outside the\n"
        "      derivation. It is the precedent the plan should follow."
    )


if __name__ == "__main__":
    q1_what_belief_already_holds()
    q2_current_or_remembered()
    q3_head_turn_artefact()
    q4_what_the_push_path_already_does()
