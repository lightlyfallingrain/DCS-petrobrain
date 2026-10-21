# Explore notes — BL-B80, pointing the 9K113 sight

2026-10-22, main loop with the user. Evidence base:
`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md` ("Pointing probe runs
2–3"), plus the user direction recorded on `body-layer/ROADMAP/BL-B80.md` (the SUPERSEDED block).

## What is settled by measurement (2026-10-21)

- Channel: AI axis, `SetCommand(3061, deg/60)` azimuth and `SetCommand(3060, v)` elevation, on
  device 7. It is a position target and exact: `arg_874 = value × 0.44`;
  `arg_876 = v` for v ≥ 0 and `0.75 × v` for v < 0.
- Conditions: **DCS AI Petrovich on** (the overlay), and the target **re-sent every frame**.
  Otherwise the writes are inert and 874/876 read 0. When re-sending stops, he takes the sight
  back.
- With the wheel hidden in DCS settings, `ShowMenu` (device 30, cmd 3001) still toggles his AI,
  and one press reliably flips it (user: *"yes"*, *"yes"*).

## User direction (2026-10-21), verbatim

> *"DCS Petrovich AI overlay *must be on* when Petrobrain uses 9K113. We must ensure that in code.
> Turn AI overlay ON when with OBSERV ON and make sure it keeps ON, even if player closes it, open
> it again immediately. Turn overlay OFF with OBSERV OFF. Note that DCS AI may turn OBSERV OFF at
> too hard manouvres (or player can turn any switch at any time), so OBSERV state in code must
> come from OBSERV state in DCS."*

> *"Since we have to keep overlay open, I'd rather hide the wheel, it's possible in DCS settings.
> We need some other way."* So AI-on is detected from the pointing readback: with a non-zero
> target, 874/876 stuck at 0 means his AI is off. A centre target is offset 0.5°, because centre
> reads 0 either way.

## Answers 2026-10-22, verbatim

1. **Slew rate** — *"at least the ASP-17 moved at steady pace, not instantanously. If AI 9K113
   really moves instantatnously, mimick slew rate."* So the commanded position is rate-limited
   toward the target at the 9K113's own rates (`Devices_specs/9K113.lua`: 20°/s horizontal,
   10°/s vertical), every frame. The real sight then moves smoothly rather than in 1 Hz jumps.
2. **Who holds the sight** — *"always hold. The purpose with Petrobrain is to *replace* DCS
   Petrovich. Using the overlay is simply a workaround."* While OBSERV reads on, Petrobrain always
   holds the sight, idle included, and never releases it to ED's AI.
3. **ED Petrovich's side effects** — *"when AI has not been commanded to scan he does not. So
   OBSERV switch ON + AI overlay -> he does not automatically use 9K113 -> it's free for us to
   use, we just need to keep the overlay open. AI Petrovich sometimes speaks, I cannot turn it
   off. AI mostly speaks by text lines that I can ignore. Automatic OBERV OFF he announces aloud.
   Also incoming fire (kinda good for us, since we've had trouble detecting it)."* Nothing to
   suppress. Never command his scan. His spoken incoming-fire warnings are an accepted side effect.
4. **Report only once the sight is there** — *"yes. Using simulated sight to look at something
   the sight is not pointing at would be breach of no omniscience."* Petrovich's sight perception
   uses the **actual** position (readback), never the desired one. Nothing is perceived through
   the 9K113 along a bearing it has not reached.

## Gyro re-alignment, 2026-10-22, verbatim

> *"note that if anything sets OBSERV OFF (AI, player) turning it back ON causes the ~10s gyro
> alignment delay every time."*

After every observed OBSERV off→on transition, the sight is unusable for ~10 s, whoever caused it.
In that window: no sight perception, and the AI-off detector must not fire. Nothing in Petrobrain
should cycle OBSERV casually.

## Open, measured by the 2026-10-22 probe

- Latency from `ShowMenu` (AI back on) until the readback obeys. This sets the AI-off detection
  timeout and the re-press interval.

## Gap carried from BL-B66

Body-layer's sight mode follows the OBSERV *command*, but must follow the observed arg 886
(direction above). It belongs in this entry's first stage.
