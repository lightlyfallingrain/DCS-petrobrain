# Mi-24P AI pilot wheel: layout and overlay readback (screenshots, 2026-11-14)

**Source:** five in-game screenshots taken by the user on Windows, operator seat, stick parked,
ED's AI pilot flying. Originals are not in git: `win-mac-sync/from-windows/AI_flight_wheel/`
(`flight - radar  alt.png`, `flight - baro alt.png`, `combat.png`, `hover.png`,
`hover translate.png`). This note is the transcription; evidence tags follow
`docs/CONVENTIONS` usage (`[screenshot]` observed on the image, `[inference]` read from it).

**Closes** open question 4 of `2026-10-31-mi24p-park-controls-ai-pilot.md` ("read
`list_indication(10)` while parked, with the wheel open") for the *labels*: the wheel's four modes
and every option on each are now known. Whether a "release controls" option exists is also
answered: **none** — no mode offers one.

Feeds BL-16 mode 2 (parked: drive ED's AI through HELPER_AI wheel commands, plan row S0-P3b).

## 1. The four modes

`[screenshot]` The mode is shown twice: in a box under the compass overlay (bottom-left) and as
the inner-left wheel option. The inner-left option is the mode name itself, so pressing it is
presumably the mode cycle (`[inference]`).

| mode box | wheel inner-left | seen with |
|---|---|---|
| `FLT` | `FLT` | IAS 60 / 150, forward flight |
| `CBTM` | `CBTM` | IAS 150 |
| `HVR` | `HVR` | IAS 0 |
| `HVRT` | `HVRT` | IAS 0 (hover translate) |

## 2. Option layout per mode

Wheel positions: outer up / inner up / left / inner-left / centre / inner-right / right / inner
down / outer down. Inner-left is the mode name in every mode; inner-right is `HDG LOS` in every
mode. Centre is used only in FLT and HVR.

### FLT (flight)

| position | label |
|---|---|
| outer up | `ALTITUDE +` |
| inner up | `SPEED +` |
| left | `HDG LEFT` |
| inner-left | `FLT` |
| centre | `ALT REF RAD` / `ALT REF BARO` (toggle; shows current reference) |
| inner-right | `HDG LOS` |
| right | `HDG RIGHT` |
| inner down | `SPEED -` |
| outer down | `ALTITUDE -` |

### CBTM (combat)

| position | label |
|---|---|
| outer up | `ALIGN FOR LAUNCH` |
| inner up | `ALIGN TO 9K113` |
| left | `BREAK LEFT` |
| inner-left | `CBTM` |
| centre | (none) |
| inner-right | `HDG LOS` |
| right | `BREAK RIGHT` |
| outer down | `BREAK 180` |

`[inference]` These are the keybindable HELPER_AI commands of the 2026-10-31 recon §2 by another
name: `ShootIn_EXT` "ATGM launch align" = `ALIGN FOR LAUNCH`, `LineUp_EXT` "Turn to sight heading"
= `ALIGN TO 9K113`, `UTurn_EXT` "Evasion turn (180 degrees)" = `BREAK 180`; voice lines
`Break_Left/Right`, `t180`, `Aligning` match.

### HVR (hover)

Same layout as FLT with the mode label `HVR`: `ALTITUDE ±`, `SPEED ±`, `HDG LEFT/RIGHT`,
`ALT REF RAD`, `HDG LOS`.

### HVRT (hover translate)

| position | label |
|---|---|
| outer up | `HOVER FWD` |
| inner up | `HOVER +2m` |
| left | `HOVER LEFT` |
| inner-left | `HVRT` |
| centre | (none) |
| inner-right | `HDG LOS` |
| right | `HOVER RIGHT` |
| inner down | `HOVER -2m` |
| outer down | `HOVER BACK` |

`[inference]` `HOVER ±2m` is the `alt_change_step = 2` constant of `HelperAI.lua:13-23`: the
altitude tap step is **2 m**, which fixes the unit the 2026-10-31 recon §7 could not. Voice lines
`Move_Back/Forward`, `Slide_Left/Right`, `Coming_Up/Down` match this mode.

## 3. Overlay readback: the held values are on screen as text

`[screenshot]` Top of the compass overlay, every mode:

| box | caption | values seen |
|---|---|---|
| IAS | `IAS` | `60`, `150`, `0` |
| heading | (none, above compass) | `71` |
| ALT | `ALT` | `196 R`, `948 B` |
| mode | (bottom-left) | `FLT`, `CBTM`, `HVR`, `HVRT` |

- `[inference]` These are the `speed_text`, `course_text`, `alt_text` + `alt_add_text` and
  `mode_text` holders of `HelperAI_page_common.lua` (recon §7), so `list_indication(6)` should
  return exactly these strings while the AI flies. The `R` / `B` suffix is `alt_add_text`, the
  altitude reference. Still unverified: whether the texts are filled when the overlay is hidden.
- `[screenshot]` `196 R` was shown with `ALT REF RAD` on the wheel and `948 B` with `ALT REF
  BARO`, consistent with `baro_alt_threshold = 700` switching the reference (196 < 700 < 948),
  though the wheel also carries an explicit toggle, so the threshold may only pick the default.
- `[screenshot]` The IAS and ALT boxes are white in all five shots; the recon's yellow "being
  changed" variant was not captured.

## 4. What this means for BL-16 mode 2

1. **Commanding ED's AI = pressing wheel options.** All of them are nudges or fixed manoeuvres;
   there is no numeric entry and no "release controls", as recon §7 inferred. A spoken
   `turn heading 3 1 5` becomes a FLT-mode `HDG LEFT/RIGHT` press-and-hold loop closed on the
   heading box; `hold 200 m radar` becomes `ALT REF RAD` plus `ALTITUDE ±`; `speed 2 2 0`
   becomes `SPEED ±` closed on the IAS box.
2. **Mode selection matters before any nudge**: FLT/HVR share the hold vocabulary, HVRT is
   2 m / translate steps, CBTM is the 9K113 alignment set. The nudge loop has to read `mode_text`
   first and cycle modes if needed.
3. **CBTM `ALIGN TO 9K113` / `ALIGN FOR LAUNCH` are ED's versions of BL-B67's launch alignment.**
   Whether to reuse them in parked mode or keep Petrobrain's own alignment is a plan decision,
   not settled here.
4. **Open for a probe:** which HELPER_AI `Up/Down/Left/Right` presses reach the outer versus
   inner ring (two presses in one direction? long press?), the tap/hold step size per option in
   real units, and `list_indication(6)` content with the overlay hidden.
