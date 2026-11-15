# 2026-11-15 — Testing-debt cleanup: `#needs-flight` items accepted without a sortie

**User direction, 2026-11-15, verbatim:**

> *"We have quite many old test flights pending. Let's do this. For all the items that are waiting
> on a test flight, check if there is a probe that needs running. If there's no probe waiting and
> the item has been merged earlier than this week, set item as closed and accepted. If I find
> problems in my flights, I'll bring them up separately, and we'll work on them. I need to get the
> in progress work cleaned even if it means not testing everything properly. It's an acceptable
> tradeoff at this point. Best behaviour observations happen when I fly actual missions and
> cleaning the testing debt gets me flying missions."*

Rule applied: an entry keeps `#needs-flight` only if (a) a probe script is still waiting to be
flown, or (b) it merged this week (2026-11-09 or later). Everything else is accepted as merged.
"Accepted" means the code is on `main` and trusted until mission flying says otherwise; a defect
seen later is filed as a **new** entry, not a reopening.

## Kept open (probe waiting)

| entry | probe |
|---|---|
| [[BL-16]] | `Export.probe-ai-pilot-wheel.lua` (P0), card `docs/acceptance/2026-11-15-bl16-batch-a-card.html` |
| [[BL-B67]] | Stage 0 probe sortie (`Export.probe-weapons.lua`, damage-events probe Hook), card `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` |
| [[BL-B80]] | Flight A calibration probe (`Export.probe-9k113-calibration.lua`, `Export.probe-9k113-hud-elevation-limits.lua`); `ASP17_FIELD_EL_HALF_DEG`/`ASP17_FIELD_MARGIN_DEG` still guesses |

## Kept open (merged this week)

[[BL-B108]] (2026-11-09), [[BL-B110]], [[BL-B111]], [[BL-B106]], [[BL-B112]], [[BR-2]] (sortie
card 2026-11-13).

## Accepted, tag removed

Header status unchanged (already `#status/done`, or open for a reason other than the flight):
AA-2, AA-5, AA-6, AA-B6, AA-B7, AC-B7, AC-B8, BL-8, BL-11, BL-12, BL-14, BL-15 (Stage 2 still
deferred, so `[~]` stays), BL-B47, BL-B55, BL-B59, BL-B64, BL-B70, BL-B71, BL-B72, BL-B73,
BL-B76, BL-B81, BL-B82, BL-B89, BL-B90, BL-B96, BL-B97, BL-B98, BL-B99, BL-B100, BL-B102,
BL-B104, BL-W6, BL-W35, BL-W36, BL-W40, BR-1.1, BR-1.2, BR-B1, X-B31.

Flipped to `[x] #status/done`, because the flight was the only open part:
[[BL-W12]] (group cohesion redesign, merged 2026-10-01), [[BL-W41]] (voice latency
instrumentation, merged 2026-10-20), [[BL-B85]] (sight stall cooldown; `SIGHT_STALL_COOLDOWN_S`
stays at 132 s until mission flying says otherwise), [[BL-B68]] (belief reset on mission restart;
its sortie flew on BL-15 2026-10-20).

In each accepted entry the tag is rewritten as plain `needs-flight` so that
`grep -rl '#needs-flight'` lists only the live debt, and a dated "Accepted 2026-11-15" paragraph
is appended.

## Not touched

AC-8 (the tag is deliberately withheld there, prose only), X-T26 (says it has no tag), X-T7
(prose about other entries). The X-T27 priority table rows for BL-B64 and BL-14/BL-B70 now say
"accepted 2026-11-15 without sortie".
