# AA-B1 — Voice character — accent and prosody

- [ ] **AA-B1 — Voice character — accent *and* prosody.** #status/open Currently a generic English voice. Two distinct
  problems, and the second was not obvious until it was heard aloud (user, 2026-09-18): no
  Russian-accented English voice exists in macOS `say`, **and the delivery is monotonous** — flat
  pitch and even stress regardless of whether the line is a routine contact report or "break
  right". Out of scope while the pipeline was being built; worth separating when picked up, since
  prosody may matter more for believability than accent does, and the two have different fixes
  (a different engine or voice for accent; SSML, per-line rate/pitch, or an urgency-aware
  template for prosody). Auditioning candidates costs one `--target local --piper-voice <name>`
  command each (Piper server started with that model available). See `body-layer/ROADMAP.md`'s backlog entry.

  **Accent candidate, 2026-10-19: Piper's `ru_RU-ruslan-medium`** (user: *"would be perfect"*).
  Arrives with [[AA-6]], which moves synthesis to Piper on both OSes with
  `en_GB-northern_english_male-medium` as the default voice, so trying `ruslan` becomes a matter of
  pointing the engine at a different model file. Untested; two ways it could be used:

  - **Feed it the English text as-is.** Expected to be unreliable: Piper phonemizes with the
    voice's own language (espeak-ng `ru`), so Latin text is read by Russian rules, and the model
    has only learned Russian phonemes (no English *th*, *w*, short *a*). Likely somewhere between
    heavily accented and garbled, varying word to word. Cheap to confirm by ear.
  - **Idea: transliterate the English line into Cyrillic first** — *"Контакт, ту о'клок, сри
    километрс"* for *"Contact, two o'clock, three kilometres"* — so `ruslan` reads it as Russian,
    which should come out as English spoken with a genuine Russian accent: a Russian pilot speaking
    English. Costs a transliteration step between body-layer's text and synthesis (an
    audio-adapter concern — body-layer and the brain stay text-only), plus an exceptions list for
    words the rules mangle. Petrovich's vocabulary is small and closed (clock bearings, ranges,
    unit types, a few verbs), which is what makes a hand-tuned table plausible here at all.

  Either test is one ~60 MB voice download into the Piper voices directory
  (`research/2026-10-19-piper-cross-platform-recon.md`; Piper is the `piper-tts` venv, not a binary —
  see the recon's 2026-10-20 addenda).
