---
name: project_bl2_5_restyle_followup
description: BL-2.5 follow-up (overlay restyle + contact-id + clipped-line fix, 2026-09-09) -- gameMessages.dlg as the grounding source, live-vs-guessed sizing tradeoff, id-format reuse.
metadata:
  type: project
---

Follow-up refinement pass on BL-2.5 (see [[project_bl2_5_overlay_hook]] for the original build),
after Stage 2 + Stage 4 both passed live acceptance: user saw the working overlay, decided
2026-09-09 to keep it but restyle it to look like DCS's native message feed, plus two defects from
a live screenshot (no contact id per line; last line clipped at fixed 420x200). Full record:
`plans/dcs-text-panel-output/plan.md` "Output-target decision, revisited after live acceptance",
`implementation.md`'s "Follow-up" section.

**`Scripts/UI/gameMessages.dlg` (DCS's own real, shipped message-box `.dlg`) is the single best
grounding source for "how should our custom dxgui overlay look/behave" questions** -- more useful
than SRS's overlay for *style* questions, because it's DCS's own first-party answer, not a
third-party addon's independent choice. It gave concrete, real values for: no title bar
(`headerHeight = 0`), no opaque background (`bkg.center_center = "0x00000000"` on the window,
`"$nil$"` on the per-line text sub-skin), legibility via glyph shadow not a panel (`shadowColor`/
`shadowOffset`, not a background box), and real screen position (`autoScrollTextRadio` at
`(29, 59)` inside a top-left-anchored window). When asked to make a custom DCS UI "look native,"
read the real file DCS itself ships for that exact use case before inventing values.

**When a fixed pixel constant is being guessed under genuine uncertainty (native/closed-source
wrap behavior, unknown glyph metrics) and the plan itself points at a runtime self-diagnostic API
(`calcSize()`/`getTextLinesCount()`), prefer turning that diagnostic into the live sizing
mechanism over enlarging the guessed constant.** Concretely: `apply_content_size()` now calls
`calcSize()` after every `addText()` and resizes the widget/window to the real reported content
height (clamped), instead of picking a bigger fixed `HEIGHT`. This is strictly more defensible
when static recon genuinely cannot pin down the missing number (see
[[project_m6_terrain_semantics]]-style "resolution ceiling, not a guess to fix" framing) --
but it is also new, previously-unexercised runtime behavior, so flag it as the *most* load-bearing
unverified piece of the pass, not a routine change, in both the commit message and
implementation.md.

**Reuse an existing id-rendering convention rather than inventing a second one when a bug report
says "can't tell contacts apart."** `console.py` already had `"<id>: <text>"` for `contacts`/
`show <id>`; the overlay's `format_event_for_overlay` was missing the id entirely (its own
oversight from the original build, not a new requirement) -- fixed by reusing that exact
convention (`"<contact id>: <kind>, <summary>"`) rather than picking a fresh format. When a task
says "match however X already renders Y," grep the actual existing renderer first
(`_format_contact_line` here) instead of designing a plausible-looking format from scratch.

**A lifecycle-event model where `CONTACT_DETECTED` can only fire once per contact
(`previous_certainty is None`, true exactly once) makes "one contact re-firing the same event N
times" structurally provable-impossible from reading the state machine alone** -- worth checking
before assuming a "duplicate line" symptom is a re-fire bug; it may instead be genuine multiplicity
(N real objects) or upstream churn (an association gate minting a new contact per poll for one
real object). Report which is structurally possible rather than guessing which occurred.
