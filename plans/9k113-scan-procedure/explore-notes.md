# Explore notes: BL-B89, the 9K113 scanning procedure

2026-10-25, main loop with the user. `[[BL-B89]]`'s own entry asked for *"a plan and a mock first"*.
Queued by the user to start after `[[BL-B96]]` merges.

## The mock shown

One forward-sector cycle, built from BL-B89's procedure. The numbers were placeholders, labelled
as the main loop's:

```
1  wide S-scan  near→mid  (≈0.5–4 km)   3 rows across the sector    ~6 s   close threats/targets
2  wide S-scan  far       (≈4–8 km)     2 rows                      ~4 s   points of interest
3  narrow  unidentified units inside ID range, by priority   ~2 s each, skip if too far/blocked
4  narrow  unclassified units inside class range             same rule
5  narrow  far sweep for detection                           ~6 s
6  naked eye  quick all-round sweep                          ~3 s
   → back to 1    (known unit that hasn't crossed a range threshold: quick position check only)
```

## Answers, verbatim

- **Near limit.** *"wide scan near -> 0.5 km is too close. naked eye can detect, no 9K113 needed.
  more like 1.5 km - 4 km."*
- **The rest of the cycle stands.** *"otherwise good pattern"*. Rows and time per pass were not
  corrected, so the placeholders stand as starting values. They should be tunable.
- **Sector widths:**

  > *"width -> o'clock sector or two, 30-60 degrees. could well be alternating sequence -30 to +10
  > deg and -10 to +30 deg. That would be the normal scan ahead sweep. left scan -60 to 0 deg.
  > right scan 0 to +60 deg. one o'clock sector such scan is comanded."*

  So, relative to the nose:

  | scan | sector |
  |---|---|
  | ahead | alternating −30…+10° and −10…+30° |
  | left | −60…0° |
  | right | 0…+60° |
  | a commanded o'clock | that one o'clock sector |
- **The naked-eye sweep is a pause in the sight scan, and it is required.** *"naked-eye sweep -> the
  sight is like a periscope that the operator puts his eye to. So naked eye sweep is a pause to
  9K113 sweeping. Still, needed so that no surprise attack creeps up on us."*
- **Pointing at a known place: a second stage, but in this item.** *"sector fisrt, pointing as
  second stage, but do that too"*.
- **`[[BL-B86]]` is folded in.** *"yes"*. Above ~4 km AGL the idle cycle must not go fully idle.
- **Code, not a script.** *"this is quite complex still, keep in code"*. It is built in code, shaped
  per root `CLAUDE.md`, "Behaviour as actions and params" (`[[BL-B95]]` stays deferred).

## Operating altitude, 2026-10-25 (verbatim)

> *"note that 4km AGL it practically never. Helicoters do not fly that high. Assume normal
> operation at 50 - 800 m AGL, with 1000 - 2000 m AGL being possible but rare. 2000+ m AGL do not
> even consider."*

So the design and the tests target 50–800 m AGL, with 1000–2000 m as a rare case that must still
work. Above 2000 m is out of scope. `[[BL-B86]]` (the cycle goes idle above ~3.6–4 km AGL) is folded
in only as far as it falls out of the design naturally: no special handling and no tests above
2000 m.

**`[[BL-B86]]` declined, 2026-10-25.** *"if B86's only thing is the high alt scan then reject it."*
It was, so it is declined, not folded in. One residue carries into this plan: the altitude at which
a band empties moves with pitch, and nose-up lowers it. Test the scan at a nose-up attitude within
50–800 m AGL.

## Stage 2 — pointing at a known place, 2026-10-25

Shown a mock exchange (*"Sight two o'clock, three kilometres."* → *"Two o'clock."* → wide look →
*"Contact, two o'clock, three k."* → narrow → *"Two tanks."*, or *"Nothing at two o'clock."*) and
asked five questions. Answers, verbatim:

1. **Words.** *""Sight", "look [at]", "what is [at]""*
2. **No distance given.** *"near to far"*
3. **How long, and when nothing is there.** *"two proper sweeps of the area -> if nothing, say
   "<where> clear" and continue what the previous action was"*
4. **Something found.** *"report, then go back to scanning. target count makes no difference, report
   as usual"*
5. **During an attack run.** *"during attack run, keep the sight on the attack runs target. If
   OBSERV OFF, then eyesight/binoculars on the target."*

Already settled earlier (2026-10-20): the place is an o'clock or a compass bearing, with an optional
distance; landmarks, waypoints and player marks come later.

## Stage 2 vocabulary, mid-task clarifications, 2026-10-25 (architect pass, same day)

Five follow-up messages arrived from the user while this plan was being written, each narrowing the
vocabulary/command design below. Recorded verbatim, in the order they arrived.

**1. The "look" clash:**

> *"Let's reserve "scan <direction>" for scanning. "Look" for 9K113 scan."*

**2. "look left/right" named directly:**

> *""look left/righ" -> the 9K113 left/right scan that Stage 1 implemented"*

**3. The scan/look split, settled:**

> *""scan" can use 9K113, free to decide with logic the used optic*
> *"look" and it's synomyns request an explicit 9K113 scan of <where>"*

**4. OBSERV-off handling for an explicit "look", first answer:**

> *"when observ off -> "Need observ, confirm" -> player:"yes" -> observ on -> use sight when observ
> ready (lamp lit)"*

**5. OBSERV-off handling, refined — no new confirm vocabulary:**

> *"use the exiting comfirm -behaviour logic and words.*
> *"no" -> cancel look*
> *"yes"/"confirm"/"observ on" -> observ on, ..."*

Read together: `scan <where>` is unchanged (Petrovich's own logic still picks eyes/binoculars/9K113
for it, exactly as today). `look <where>` and its synonyms (`sight <where>`, `what is [at] <where>`)
are a new, explicit request for the 9K113 specifically. `<where>` for `look` covers both a sector
(left/right/ahead — Stage 1's own commanded-sector shape) and a point (o'clock/compass, optional
distance — Stage 2's pointing). Whether a commanded o'clock/compass under `look` is read as a 30°
sector or a point swept near-to-far turned out not to be a real fork — see "`look <o'clock>`
collapses" below. The OBSERV-off path reuses the existing confirm-band mechanism and its existing
accepted words (`confirm`/`yes`/`okay`/... already affirm; `no`/`negative`/... already negative) with
one narrow, explicitly scoped exception: the spoken command `"observ on"` itself, if it resolves to
the real `observ_on` token while this specific confirmation is pending, also counts as the "yes" —
see "OBSERV-off confirm flow" below for why `classify_yes_no`'s general rule 2 (a resolved command
token is never an answer) would otherwise swallow it.

**6. Supersession by a later command, while a look is pending or running:**

> *"new command replaces if it is look or scan command. Effector sequences and commands to trigger
> tham can fire."*

So: a new `look …`/`scan …` command replaces a pending-on-OBSERV or already-running look outright.
A command that triggers an effector sequence (`observ_on`/`observ_off`/`weapons_armed`/
`weapons_safe`) runs normally rather than being blocked by a pending look — it does not get a
special "cancel the look first" rule of its own, because `observ_off` already tears the look down
as a side effect of the existing `[[BL-B98]]` rule (aim resets to boresight, `home_phase` leaves
`SIGHTING`), not because this command class was taught to cancel it. See "Supersession" in
`plan-stage2.md` for the full command-class table and the one case flagged there (`silence`).

### Stage 2 plan decisions, 2026-10-25 (verbatim)

Answering `plan-stage2.md`'s "Decisions Requiring User Input":

> *"Correction: look x o'clock. -> scan not in line, but that 30 deg sector near to far. S shape
> when needed by FOV.*
> *1 - approved / 2 - approved / 3 - approved / 4 - yes"*

So: `look <o'clock>` is **not** a sweep along the hour's centre line; it is a 9K113 scan of that
hour's 30° sector, near to far, in an S shape where the sight's field of view is narrower than the
sector. (1) `look` during an attack run is refused, `"unable, attack run"`. (2) `silence` does not
cancel a look. (3) "no" to the OBSERV confirm cancels the look silently. (4) one `look` command
covers sectors and places.
