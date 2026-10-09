# BL-W9 — 2026-09-25 crew-behaviour sortie card

- [ ] **Everything merged 2026-09-24/25 that has not been heard in the air — one card,
  `docs/acceptance/2026-09-25-crew-behaviour-sortie.md`** #status/open (user direction, 2026-09-25: *"fold into
  single"*). Covers watch reporting (`9b16c3b`), scan-is-not-watch, cancel-everything, the
  range-crossing direction words, the subitizing cap at 5, glass-watched-first, the orange watched
  marker and the console-fit eyesight view, and BR-1 Stage 1. Two earlier cards were folded into it
  and are marked superseded in place: `2026-09-24-watch-reporting-sortie.md` (never flown, and
  **stale before it could be** — written while a commanded `scan` still conferred watched-ness, so
  its watch blocks would have tested the wrong thing) and
  `2026-09-25-brain-layer-stage1-sortie.md` (not stale, absorbed).

  **The reason this is one card rather than nine.** Most of what it checks came out of the
  eyes-and-voice sortie, which produced eight fixes rather than a pass. So the thing worth a flight
  is not "do these features exist" but "are the fixes right", and that is one continuous listening
  exercise: the card's block 1, whether commanded scans are still noisy, is the single item worth
  most.

  Two things it explicitly cannot judge, said on the card so no flight time is spent on them: with
  `StubDecider` behind the wire there is no intelligence to evaluate (only responsiveness,
  stand-by timing, and hearing a reply at all), and `follow <descriptor>` still cannot pick the
  right contact — the D10 validator wants the model's evidence to be a literal substring of the
  candidate's own description, which the structured-candidate revision fixes. Clears when the
  sortie is flown and its "Bring back" items are answered.

