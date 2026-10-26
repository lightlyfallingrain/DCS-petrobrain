# "that" / "it" referent — explore notes (2026-10-26)

Entry: `body-layer/ROADMAP/BL-B102.md` (the user's request, verbatim). Branch:
`feature/that-it-referent`.

## State found before the conversation (measured, not assumed)

- Spoken lines reach `CrewConsole._print` as bare strings. Nothing records which contact or group a
  line was about.
- `audio-adapter`'s `match_transcript`, today:

  | said | matched as | problem |
  |---|---|---|
  | "where is it" / "where is that" | `where_is_it` → attack target | wrong referent if he last spoke about something else |
  | "follow that group" | `follow {descriptor: group}` → nearest group | silently wrong pick |
  | "engage that 11 o'clock armor, missiles" | `engage {armor, 11, missiles}` over all contacts | "that" ignored |
  | "mark that" | `mark_target` (ratio 0.80) | target, not referent |
  | "target it", "follow it", "mark it", "watch that", "where is that AAA" | no match → "say again" | — |

- Prior design: `plans/inbound-speech/plan.md` "Command chaining" — the matcher stays stateless,
  resolution happens in body; ambiguity asks rather than guesses.

## Mock shown

```
P:  "AAA, 2 o'clock, far."                       mention → [AAA#7]
Pl: "Where is it?"                               → AAA#7
P:  "2 o'clock, 6 km, east of Kobuleti."
Pl: "Describe."
P:  "Group 11 o'clock, armor and trucks.          mention batch → [G3, G5]
     Group 2 o'clock, armor, moving east."
Pl: "Follow that moving group."                  → filter batch by qualifier → G5
Pl: "Engage that 11 o'clock armor."              → G3 → armor unit inside G3
Pl: "Target it." (90 s later, nothing said)      → expired
```

## Decisions (user, 2026-10-26)

1. **"Where is it" during an attack run means the last-talked-about contact, not the target.**
   Accepted as proposed. "Where is target" stays bound to the attack target.
2. **The last line wins — every line with a subject sets the referent, attack-run steering lines
   included.** User: *"last line. "where is that AAA" would the point to the AAA line (unless attack
   target is AAA which would take priority)"*. So the proposal to exempt repeated steering lines was
   rejected. A **qualified** referent ("that AAA") searches the recent mentions for a match rather
   than taking the last line; if the attack target itself matches the qualifier, the target wins.
3. **A group line and a unit verb ("target it" after "Group 11 o'clock, armor and trucks") pick the
   group's lead / most threatening member.** "That group" always takes the whole group. User: *"yes"*.
4. **The referent lives ~60 s (tunable). It does not die when the contact stops being seen — the
   answer comes from belief.** User: *"time ok, but use belief if not visible"*. So the proposal to
   kill the referent on `lost` was rejected: within the window, an unseen contact still resolves,
   and anything spoken about it uses its believed position. No omniscience issue — belief is what he
   holds.
5. **"Moving" as a qualifier is deferred.** User: *"defer moving"*. This cut handles clock, type and
   "group" qualifiers only.
6. **No new pronoun vocabulary.** User: *"keep current vocabulary"* — "it" and "that" only; not
   "him", "this one", "the second one".

## Not decided here, for the plan

- Which commands accept a referent: the contact-taking ones already in the vocabulary
  (`where_is_it`, `follow`, `select_target`, `engage`, `mark_target`, and the `watch` family) — the
  user said not to build new commands, so a referent form is a slot on an existing token, not a new
  token. "Where is that AAA" follows from decision 2 and needs a descriptor slot on `where_is_it`.
- What "where is it" says for a non-target referent: the user's own shape, *"<o'clock> <distance in
  km> <world ref>"*.
