# BL-B75 — Smoke and flare markers as emitters, if DCS exports them

- [>] **BL-B75 — Static smoke, signal smoke and signal flares are visible far away for the same
  reason a fire is, and would ride the same gate bypass — *if* they are exportable at all.**
  #status/deferred Filed 2026-10-15 from user direction, explicitly as the lowest-priority member of
  the emitter family: *"If we get export info on DCS static smokes, signal smokes, signal flares,
  add them too. This is lower priority and can be left out, but if easy then do."*

  **The conditional is the whole item.** If these turn out to be exportable, they are nearly free —
  the `emitter` bypass built for `[[BL-B72]]` takes them with no new mechanism, no new transport and
  no new gate behaviour. If they are not, the item is closed rather than worked around. **It is
  therefore an Investigator question before it is an Architect one**, and the probe is small.

  ## What is actually unknown

  Mission-created smoke and flares come from `trigger.action.smoke()` / `.signalFlare()` and are
  **effects, not units**. Nothing establishes that they appear in `LoGetWorldObjects` — and there is
  a directly relevant precedent pointing the other way: the 2026-09-24 probe found **gun rounds are
  not world objects while rockets are**, so "it is visible in the sim" has already proven to be a
  poor predictor of "it is in the object table". Expect the same split here and probe rather than
  assume.

  If they are absent from the object table, the fallbacks are the same shape as the firing case —
  an event, or a per-trigger record over the mission-scripting bridge — and are **not obviously
  cheap**, which is where the user's *"can be left out"* bites.

  ## ED's own Petrovich already speaks smoke

  Worth recording because it settles whether this is a real crew behaviour or our invention:
  `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` lists the
  HelperAI phrase vocabulary, and its "Other" row is **`OP_LAUNCH` plus smoke colours
  (`OP_WHITESMOKE` … `OP_BLACKSMOKE`)**. So the stock operator reports smoke, by colour, and a
  launch — two of the four emitter kinds this family is building. That is evidence about the
  *behaviour being right*, not about our export path, and the two must not be confused: the
  vocabulary existing in ED's model says nothing about whether the underlying state is reachable
  from outside the aircraft's own Lua.

  ## Different in kind from the other three emitters, and the design should say so

  `[[BL-B72]]`/`[[BL-B73]]`/`[[BL-B74]]` are all **involuntary** — a unit firing, launching or
  burning gives itself away. **Signal smoke and flares are deliberate markers**, usually friendly,
  and often mean *look here* rather than *something dangerous is here*. The same visibility
  mechanism serves both, but the callout and the belief do not:

  - A marker's **colour carries meaning** assigned by the mission, which Petrovich has no way to
    interpret — he can report *"green smoke, ten o'clock"* and must not infer what it signals.
  - A marker is **not a contact**. Admitting it as a `PRESENCE` contact would put a smoke grenade in
    the contact store alongside vehicles, which is almost certainly wrong — and is the first
    question any plan here has to answer.

  Related: `[[BL-B72]]` (the gate bypass this would reuse), `[[BL-B73]]`, `[[BL-B74]]`,
  `[[AC-B8]]` (the event channel, if the fallback path is needed).
