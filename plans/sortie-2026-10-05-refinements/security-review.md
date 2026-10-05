# Security Deep Analysis: sortie-2026-10-05-refinements (items 2/3/4)

Branch `feature/sortie-refinements`, tip `18da60e`, verified by `git rev-parse HEAD` before
any file was read. The worktree was created on `main` (`19143fa`) — the AGENTS.md rule 4 trap —
and was detached onto `18da60e` before review; nothing below was read off `main`.

Diff base: `896369e` (merge-base with `main`). Source files in scope:
`audio-adapter/src/vocabulary.py`, `body-layer/src/belief/crew_console.py`,
`body-layer/src/belief/speech.py`, `body-layer/src/perception/gaze.py`.

## Dependency Status

No dependency change. Nothing added, removed or version-bumped in any `pyproject.toml`; the
diff introduces no import that was not already in use. No CVE search was owed.

## Scope notes

- Knowledge-graph query was attempted (`.claude/scripts/gq.sh`) and is **unavailable in a
  worktree**: `graphify-out/` is gitignored, so the script answers `No graph yet`. Reported
  rather than skipped silently. Conclusions below rest on reading the code, not on an absence
  of documentation.
- Neither subproject has a `.venv` inside the worktree and `pytest` is not on `PATH` here, so
  the suites were not re-run (Reviewer already ran them; DoD runs them again). This does not
  weaken the findings: the one empirical claim below was produced by executing
  `command_matcher.match_transcript` directly, which needs only the stdlib.

## Code Findings

| # | File:Line | Pattern | Assessment | Action |
|---|---|---|---|---|
| 1 | `body-layer/src/belief/crew_console.py:1271-1281` | unobserved failure + overstated count in speech | Real, new, small | **REQUIRED FIX** |
| 2 | `audio-adapter/src/vocabulary.py:323-329` | new fuzzy-match false positives (`descend`, `prescribe`) | Instance of an accepted pre-existing class | Note / user decision |
| 3 | `body-layer/src/belief/crew_console.py:1639` | `report_all` speaks rear-hemisphere clock hours by design | Pre-existing decision, not this branch | Queued for user (touches the live gate fix) |
| 4 | `body-layer/src/belief/crew_console.py:1273` → `tools.watch_contact_task` | unbounded task creation × group size | Growth, fully cancellable | Note (performance-reviewer's call) |
| 5 | `body-layer/src/logger.py:676-709` | watch-priority inversion in the look queue | Behavioural, not a vulnerability | Note |

---

### 1. REQUIRED FIX — `_mark_watched_with_group` discards every member's success flag and speaks a count it did not verify

`body-layer/src/belief/crew_console.py:1271-1281`

```python
        found = False
        for member_id in member_ids:
            ...
                ok = set_attention(self.store, member_id, "watch", source=source)
            if member_id == contact_id:
                found = ok
        return found, len(member_ids)
```

`ok` is computed for every member and then thrown away for all of them except the one the
resolver picked. The returned `group_size` is `len(member_ids)` — the *intended* member count,
not the number of members actually marked — and `crew_console.py:1326-1327` / `1492-1493` speak
it as `"Watching four."`.

**Failure scenario.** `Group.member_contact_ids` is recomputed from the live `Contact` set by
`GroupStore.reconcile` (`belief/groups.py:553`), so between a reconcile and the next command a
member id can stop resolving to a live `Contact` — it is also the only reason `found` exists for
the resolved contact at all. When that happens, `watch_contact_task`/`set_attention` returns
`False` for that member, nothing is watched, no task is created, and Petrovich still says
"Watching four". The pilot has no way to observe the discrepancy: the un-tagged member produces
no range-crossing callouts, and the only evidence is its absence. This is exactly the shape
`render_group_disclosure` already refuses — it returns `None` unless at least two members still
resolve to a live `Contact` (`belief/speech.py:1573-1575`) — so the branch introduces a readback
that is *less* careful than the renderer it sits next to, about the same group.

Severity **low** in consequence (one unreported vehicle, no wrong claim about the world beyond
the count) but it is a spoken assertion that the code did not check, in new code, and the project's
core invariant is about not saying things that are not backed. The fix is local.

**Fix.** Count what actually succeeded and report that:

```python
        found = False
        marked = 0
        for member_id in member_ids:
            ...
            if ok:
                marked += 1
            if member_id == contact_id:
                found = ok
        return found, marked
```

`marked` is then `0` when the resolved contact itself failed (the existing `if not found` branch
already covers that), `1` for the single-contact case, and the honest member count otherwise —
the `group_size > 1` branch keeps working unchanged, and a group that lost members since the last
reconcile falls back to the single-contact readback rather than overstating. Update
`_mark_watched_with_group`'s own docstring (`:1260-1264`), which currently promises "the real
member count".

---

### 2. NOTE — `describe` adds two new single-word false positives, one of which is a real aviation word

`audio-adapter/src/vocabulary.py:323-329`

Measured directly against `command_matcher.match_transcript` with this branch's table and, for
comparison, with the `896369e` baseline table:

| transcript | baseline | this branch |
|---|---|---|
| `"descend"` | `token=None` | `report_all`, ratio **0.667** |
| `"prescribe"` | `token=None` | `report_all`, ratio **0.823** |
| `"described"` | `token=None` | `report_all`, ratio 0.941 |

The implementation note in the diff is accurate about *sentences* — `"describe the mission to
me"`, `"describing the situation"`, `"the scribe wrote it down"`, `"describe the target"`,
`"descend to five hundred"` all come back `token=None`, confirmed by execution. The gap it does
not mention is the bare single word, which is what a push-to-talk transmission often is.

**This is an instance of an already-accepted class, not a new weakness.** The same probe against
the *baseline* table returns `"shop"` → `stop_talking` (0.75), `"support"` → `report_all` (0.615),
`"hollow"` → `follow` (0.833), `"fallow"` → `follow` (0.833), and `"record"` → `report_all` is
deliberate (whisper mishears "report" as "record", per the module docstring). `MATCH_FLOOR` at
0.6 is a tuned acceptance of exactly this trade, and `VERB_FLOOR` sits *below* it on the stated
grounds that a false rejection is the worse error. I am not asking for a change.

What makes it worth one line to the user rather than silence: `"descend"` is a word a pilot
actually says, and its consequence is an unsolicited full contact report — see finding 3 for why
that specific consequence is not neutral right now.

---

### 3. QUEUED FOR USER — `report_all` speaks rear-hemisphere clock hours by design; `describe` adds a trigger, not a bypass

`body-layer/src/belief/crew_console.py:1636-1655`

Checked against the live defect named in the task (20 of 357 spoken lines naming clock hours
5/6/7, hours `_CO_PILOT_MASK.rear_cutoff_deg = 130.0` declares unviewable). **This branch adds no
new callout path and nothing that bypasses the 2026-09-27 gate.** Specifically:

- `CONTACT_ATTENTION_CHANGED` — the one event the new group tagging emits per member — has
  **no speech template**: `route_event` returns `None` for it and does not even acknowledge it
  (`belief/speech.py:58-65`, `1933-1935`). Tagging N members adds N events and zero spoken lines.
- The two watched-only *spontaneous* paths are both already behind the gate:
  `CONTACT_MOTION_CHANGED` and `CONTACT_RANGE_CROSSED` each test `observable_or_grace`
  (`belief/contacts.py:1162-1174` and `:1286`). Expanding the watched set therefore expands a
  gated surface, not an ungated one — which is the right answer to "what does group-tagging let
  him say".

The remaining path is the *pulled* report, and it predates this branch: `_handle_report` iterates
every contact whose certainty is not `"lost"` with no observability test
(`crew_console.py:1636-1655`), and its own docstring states the rule deliberately — *"belief
survives the aircraft turning away; only the absence claim is withheld"* (`:1609-1611`); the
rear-hemisphere carve-out applies to `render_clear`/`render_no_view` for a `sector` request only,
and `report_all` "never claims a direction at all".

**So the question for the user, not a finding against this branch:** the `fix/callout-observability-gate`
work is extending the gate from crossing+motion callouts. If the intent is that *no spoken line
should ever name an unviewable clock hour*, then `crew_console.py:1639` is the third site and it
is governed by a documented decision that would have to be revisited, not an oversight to patch.
If the intent is narrower — spontaneous callouts only, a pulled report answers from belief — then
nothing needs to change there and this note closes.

The interaction with finding 2 is the reason it is raised here: a `report_all` fired by a
mis-anchored `"descend"` is an *unsolicited* rear-hemisphere clock callout, indistinguishable in
the speech log from the defect being fixed.

---

### 4. NOTE — one `watch group` now creates N permanent tasks, and repeating it creates N more

`body-layer/src/belief/crew_console.py:1273` → `belief/tools.py:1008`

`watch_contact_task` creates a `PendingIntent` with `deadline_sim=math.inf` that `TaskStore.tick`
never resolves (no `area`), with no dedup against an existing task for the same contact. One
`follow`/`watch nearest` landing on a 12-unit convoy now creates 12 such tasks instead of 1, and
saying it twice creates 24 for the same twelve contacts.

**Not a stuck state:** `cancel_watch` cancels *every* active `watch_contact` task, not just the
governing one (`_handle_cancel_task`, `crew_console.py:1842-1853`), and `cancel_task` returns each
member's attention to `"normal"` — so the pilot can still fully undo a group watch by voice, and
every member really is released. Verified by reading both, since a partial cancel here would have
left group members reporting forever after the pilot said stop; it does not.

That leaves growth only, in a sortie-bounded structure, and the uncapped watch list is already
reviewed and accepted as pre-existing in `plans/dcs-driven-los/performance.md`. This branch
multiplies the constant rather than changing the shape. Performance-reviewer's call, not a
security fix.

---

### 5. NOTE — a group watch promotes N contacts to the top of the look queue

`body-layer/src/logger.py:676-709`

`watched` feeds `optic_policy.choose_look`'s *ordering* ("it never decides whether an unwatched
contact gets identified at all", `:682-684`). After a group watch, N contacts sit at the front of
that ordering, which can delay the first closer look at an unwatched contact elsewhere — including
an air-defence contact the pilot would want identified first. No omniscience, no vulnerability,
and arguably what the pilot asked for by watching the group. Raised only because it is a
pilot-visible consequence of item 3 that the plan does not mention.

---

## Explicitly clean — stated so the list stays credible

- **No omniscience leak in the group tagging.** `Group` membership is single-link clustering over
  `Contact.position` (the fused belief estimate) with a backstop scaled by `object_model.size_m`
  via each contact's `last_class_raw` — belief only, "never a DCS object_type", per
  `belief/groups.py`'s own docstring, which I verified rather than took. Every member is an
  already-individuated contact that exists because it was perceived. `render_watch_group_readback`
  speaks a count of such contacts and nothing else — no composition, no type, no position — so it
  discloses strictly less than the group-disclosure line already does.
- **Watched-ness grants no new knowledge.** The only belief-side effect found beyond callout
  eligibility is `enrichment.py:601`, where `attention == "watch"` selects the iterative
  fixed-point projection instead of the single-shot one. That refines the arithmetic of a
  projection *from the existing belief*; it introduces no new input.
- **The `ahead` sweep is strictly more conservative at 12 o'clock**, and the two hours it adds
  (11, 1) are already inside the commanded forward arc and already in `SCAN_PLAN` and in
  `left`/`right`. `LOOK_DIRECTION_FOV_HALF_DEG` is untouched, so no cone widened.
  `gaze_at`'s index is clamped (`min(..., len(legs) - 1)`) and Python's `%` keeps `elapsed_s`
  non-negative even for `t_sim < command_t_sim`, so no negative or out-of-range index is reachable
  (`perception/gaze.py:458-465`). The pre-existing `assert plan.command_t_sim is not None` on
  `:461` would become a `TypeError` under `python -O`; it is guaranteed by `ScanPlan.__post_init__`,
  predates this branch, and is not worth changing.
- **No new attack surface of any kind in the diff:** no subprocess, no network call, no filesystem
  path construction, no deserialization, no secret-shaped literal, no `eval`/`exec`, no new
  `dostring_in` splice, no broadened bind. The three source changes are a tuple literal, a method
  extraction with a loop, and a dict value.
- **Not inflated:** single-player, LAN-only, single-user. Finding 2 needs the player to say one
  specific word alone on push-to-talk; finding 1 needs a contact to drop between a reconcile and
  a command. Neither is reachable by a remote party, and there is no untrusted-input channel on
  this branch.

## Verdict

**APPROVED WITH REQUIRED FIXES** — one required fix (finding 1).

Per `AGENTS.md`, that re-enters the loop as **Implementer → Reviewer → DoD**, not straight to DoD.

### Required Fixes

1. Count the members actually marked and speak that count, instead of `len(member_ids)` —
   `body-layer/src/belief/crew_console.py:1271-1281` (and the docstring promise at `:1260-1264`).
   A test pinning the shrunken-group case belongs with it: a `Group` whose membership includes an
   id no longer in the store must not produce a readback naming it.

### For the user (queued — nothing here blocks the fix above)

- Finding 3: does the observability gate being extended on `fix/callout-observability-gate` mean
  to cover the *pulled* `report_all` path too (`crew_console.py:1639`), or is that path's
  "belief survives turning away" decision still what you want? It is a decision, not a bug.
- Finding 2: `"descend"`, said alone, now triggers a full contact report. Accept (it is the same
  trade already made for `"shop"`/`"support"`/`"hollow"`), or drop the bare `"describe"` phrasing
  and keep only `"describe contacts"`?
