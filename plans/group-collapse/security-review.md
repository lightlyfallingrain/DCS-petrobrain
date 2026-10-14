## Security Deep Analysis: group-collapse (Stages 1-4)

Reviewed `feature/group-collapse` at `ed50840a2b43ef117773f4624951eb9a0c6c960b` (worktree HEAD
`f25c57c` was a strict ancestor on a clean tree; fast-forwarded, confirmed by `git rev-parse HEAD`
after). Read `plans/group-collapse/plan.md`, `implementation.md`, `review.md`,
`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md`, and every file the task named in
full: `belief/group_view.py`, `belief/speech.py`, `belief/tools.py`, `belief/groups.py`,
`belief/classification.py`, `belief/percept.py`, `belief/contacts.py`, `belief/cardinality.py`,
`belief/callouts.py`, `belief/position_belief.py`, plus the full diff `cbf4c1e..ed50840`.

### Dependency Status

No dependency change. Nothing new in `pyproject.toml`; no new import source. Matches the plan's own
central claim ("nothing new is stored and no new input source is introduced") — verified by reading
`group_view.py`'s import block directly, not taken on the plan's word.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `belief/group_view.py` (whole file) | no-omniscience boundary | **Verified independently, not just re-confirmed from the Reviewer's grep.** Imports are `belief.classification`, `belief.classification.SpecificityLevel`, `belief.contacts.{Contact,ContactStore}`, `belief.decay.classification_confidence_at`, `belief.groups.Group` — nothing from `perception/`, no `last_class_raw`, no `describe_contact`, no `profile_for`. The `CONTACT`-depth leaf's `x`/`z`/`radius_m`/`contact_id` (the deepest, most identity-revealing rung this feature adds) are `Contact.position.x`/`.z`/`.radius_m()`/`.id` — fields already exposed in `facts["position"]["dcs"]` by `tools.py:349` for any single contact. This derivation surfaces nothing that was not already legitimately in belief and already reachable through an existing fact. | None |
| `belief/group_view.py` `CollapseDepth`/recursion | unbounded depth / recursion | **Not reachable.** `depth: CollapseDepth` is an `IntEnum` with no runtime validation against out-of-range `int`s, but `grep -rn "CollapseDepth(" src/` (excluding the class definition itself) finds zero dynamic construction anywhere in the merged code — both call sites (`tools.py`, `speech.py`) pass the literal constants `CollapseDepth.SUBCLASS`/`CollapseDepth.TYPE`. No path from console input, voice command, or brain reply constructs a `CollapseDepth` value. The tree itself cannot recurse unboundedly: the four explicit per-level functions (`_class_children` → `_subclass_children` → `_type_children` → `_contact_children`) each advance exactly one level and never re-enter a shallower one — traced by hand, confirming the implementer's own account of why the earlier generic-dispatch draft looped (a `SUBCLASS` remainder re-entering its own dispatch) cannot recur here. `_LEAF_LEVEL_WORD`'s partial-over-`{SUBCLASS,TYPE}` table in `speech.py` is only ever indexed with a leaf produced by `collapse_members(..., CollapseDepth.TYPE)`, and tracing `_class_children`→`_subclass_children`→`_type_children` at `max_depth=TYPE` shows a leaf can only be `SUBCLASS` or `TYPE` at that depth — never `CLASS`/`CONTACT`/`GROUP`. The implementer's own mutation (`TYPE`→`CLASS`) turning this into a live `KeyError` is consistent with, not contrary to, this being unreachable in the merged code. | None |
| `belief/callouts.py:1140-1220` | resource exhaustion on push path | `render_group_disclosure` **is** called every poll for every group with at least one observable member (confirmed by reading, not assuming) — this is the push path the plan measured (`probe_collapse_cost.py`: ~78 µs/tick at 10 groups × 6 members, full `TYPE` depth, against a 12.6 ms poll = 0.6%). No new unbounded-growth mechanism is introduced: group/member counts are bounded upstream by clustering/cohesion (unchanged by this feature), and this same loop already calls the far more expensive per-member `describe_contact` path (`BL-B49`: 63.25 ms/contact cold) for the very same groups. A pathological scene that stresses this loop stresses the pre-existing `describe_contact` cost by orders of magnitude before `collapse_members` becomes material. | None |
| `belief/group_view.py` `_contact_leaf` | non-finite position | `member.position.x`/`.z` flow into the `CONTACT`-depth leaf unguarded at this call site, but `position_belief.py:739-741` already enforces `math.isfinite` on fused `x`/`z` at the fusion boundary (the forest-occlusion fix merged the same day, per `git log`), fail-open. By the time a `Contact` exists for `collapse`/`collapse_members` to read, its position is already guaranteed finite upstream — this feature adds no new unguarded arithmetic on a potentially non-finite value, it reads an already-validated field. | None |
| `belief/cardinality.py` `OP_MORETHAN15UNITS`/`UNKNOWN` buckets, summed in `group_view._units_hi` | non-finite value, latent | **Low-risk, not a defect requiring a fix in this stage.** `CardinalityBelief.hi` is `math.inf` by design for the `OP_MORETHAN15UNITS` (>15 units, reachable via `perception.clustering.count_bucket_for`) and `UNKNOWN` buckets. `group_view._units_hi` sums `member.cardinality.hi` across a bucket's members with no guard, so `CollapseNode.units_hi` (and every ancestor's, summed up the tree) becomes `math.inf` whenever any contributing member holds that bucket — a real, reachable value, not a theoretical one. `tools._collapse_node_to_dict` passes it through unguarded into the `facts["group"]["tree"]` dict. **Why this is not yet exploitable:** no current consumer does `int()`/`math.floor()`/`round()` on `units_hi` (grepped: only `group_view.py` and `tools.py` reference the field at all), and no current serialization path strict-JSON-encodes this dict — `console.py`'s `show <id>` renders it via an f-string (`inf` prints as the literal text `inf`, no crash), and the only `json.dumps` call reachable from belief state (`brain_client.py:246`, the escalation payload) carries a different, already-int, lower-bound figure (`_estimated_units_lower_bound`), not this tree. See risk statement below. | See below — presented, not auto-fixed |
| `belief/groups.py` Stage 4 diff | matcher behaviour change | Confirmed behaviourally identical to the prior `- AIR_DEFENSE_OP_CLASSES` carve-out by reading both forms directly: `CLASS_GROUP_OF`'s domain *is* `AIR_DEFENSE_OP_CLASSES` (one dict comprehension over that exact frozenset), so `CLASS_GROUP_OF.get(c, c) != "air defense"` and `c not in AIR_DEFENSE_OP_CLASSES` partition identically. No new matching surface. | None |
| `belief/group_view.py` thread safety | shared mutable state | `collapse`/`collapse_members` are pure functions over their arguments — every intermediate structure (`buckets`, `typed`, `remainder`, `children`) is function-local, no module-level mutable state, no `@lru_cache`, no sqlite access of any kind. Confirmed by reading the full file; nothing to race on. | None |
| `belief/speech.py` `_contact_for_member_facts` | internal data trust | `SpecificityLevel[level_name.upper()]` and the `isinstance` guards on `cardinality_facts` would raise `KeyError`/produce wrong defaults on malformed input, but the only producer of this dict is `tools.py`'s own facts builder (`.name.lower()` of a real `SpecificityLevel`), reached only through `_group_member_facts`/`describe_contact` on belief's own store — never external/untrusted input (no DCS object, no network payload, no console text reaches this shape). Not reachable from outside the process. | None |

### The `OP_GROUPSOMETHING` wording divergence

Not re-litigated here — this is a product/wording question the Reviewer already surfaced, the
implementer resolved with a pinning test
(`test_speech.py::test_group_composition_clause_folds_op_groupsomething_into_undifferentiated`,
confirmed present), and `STRUCTURE.md`'s Stage 3 entry is confirmed updated. No security content:
it changes which phrase Petrovich speaks for one classification value, not what data reaches him or
the pilot.

### Risk Communication — `units_hi` can propagate `math.inf`

**Finding:** A group containing a contact held at the `OP_MORETHAN15UNITS` or `UNKNOWN` cardinality
bucket produces a `CollapseNode.units_hi` of `math.inf`, propagated to every ancestor node up to the
group root, and passed through unguarded into `facts["group"]["tree"]`.

**Location:** `body-layer/src/belief/group_view.py:154` (`_units_hi`), surfaced via
`body-layer/src/belief/tools.py:278` (`_collapse_node_to_dict`).

**Probability:** low-medium — `OP_MORETHAN15UNITS` requires a single naked-eye cluster of >15
units, an unusual but real battlefield scene; `UNKNOWN` requires a cardinality contradiction
collapse, also real but less common.

**Impact:** low today — nothing currently consumes `units_hi` arithmetically or strict-JSON-encodes
this particular dict, so no crash or wrong-value path exists right now. The impact is forward-facing:
this project has fixed the same shape of defect (an unguarded non-finite float reaching an
integer conversion or a strict serializer) three times in one day elsewhere in body-layer
(`position_belief.py` ×2, `perception/forest.py` ×1). The first future caller that does
`int(units_hi)`, renders it through a template expecting a bounded number, or serializes `facts`
through a strict JSON encoder (e.g. a future brain-layer HTTP surface for this fact) inherits this
silently.

**Recommended action:** not a fix in this stage — no live consumer is affected, and guessing at a
representation (cap at some large int? keep `math.inf`? render as `"15+"`?) now would be inventing
policy ahead of the attention-tier work that is this field's actual consumer. Worth a one-line note
in `group_view.py`'s own docstring (next to the existing "never `len(members)`" note) so the next
caller that reaches for `units_hi` arithmetically sees the warning before, not after, it bites.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md / BL-B61-adjacent backlog item — fix when a real consumer needs units_hi arithmetically
  (C) Fix now — add a docstring note (no code change) before merge
  (D) Stop — do not proceed until resolved

My recommendation is (C), since it costs one sentence and this project has a specific, recent,
three-times-paid lesson about exactly this shape of latent defect — but this is not blocking, and I
am not withholding approval over it.

### Verdict

**APPROVED.**

No confirmed exploitable vulnerability and no probable risk in the feature diff. The no-omniscience
boundary holds under independent verification (not just re-checking the Reviewer's grep), depth/
recursion is both logically bounded and never constructed from untrusted input, the push-path cost
is the same linear, already-measured profile the plan committed to and is dwarfed by the pre-existing
`describe_contact` cost in the same loop, non-finite position is already guarded upstream, and the
matcher change is confirmed behaviour-identical. The one latent finding (`units_hi` → `math.inf`) is
presented per the risk-communication format above rather than silently accepted or used to block —
it is real but not exploitable today, and the fix would be guessing at policy this feature's own
scope correctly defers.

### Checks run (from inside `body-layer/`, this worktree's own `src`, confirmed by import-path check)

- `ruff check src tests`: pass
- `mypy src` (strict, 57 source files): pass
- `pytest`: **1748 passed, 4 xfailed** — matches the expected baseline exactly
