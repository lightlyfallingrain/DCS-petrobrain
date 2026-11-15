---
name: project_bl_b112_buk_forward_note_wrong_precedent
description: BL-B112's forward-looking "if Buk is added" default picked the wrong precedent from the user's own two-branch mobility rule — check a plan's precedent-matching against this project's own prior research, not just internal consistency
metadata:
  type: project
---

BL-B112 (motion-aware contact certainty) stated a structural rule from the user with two
branches: "radar and launcher are different units -> fixed" vs. "a self-contained mobile SAM
platform that can up-and-go without deploying a separate radar -> mobile." The user named SA-6/Kub
an explicit exception to the first branch, because Kub's radar and launcher, though separate
units, are both self-propelled.

The plan's own forward note for a not-yet-added Buk/SA-11 picked the *first* branch ("same
structural shape as Kub" -> would land `immobile=True`), reasoning only from unit-count. But
`body-layer/research/2026-10-01-sam-site-geometry.md`, already on file, says Buk's TELARs (unlike
Kub's bare TEL) each carry their own engagement radar — the second branch, the one that made SA-6
mobile in the first place. The plan was internally consistent and traced cleanly against every
expectation; the error was a precedent match that contradicted this project's own prior research
note, not a logic error inside the plan.

**Why general:** a plan can be self-consistent and still reason from the wrong precedent when a
structural rule has two branches and a forward-looking item doesn't trigger a graph/research
check. Grep/graph the project's own prior research on the exact system named, not just the plan's
own stated reasoning, whenever a plan classifies something by analogy ("same shape as X").

See `[[project_bl_b111_decision_narrows_just_answered_expectation]]` for another case where a
structurally-clean plan needed checking against the user's own earlier wording, not just internal
consistency.
