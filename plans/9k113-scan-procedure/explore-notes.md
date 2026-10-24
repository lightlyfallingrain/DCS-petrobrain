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
