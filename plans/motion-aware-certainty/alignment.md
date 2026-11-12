# BL-B112 — motion-aware contact certainty: alignment

## Goal check — 2026-11-12

**Verdict:** CONCERNS

Checked at `bfced060`. The inputs read were `explore-notes.md`, `BL-B112.md`, the 2026-10-13 direction,
BL-B111's plan Decision 1 and its DoD milestone answer, and `belief/decay.py`,
`association_over_time.contact_growth_rate_mps`, `position_belief`, `belief/motion.py`,
`perception/motion.py`, `perception/estimation.py`, `perception/object_model.py`, and every
`certainty_of` consumer.

### Why

The pilot builds his picture of the threats from what Petrovich has told him. That picture should
stay as solid as the world actually is. A SAM site or a parked column does not become doubtful, or
disappear from Petrovich's answers, just because nobody has looked at it for half a minute while
the crew circles at a distance. And Petrovich should hedge ("last I saw") when, and only when, the
unit could really have moved far enough that the pilot would look in the wrong place.

Ask why once more and the purpose turns out to be **where to look and what to avoid**. A label
counts only through what the pilot then hears: whether the report is stated as fact or hedged, and
whether the unit is still in the answer at all. The label is the mechanism. Truthful wording and a
persistent threat picture are the purpose.

### Player expectations

The hedge is driven by one quantity: **how far the unit could have moved since it was last seen.**
That is growth, not total position uncertainty (finding 2).

```
unseen for →                      30 s        2 min        10 min       30 min
fixed site (SA-2, dug-in)         as fact     as fact      as fact      as fact      never hedged, never lost by time
mobile, seen stopped (0.3 m/s)    as fact     as fact      as fact      last I saw   0.5 km at ~28 min
mobile, seen moving: truck 15     as fact     last I saw   last I saw   (lost?)      0.5 km at ~33 s
                     armour 8                 last I saw   ...                       0.5 km at ~1 min
                     infantry 2   as fact     as fact      last I saw                0.5 km at ~4 min
```

- **E1** — When the pilot asks about a fixed SAM site (SA-2, an installation, a dug-in unit) seen
  any time this sortie and not seen since, Petrovich states it as present fact. He does not say
  "last I saw", and it stays in the answer however long ago it was seen.
- **E2** — A fixed site never drops out of report answers, group pictures or threat summaries
  through time alone. It goes away only when someone looks at its place and finds it empty
  (BL-B111's absence route), or when it is destroyed.
- **E3** — While circling a known fixed site, the pilot does **not** hear it re-announced as a new
  or reacquired contact each time Petrovich's eye comes back round to it.
- **E4** — A mobile unit Petrovich saw standing still is reported as fact for a long time (about
  28 min at today's 0.3 m/s drift) unless he sees it move. Once it is seen moving it is treated as
  a mover.
- **E5** — A unit Petrovich saw moving is reported "last I saw …" once it could have gone 0.5 km
  or more since he last saw it: a truck after about half a minute unseen, a tank after about a
  minute, infantry after about four. Before that it is reported as fact.
- **E6** — A contact Petrovich is watching right now, or that he saw moments ago, is never hedged
  at any range. A 4 km naked-eye fix is "as fact" while he is looking at it.
- **E7** — How confident a report sounds depends on what Petrovich perceived, never on DCS truth.
  "Fixed site" comes from what he identified it as, and "stopped" comes from what he watched.

### Open assumptions

- **What the 0.5 km is measured on** — serves the why: growth since last seen ("how far could it
  have gone"). Would not: the total position radius. That includes the measurement error of the
  look itself, so most naked-eye contacts beyond ~3 km would be hedged the moment they are seen
  (finding 2).
- **What "lost" is** — serves the why: a unit leaves the picture when it could be anywhere, or when
  someone looked and it was gone. For a fixed site that is never by time. Would not: a flat 120 s
  for every contact, which drops a known SA-2 from every answer after two minutes (finding 1).
- **Which mobile/fixed fact is used** — serves the why: the type or class Petrovich has actually
  identified, with an honest fallback when he only knows "short range SAM". Would not: the DCS
  `object_type` read through regardless of how deep his identification has gone (finding 4).
- **What "seen stopped" means** — serves the why: watched long enough, at a range where motion
  would have been noticed. Would not: one glance below the angular-rate threshold, which at 4 km
  also returns "stopped" for a tank driving at 8 m/s (finding 3).
- **Never observed for motion (`motion is None`, a scope-only contact)** — serves the why: keep the
  2026-10-30 decision that `None` drifts like `stopped`. Would not: giving it the class speed. That
  makes a scope-seen truck "last I saw" in 33 s and widens the association gates the user narrowed
  on purpose (BL-B58/B24).
- **Other time-keyed things** — `position_confidence` (exponential, half-life 30 s, feeds
  enrichment), the range-crossing `fresh` gate and `GROUP_REIDENTIFY_WINDOW_S` all assume the time
  ladder. The planner has to choose, for each one, whether it follows the new quantity. The why says
  that anything the pilot hears about a fixed site should not decay on a timer.

### Findings

1. **Taken literally, "Use current implementation" for lost removes a known SA-2 from the picture
   after 120 s, and re-announces it every orbit** — lens: Purpose, Crew sense
   - *Assumption:* lost stays at a flat 120 s for every contact.
   - *In the code today:* a `"lost"` contact is dropped from `report` answers (`crew_console`
     `_handle_report`, "drop `certainty == 'lost'`"), from follow targeting, from group clustering
     (BL-B23) and from callout proximity (`callouts.py:856`). The lost moment itself is silent
     (`speech.py`: no `CONTACT_LOST` template). Coming back from lost emits `CONTACT_REACQUIRED`,
     which renders a full positional callout.
   - *The pilot would see:* he circles an SA-2 at 5 km and asks "any SAMs?" after three minutes:
     no SA-2 in the answer. Petrovich's eye comes round, and "SAM, 2 o'clock, 5 km" is called again
     as though it were new. The BL-B110/I2 coupling exists to stop exactly this churn.
   - *Grounded in:* `BL-B112.md`'s own "For the pilot" ("does not go 'lost' while it is certainly
     still there"), the user's origin quote, and the code paths above.
   - *Suggests:* the user most likely meant "keep the lost lifecycle as it is", that is the events,
     the filters and BL-B111's absence route, not "keep 120 s for a fixed site". Question Q1.
     Nothing in his three answers asks for a fixed site to drop out.

2. **"Location inaccuracy ≥ 0.5 km" has to mean growth since last seen, not total uncertainty** —
   lens: World truth, Crew sense
   - *Assumption:* the hedge keys on `position.radius_m()`.
   - *In the code:* one naked-eye look has σ_down = 0.17 × range (`estimation.RANGE_FRACTIONAL_SIGMA`),
     which is ~680 m at 4 km before any time has passed.
   - *The pilot would see:* "last I saw" on a contact Petrovich is looking at right now, for most
     naked-eye contacts beyond ~3 km. That is the opposite of the user's intent (E6).
   - *Grounded in:* code. The user's phrasing ("as inaccuracy grows") also points to growth.
   - *Suggests:* the planner keys on how far the unit could have moved since last seen. No user
     question needed unless the main loop reads his words differently.

3. **"Observed not moving" is one sub-threshold glance today, and at Mi-24 ranges that misses real
   movement** — lens: World truth, Bounded knowledge, Non-obvious case
   - *In the code:* the founding `apparent_motion=False` is adopted as `"stopped"` at once
     (`belief/motion.py`). The threshold is 8 arcmin/s (`perception/motion.py`), which needs about
     9 m/s across the line of sight at 4 km. A tank at 8 m/s broadside at 4 km, or any vehicle
     driving toward or away from the aircraft, reads "stopped".
   - *Vignette:* a column on a road, heading toward the helicopter at 4 km, is seen once and then
     goes behind a ridge. Under this goal it is stated as fact at its first place for about 28 min,
     while it closes 10 km.
   - *Today the cost is small,* because growth is already 0.3 m/s for stopped units. BL-B112 adds
     **confident wording** on top of that belief, and that wording is what the pilot acts on.
   - *Grounded in:* code, and the user's "seen **and observed** not moving", which suggests
     watching rather than glancing.
   - *Suggests:* Q2.

4. **Fixed versus mobile can be known only at type depth, and SA-2 is not in the table** — lens:
   Bounded knowledge, World truth
   - *In the code:* `installation_component=True` exists only for S-125 (SA-3) and Kub (SA-6). No
     `object_model` row matches an S-75/SA-2 type string, so an SA-2 falls to the default profile
     and is treated as mobile. A naked-eye contact carries ED's coarse class (`OP_SRSAM` and so on).
     `OP_SRSAM` covers both the fixed S-125 and the mobile Osa/Strela/Tor, so "short range SAM"
     cannot tell the two apart.
   - *What softens it:* a SAM Petrovich glanced at below threshold is "stopped" anyway, so it is
     stated as fact for ~28 min. Fixed versus mobile matters mainly after that, and for lost.
   - *Kub/SA-6* is marked fixed today. Under the user's rule ("a SAM site that is not a mobile SAM
     unit itself") it may belong with the OSA. Only the user can say how DCS missions use it.
   - *Suggests:* Q3.

5. **BL-B111's DoD expects BL-B112 to narrow its Decision 1 exclusion, and under this goal it will
   barely move** — lens: Purpose
   - The excluded case BL-B111 measured is armour **seen moving**, 5–6 km wide at 700 s
     (8 m/s × 700 s). Moving units keep their class rate under every reading of the user's answers.
     Stopped and `None` units already grow at 0.3 m/s, and installations at 0.
   - The only growth BL-B112 plausibly narrows is an SA-2 (or another fixed type the table
     lacks) going from 0.3 to 0. That is about 200 m at 700 s, already well inside one look.
   - *Grounded in:* `contact_growth_rate_mps` and BL-B111's own measurement.
   - *Suggests:* the acceptance check against `EXPECTED_AREA_MAX_HALF_WIDTH_DEG` should be written
     as "expected: unchanged, except fixed types now at zero", not as a narrowing to look for. A
     plan that promises narrowing will either fail that check or change moving-unit growth, which
     the user has not asked for.

6. **"Tracked" versus "estimated" stays a real player-facing difference if it maps to the hedge** —
   lens: Purpose
   - Today the pilot does not hear the two labels as such. "Last I saw" keys on age greater than
     one scan cycle (`speech._is_stale`), not on the label. The labels reach him through the
     brain's phrasing hint ("recent" or "remembered") and the range-crossing `fresh` gate (tracked
     only).
   - *Serves the why:* tracked means "good enough to point the pilot at, said as fact", and
     estimated means "said with 'last I saw'". Two states, one meaning each, and the pilot can tell
     them apart.
   - *Consequence to accept:* a fixed SA-2 that stays tracked keeps range-crossing callouts alive
     ("SAM inside 3 km") as ownship closes on its remembered place. For a site that cannot move
     this is the most useful call Petrovich can make, but it is a call made without a fresh look.
     That makes it Q4.

### Questions for the user

- **Q1** — "Use current implementation" for lost: did you mean keep 120 s for everything (an SA-2
  last seen three minutes ago then drops out of "report" answers, and is called again as a new
  contact when Petrovich looks back), or keep how "lost" works while a fixed site never goes lost on
  time alone, only when he looks and finds the place empty? *Recommended:* the second. Your other
  two answers and the origin quote are all about the site still being there.
- **Q2** — "Observed not moving": is one glance enough, or must Petrovich have watched it for a few
  seconds? At 4 km a single look cannot tell a tank driving straight toward you from a parked one,
  and this change would then state its old position as fact for about half an hour.
  *Recommended:* a short watch, for example the existing 5 s stop confirmation, and nothing from
  one glance.
- **Q3** — Which SAM systems should count as "fixed site, never moves" in DCS: SA-2 and SA-3 for
  certain, and SA-6 (Kub), SA-10/S-300, SA-11 (Buk)? And when Petrovich only knows "short range
  SAM", not which one, treat it as mobile? *Recommended:* fixed = SA-2, SA-3, SA-10 site components;
  treat SA-6 as you rule; class-only "SAM" is mobile until identified.
- **Q4** — For a fixed SAM site that he has not seen for a while, should Petrovich still call
  "SAM inside 3 km" as you close on its remembered position? *Recommended:* yes. A site cannot
  move, so the call is true, and it is the warning you would want most.
