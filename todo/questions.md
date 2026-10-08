# Questions queued for the user

Created 2026-10-06, when the user handed over an autonomous overnight run and said:
*"Any input you need from me, queue and I'll get back to it."*

**Rules for this file**, so it stays usable rather than becoming a second backlog:

- One question per entry, with **why it blocks** and **what happens if it is not answered** — if the
  answer is "nothing blocks, I picked a default", it does not belong here; it belongs in the plan or
  commit that records the choice.
- An entry is removed when answered, and the answer goes to the plan, roadmap entry or decision list
  it belongs to — never left only here.
- Agents running in worktrees cannot reach the user. Anything they queue arrives in their report and
  is transcribed here by the main loop.

---

## Open

### ~~Q1 — `flight-feedback-clear.sh` cannot see a capture written through Bash~~ APPROVED AND DONE

**User, 2026-10-08: "approved."** Implemented the same day. The hook is now wired to the `Bash`
PostToolUse matcher as well as `Write|Edit`, and the Bash branch asks
`git status --porcelain -- docs/acceptance/` whether a feedback/sortie file actually changed instead
of looking for a `file_path` field that Bash payloads do not have. **Observe the effect, not the
instrument** — the same reasoning that made the gate structural.

It had misfired three times on 2026-10-08 before this landed.

**One thing changed during implementation, and it is the part worth remembering.** The first version
also checked `git diff HEAD~1 HEAD` so a capture written *and committed* inside one Bash call would
clear. That is wrong: it stays true for every later Bash invocation until another commit lands, so a
single acceptance-file commit would silently clear the gate for every unrelated command after it —
the one failure direction this hook must not have. Dropped it; working-tree only. A combined
write-and-commit that slips through costs an advisory warning, which is the safe way round. Five
regression cases run (no-marker no-op, bash+dirty clears, bash+clean keeps *even after an acceptance
commit*, write-to-acceptance clears, write-elsewhere keeps).

### ~~Q2 — `BL-B36`: the speech log is a verbatim transcript~~ ANSWERED — leave it as it is

**User, 2026-10-08, and the premise of the finding was wrong:**

> *"Audio only captures when I key the PTT. And the microphone is close to my mouth, does not pick
> ambient that well. Ignore, keep as it is now."*

So the log is not a transcript of the room — it is a transcript of **deliberate keyed transmissions**
into a close-talking mic. The security audit read `"Peace."` / `"All right."` / `"Can I sell it?"` as
ambient capture; they are the user talking *on the intercom*, which is exactly what the log exists to
record. No change, no opt-in, no hashing.

`BL-B36` is closed as **declined with reason**, not deferred: the privacy exposure it described rests
on ambient capture that the hardware does not do.

### ~~Q3 — `report` band slot: filter or sort hint?~~ ANSWERED — **filter**

**User, 2026-10-08: "filter."** Matches the literal reading and the Architect's recommendation. A
band narrows the answer rather than merely ordering it, so `report two o'clock near` does not mention
a tank at 2.1 km. Shorter answers are the point; the user can ask again with a wider band.

Recorded in `plans/crew-query-path/plan.md` Q1.

### ~~Q4 — Should air defence always survive the summary's aggregation?~~ ANSWERED — **yes**

**User, 2026-10-08: "air defense survives."** Air defence is named individually even when everything
else aggregates, with the length budget absorbing it by dropping the deferral clause. Consistent with
decision 6 (air-defence classes need positive confirmation to inherit an identity) and with the
project's own test — a summary that hides the one SAM among seven infantry has failed the pilot it
exists to serve.

Recorded in `plans/crew-query-path/plan.md` Q2.

### Q5 — Is ~25 words / ~10 s the right answer length?

Derived from **your own chosen moc### Q5 — Is ~25 words / ~10 s the right answer length? — **DEFERRED by the user, stays open**

**User, 2026-10-08: "cannot tell yet, we'll determine later."**

Left open deliberately rather than closed with a default: the current ~25-word budget came from the
user's own chosen mock B (24 words ≈ 10.2 s at `speech_duration_s`), so it is not a guess, and it
ships as-is. The question is whether it is still right in a hover under fire, which only flying it
answers. **Nothing blocks.** Revisit when a sortie produces an opinion.

### ~~Q6 — Do you recall the confirm prompt saying "report east, confirm?"~~ ANSWERED BY THE LOG

Withdrawn 2026-10-06 — you do not need to remember it. `~/dcs-speech.jsonl` records it directly: at
`t_sim 1585.1`, transcript `'report left.'`, **`acted_token: report_bearing_e`**. The diagnosis holds
on the live path, not just in the matcher. Recorded in `plans/post-review-fixes/explore-notes.md` §9.

---

## Decided without you, recorded so you can overrule

### D9's road corridor moved to `BL-8`, with a cheap stand-in now

You said *"units traveling on a road typically follow that road… They may turn at intersecions"*, and
decision 9 turned that into a directional corridor along the road graph branching at junctions.
Architect flagged it on effort/value and I took the recommendation:

**The graph traversal is a world-model milestone in a belief-layer costume.** World-model exposes
`nearest_road`/`nearest_junction` only as *point* facts inside `describe_position`, which is
**51.6 ms median** on `syria-full` — there is no traversal API. And at the belief layer's own
horizon it narrows a region that is not what is failing: 60 s × 8 m/s ≈ 480 m, against the measured
236–625 m median cluster-to-cluster separation. It pays for itself at `BL-8`'s ten-minute horizon
(≈4.8 km), which is where decision 10 already puts the long-horizon work.

**So: `BL-12` takes the cheap stand-in** — elongate the existing displacement bound along a
per-group *cached* `nearest_road.orientation_deg`. That captures "units follow roads" at roughly zero
cost, with no graph, no junctions and no per-tick query. The full corridor goes to `BL-8`.

Your model is unchanged; only where it gets implemented moved. Say if you want the full version in
`BL-12` anyway.

### Three tests get rewritten rather than extended

`AGENTS.md` says escalate when existing tests must be rewritten. These assert the invariant your
decision 5 inverts, so rewriting them *is* the decision taking effect rather than a surprise:
`test_contacts.py:132` (`test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`), `:183`
(reuses its geometry by name), and the `test_callouts.py:489-554` merge-echo fixture built on that
behaviour. Proceeding; flagged because the rule says to flag it.

### A watched group's range-crossing and motion lines become ONE line for the group

Performance found that `watch group <where>` tagging all N members turns one event stream into N —
8 members × 2 `describe_contact` calls ≈ **820 ms added to one tick** (1.6 s with motion events),
reproducible from a single player command on exactly the convoy case the feature exists to serve.
The fix reuses the suppression rule already applied to contact detections one branch above. It
needed a product call on the wording, and I took it rather than waking you.

**One line for the group**, not one member's line — because it is a direct application of decision 13
from the same conversation: *"B. I can also look myself, so a summary is good, I then know where and
what to look for."* A report aims your eyes; the answer's grain follows the belief's grain. It also
matches what detections already do for a grouped contact.

**Correction after implementation — my decision was only half-satisfiable, and the code already knew
why.** `_WATCHED_ONLY_KINDS`' own docstring, three lines above the block both reviews quote, had
already settled this: these kinds render through `_contact_report_text`'s affixes
(*"Getting closer, "*, *", moving"*), which `render_group_disclosure` has no concept of, **"so
folding one into a group's own line would silently drop the very fact the event exists to
report."** Neither review cited it and I did not know it when I decided.

So what shipped is **one line per group, spoken as the leading member's line with its affix intact**.
Eight lines become one — the flood and the 820 ms are gone, which was the point. What did *not*
change is that the line names one member rather than "the group". A genuine *"the group is getting
closer"* needs new templates carrying the affix at group grain, which is well beyond the six-line
mitigation and is its own slice. Say if you want it and I will scope it.

### `CONTACT_DETECTED` / `CONTACT_REACQUIRED` are now gated by observability too

The masked-hour fix gates **every** callout kind, not just the two that misfired. The Debugger's
reasoning: the defect's shape *is* a per-kind list that the next kind fails to join. Near-nil in
practice — both perception channels already respect the mask at founding — but it does mean a
contact founded ahead and spoken about several seconds later from astern now goes **quiet** instead
of arriving late. Narrowing it to the two kinds is a one-line change if you would rather hear it late
than not at all.

Related, and deliberately not decided: **this fix silences, it does not re-time.** Those 17 lines
become unspoken rather than spoken correctly. The contacts are still believed, still in the debug
view, still answerable by `report`. Whether some should reach you another way — an "I've lost sight
of it" marker — is a product question nobody has answered.

### ~~Q7 — Should the detection trace keep one `PLAYER_BUBBLE` row per out-of-bubble candidate?~~ ANSWERED — **drop them**, plus one more thing

**User, 2026-10-08:**

> *"drop them, if it does not disable the ASCII graph view. The detection lines below the graph are
> not necessary."*

**The condition is satisfiable, and the distinction is load-bearing** — checked before recording this,
because the first reading was wrong:

- Markers beyond the view radius are **clamped to the rim, not dropped** (`eyesight_view.py:448`,
  `clipped_rng = min(rng, radius_m)`, and the module docstring says so explicitly: *"a contact beyond
  `radius_m` is never silently dropped"*). So out-of-bubble objects **do** appear in the graph.
- But the live `--eyesight-view` builds its ground-truth half from the **in-memory
  `DetectionTraceCollector` snapshot**, not from the JSONL file (`logger.py:_eyesight_frame`'s own
  docstring).

**So: drop the rows at the JSONL writer, never at the collector.** A writer-level drop costs the
graph nothing. A collector-level drop would strip the rim markers — which is the ASCII view the user
is asking to preserve. Two changes that look alike and are not.

**Second ask, independent:** the lines printed *below* the graph are `render_frame`'s `beyond` list —
one line per believed/ground-truth marker past `radius_m`. Those go.

Both filed as `BL-B43` (writer-level row drop) and `BL-B44` (remove the `beyond` footer). Not done in
this turn: an Implementer is live on `body-layer` for `BL-11` Stage 4 and `logger.py` is in its blast
radius, so these wait for that branch to land rather than racing it.

### `CONTACT_ENGAGEMENT_CHANGED` is excluded from the observability gate

The Reviewer found that the masked-hour gate silently covers a **third** kind nobody had named:
`CONTACT_ENGAGEMENT_CHANGED`, minted by `ContactStore.tick`'s seventh block, which was never gated
at emission and is caught by the new gate because the gate discriminates on the *contact*, not the
kind.

That one is a **threat warning about a contact you already asked to watch**. And because
`CALLOUT_OBSERVABILITY_GRACE_S == CALLOUT_MAX_AGE_S == 10.0`, a watched threat masked for more than
ten seconds loses the callout **permanently, not late** — a SAM or ZSU astern that starts being able
to shoot at you simply goes quiet.

**Decided: exclude it.** Gate the identification kinds totally, let threat-envelope changes through.
The reasoning, in case you disagree: an envelope change is not an identification. It is derived from
a contact Petrovich **already perceived** plus your own position, so it invents no knowledge — a real
copilot who saw a SAM twenty seconds ago would say "we're inside its range now" without eyes on it.
Set against that, silence about a threat you cannot see is the exact case root `CLAUDE.md` says he
exists for (*"helps the pilot evade dangerous units"*), and your own decision 6 already singles air
defence out for special handling for the same reason.

Implemented as a **named, documented exclusion** rather than a buried condition, because this whole
defect was a per-kind list that the next kind silently failed to join, and an exclusion list has the
same failure shape in reverse.

### `CALLOUT_OBSERVABILITY_GRACE_S = 10.0` is now load-bearing for three more paths

Still an untuned starting value by its own docstring, and because it equals `CALLOUT_MAX_AGE_S`,
anything masked for over ten seconds is **dropped rather than deferred**. Not a decision needed now —
a sortie can measure it, and nobody has changed the number.

### ~~Q8 — Should *"Safe from <threat>"* survive the observability gate?~~ ANSWERED — **yes, but it needs mission memory first**

**User, 2026-10-08:**

> *"mission memory will let Petrovich remember where that threat was -> safe from is realistic. But
> only from mission memory, that is needed first."*

This settles the argument rather than picking a side of it. The reviewer's case (*a pilot who heard
"Danger" is owed the "Safe from" that closes it*) is **accepted in principle** — an unclosed warning
leaves the pilot believing they are still inside an envelope they have left. The orchestrator's
narrowing was right **for now**, and for a reason neither side had stated: a close-out call about a
threat he can no longer see is only honest if he *remembers where it was*, and that memory does not
exist yet.

**So the current behaviour stands — entering transition only — and this becomes a dependency rather
than a disagreement.** When the memory layer (`BL-8`) can supply a remembered threat position, the
close-out call becomes licensed by that memory rather than by the live percept, and the bar becomes
"a threat-envelope transition either way, where the leaving call is sourced from mission memory."

Filed as `BL-B45`, explicitly gated on `BL-8`. The one-line reversal is **not** taken now: doing it
without the memory layer would reintroduce exactly the no-omniscience violation the gate was built to
close.

### ~~Q9 — Three research asks open across multiple sessions~~ ANSWERED — all three closed

**User, 2026-10-08: "Drop points 2 and 3. I'm pasting the forum content below."**

1. **The `Export.lua` destroyed-object thread — read, and it answers nothing.** Full writeup:
   `aircraft-layer/research/2026-10-08-export-lua-destroyed-object-forum-thread.md`. Three posts over
   sixteen months, no solution; the asker gets stuck on `coalition` being nil in `Export.lua` and a
   `world.addEventHandler` that does not fire there, and nobody ever replies. **The destroy/respawn
   object-id lifecycle question is untouched by it.** Closed as *read, no finding* — which is worth
   the paste anyway, because it stops a fourth session reopening the URL.

   Two incidental confirmations kept: `Export.lua` state genuinely has no `coalition`/`world` (an
   independent 2018/2020 attestation of the state separation this project already bridges with
   `net.dostring_in("scripting", ...)`), and `unit:getLife()` plus `S_EVENT_DEAD`/`S_EVENT_CRASH` do
   exist in the *scripting* state, which is where a future damage feed would have to call them.
   MIST was mentioned and is declined — it is a dependency on the mission author's setup, and this
   project flies others' missions.

   And the risk has largely dissolved from another direction: the id-lifecycle question was a risk on
   the `Unit:getID()` branch, which the 2026-10-06 probe ruled out anyway (`getObjectID` does not
   exist on `StaticObject`, so the join key stays `getName()`).

2. **Mobile TELAR spacing — DROPPED** by user direction. Recorded as not worth the time rather than
   unresolved, so it is not re-attempted.
3. **The unparseable RUSI PDF — DROPPED**, same direction, same reason.
