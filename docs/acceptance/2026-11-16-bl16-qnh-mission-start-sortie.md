# BL-B118 (operator altimeter QNH sync at mission start): acceptance sorties (2026-11-16)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/LreisCNWCt6k6P4Nph9aJa
**Card source:** `docs/acceptance/2026-11-16-bl16-qnh-mission-start-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

What is under test, verbatim from `plans/bl16-qnh-mission-start/dod.md`'s Acceptance Testing
Plan: whether the operator (copilot) altimeter's pressure window actually settles on the
mission's QNH shortly after mission start, on both a ground start and an air start; whether the
body-layer log shows the QNH/atmosphere-type/target it set; whether "Request Aircraft Control"
no longer produces the wild barometric target the takeover-fix probes measured; and, if the knob
does not respond (the plan's own named risk — unverified whether device 42 honours a write from
the pilot seat), whether Petrovich says the "unable" line once and the log says why.

Two short sorties, per the pilot's own "both ground start and air start" requirement (U2). One
flight each is enough — this is the mechanism's own first live run, not a regression sweep.

**Requires a redeploy on the Windows box**: `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua`
now reads two more mission fields. Copy it to `Saved Games\DCS\Scripts\Hooks\
petrobrain-mission-start-hook.lua` and **restart DCS itself** (not just the mission — this Hook
loads once into the GUI Lua state at DCS application startup). `Export.lua`'s own version is
unchanged by this feature (no edit to it or to `Petrobrain/` in this branch) — only the Hook
script needs redeploying. **There is no staleness warning for a stale Hook script** (unlike
`Export.lua`, which the collector checks) — if the sync never arms and nothing is logged, redeploy
is the first thing to check, not a code defect.

Results go to `body-layer/ROADMAP/BL-B118.md`, not into the card.
