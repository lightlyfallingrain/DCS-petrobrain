# WM-B5 — Valley boundary extraction

- [ ] **WM-B5 — Valley boundary extraction: where a valley *ends*, not just where its floor runs.** #status/open
  **This entry was written 2026-10-05, after an audit found `WM-B5` cited in [[WM-B6]]'s parking list
  and in several plans while no entry defining it existed anywhere in this file.** The ID was in use
  before it was declared; it is written down here rather than renumbered, per the never-reuse rule.

  What it means: the stored `valley` rows are **centre lines**, not extents. A pilot asking whether
  a contact is *in* a valley is asking about an area, and the line cannot answer it — which is
  exactly the gap `plans/terrain-feature-probing/`'s Revision 3 works around with a nearest-line
  dominance rule rather than closing. The honest versions are a per-vertex half-width (cheap, keeps
  the `LineString` shape, consumers unchanged) or a real polygon (expensive, new geometry type, new
  storage question).

  **Not scheduled, and deliberately so**: Revision 3's dominance rule is the cheap approximation,
  and whether it is good enough is a listening question the next sortie answers. Revisit only if
  flying shows "in a valley" landing on contacts that are plainly not in one.
