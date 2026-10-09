# BL-B44 — Remove the detection lines below the eyesight graph

- [ ] **BL-B44 — Remove the detection lines printed below the ASCII eyesight graph.** #status/open User direction
  2026-10-08, same answer: *"The detection lines below the graph are not necessary."*

  These are `render_frame`'s `beyond` list (`eyesight_view.py`) — one line per believed or
  ground-truth marker past `radius_m`, nearest-first. The graph already shows them clamped to the
  rim, so the footer restates what the rim conveys.

  Independent of [[BL-B43]] (that one is about the JSONL file; this one is about the terminal), but
  both came from the same answer and both touch the same subsystem, so they are worth doing together.
