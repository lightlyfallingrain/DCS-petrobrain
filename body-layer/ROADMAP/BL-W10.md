# BL-W10 — Two items waiting on the user's own machines

- [x] **Two things waiting on the user's own machines, added 2026-09-19.** #status/done Neither blocks work.
  - ~~**The daily status-page launchd job**
    (`.claude/scripts/com.petrobrain.status-page.plist`), written but never installed.~~ **Closed
    2026-09-27 — the user rejected installing it, permanently** (`X-B24` in `todo/backlog.md`;
    `.claude/skills/status-page/SKILL.md` carries the reasoning). Regenerating the page is a manual
    `/status-page` run by design: the page is explicitly derived-not-authoritative, so a stale one
    is cosmetic, and that did not earn a background job on the user's machine. The plist stays in
    the repo as an unused template — do not offer to install it again. Found still listed here as
    an open item on 2026-10-01, four days after the decision.
  - ~~**The sortie.** Five separate entries clear on one flight — see the list below plus Stage 4b
    speech and the contact-report wording. Flight card:
    `docs/acceptance/2026-09-18-stage6-sortie.md`.~~ **Closed 2026-09-25 (user direction) without
    being flown**: all five blocks were answered piecemeal by later sorties. Detection ranges pass
    ("close enough for current stage"); voice, F10 scan vocabulary and attention/events were covered
    by other flights; contact separation moved to
    `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`. The card carries the per-block verdicts
    and is marked do-not-fly — it had gone stale (it still names `srs-adapter`) before it could be
    flown, which is why the 2026-09-25 cards were folded into one instead of batched the same way.

