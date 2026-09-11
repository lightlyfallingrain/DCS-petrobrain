---
name: reference-mi24p-quickstart-ru-manual
description: The real RU Mi-24P Quick Start PDF is a canonical systems-manual source for 9K113/ASP-17/crew-procedure questions — reach for it before forum/code digging.
metadata:
  type: reference
---

`docs/concept/mi-24_info/DCS Mi-24P QuickStart RU.pdf` (167 pages, Russian,
poppler installed so `Read` with `pages:"a-b"` works, max 20 pages/call) is
the **real cockpit/systems manual** (distinct from the thinner English guide
already consulted previously) and is a strong, documented-grade source for
how real Mi-24P systems work — panel-by-panel descriptions with figures,
not folklore. Confirmed reliable in session 2026-09-11: it correctly
described the 9K113/ПН as manual-optical-search-only with a rate-control
(not positional) operator joystick, which matched a live DCS probe finding
exactly (see [[project_bl6_command_feasibility]] and
`aircraft-layer/research/2026-09-11-quickstart-ru-9k113-manual.md`).

**Scope/limits found this session:**
- It documents the *real aircraft's* systems in exhaustive panel/switch
  detail (§4.x cockpit panels, §5.x weapon-employment procedures with
  numbered steps + screenshots + keybinds).
- It does **not** document DCS's own AI-wheel/AI-command abstractions
  (`SRCH FWD/BRST/PILOT LOS/9K113 LOS`, `DesignateAttackPoint`, etc.) — those
  are DCS/ED inventions layered over the real system, with no real-hardware
  analog, so don't expect this manual to explain AI-command misbehavior.
  Confirming those still requires live probes or DCS's own AI Lua
  (`HelperAI.lua`).
- Chapter 6 "КАК ИГРАТЬ" (p.130+) is generic DCS World UI/campaign
  boilerplate, not an Mi-24P/Petrovich reference — don't expect AI-command
  detail there.

**Reuse pattern:** when a BL-6/Petrovich or systems question has a
plausible real-world analog (sight optics, weapon panels, engagement
sequencing), check this PDF's table of contents (already read once, pages
1-10) before falling back to forum posts or DCS Lua reverse-engineering —
it's faster and stronger evidence when it covers the topic.
