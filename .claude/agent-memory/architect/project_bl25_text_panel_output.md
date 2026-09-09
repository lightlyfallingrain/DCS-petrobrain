---
name: project_bl25_text_panel_output
description: BL-2.5 (in-cockpit text mirror) design — transport, message model, milestone-naming precedent, and the aircraft-layer's first write path
metadata:
  type: project
---

**BL-2.5 plan** (`plans/dcs-text-panel-output/plan.md`, branch `feature/dcs-text-panel-output`):
an interim milestone between BL-2 and BL-3, scheduled by explicit user decision (2026-09-09) — not
an Architect recommendation. Builds a DCS in-cockpit scrolling text overlay (Hook-state script +
`AutoScrollText` widget, modeled on SRS's real installed overlay) fed by body-layer's belief
lifecycle events (`CONTACT_DETECTED`/`LOST`/`REACQUIRED`), for live sortie dev-visibility now and
reuse as BL-10's SRS-fallback transport later.

**Why:** near-term driver is watching BL-2/PB-1.5 belief state in-cockpit instead of alt-tabbing to
an external log during a live sortie. Long-term driver is BL-10 (SRS fallback) reusing the same
transport with a different producer.

**How to apply — milestone-naming precedent (PB-x vs BL-x):** when a cross-cutting interim
milestone needs a decimal label (mirroring PB-1.5's insertion between PB-1/PB-2), the family it
takes is **whichever roadmap it's actually scheduled into**, not whichever module has the most new
code. PB-1.5 got the PB- label because it was itself a real cognition-capability tier (naked-eye
perception), even though its code landed in body-layer's BL-1 window. A milestone that is pure
infrastructure/tooling (no perception/memory/attention/dialogue content) has no natural PB- slot
even if it's scheduled inside the BL-x sequence — take the BL- label instead, and cite BL-2 Stage
-1 (a pure aircraft-layer change tracked under a BL-numbered plan because BL-2 was the consumer) as
the precedent for a BL-numbered milestone containing mostly non-body-layer work. See
[[feedback_stage_memory_files]] for the unrelated staging habit; this is a naming-convention note,
not a process one.

**How to apply — aircraft-layer's read-only framing:** `aircraft-layer/CLAUDE.md`'s "What this is"
opening line ("read-only telemetry pipeline") stops being accurate once BL-2.5's `POST /text/push`
lands — this is the pipeline's first inbound/write direction. BL-2.5's plan revises that line to
"read-mostly, one narrow write-back channel for text display" rather than leaving the stale
"read-only" claim in place. If a future milestone touches `aircraft-layer/CLAUDE.md`'s framing
again, check whether BL-2.5 actually shipped that edit (this plan; not yet Implementer-confirmed as
of the plan being written) before assuming "read-only" is still true. **BL-7's future real command
channel is a much larger instance of the same shape and still needs its own Security plan review
when it arrives** — `plans/aircraft-layer/plan.md`'s existing flag on that is unchanged and is not
discharged by BL-2.5's narrower write path.

**Investigator pattern worth repeating:** Session 1 of the dxgui/text-panel research left
"`dxgui`/`Static` source not found" as unresolved. A second Investigator pass (Session 2, same
research file) searched a directory Session 1 never checked (`$DCS_INSTALL_PATH/dxgui/`, a
top-level install dir, not under `Scripts/`) and found the complete real source tree — closing a
gap in under 15 minutes that would otherwise have forced the plan to guess at message-model
constants. Worth remembering when a first Investigator pass reports "source not found": check
whether it searched under the *install root*, not just `Scripts/`, before accepting the negative
finding.
