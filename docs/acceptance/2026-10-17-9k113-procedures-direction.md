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
- **Four switches power the guidance unit** — five were named, then `L166V POWER` was dropped the
  same day (*"skip L166V POWER for now, it is not that important, everything works without it
  too."*), which also disposes of the one argument number still unmapped. The buildable sequence
  is `MISSILE POWER` (773) → `CPLR DISTR` (761, probable) → `Sight Power` (885) → ЩО `PWR` (955),
  three of them already written successfully in flight. **Not the recon table's eleven.** Three of the five are
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
| `CPLR DISTR` | **761, probable** | `ASP_17V` · `asp_commands.USR` (`WEAP-DISTR-POWER-OP-PTR`) | rejected, then reinstated by the user's own layout — see below. **Unverified** |
| `OPER/TEST1/TEST2` | **762, probable** | `ASP_17V` · `asp_commands.USR_check` (`WEAP-DISTR-CONTROL-OP-PTR`) | not in the five, but it is the switch he used to place `CPLR DISTR`, and it closes recon row 5 |
| `L166V POWER` | **unknown — DROPPED** | — | **Out of the sequence, user direction 2026-10-17:** *"skip L166V POWER for now, it is not that important, everything works without it too."* 870 was rejected; nothing replaced it and nothing needs to |

### Both guesses are withdrawn, 2026-10-17 (user corrections)

> *"870 is probably TEST LMAPS button, B3 on missile selector unit. PWR is B1. 761 is wrong, if it
> sits on ASP_17V."*

- **`761` was withdrawn, then the user's own layout brought it back. It is now the leading
  candidate.** Flagged here rather than quietly reinstated, because he rejected it earlier the
  same day.

  His location, 2026-10-17: *"CPLR DISTR is copilot switch. physically right above missile power.
  right of FDI and left of OPER/TEST1/TEST2."* Against the command surface:

  | pointer | arg | what it looks like |
  |---|---|---|
  | `WEAP-MISSILES-POWER-OP-PTR` | 773 | `MISSILE POWER` — **confirmed**, and he says `CPLR DISTR` is directly above it |
  | **`WEAP-DISTR-POWER-OP-PTR`** | **761** | distributor **power**, `-OP-` = operator |
  | `WEAP-DISTR-CONTROL-OP-PTR` | 762 | distributor **control/check** — fits `OPER/TEST1/TEST2`, immediately to its right |

  **The adjacency matches his description exactly**, including the switch to the right that he
  named. 762 also closes the recon table's row 5 (`OPER / CHECK`, device/arg previously
  unresolved).

  **His rejection was conditional — *"761 is wrong, if it sits on ASP_17V"* — and the condition
  does not hold the way it reads.** The device column is the **owning Lua device**, not the seat:
  today's probe wrote the *operator's* ЩО and ПК switches through `WEAP_SYS` and `I9K113` while
  the player sat in the **pilot's** seat. Device ownership has already been shown not to determine
  reachability. So a switch physically on the operator's right panel can legitimately be owned by
  the `ASP_17V` device — the ASP-17 computer is what a weapons *distributor* would report to.

  **This does not make it verified.** The pointer name and the physical layout agree, which is two
  independent signals rather than one, but both are still readings of a table. The read-probe below
  settles it in seconds and should still happen before either number is encoded.
- **The ЩО's `TEST LAMPS` button is `956`**, not `870` — `SHSCHO-CHECK-PTR` ·
  `Operator_CHECK_LAMPS_9C475` on `WEAP_SYS`, the same panel whose `PWR` B1 is `955`. The user's
  reading of what 870 *is* lands on a real button; the argument number for it is 956.
- **`870` is left unresolved rather than relabelled.** Its pointer is `L166V-SWITCH-PTR` and its
  command is `Command_CHECK_LAMPS`, on `I9K113` — a name disagreement inside one row, in a table
  that is positional. Two check-lamps commands on two panels is plausible; so is a stale pointer
  name. **Neither `L166V POWER` nor `CPLR DISTR` has a known argument**, and neither should be
  guessed at again from the table.

**How to settle 761: read, don't write.** One pass with the user throwing each switch by hand
while a probe logs changed arguments identifies it by observation — no clicking, no table
archaeology. One switch now, not two. Fold it into whatever flies next.

## 3a. Petrovich is the copilot, so the pilot's steps are not his to do

**User direction, 2026-10-17:** *"The quickstart guide includes steps that the pilot does, like the
ASP-17 switches. For now Petrovich is copilot only."*

This is the same boundary root `CLAUDE.md` already draws — the pilot owns flying, navigation and
weapon deployment — applied to the power-up checklist. **A switch on a pilot-side panel is out of scope whatever the checklist says.** The recon table's
`AUTO/MAN` (553) and PUVL weapon selector (523) drop out on that basis — both are the pilot's own
instruments, not merely owned by a pilot-ish device.

**`CPLR DISTR` is not one of them: the user placed it himself** — *"CPLR DISTR is copilot
switch"* — so the question of whether the sequence must wait on the pilot is **closed, and the
answer is no.** All five power-up switches are the operator's, and Petrovich can run the whole
sequence unaided.

**The lesson worth keeping is the test, not the row.** "Which device owns it" is not "which seat
reaches it" — today's probe wrote operator panels through `WEAP_SYS` and `I9K113` from the pilot's
seat. Scope by **where the switch physically is**, which is what the user can see and state.

## 3b. The warm-up is ~5 minutes, measured

**User direction, 2026-10-17:** *"The guindace unit warmup took about 5 minutes, I measured."*

Longer than both earlier figures — his own *"about 3-4 minutes"* in the same day's procedure text,
and the recon note's 210 s program timer read off the PDF. **The measurement supersedes both.**

It also sharpens a question already on the list: a five-minute silence after *"Observ on"* is a
long time for a crew member to say nothing. The zero-warm-up direction still stands for now
(*"ignore until effectors built. Prepare code for it, but use no warmup time"*), so this is a
number to carry, not to build against yet.

## 4. Open, for the explore pass before `BL-B80` is planned

1. **`X s` for gyro alignment** — the user left the number open. Recon says 10–15 s; nothing
   confirms it and nothing can read the completion.
2. **What Petrovich says during a 3–4 minute warm-up**, if real warm-up ever returns. The plan's
   §5 already flags that a 3-minute silence after *"Observ on"* would be wrong behaviour.
3. **Whether the attack-run ARMED trigger fires on the pilot's command word or on the guidance
   state** — *"any attack run start"* could be either.

## Addendum, 2026-10-26 — OBSERV and the cannon are mutually exclusive

Given during the `[[BL-B67]]` explore (`plans/bl-b67-atgm-run/explore-notes.md`), verbatim:

> *"One Mi-24P quirk to note down. OBSERV ON and the Hind's 30 mm cannon being selected as weapon
> (pilot weapon selector) are *mutually exclusive*. If cannon is selected, OBSERV will not turn
> on."*

So with the cannon selected on the pilot's weapon selector, an OBSERV ON write is refused by the
aircraft: the observed arg 886 stays off. Any OBSERV-on path (`[[BL-B66]]`, `[[BL-B80]]`,
`[[BL-B67]]`) has to expect that refusal.
