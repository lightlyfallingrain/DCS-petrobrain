---
name: bl17-collision-loosening-not-a-confident-wrong-command-vector
description: audio-adapter's 2026-11-19 rule-x-legacy collision loosening (confident_loss_disables=False) widens what PUT /rules accepts but does not create a new confident-wrong-command path -- the runtime merge in command_matcher already picks by match_ratio regardless of registry membership
type: project
---

`fix/rule-collision-misheard` (`[[BL-17]]`) added `confident_loss_disables: bool` to
`rule_patterns._is_genuine_collision`/`_collides_with_legacy`, so a rule whose only legacy collision
is a confident *loss* on a perturbed sample is now accepted instead of disabled (exact ties on clean
wording are still rejected, unchanged).

**Why this is not a security widening despite accepting more rules via an unauthenticated LAN
endpoint (`PUT /rules`):** `command_matcher.match_transcript`'s rule/legacy merge
(`audio-adapter/src/command_matcher.py:1166-1182`) already resolves a confident mis-hearing to
whichever branch has the higher `match_ratio`, independent of whether the colliding rule exists in
the registry at all. So whether the rule is accepted or rejected changes nothing about which command
actually fires for the mis-heard sample that drove the rejection — only whether the rule's *clean*
wording also works. Confirmed by re-reading the merge logic independently of the Reviewer's own
verification (`plans/rule-collision-misheard/review.md`).

**General lesson for this collision-check family**: when assessing whether a load-time acceptance
gate loosening is security-relevant, check what the *runtime* matcher does with an accepted-but-risky
entry before concluding the gate change widens an exploit surface — the gate and the runtime
disambiguation are two separate mechanisms here, and the runtime one is often the one actually
carrying the safety property.

**Pre-existing, unrelated to this fix**: `PUT /rules`/`/speak`/`/transcribe`/`/stop` carry no
authentication by design (`audio-adapter/CLAUDE.md`, "Running the server" section) — a hostile LAN
host could already push arbitrary rules before this change. Not filed as a new finding; already a
named, accepted project decision.

See also [[project_bl17_rule_x_legacy_confident_loss_no_longer_disables]] (reviewer's memory on the
same mechanism).
