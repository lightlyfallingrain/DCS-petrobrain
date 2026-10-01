# Explore — what a group sounds like over time (user, 2026-10-01)

Answers to `plan.md`'s "Decisions Requiring User Input" items 3, 4 and 5, given as worked examples
rather than as rules. **The examples are the specification**; the rules below them are this file's
reading of them, and where the two disagree the examples win.

## Settled first, briefly

- **Item 4 (test rewrite) — confirmed.** `test_2c_transcript_fixture_renders_four_lines_not_seven`
  changes its expected output; the infantry pair now merges.
- **Item 3 (SAM installation geometry) — the measurement was worthless and must not be used.**
  > *"the SAM battery placement was not realistic, rather that units put on map for testing. Search
  > internet for realistic SAM site patterns."*

  The 236–838 m spacing the debug pass measured came from units a mission author dropped on a map
  for a test, not from a real emplacement, so the proposed 1000 m cap rests on nothing. Real site
  geometry has to be researched before the cap is set. **This invalidates the plan's own §3
  justification, not just its number.**
- **Item 5, first half — on a leading-threat change, delta only** (the plan proposed a full line).

## The utterance examples, verbatim

Progression of a single group:

```
"group <where>"
"AAA in the group"
"there's a zsu"
"Shilka and zsu"
```

Two groups, tracked over time:

```
"group 2 o'clock, 3 km"
"group 10 o'clock, 2 km"
"10 o'clock (group) is trucks on road"
"2 o'clock (group) has armor, several"
"SRSAM, in 2 o'clock group"
"11 o'clock trucks are moving north, towards <village>"
"Shilka, in 2 o'clock group"
Pilot: "report"
"SRSAM, Shilka, armor 2 o'clock 2.5 km. Trucks moving north 11 o'clock, 1.5 km."
```

## What the examples say

**Departure splits by cause.**
> *"departs depends on why. If detection lost -> silent. If destroyed '<unit> destroyed'."*

Losing sight of something is not an event; losing the thing is. Note this requires distinguishing
the two, which is a perception question, not a disclosure one — Petrovich must have grounds to
believe it was destroyed rather than merely gone from view.

**Refinement is worth speaking when it changes a CLASS, not a count.**
> *"Classifications are important. 'SAM and something' -> 'SAM and armor' is important, so is 'plus
> trucks'. one more armor or truck etc makes no difference — exception, more air defense does make a
> difference."*

So: a new class appearing in the group is news; another instance of a class already reported is not;
**more air defence is always news**, even as a count increment. That last exception is the asymmetry
that matters in the cockpit, and it is the mirror of the infantry decision — the error costs are not
symmetric across classes.

**Classes carry the threat; types refine it.**
> *"Knowing the classes is more important than exact types. Classes already tell threat level
> regardless of exact type, type refines it further."*

Disclosure should therefore prioritise reaching class-level coverage of a group over refining any
one member to an exact type. "AAA in the group" before "there's a zsu", which is exactly the order
of the first example.

**"Group" is the default and usually goes unsaid.**
> *"typically units move in groups, not individually. Therefore 'group' is default behaviour and can
> be left out beyond initial report stating it's a group, unless needed to specify belonging like
> the 'shilka in 2 o'clock group' so it's not a single shilka that is detected (which could also be
> true for certain air defences especially)."*

Two uses of the word survive: the initial report, and disambiguation — naming the group a unit
*belongs to*, so a Shilka in a group is not heard as a lone Shilka. The parenthetical "(group)" in
the examples marks exactly where it would be dropped in speech.

**A group is addressed by its clock position**, as a handle the pilot can act on: "10 o'clock is
trucks on road", "SRSAM, in 2 o'clock group".

**"Report" is a roll-up**, one compact line per group with the leading threats first and movement
included: *"SRSAM, Shilka, armor 2 o'clock 2.5 km. Trucks moving north 11 o'clock, 1.5 km."*

**Movement is reported against a landmark**, not as a bearing: *"trucks are moving north, towards
<village>"* — which is where this meets the terrain/landmark work, and the first concrete consumer
for a named place in a callout.

## Open, raised by this file rather than by the user

- **A clock handle is not stable.** The aircraft turns, and the "2 o'clock group" becomes the
  10 o'clock group without anything about the group changing. Recomputing the clock at speak time is
  obviously right for a single utterance, but the examples use it as an *identifier across
  utterances* ("SRSAM, in 2 o'clock group" refers back to a group named earlier). Whether that
  survives a turn between the two callouts needs deciding — it may be fine in practice, since the
  pilot also turned and his own frame moved with it.
- The "report" roll-up's ordering (leading threat first, then movement) is inferred from one
  example.
