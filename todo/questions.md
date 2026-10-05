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

### Q1 — `flight-feedback-clear.sh` cannot see a capture written through Bash (config change, needs your ok)

**What happened:** the feedback-capture hook fired correctly when you raised the two review items,
and then stayed up after the capture was written — so it warned on every later Architect dispatch
even though the feedback was captured *and* explored. `flight-feedback-clear.sh` is `PostToolUse` on
`Write|Edit` and matches `.tool_input.file_path`; the capture went into
`docs/acceptance/2026-10-05-sortie-feedback.md` via a Bash heredoc, which has no `file_path` field,
so the marker never cleared. I cleared it by hand.

**Why it will keep happening:** this session runs with an auto-mode instruction to prefer Bash for
file edits, so the common path for writing a file is exactly the one the hook cannot observe.

**Proposed fix:** add `Bash` to the clear hook's matcher and have it clear the marker when
`git status --porcelain docs/acceptance/` shows a change, rather than reading `file_path`. That makes
the hook observe the *effect* instead of the *instrument*, which is the same reasoning that made the
gate structural in the first place.

**Needs you because** it edits `.claude/settings.json` hook wiring, and I do not change your hook
configuration on my own judgement. Nothing blocks meanwhile — the gate is advisory and never blocks
a dispatch.

### Q2 — `BL-B36`: the speech log is a verbatim transcript of everything the microphone heard

From the 2026-10-05 security audit. The sortie log contains `"Peace."`, `"All right."`,
`"Can I sell it?"` — you talking, not commanding. Harmless on your own machine; this repo is
**intended to go public**, and a committed or shared log is a voice transcript of your living room.

**Three options, and it is your call which:** hash or omit non-command utterances; keep the full
transcript but make the log opt-in with that stated in `RUN.md`; or leave it and rely on never
sharing the file. I would take the second — the full transcript is genuinely useful for diagnosing
`say_again` cases, which is exactly what it earned its place for.

**Does not block** anything in flight. It blocks a public release.

### Q3 — `report` band slot: filter, or sort hint? (`plans/crew-query-path/plan.md`, Q1)

You asked for `report|describe [what] [where] [how far]` with bands near <2 km / medium 2–5 km /
far 5 km+. The plan needs to know whether the band **filters** or merely **orders** the answer.

Literal reading is a filter, and it gives a shorter answer — but then a tank at 2.1 km goes
unmentioned to someone who asked about two o'clock. Architect recommends filter. **Not blocking:**
Stage 1 ships the grammar without the band's semantics being settled.

### Q4 — Should air defence always survive the summary's aggregation? (`plans/crew-query-path/plan.md`, Q2)

A summary can hide the one thing that mattered — one SAM among seven infantry. Architect
recommends air defence is **always named** even when everything else aggregates, with the length
budget absorbing it by dropping the deferral clause. This interacts with decision 6 (air-defence
classes need positive confirmation to inherit an identity), so the two should be answered together
if you disagree with either.

### Q5 — Is ~25 words / ~10 s the right answer length?

Derived from **your own chosen mock B** (24 words ≈ 10.2 s at `speech_duration_s`), not guessed. But
you read that mock on the ground. It may be too long in a hover under fire, and the honest answer is
that only flying it will say.

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

So you will hear *"the group is moving"* / *"group at two kilometres"* rather than up to eight
separate member lines. Say if you want member-level lines back for watched groups specifically.

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

### Q7 — Should the detection trace keep one `PLAYER_BUBBLE` row per out-of-bubble candidate per poll?

`BL-11` Stage 5 rolled the logs per run and halved the bytes, so the trace is now ~25 MB/min rather
than ~50 — but **60–80 % of what remains is still `PLAYER_BUBBLE` rows**, one per candidate that was
never evaluated, each carrying one bit of information ("further than 10 km") that any other row's
`true_range_m` already implies.

Dropping them behind a flag is a ten-line change. **The reason I did not do it unasked**: you have
been reading the debug ASCII view off these rows, and what gets recorded is a product decision, not
a performance fix. Perf review recommended dropping them; I overrode that on those grounds.

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

