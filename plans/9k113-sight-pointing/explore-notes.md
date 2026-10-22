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

## How the sight stabilises, 2026-10-22, verbatim

> *"the sight does not hold a fixed ground point. I may have expressed it imprecisely. It holds the
> last set pointing direction in world coordinate angles, within gimbal limits of course. So in
> practice, the gyro stabilized sight operates in world coordinate axis and keeps it direction. The
> gimbal limits from the airframe coordinate axis of course limit the sight position. From this
> follows: sight does not track a point on ground, but it keeps its world axis relative angles
> steady when the airframe axis rotates. When aircraft moves, so does the point-on-ground where the
> sight is looking. The slew axis commands, I'm not perfectly sure, but I think they are relative to
> current sight gyro stabilised angles."*

Open: whether the AI axis (3061/3060) commands airframe (gimbal) angles or world-stabilised
angles. Every exact-match measurement so far was in steady flight, where the two agree. Body-layer
sends `look_azimuth_deg` as nose-relative; if the axis is world-relative, that needs a heading
conversion. The latency probe's TURN 2 settles it (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`).

## Probe runs 1–3 overturn the channel model (2026-10-22)

Full record: `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` on `probe/9k113-ai-latency`.

- With the overlay **off**, the AI axis re-asserted per frame **does** move the sight, but as a
  **rate** command (deadzone ~1.5°, rate ≈ (|cmd| − 1.5°) °/s), into the gyro-stabilised world
  direction. Not a position.
- 874/876 echo the demand, in every mode tried. They are not a head readback.
- 565/566 (az) and 555/556 (elev) are the ASP-17 mark position: the actual line of sight, clipped
  at the ASP-17 field edge (≈ ±6°, ~0.028 per degree for 565).
- No run has shown a true position command with the overlay on either; run 4 tests that.

This invalidates the plan's premise (position target, overlay kept on, 874 as readback).

Pilot, verbatim: real 9K113 slew is rate with *"small deadzone"*; *"copilot knows by the
indicators in the sight view itself"* (`docs/concept/mi-24_info/9k113-reticle-narrow-x10.png`);
*"The pilot does not outside of ASP-17 crosshair, except that what the copilot *says*."*

Direction, verbatim:

> *"If there's no way to know where it is pointing, we may have to separate within HUD and outside
> HUD pointing logic.*
> *- outside could just be the current simulation plus slew time*
> *- within HUD it's important to get the ASP-17 show *where* the target is so that pilot can line
> up. Important for attack runs in general and critical for ATGM guidance."*

## Open, measured by the 2026-10-22 probe

- Latency from `ShowMenu` (AI back on) until the readback obeys. This sets the AI-off detection
  timeout and the re-press interval.

## Gap carried from BL-B66

Body-layer's sight mode follows the OBSERV *command*, but must follow the observed arg 886
(direction above). It belongs in this entry's first stage.

## Explore 2026-10-22 (after probe runs 1–8): pointing with an unreliable AI axis

Evidence going in: `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` and
`aircraft-layer/research/2026-10-22-9k113-ai-axis-obedience-prior-art.md` on `probe/9k113-ai-latency`.
The AI axis is a rate command that DCS obeys intermittently (ignored 3–100+ s, invisibly); the
ASP-17 mark (565/566, 555/556) is the only readback, inside ±~4.3°.

**Q1 — is Petrovich allowed to "see" through Petrobrain's simulated sight where the DCS sight cannot
be verified?** Pilot, verbatim:

> *"what Petrovich could plausibly see with a sight that works as it should. -> Yes. Ideally we
> could drive the CDS sight and get back it's readings, but since we can't, a Petrobrain simulation
> of that beats a non-functional sight. That means we do have to build code for the angular limits
> and a max slew rate. Those are the important things that keep it from being an instant point
> anywhere miracle optic."*

So **Petrobrain's simulated sight is Petrovich's sight**: perception comes from it, constrained by
gimbal limits and maximum slew rate. This revises the 2026-10-22 answer 4 above ("perception uses
the actual position (readback), never the desired one") — the rule is now plausibility of a working
sight, not agreement with DCS's sight object.

**Q2 — when must the ASP-17 mark sit on the target?** *"as soon as target is within HUD. Exact."*

**Q3 — mark won't move while lined up?** *"ATGM run is completely dependent on the sight
moving/being on target. Plan B is DCS AI guindance, but I'd rather not."*

**On Q2 and Q3 together**, verbatim:

> *"We need to point the DCS 9K113 where we simulate it being, but accept that it may or may not
> work. Within HUD limits, any cheats that get the 9K113 where we need it are allowed, since this
> is a dcs-commanding-problem not us trying to break the no-omniscience rule."*

So the DCS sight is a **best-effort slave** to the simulated one everywhere, and inside the HUD
(where it shows to the pilot and matters for attack runs and ATGM) any DCS-side trick that gets it
onto the simulated direction is allowed — closed loop on the mark, recovery actions, anything.

Pilot's idea for the gate, verbatim: *"Would not stopping sight movement help? Keep small movement
all the time, small circle on target unit?"* — to be tested in probe run 9.

### ATGM accuracy (2026-10-22, after probe run 9 showed dither keeps the AI axis obeyed)

Pilot, verbatim: *"for ATGM guidance we need to hit a target like BTR-2 at about 3-4 km. That gives
angular freedom of X deg. It can wobble a bit first but should focus on target unit body as the
missile get closer (maybe <1km)."*

X, for a BTR-80-sized front (2.9 m wide, 2.4 m high): the miss distance is the sight's angular error
× the **aircraft-to-target** range, so at launch range 3–4 km the half-width is **0.021–0.028°**
and the half-height 0.017–0.023°. The final ~1 km of missile flight is ~2.5 s.

Dither wobble on the mark ≈ (command amplitude / 3) °/s ÷ (2π f): run 9's 1.5° at 1 Hz → ±0.08°
(±5 m at 3.5 km) — fine for search and lining up, too coarse for the terminal phase. The same 1.5°
at 4 Hz → ±0.02°; 0.6° at 4 Hz → ±0.008°. So **dither frequency, not amplitude, is the lever**
(amplitude must stay above the 0.18° deadzone). Unmeasured: whether faster dither keeps the axis
obeyed as 1 Hz did.

### Decisions after probe run 10 (2026-10-22), verbatim

> *"If there's no reason to use big wobble, use tiny all the time"*
> *"close probe phase"*
> *"take in the guidance unit ready light while building this all"*

- Dither: the smallest/fastest dither that kept the axis obeyed in run 10 (0.6° at 8 Hz; mark
  wobble ~0.03° p-p including loop motion) is used **always**, not only near the target — run 10
  gave no reason for a larger one.
- The probe phase is closed; `probe/9k113-ai-latency` merges to `main` as research.
- BL-B80's rebuild includes the guidance-unit **READY lamp, arg 960** (`SCHO_9K113_READY`, very
  likely the ЩО `READY` lamp BL-B66 could not read via `list_indication`) as the warm-up-done
  signal, alongside Л5 (arg 898) as the gyro-alignment-done signal. 960 is unconfirmed on a cold
  start (expected 0 → 1 about 3–5 min after `PWR`); every air start shows it lit from t ≈ 0.

### Pilot's hypothesis for why dither works (2026-10-22), verbatim

> *"joystick axis value that does not change, and if something else then overrides that, it can be
> overwritten, and because the joystick axis value doesn't change, it doesn't re-override that. So
> that may be behind this behavior, because it's in our case constant 40 constant rate movement.
> But then because we introduced that circling behavior or other small deviations in the movement,
> then that overrides the axis value at every change. I think this is a general rule for all
> joystick axis behavior in DCS."*

Fits the record: run 8 (one constant value for 100 s) was dead throughout; run 7 (joystick axes
bound — a jittering physical axis is exactly such an "other writer") was worse than 7b (unbound);
dither changes the value every frame and was obeyed 29/29. **Consequence if true:** the wobble does
not need to be physical — a per-frame change far below the 0.003-unit deadzone (e.g. ±1e-5 on the
value) would keep the axis obeyed with **no visible wobble**, which removes the dither error from the
ATGM precision budget. Testable in probe run 11.

### Plan v2 open questions answered (2026-10-22), verbatim

1. Terminal ATGM aim: *"actual position. This same question was discussed and explored earlier,
   search for it. Crux: Petrovich can \*see\* the target and point sight at it even if belief about
   world location is incorrect."* (earlier: `docs/acceptance/2026-10-15-9k113-sight-direction.md`
   §2–§3).
2. "Guidance unit ready" on air starts: *"only on change"*.
3. Alignment / stall speech: *"nothing new"*.
