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
