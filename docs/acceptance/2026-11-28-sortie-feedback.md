# Sortie feedback — 2026-11-28: BL-16 LV-2 breaks

**Branch flown:** `feature/bl16-lift-vector-law` (card: `2026-11-27-bl16-lv2-card.md`).
**Logs:** `docs/acceptance/logs-2026-11-28/lv2-aircraft_layer_debug.log`,
`lv2-aircraft_layer_flight_trace.log` (gitignored, local only).

## User's words (verbatim)

> *"LV-2 breaks — Fail. Break pulls (too much) cyclic back causing loss of speed and oscillation
> out of control."*

### Status

Captured; log analysis and `/explore` with the user follow before any fix (CLAUDE.md, "Flight
feedback is captured, then explored, then planned").

### Log reading (one break flown: left, ~213 km/h, ~190 m AGL, t = 57 s)

| t (s) | what happened |
|---|---|
| 57.3 → 59.7 | roll-in to 60° in ~2.4 s — fast, as asked; overshoots to **66°** |
| 59 → 61 | nose drops −2° → −8°, sink grows to −9 m/s; law answers with aft cyclic (+0.28) and collective ramping to **full up** (u_c = 1.0 at 61.1) |
| 61 → 64 | full collective at ~60° bank: nose rises −6° → **+19°**, AoA 46°, IAS 213 → 120 km/h. Cyclic goes **full forward** (out_pitch = a1100 = −1) from 63.3 and cannot stop it |
| 64 → 68 | pitch integrator winds to −1 under the forward saturation; once bank comes off, nose falls to **−52°** — the oscillation |
| 68 → 80 | recovery: sink −14 m/s, rotor 88 % (warning), h_ref 190 → 45 m — **>100 m lost and below the 50 m break floor** |

Inference: the vertical channel, not the pitch channel, starts it. Height-give lowered the
reference (w_ref ≈ −7 m/s) but the real sink (−9.8) was faster, so the law still demanded
+2 m/s² up on top of ~2.3 G of turn → full collective. At 200+ km/h full collective pitches the
nose up harder than full forward cyclic can hold. Rests on: `a1100` sign = aft positive (third
re-fly, `flight_control.lua` header).

## Second sortie, ~18:39 (flown on `feature/bl16-lift-vector-law` @ `aa9dc4e0`)

**Logs:** `docs/acceptance/logs-2026-11-28/lv3-aircraft_layer_debug.log`,
`lv3-aircraft_layer_flight_trace.log` (gitignored, local only).

User's words (verbatim):

> *"SAU — channels are not turned off when handing over control to Petrovich. expected: channels
> are turned off."*
> *"slow speed — pedal reacts too slowly -> loss of control, see log files."*

### SAU (BL-16 M4, `03b67fcb`, is in the flown commit)

- Sortie 2: take at 18:39:46 ("you have controls"); **no** `cockpit_switch` to device 10 after it.
  The only device-10 presses are mission-start's ON presses at 18:39:34.
- Sortie 1: take at 18:22:56; the H/K/T OFF presses (3007/3003/3011) went out at **18:23:35** —
  39 s late, ~6 s after "break turn left".
- So M4's trigger, or the sequence it starts, is delayed or blocked. Expected behaviour was already
  settled (explore-notes "M4 SAU explore (2026-11-28)"): a bug, not an open question.

### Slow speed ("speed five zero" at t = 23.6, ~162 km/h entry)

| t (s) | what happened |
|---|---|
| 24 → 40 | decel, nose +8…+15°; sideslip already 29° by t = 40 |
| 40 → 47 | nose yaws left (−1.3 → −4.9 °/s) while wanted yaw rate is +3…+7 °/s right; pedal output ramps only 0.11 → 0.65 |
| 47 → 50 | pedal output reaches full right (1.0) at t ≈ 50; the cockpit pedal arg 1103 **pins at −0.567** from t ≈ 49 |
| 48 → 58 | sideslip 65–73°, sideways ground speed 22 → 42 m/s, forward −16 m/s (backwards), bank +20…30° right, collective full up, rotor 80 % — out of control |
| 42 → 58 | λ falls only to 0.93 then **returns to 1.0**: it is computed from total ground speed, which the sideways slide keeps above 80 km/h |

Confound: SAU H/K/T were **on** for this flight (the M4 failure above), against U4 — the heading
channel acts on the pedals' hydraulics. The pedal result has to be re-flown with SAU off.

## Third sortie, ~19:03 — hand-flown hover transitions (pedal authority probe)

**Logs:** `docs/acceptance/logs-2026-11-28/hover-hand-flight_trace.log`, `hover-hand-debug.log`.

User's words (verbatim):

> *"Here's logs of me hand flying several transitions to/from hover. first few without SAU, with
> adjustable stops; then without SAU and without adjustable stops; last with SAU and with
> adjustable stops. I held full right pedal on several occasions. In cockpit I could see the pedals
> fully right, but the controls overlay showed maybe less than half right pedal. I do not know what
> causes that (possibly the trim or something) or how to affect that. I did not use the trim button
> until the last phase where I turned SAU on."*

Reading (phase times inferred from the trace, not marked in the log):

- With adjustable stops ON, the player's own full right pedal puts arg 1103 at **−0.569** and it
  pins there (12 runs, up to 11 s, mostly at hover / below 50 km/h, t ≈ 54–290 and 419–469). Left
  side tops out at **+0.247** (seen repeatedly in cruise).
- In the stops-OFF phase (t ≈ 300–400) the arg goes **past** that cap: −0.647, −0.676, −0.635
  (t = 341, 361, 368).
- Petrovich's own full-right write in sortie 2 landed at the same −0.567. **So the right-pedal cap
  is DCS's adjustable stops, applied to the player's hardware pedal and to our writes alike — not
  our write path.** The main loop's earlier reading (the ~0.32 learned write offset plus the ±1 write
  clamp eating our travel) was wrong; corrected here.
- Arg 1103 behaves as the *effective* pedal (what the controls overlay shows), not the cockpit pedal
  animation the user sees at full travel.
- The player at hover also sat at that cap for seconds at a time — hover in DCS's Mi-24 uses almost
  all the right pedal the stops allow. Petrovich has the same authority as the pilot; what he lacks
  is knowing where it ends: `pedal_limit_positive` is 1.0 since LV-3's U13, so the near-limit
  collective guard never sees the real ~0.57 cap.

### User's answers on the pedal cap (verbatim, 2026-11-28)

Questions: (1) stops off ≈ 300–400 s and full right held then? (2) what the pilot does when right
pedal hits the stop at low speed; (3) stops stay on for Petrovich?

> *"1 - about right. I did hold full right.*
> *2 - ease collective. That causes slight descent -> if there's no altitude to spare, then speeding
> up is the only option. left yaw can get out of control fast and then there's no more right pedal
> to do anything about it.*
> *3 - we can turn stops off if it helps*
>
> *Additionally, adjustable stops do have a controller knob for adjusting the stops. Not sure what
> it's effect is since I controlling a hover is difficult enough without trying to spin a knob with
> mouse -> I haven't tried. But Petrovich could try."*

So: stops off → right cap −0.676 (full right held), stops on → −0.569; about 19 % more right pedal
with stops off. At the cap: ease collective and accept a slight descent; with no height to spare,
gain speed. Act early — once the left yaw runs there is nothing left to stop it. The stops knob's
effect is unknown; worth a probe.

### Correction: SAU channel B is the ALTITUDE channel (user, verbatim, 2026-11-28)

> *"Ah, you are correct, B is altitude channel. In the image, adustable stops are the panel at top
> right corner. And there is a know to adjust it, but I'm not sure what it does"*

(The image: the pilot's AFCS console — an "ADJUSTABLE STOPS" panel top right with gauge, red OFF
button, a knob and a "P ←→ t" toggle; an "ON / ADJUST STOPS" toggle on the top strip; YAW / ROLL /
PITCH / ALT channel units below.) Prompted by the main loop noticing `SAU-B-SWITCH-PTR` is labelled
"Autopilot Altitude Control" (Cyrillic В = высота).

Consequences:
- The 2026-11-20 note "B - adjustable stops channel. Just keep it turned ON" (`explore-notes.md`,
  "SAU in mode 1") named the wrong unit. **Every sequence that presses `p_sau_b_channel_on` has been
  switching the altitude hold ON**: `seat-pilot.md` at mission start (3013 pressed at 18:22:34 and
  18:39:34 in sorties 1 and 2), `controls-to-petrovich.md` (M4) and `controls-to-player.md`.
- So in both Petrovich flights the altitude channel was (at least commanded) on while the law flew
  the collective — a further confound alongside H/K/T, unknown whether it engaged.
- The "stops off" phase of the hand-flown sortie was the real adjustable stops, not channel B.

### Pedal-stops probe and the stops decision (2026-11-28)

Probe flown twice (`aircraft-layer/research/2026-11-28-mi24p-pedal-stops.md`, "Probe flown"): only the
SPUU-52 power switch moves the right-pedal cap (on −0.566, off −0.678, flat 14–140 km/h); the knob,
OFF button and P/t switch do nothing measurable. User: *"OAT ~13 C, same mission as earlier hover
logs, to same OAT"*.

Options put to the user: (1) stops off below ~80 km/h, on above; (2) off for as long as Petrovich
flies, back on at hand-back; (3) always on. User, verbatim: *"2"*. Built: `controls-to-petrovich.md`
switches `p_spuu_power` off, `controls-to-player.md` switches it back on.

## Mode-2 fixes card (`2026-11-27-mode2-fixes-card.md`)

User's words (verbatim):

> *"'Speed 250' - OK. 'speed up' - OK. 'slow down' -> 'action file error' -- fix the action
> file."*
> *"recovery - PASS"*

`[[BL-B139]]` (recovery) PASS; `[[BL-B140]]` ("speed 250") PASS.

"Slow down" cause: the rule file (`config/rules/flight.lua`) was fine. Sequence in the speech
log: "speed 250" → "speed up" (overlay now reads the literal `MAX`) → "slow down". The gate
reads `flight_authority_state.ias_kmh` (known) and passed; the mode-2 action reads the
overlay's `held_speed`, which parsed `"MAX"` as `None`, and its `assert` fired — the engine
reports any action exception as "Action file error.". The gap was flagged in `step_speed`'s
own docstring. Fixed: `"MAX"` parses to the MAX sentinel (so slow down → 250), and the assert
is now an ordinary "unable, not ready".
