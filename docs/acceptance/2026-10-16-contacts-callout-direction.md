# 2026-10-16 — "Contacts": what Petrovich says about many units that do not group

Captured verbatim, before any planning pass, per root `CLAUDE.md`'s "Flight feedback is captured,
then explored, then planned". This answers the question `todo/todo/X-T4.md` has carried open since
2026-09-28 — *"what a crew member should **say** when sixteen individually-resolvable vehicles sit
in one sector"* — which that entry marks as **needing the user's judgement before any plan**.

## 1. The direction, in the user's own words

> *"'Sixteen vehicles, one sector, what does he say?' or more generally X individual units that do
> not group.*
>
> *-> Even if they don't group, use a group (or dercribe) like callout: "contacts, [\<classes\>|\<types\>]
> \<where\>", where can be range in this case. classes array.*
>
> *That keeps it from becoming X individual reports, but let's me know what is out there. Saying
> "contacts" instead of "group" makes that distinction clear."*

## 2. What the direction settles

- **The answer is a sentence shape, not an association change.** The 2026-09-28 log analysis
  (`plans/contact-fragmentation-at-range/2026-09-28-log-analysis.md`) established that clustering
  was *right* to see sixteen things — 3 of 52 contacts were ever plural against 62 real objects,
  near 1:1. So the lever was never the gate; it is what gets spoken. This direction operates
  exactly there.
- **A group-shaped line is used for a non-group.** The existing group-disclosure line form is
  reused for a set of contacts that did **not** cohere into a `Group`.
- **The signal word carries the distinction**: `"contacts"`, not `"group"`. The user's reason is
  explicit — it tells him these are separate things that happen to be in one place, not a formation
  Petrovich believes in.
- **`<classes>` is an array**, i.e. the line names more than one class where more than one is
  present.
- **`<where>` may be a range** in this case, rather than only a sector.
- **The purpose is stated**: *"keeps it from becoming X individual reports, but let's me know what
  is out there."* Both halves are the acceptance criteria — quieter, and still informative.

## 3. What already exists, so it is not rebuilt

Checked before opening the conversation (`/explore`'s own first step):

- **The word is already in the vocabulary.** `_plural_unit_type_display("OP_GROUPSOMETHING",
  "presence")` returns `"contacts"` today (`body-layer/tests/test_speech.py:1650`), and
  `render_group_disclosure` already emits `"A couple of contacts."` for an all-undifferentiated
  group (`:2642`).
- **The class breakdown already renders as an array.** `_group_composition_clause` produces
  `"two armor and truck"` and `"truck and something"` — a per-class breakdown with an exact count
  and an aggregated phrase for undifferentiated members. It is already re-expressed over
  `collapse_members` at `CollapseDepth.TYPE` (`BL-W39`), so class-vs-type depth is a parameter that
  exists rather than a thing to invent.
- **Speech-time aggregation exists and almost never fires.** `belief.callouts.group_candidates`
  needs members pending *simultaneously* and sharing the same range *word*; detections trickle in
  one per poll and `"2 kilometres"` vs `"2.5 kilometres"` are different buckets — which is precisely
  why the 2026-09-28 sortie was one line every eleven seconds.
- **The 2026-10-13 attention-tier direction already specified the information content** for the low
  and medium tiers: `<where>` + far/mid distance + **few/several/many**, plus a rough class at
  medium (`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` Part 3). This direction
  gives the *sentence*; that one gave the *fields*. **They are not identical** — see the open
  question on count below.

## 4. Open questions this direction does not settle

Recorded as questions, not as assumptions, and to be answered in conversation before an Architect
pass:

1. **Does a count or a hedge appear in the line?** The form as written carries classes and where,
   no count. The 10-13 tier direction asked for `few/several/many`. *"Contacts, armor and trucks,
   two kilometres"* and *"Many contacts, armor and trucks, two kilometres"* are both consistent with
   one of the two directions.
2. **What binds a set into one line — sector, range band, or both?** The user named range as a
   possible `<where>`, which suggests the binding is not purely angular.
3. **How few is still "contacts"?** Two resolvable vehicles: one line or two? The subitizing
   boundary (5) is already a constant in this project for a different purpose.
4. **What happens on the next look?** Groups speak a delta rather than restating the roster. Does a
   contacts line re-speak when a class appears or disappears, and go silent otherwise?
5. **Do watched or selected units still get their own line** while the rest of the set is covered by
   the contacts line?

## 4a. Four of the five answered, same day

Asked as open questions with a mock transcript in front of him; his answers, verbatim:

> *"1 - few/several/many*
> *2 - one line: 2 to 6 km*
> *3 - delta*
> *+ o'clock position is a must in the callouts"*

Taken in order, and what each one settles:

1. **The count is a hedge, never an exact number**, in the `few/several/many` register. This
   matches the 2026-10-13 tier direction rather than the bare form in §1, so the line carries a
   cardinality word.
2. **One line covers a set spanning 2 to 6 km** — answering the mock's own example (vehicles at
   2 km in 1 o'clock plus more at 6 km in 2 o'clock). So the binding is **deliberately coarse in
   range**, and a 4 km spread is one callout rather than two.
3. **Delta only.** Same discipline as a group's disclosure: silent until the set's content changes
   (a class appears or disappears), not a periodic refresh.
4. **Unprompted correction, and it invalidates the mock that was shown**: *"o'clock position is a
   must in the callouts."* The mock transcript dropped the clock hour and read *"Contacts, armor and
   trucks, 2 kilometres"*. Wrong — the bearing is not optional. Worth recording because the error
   was in the elicitation material rather than in the direction, and it was caught by showing
   something concrete, which is exactly what that technique is for.

## 4b. What is left open after those answers

1. **What the bearing says when the set spans clock hours.** The clock hour is mandatory and the
   range may be a 2–6 km span, so a set that sits across 1 and 2 o'clock needs a rule: a span
   (*"1 to 2 o'clock"*), the nearest or densest hour, or a split into one line per hour. The §4a
   answer to (2) implies the set is *not* split on range; whether it splits on bearing is not
   stated.
2. **Which words, given the shipped vocabulary is four and not three.** `_cardinality_phrase`
   already speaks `"a couple of"` (2–3), `"a handful of"` (4–5), `"several"` (default plural) and
   `"many"` (16+), with an exact number only for an *attended* contact whose interval is exact
   (user direction, 2026-09-19). `few/several/many` is three. Whether `"few"` replaces the
   couple/handful pair, or `couple`/`handful` *are* the "few" band in practice, decides whether this
   is a new vocabulary or a reuse of the existing one.

## 4c. Both closed, same conversation — the direction is complete

Shown the three bearing rules as mock callouts side by side, his answers:

> *"- split per hour. relative position is important as is contact class.*
> *- use the existing hedge vocabulary*
> *- current watched contact behaviour stays"*

1. **One line per clock hour, and the reason given is what matters**: *"relative position is
   important as is contact class."* So the set is keyed on the **clock hour**, and range is whatever
   span the members of that hour cover (2–6 km, from §4a). A set straddling 1 and 2 o'clock is
   **two** callouts, not an arc and not a nearest-hour anchor. Bearing and class are the two things
   the line exists to deliver; range is the third field, not a splitting key.
2. **No new vocabulary.** The shipped `_cardinality_phrase` register stands as it is — `"a couple
   of"` (2–3), `"a handful of"` (4–5), `"several"` (default plural), `"many"` (16+). So
   `few/several/many` in §4a names the *register*, not three literal words to implement, and
   `couple`/`handful` already are its "few" band. Nothing in that function changes.
3. **The watched-contact exemption is untouched.** A watched or selected contact keeps behaving as
   it does today, including `_cardinality_phrase`'s `attended` path speaking an exact number when
   the interval is exactly known (2026-09-19 direction). A contacts line does not swallow it.

**So the resulting line form, with every field settled:**

> *"\<hedge\> contacts, \<classes\>, \<clock hour\> o'clock, \<range or range span\>."*

and worked against the sortie that raised the question — sixteen resolvable vehicles, mixed classes,
1 and 2 o'clock, 2 to 6 km:

| | spoken |
|---|---|
| first disclosure, 1 o'clock | *"Several contacts, armor and trucks, 1 o'clock, 2 to 4 kilometres."* |
| first disclosure, 2 o'clock | *"A couple of contacts, trucks, 2 o'clock, 6 kilometres."* |
| next looks, nothing new | *silent* |
| air defence resolves at 1 o'clock | *"Contacts, armor, trucks and air defence, 1 o'clock, 2 to 4 kilometres."* (delta) |
| one of them is watched | unchanged from today — its own line, exact count when known |

Against the 2026-09-28 baseline that raised this: ~160 lines over half an hour, one every eleven
seconds, nearly all the same words.

## 5. Status

- Captured and **explored** 2026-10-16, in one conversation; every open question in §4 is
  answered in §4a/§4c. **Not yet planned** — Architect pass next, with these constraints in hand.
- Tracked against `todo/todo/X-T4.md`, whose closing "needs the user's judgement" paragraph this
  document answers.
