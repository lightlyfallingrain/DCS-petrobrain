---
name: command-map-check-vs-hand-redraw
description: command-map-check.py passing only proves the token<->card manifest matches TOKENS; it says nothing about stale badges/captions that need a manual Mermaid-card edit
metadata:
  type: feedback
---

`command-map-check.py` (the mechanical half of the `/command-map` skill) validates one thing: that
every token in `audio-adapter/src/vocabulary.py`'s `TOKENS` has exactly one card in
`docs/status/petrovich-commands.html`'s manifest, and vice versa. It does **not** check whether a
card's hand-drawn badges, captions, or prose correctly describe current behaviour.

**Why this matters for review**: BL-B96 (`plans/default-crew-pipeline/plan.md`) removed the F10
radio-menu transport but deliberately left `vocabulary.py`'s `LEGACY_F10_TOKENS` constant
unchanged (a pure naming/classification leftover, not a dependency — the plan's own Decision). The
token set therefore didn't change, `command-map-check.py` reported "current," and the
implementation report concluded "no redraw needed." But the plan had *explicitly* flagged that the
page's F10 badges/caption (a real-world affordance claim, "there used to be a button") do need a
manual redraw regardless of the token-set check passing. The check passing and the page being
correct are two different claims — conflating them let a stale, now-false player-facing claim
("F10 has ahead/left/right/full...") ship unnoticed through an otherwise clean implementation.

**How to apply**: whenever a feature removes/changes a *transport* or *affordance* without
changing the *token set* itself (voice vocabulary unchanged, only how a command reaches dispatch
changes), don't accept "command-map-check reports current" as proof the status page is accurate.
Actually read the page's cards/badges/captions for claims the change falsified. This is the same
shape as the broader "verify state, not the account of it" failure mode — a green mechanical check
answering a narrower question than the one being asked of it.
