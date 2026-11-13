# Brain tool calls (BR-2) -- explore notes

No Explore conversation preceded the goal check (user went straight to alignment, 2026-10-31). The
goal check's questions (`alignment.md`, goal check, CONCERNS) served as the explore; answers below.

## User's goal statement (verbatim, 2026-10-31)

> *"There's two things I'd like to advance soon: brain layer being able to *do* things, in other
> words the tools that brain can call to either query data or command/reply things. [...] Getting
> these right at goal and plan stage is important."*

## Goal-check answers (user, verbatim, 2026-10-31)

Questions: 1 real examples the phrasebook could not take; 2 act or confirm on brain-understood
commands; 3 callout style vs model's own words; 4 phrasebook command with extra words -- act now or
wait for brain; 5 acceptable latency, "stand by"; 6 brain not running; 7 "him" carrying over;
8 flight commands via brain; 9 pilot's notes read back as pilot's; 10 brain initiative.

> *"1 - no real examples, since the functionality is not there, I haven't been able to test it.
> But, most likely thing related to where units, groups, things are. Questions about current belief
> + mission memory + world. Telling targets from eachother. Not likely weapons employment, but maybe
> information about loadout.*
> *2 - read back and do.*
> *3 - when simple answer suffices, use the existing callout style. If those do not support
> answering, brains own words.*
> *4 - no. Key brain on "Petrovich, ..." then "Petrovich, report south of Gemerek" uses the brain.
> This way I know to expect a slower answer and can use the simple "report [o'clock]" for fast
> answer.*
> *5 - "stand by" is good. I'll likely only ask things I can wait for. How long, that needs
> pracical experimentation. No more than 1 minute.*
> *6 - "unable, no brain"*
> *7 - "it/that" as implemented recently*
> *8 - fixed only. Need fast responses, can't wait for brain.*
> *9 - sure, not very important*
> *10 - only when prompted. Even the small model we use takes time to process. Keep it for when we
> need it, avoid unnecessary use."*

## Reading (main loop)

- (1) First tool surface is **queries**: where units/groups/things are, across current belief,
  mission memory and the world model; telling targets apart (distinguishing features, relative
  position); possibly own loadout. Weapons employment is not a target use. The acceptance set is
  built from those categories, since there are no real utterances yet.
- (2) A brain-understood command is read back and executed, no "confirm?" -- through the same
  command handler as the phrasebook (goal-check finding 1 / E3).
- (3) Answers: existing callout phrasing when it can carry the answer; the model's own words only
  when it cannot. Partially reopens D5 (model never phrases) -- the user's answer is the new rule.
- (4) **Routing is by wake word, decided by the pilot:** an utterance starting "Petrovich, ..." goes
  to the brain, even if the rest would match a fixed phrase ("Petrovich, report south of Gemerek").
  Without the wake word, the phrasebook handles it, fast. The pilot chooses fast vs slow by how he
  speaks. Related existing work: `[[AA-B7]]` wake-prefixed escalation, `[[BL-B100]]` wake-prefix
  stripping.
- (5) "Stand by" while the brain works. Hard ceiling 1 minute; the real budget is tuned in flight
  (tunable).
- (6) Brain unavailable -> "unable, no brain".
- (7) Pronoun carry-over reuses `[[BL-B102]]` ("that"/"it" = the contact Petrovich last talked
  about) -- no new referent mechanism.
- (8) Flight commands are fixed-phrase only (consistent with BL-16's plan); the brain never maps
  speech to flight control.
- (9) Pilot-noted locations read back as the pilot's note -- low priority.
- (10) Brain runs only when prompted by the pilot. No autonomous initiative; avoid unnecessary
  model calls.

## Plan decisions U1–U4 (user, verbatim, 2026-11-01)

> *"1,2,4 - as recommended*
> *3 - ok, let's try these"*

Reading (main loop):

- U1: no model call without the wake word. Unprefixed misses answer "which one?" (several
  candidates) or "say again".
- U2: `engage`, `disengage`, `weapons_armed`, `weapons_safe`, `observ_on`, `observ_off`, `point`
  excluded from the brain in BR-2; answer "Unable, fixed command only."
- U3: the five "Unable, …" lines as proposed, a first try; flights may change the wording.
- U4: BR-B2 and BR-B3 folded into Stage 2.
