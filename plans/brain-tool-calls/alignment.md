# BR-2 — brain tool calls: alignment

## Goal check — 2026-10-31

**Verdict:** CONCERNS

Run with no Explore beforehand: the user went straight to alignment (*"Getting these right at goal
and plan stage is important"*, 2026-10-31). So the questions at the end matter more than the findings.
Most of the open assumptions below can only be settled by the user.

### Why

The pilot can already get Petrovich to act by using the right phrase (about 90 command tokens,
answered in under a second). He cannot yet talk to him the way he would talk to a human front-seater:
in his own words, naming things by landmark or by what was seen earlier, asking what is out there,
following up on something said a minute ago. BR-2 lets the speech that falls outside the phrasebook
be **acted on or answered**, so the pilot can keep his eyes out and his hands on the controls
without having to recall the exact wording.

Second why: *"tools to query data or command/reply"* is the mechanism. The purpose is that
**Petrovich understands what the pilot means and responds as a crewmate would: he does it, asks one
short question, or says why he can't.** Tools are only how the brain finds out what he knows and
reaches what he can do. So the plan is judged by what the pilot hears and sees happen, not by how
many tools are dispatchable.

### Player expectations

- **E1 — The phrasebook is untouched.** Anything that matches a command today behaves exactly as it
  does today: same action, same readback, same sub-second timing, with no model in the way. The brain
  never slows down or second-guesses a clear phrasebook command.
- **E2 — Heard speech always gets an answer.** Speech the phrasebook does not cover, but a competent
  crewmate would understand, gets one of four answers: Petrovich does it, asks "confirm `<command>`?",
  asks "which one, A or B?", or says "unable, `<reason>`". Speech that was heard is never met with
  silence, and he never guesses.
- **E3 — A brain-carried command has the same effect as the phrasebook command.** *"Keep an eye on
  the tank by the village"* leaves the same watch, the same target state, the same readback and the
  same orange marker as selecting that tank and saying "watch". `cancel`, `drop target` and `silence`
  work on it in the same way. The pilot cannot tell which path carried it out, except that it took
  longer.
- **E4 — Questions are answered from what Petrovich knows.** *"Where's the Shilka?"*, *"anything near
  the bridge?"*, *"what did we mark?"* are answered from what he has seen, what he remembers and the
  map, in his usual callout register: clock, range, landmark. He says how old the information is
  (*"not seen for four minutes"*) and says when he has lost the contact. He never mentions anything
  he could not have perceived.
- **E5 — Answers are current when spoken.** A short brain answer arrives within a couple of seconds.
  A longer one is preceded by "stand by". When it is spoken it still fits: bearings and ranges are as
  of the moment he says them, not the moment he was asked; he does not act on a contact that has gone
  ("lost him"); and he does not answer a question the pilot has since replaced.
- **E6 — Danger comes first.** Brain work never delays, masks or talks over a threat callout or
  attack-run guidance. Active danger always pre-empts.
- **E7 — Consequential actions need the pilot's word.** Arming weapons, launching the ATGM or taking
  the controls never starts on the brain's interpretation alone: the pilot either used the explicit
  phrase or confirmed. *(Agent's assumption. See Q2.)*
- **E8 — The pilot knows when the brain is unavailable.** If it is down or wedged, every phrasebook
  command still works, and the pilot can tell that free speech is not available. *(How loud: Q6.)*
- **E9 — The pilot's notes stay the pilot's.** Something the pilot asked Petrovich to remember in his
  own words comes back later as the pilot's note, never as something Petrovich saw.

### Open assumptions

- **Where a brain command lands.** Serves the why: the brain fills the same command and slots the
  voice path uses, and `CrewConsole.handle_command` executes it, so E3 holds by construction. Would
  not serve it: brain commands executed through `TOOL_SET`'s own write tools (`set_attention`,
  `watch_area`, `scan_area`), a second, narrower action surface whose effects differ from the
  phrasebook's (Finding 1).
- **Who words the reply.** Serves the why: the brain decides the content, and body renders it from
  data in the callout register (D5 as it stands), so every fact spoken came from a tool result.
  Would not serve it: free model prose. It is slower, can be wordy, and can add a fact that is in no
  tool result. Only the user can say whether he wants the model's own voice (Q3).
- **When the brain gets an utterance.** Serves the why: deterministic first, with the brain taking
  only what the phrasebook could not use. Would not serve it: every utterance going through the
  model. Undecided: a matched command whose extra words were dropped, such as *"report south of
  Gemerek"*, which today degrades to a bare report (Q4).
- **Act or confirm.** Serves the why: the brain acts and reads back when the pilot's words resolve
  cleanly and the action is ordinary, and confirms when its evidence is weak or the action is
  consequential. Would not serve it: "confirm?" on every brain command. Today's sortie feedback shows
  what that costs (*"having to confirm a command many times per mission is very annoying"*,
  2026-10-31).
- **Which tools are exposed.** Serves the why: tools that answer a question the pilot would ask, or
  carry a command he would give. Would not serve it: bookkeeping exposed because it is in the
  registry, such as `acknowledge_event` and `poll_events`, which the pilot never asks for.
- **What "data" is.** Serves the why: belief, mission memory, and the world model's map knowledge,
  which the crew legitimately has. Would not serve it: DCS truth, or anything mission-author-only.
- **Conversation state.** Serves the why, if the user wants it: *"still there?"* resolves to the unit
  the pilot asked about two minutes ago (explore notes §4 put this in scope, with BL-8's memory).
  Would not serve it: every utterance treated as stateless, while the plan claims to be
  conversational. Whether it is in BR-2 is a question (Q7).
- **Initiative.** Serves the why: the brain acts only in answer to the pilot. Danger reporting stays
  deterministic, and unrequested advisory stays deferred (explore notes, *"requested advisory, not
  autonomous advisory"*). Would not serve it: the brain volunteering actions or advice.
- **Flight commands (BL-16, checked in parallel).** Serves the why: numeric flight commands
  (*"turn heading 3 1 5"*, *"hold 200 m"*) stay in the phrasebook, and handover (*"you have
  controls"*) is only ever the explicit phrase. Would not serve it: the controls changing hands
  because the brain read a sentence that way (Q8).

### Findings

1. **A brain command has to land on the pilot's command surface, and `TOOL_SET` is not that
   surface.** Lens: unit of action.
   - *Assumption:* BR-2's entry frames the job as *"wire a real tool-call path to `TOOL_SET`"*, so
     "command" would mean calling the registry's write tools.
   - *In the code:* `TOOL_SET`'s 17 entries are queries plus `set_attention`, `watch_area`,
     `scan_area`, `cancel_task`, `remember_location` and `acknowledge_event`. The pilot's commands
     (`engage`, `select target`, `step`, `follow`, `point`, `report`, `silence`, `observ on/off`,
     `weapons armed/safe`) are handlers behind `CrewConsole.handle_command` and are not in
     `TOOL_SET`. Where the two overlap, they differ. The voice "watch" builds a `watch_contact_task`
     with a readback and deferral, while the tool `set_attention` only sets a mark. `scan_area`'s own
     description says it *"does NOT aim Petrovich at that area"*. A pilot who says *"check the
     bridge"* expects him to look there.
   - *The pilot would see:* a brain-understood "watch that tank" that marks the tank but does not
     behave like his own "watch" (no readback, a different cancel), or a "look over there" after
     which Petrovich's eyes keep to his own scan.
   - *Grounded in:* the code, and BL-13's existing design: *"When free speech arrives, the brain's
     job is filling these same five slots from open text and calling the same handler — not a new
     schema."*
   - *Suggests:* the plan states plainly what a brain command executes, and E3 is its acceptance
     test. Query tools and command execution are two different questions, and should not be forced
     through one registry.

   ```mermaid
   flowchart LR
     V[Pilot speech] --> M{phrasebook match?}
     M -- yes --> H[handle_command + slots]
     M -- no / wake word --> B[brain: query tools to resolve]
     B -- command --> H
     B -- answer --> R[body renders in callout register]
     B -- unsure --> Q[confirm? / which one? / unable]
     H --> A[same action, same readback]
   ```

2. **The phrasebook already carries the sorties, so the brain's value lies in the gap, and the gap
   has not been named.** Lenses: purpose; would the pilot notice.
   - *Assumption:* there is a body of free speech waiting for a brain that can act.
   - *In the logs:* the 2026-10-15 pending-flight audit found that in all three sorties *"every
     utterance matched a known command token … nothing ever fell through to the brain-layer
     escalation path. The free-text/model path has still never been heard live."* The default
     `--brain-client` is still `debug`, which is silent. BR-1.1 and BR-1.2 are both `#needs-flight`.
   - *The pilot would see:* nothing different, if what BR-2 covers is what he already says in
     phrasebook form. He would see a large difference if it covers what he holds back today:
     landmarks (BL-13 Stage 5's open-vocabulary slot), memory, follow-ups, and questions.
   - *Grounded in:* `docs/acceptance/2026-10-15-pending-flight-audit.md`; `body.py`'s
     `--brain-client` default.
   - *Suggests:* take three to five real utterances from the user (Q1) and use them as BR-2's
     acceptance set. BR-2 will also be the first time the pilot hears the brain path at all, so its
     first flight tests BR-1 too.

3. **"Reply" reopens D5, and the documents disagree about it.** Lenses: crew sense; bounded
   knowledge.
   - *In the plan:* D5 says *"the model never phrases anything"*: replies are body templates over
     tool data, which is what guarantees that nothing spoken is invented. BR-1.2's acceptance card
     calls its flight *"the first flight where the pilot hears the model's own language"*.
   - *The pilot would see:* with templates, answers that sound like his callouts and arrive fast.
     With model prose, a more natural voice that is slower and can carry a detail no tool returned
     (*"moving east"* when nothing measured motion).
   - *Grounded in:* `plans/brain-layer/plan.md` D5; `brain-layer/ROADMAP/BR-1.2.md`.
   - *Suggests:* the user decides (Q3). Either way, every fact spoken must trace to a tool result.

4. **Some commands are the pilot's to give and should not start on the brain's reading.** Lens:
   whose job.
   - *In the code:* the dispatcher carries `weapons armed/safe`, `engage` (missiles) and `observ
     on/off`. BL-16 will add the handover of the controls. The pilot owns weapon deployment and
     flying (root `CLAUDE.md`, "Whose job is whose").
   - *The pilot would see:* if a misheard or loosely worded sentence arms weapons or takes the
     controls, the crew has crossed its own boundary.
   - *Grounded in:* project invariant (whose job), plus BL-16's *"Handover is spoken only"*.
     *Which* actions count as consequential is the agent's reading: Q2.

5. **Latency and the single voice are both shared.** Lenses: the envelope; crew sense.
   - *In the plan:* the user set the budgets: fast for simple things, *"5–10 s acceptable"* for
     judgement, with "stand by" (explore notes §1). Ollama serialises generation, so one slow reply
     can delay the next utterances (BR-1.2, APPROVED — MONITOR). A tool-calling turn is several
     generations, never measured.
   - *The pilot would see:* in a defensive turn under AAA, *"where's the Shilka?"* answered three
     seconds later. That is acceptable only if the bearing is the bearing *then* (E5) and no threat
     callout queued behind it (E6).
   - *Grounded in:* the user's own words, explore notes §1 and §5.

6. **The first write tool needs a provenance line in what the pilot hears back.** Lens: bounded
   knowledge.
   - *In the code:* `remember_location(label=...)` is the only free text in mission memory that the
     brain controls. A label written once is handed back later by `recall_memory` with no mark that
     a model wrote it.
   - *The pilot would see:* *"AAA marked here"*, recalled ten minutes later as if Petrovich had
     seen AAA there.
   - *Grounded in:* `[[BL-B79]]`, which closes inside BR-2.

7. **Vignette: "anything near the bridge?"** Lenses: world truth; the non-obvious case.
   - `find_place` is a plain substring match over named places, and most bridges on a DCS map are
     not named places. The honest answer is *"which bridge?"* or *"unable, don't know that place"*.
     A guessed bridge, or a scan that doesn't look there (Finding 1), would be dishonest. If the
     answer is "nothing", it must mean *"nothing seen"*, never *"confirmed empty"*. `scan_area`'s
     description already draws that line, and the spoken answer has to keep it.
   - *Grounded in:* the `TOOL_SET` descriptions for `find_place` and `scan_area`.

**Mock exchanges**, for the user to correct. They are drawn, not designed:

| pilot says | brain does | Petrovich says |
|---|---|---|
| "Keep an eye on the tank by the village" | `find_contact("tank")` → 2 candidates → the words *"by the village"* single one out → command `watch` on it | "Watching T-72, 10 o'clock, 2 km, by Gemerek." *(identical to the phrasebook path)* |
| "Where's that Shilka?" | `find_contact`, then `get_contact_history` → last seen 4 min ago | "Shilka, last seen four minutes ago, 2 o'clock, 3 km, south of the road. Not seen since." |
| "Take out that BTR" | resolves to `engage missiles` on the BTR | "Confirm engage missiles, BTR, 12 o'clock, 1.8 km?" *(or act directly? Q2)* |
| "Remember this spot, AAA fired from the ridge" | `remember_location(ownship, label="AAA from ridge")` | "Marked." *Later:* "Your mark, AAA from ridge, 6 o'clock, 4 km." |
| "Anything near the bridge?" | `find_place("bridge")` → nothing named | "Which bridge?" / "Unable, don't know that place." |
| "Still there?" *(2 min after "watch him")* | needs conversation state | "Still on him, 11 o'clock, 1.5 km." *(only if Q7 says this milestone)* |

### Questions for the user

1. In your last few sorties, what did you want to say to Petrovich that the phrasebook couldn't take?
   Two or three real examples are worth more than any list we could draw up.
2. When the brain understands a command given in your own words, should Petrovich just do it and read
   it back, or always ask "confirm?" first? Does that change for weapons, ATGM launch, or the
   controls?
3. When he answers a question, should he sound like his callouts do now (fixed phrasing: clock,
   range, landmark), or do you want the model's own sentences, accepting that they are slower and
   sometimes wordier?
4. When a phrasebook command carries words it couldn't use (*"report south of Gemerek"*), should it
   still act at once and drop them, or wait a second or two for the brain so the extra words count?
5. How long can a free-speech answer take before it's no use to you in flight, and is "stand by" what
   you want to hear while you wait?
6. If the brain isn't running and you say something only it could handle, should Petrovich tell you
   so loudly, as he does when the world model isn't loaded, or just say "unable"?
7. *"Keep an eye on him"* … two minutes … *"Still there?"* Should "him" carry over in this milestone,
   or later?
8. For flying (BL-16): should *"turn heading 3 1 5"* stay phrasebook-only? Is there anything, such as
   *"come left a bit"* or *"get us behind that ridge"*, that you'd expect the brain to turn into a
   flight command? Should *"you have controls"* ever be accepted from free speech?
9. If the brain notes something for you (*"remember this, AAA here"*), should it come back later
   clearly as your note rather than as something Petrovich saw?
10. After this milestone, does the brain ever act on its own initiative, or only ever when you have
    spoken?
