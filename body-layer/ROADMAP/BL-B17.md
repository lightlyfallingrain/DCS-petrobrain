# BL-B17 — `certainty`/classification fusion is last-writer-wins

- [~] **BL-B17 — `certainty`/classification fusion is last-writer-wins — classification half resolved by
  [[BL-2.6]], certainty half still open.** #status/in-progress `Contact.classification` no longer overwrites on last-write
  ([[BL-2.6]]'s `fold_classification`). `decay.certainty_of` is still a pure function of
  `now_sim - last_seen_sim` with no notion of which contributing observation had tighter position
  uncertainty or which channel produced it — a tight naked-eye observation followed by a
  wider-uncertainty scope observation still fully resets `certainty` to `"observed"`. Reworking into
  a quality-weighted ladder is a real design question (what "better" means across channels with
  different uncertainty models), not a quick patch — revisit once real sortie data shows it actually
  degrading perceived contact quality.
