---
name: reproduce-the-fix-sketch-not-just-the-defect
description: A finding's own suggested fix is a claim to be measured, not a spec to implement — BL-B58's sketched check was a measured no-op because the edge it would re-test already passed
metadata:
  type: feedback
---

**When a backlog entry or review finding proposes a fix, reproduce the *fix* against the defect, not
only the defect.** The entry's characterisation of the symptom can be exactly right while its
proposed remedy is a no-op.

**Why:** `BL-B58` (2026-10-12) was written by the Reviewer who reproduced the defect, carefully and
correctly — bounded, measured, amplification quantified. Its option 3 sketched the fix as *"exclude a
newly-added member whose own gap to the pre-existing cluster fails the same pair backstop
`_cluster_contacts` already applies pairwise."* One probe dumping every pair's gap beside its
threshold showed the absorbing edge at **81.9 m against an 88.0 m backstop** — it *already passes*.
Re-applying that test changes nothing. The user had chosen that option over two others on the
strength of a description of a fix that could not work. Two further candidate designs died the same
way in the same probe: a cluster-extent bound cannot discriminate (the wrong 4-member cluster and
the correct 3-member one have **identical** extent, 329.9 m), and every tick-local displacement test
only delays the absorption one tick, because the corrupted position *persists* (t=15 byte-identical
to t=12).

The general shape: a finding is written while looking at the *symptom*, so its fix proposal is
reasoning, not measurement — and it inherits the authority of the measurement next to it.
Cf. [[feedback_reproduce_the_threshold_arithmetic]], which says to run the thresholded decision;
this is the next step out — run the **candidate rule** against the real geometry before adopting the
entry's framing of it.

**How to apply:**
- Before accepting a finding's option as the design, print the quantity the option would test and
  the threshold it would test against, for the specific edge/row where the defect occurs. If the
  verdict is already the one the option wants to produce, the option is a no-op.
- Check persistence explicitly: run two or three ticks past the incident. If the corrupted state is
  still there, every tick-local rule is a one-tick delay, and the fix must carry state or provenance.
- Report the correction to the user as a *correction to the description*, not as a re-litigation of
  their choice — the seam they picked can be right while the check they were shown is wrong. Say the
  cost shape changed (here: one more module, no new constant), and then plan their option anyway.
- Always include invariant rows the fix must not change, and assert them identical. Three of six rows
  in the BL-B58 probe were invariants, and they are the whole of the argument that the gate does not
  undo Stage 0 or `D5`.
