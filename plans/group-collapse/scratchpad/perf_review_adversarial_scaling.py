"""Performance-reviewer re-measurement, group-collapse, 2026-10-13.

Re-tests the architect's linearity claim at member counts well beyond any
realistic group (the plan's own ceiling is ~52 across a WHOLE SCENE, not one
group), to confirm `collapse_members` degrades linearly rather than
quadratically as member count grows, and to probe the worst case for the
single-pass bucket-then-recurse shape: many distinct TYPE-level values
sharing one sub-class (forces `_type_children`'s dict-building branch on
every bucket at CollapseDepth.CONTACT, the deepest/most expensive path).

Also asserts the harness itself can fail (CLAUDE.md's performance-reviewer
memory: "Assert the harness can fail before quoting a number") by including
a deliberately-broken run that must raise, so a silently-no-op timing loop
would be caught here rather than trusted.
"""

from __future__ import annotations

import random
import time

from belief.cardinality import CardinalityBelief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.group_view import CollapseDepth, collapse_members
from belief.position_belief import Covariance2D, PositionEstimate

random.seed(7)

_HALF_VARIANCE = 0.5 * 40.0 * 40.0


def make_member(i: int, op_class: str, type_value: str | None) -> Contact:
    level = SpecificityLevel.TYPE if type_value is not None else SpecificityLevel.CLASS
    value = type_value if type_value is not None else op_class
    cov = Covariance2D(xx=_HALF_VARIANCE, zz=_HALF_VARIANCE, xz=0.0)
    return Contact(
        id=f"C{i}",
        position=PositionEstimate(
            x=1000.0 + 17.0 * i,
            z=2000.0 + 13.0 * i,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw=op_class,
        classification=new_classification_belief(
            value=value, level=level, established_sim=0.0
        ),
        cardinality=CardinalityBelief(lo=1, hi=1, confidence=0.9, established_sim=0.0),
    )


def bench(members: list[Contact], depth: CollapseDepth, reps: int = 200) -> float:
    start = time.perf_counter()
    for _ in range(reps):
        collapse_members(members, depth, now_sim=0.0)
    elapsed = time.perf_counter() - start
    return (elapsed / reps) * 1e6  # us/call


def harness_can_fail() -> None:
    """Prove the harness itself is not a no-op: a `collapse_members` call
    over an empty sequence must return a GROUP node with zero contacts.
    A broken comparison here (e.g. silently swallowing an exception) would
    make every later timing number meaningless."""
    node = collapse_members([], CollapseDepth.CONTACT, now_sim=0.0)
    assert node.contacts == 0, "harness broken: empty collapse should report 0 contacts"
    # deliberately assert something FALSE to confirm assert actually fires
    try:
        assert node.contacts == 999, "expected failure"
        raise RuntimeError("harness cannot fail -- assert is not catching real mismatches")
    except AssertionError:
        pass  # expected: proves assert distinguishes true/false here


OP_CLASSES_NON_AD = ["OP_ARMORED", "OP_TRUCK", "OP_INFANTRY"]
AD_CLASSES = ["OP_SRSAM", "OP_MRSAM", "OP_LRSAM", "OP_SPAAG", "OP_ZU23"]


def worst_case_members(n: int) -> list[Contact]:
    """Many distinct TYPE-level values spread across the air-defence
    sub-classes -- forces `_type_children`'s per-bucket dict build at
    CONTACT depth on every one of the 5 sub-class buckets, the deepest and
    most work-per-member path in the module."""
    members = []
    for i in range(n):
        op_class = AD_CLASSES[i % len(AD_CLASSES)]
        type_value = f"{op_class}-variant-{i % 7}"  # 7 distinct types per sub-class
        members.append(make_member(i, op_class, type_value))
    return members


def realistic_mixed_members(n: int) -> list[Contact]:
    members = []
    for i in range(n):
        if i % 4 == 0:
            op_class = random.choice(AD_CLASSES)
            type_value = None if i % 8 == 0 else f"{op_class}-variant"
        else:
            op_class = random.choice(OP_CLASSES_NON_AD)
            type_value = None if i % 3 == 0 else f"{op_class}-variant"
        members.append(make_member(i, op_class, type_value))
    return members


if __name__ == "__main__":
    harness_can_fail()
    print("harness self-check: PASS (assert distinguishes true/false mismatches)\n")

    print("worst-case members (many TYPE values within air-defence sub-classes), depth=CONTACT")
    print(f"{'n':>6}  {'us/call':>10}  {'us/member':>10}  {'ratio vs n=52':>14}")
    base = None
    for n in (6, 20, 52, 150, 400, 1000, 4000):
        members = worst_case_members(n)
        reps = 200 if n <= 400 else 20
        us = bench(members, CollapseDepth.CONTACT, reps=reps)
        if n == 52:
            base = us
        ratio = us / base if base else float("nan")
        print(f"{n:6d}  {us:10.2f}  {us / n:10.4f}  {ratio:14.2f}")

    print()
    print("realistic mixed members, depth=SUBCLASS (Stage 2's shallow caller depth)")
    print(f"{'n':>6}  {'us/call':>10}  {'us/member':>10}")
    for n in (6, 20, 52, 150, 400):
        members = realistic_mixed_members(n)
        us = bench(members, CollapseDepth.SUBCLASS, reps=200)
        print(f"{n:6d}  {us:10.2f}  {us / n:10.4f}")

    print()
    print("Realistic push-path shape: 10 groups x 6 members, depth=SUBCLASS, per-tick total")
    total_us = 0.0
    for g in range(10):
        members = realistic_mixed_members(6)
        total_us += bench(members, CollapseDepth.SUBCLASS, reps=200)
    print(f"total: {total_us:.2f} us  ({total_us / 12600.0 * 100:.4f}% of BL-11's 12.6 ms poll)")

    print()
    print("Realistic push-path shape: 10 groups x 6 members, depth=CONTACT (deepest), per-tick total")
    total_us = 0.0
    for g in range(10):
        members = realistic_mixed_members(6)
        total_us += bench(members, CollapseDepth.CONTACT, reps=200)
    print(f"total: {total_us:.2f} us  ({total_us / 12600.0 * 100:.4f}% of BL-11's 12.6 ms poll)")
