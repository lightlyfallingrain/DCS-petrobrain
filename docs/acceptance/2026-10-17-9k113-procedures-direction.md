# 2026-10-17 — the correct 9K113 procedures, from the user

Captured verbatim before any planning pass, per root `CLAUDE.md`'s "Flight feedback is captured,
then explored, then planned". **No implementation has started** — user direction, same message:
*"OK to split BL-B66, do not start working on it yet (weekly token limit nearing)."*

This supersedes `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`'s 11-switch table
where the two disagree. That table was read off a PDF; this is the pilot's.

## 1. The direction, in the user's own words

> *"First of all, I much prefer the player axis approach, so this is good in that sense.*
>
> *OK to split BL-B66, do not start working on it yet (weekly token limit nearing). But I need to
> specify the correct processes:*
>
> *# Guidance unit power up*
>
> *switch names below are toolpit names for the switch*
>
> *- MISSILE POWER switch ON*
> *- CPLR DISTR switch ON*
> *- Sight Power switch ON*
> *- (tooltip text is in Russian, "sho" power B1) ON. ("sho" the cyrillic soft s that looks like W
> and O) (this is the missile pylon selector panel and it's power switch)*
> *- L166V POWER ON*
>
> *When Sight Power switch ON is set, it will take about 3-4 minutes before the sight can be used.
> This is the warm up period.*
>
> *# OBSERV ON*
>
> *Precondition: Sight Power must be ON and warmup elapsed, i.e. lamp READNS. is ON.*
>
> *- OBSERVE switch ON*
> *- X s wait for gyro alingment*
> *- can slew sight with player axis*
>
> *# OBSERV OFF*
>
> *- OBSERVE switch OFF*
> *-> sight resets to boresight, protective doors close, gyros safe for manouvring -- this all
> happens automatically by DCS*
>
> *# WEAPON SAFETY SWITCHES BAR*
>
> *- set ARMED on*
>   *- pilot command*
>   *- any attack run start*
> *- set SAFE on*
>   *- pilot command"*

## 2. What this settles

- **The player axis is the preferred channel on its own merits**, not merely by elimination —
  *"I much prefer the player axis approach."* So the 2026-10-17 probe result and the user's own
  preference agree, and `BL-B63` returning as a dependency is a cost he is accepting knowingly.
- **`BL-B66` splits**, approved. The switch/`OBSERV` half stays; the slew loop becomes `BL-B80`.
- **Five switches power the guidance unit, not the recon table's eleven.** Three of the five are
  not in that table's warm-up gate at all (`CPLR DISTR`, `L166V POWER`, and the ordering), and two
  of the table's steps (`AUTO/MAN` on the ASP-17, the PUVL weapon selector) do not appear here.
- **It is the `Sight Power` switch that starts the 3–4 minute warm-up**, not the ЩО `PWR` switch.
  The recon note attributes the 210 s program timer to ЩО `PWR` (arg 955); the pilot attributes the
  warm-up to `Sight Power`. **His reading wins** and the note's attribution is flagged, not edited.
- **Warm-up completion is observable only as the `READNS.` lamp**, which today's probe confirmed is
  **not readable from Lua** — `list_indication(8)` empty, `list_indication(0)` static. So readiness
  must be a self-run timer, and the zero-warm-up direction (*"ignore until effectors built. Prepare
  code for it, but use no warmup time"*) is what stands for now.
- **`OBSERV OFF` needs no sequence.** DCS boresights the sight, closes the doors and safes the
  gyros by itself. One write, nothing to model.
- **The safety bar is pilot-commanded, plus one automatic trigger**: ARMED on any attack-run start.
  SAFE is pilot-commanded only — nothing arms or safes itself on a timer or on egress.

## 3. Switch → argument, as far as the repo can map it

**Unverified rows are unverified. Do not encode them without a probe.** Arg numbers are positional.

| user's name | arg | device · command | confidence |
|---|---|---|---|
| `MISSILE POWER` | **773** | `WEAP_SYS` · `Operator_URS_POWER` | matches the recon table's row 6 (`ПИТАНИЕ УРС`) |
| `Sight Power` | **885** | `I9K113` · `Command_POWER_PN` (3001) | **written successfully today**; recon calls it `GUID.UNIT POWER` |
| ЩО `PWR` B1 | **955** | `WEAP_SYS` · `Operator_POWER_SHO_SWITCHER` (3030) | **written successfully today** |
| `OBSERVE` | **886** | `I9K113` · `Command_NABL` (3002) | **written successfully today** |
| weapon safety bar | **673** | `WEAP_SYS` · `Operator_SWITCHER_SAFE_WEAP` (3020) | **written successfully today** |
| `CPLR DISTR` | 761? | `ASP_17V` · `asp_commands.USR` (`WEAP-DISTR-POWER-OP-PTR`) | **guess from a name match only.** Needs confirming |
| `L166V POWER` | 870? | `I9K113` · listed as `Command_CHECK_LAMPS` (`L166V-SWITCH-PTR`) | **guess, and the command name disagrees with the pointer name.** Needs confirming |

The two guesses are the only new probe work this direction creates, and they are cheap — a read of
each argument while the user throws that switch by hand settles both. Worth folding into whatever
flies next rather than its own sortie.

## 4. Open, for the explore pass before `BL-B80` is planned

1. **`X s` for gyro alignment** — the user left the number open. Recon says 10–15 s; nothing
   confirms it and nothing can read the completion.
2. **What Petrovich says during a 3–4 minute warm-up**, if real warm-up ever returns. The plan's
   §5 already flags that a 3-minute silence after *"Observ on"* would be wrong behaviour.
3. **Whether the attack-run ARMED trigger fires on the pilot's command word or on the guidance
   state** — *"any attack run start"* could be either.
