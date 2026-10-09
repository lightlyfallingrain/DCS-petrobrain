# AA-B1 — Voice character — accent and prosody

- [ ] **AA-B1 — Voice character — accent *and* prosody.** #status/open Currently a generic English voice. Two distinct
  problems, and the second was not obvious until it was heard aloud (user, 2026-09-18): no
  Russian-accented English voice exists in macOS `say`, **and the delivery is monotonous** — flat
  pitch and even stress regardless of whether the line is a routine contact report or "break
  right". Out of scope while the pipeline was being built; worth separating when picked up, since
  prosody may matter more for believability than accent does, and the two have different fixes
  (a different engine or voice for accent; SSML, per-line rate/pitch, or an urgency-aware
  template for prosody). Auditioning candidates costs one `--target local --voice <name>` command
  each. See `body-layer/ROADMAP.md`'s backlog entry.
