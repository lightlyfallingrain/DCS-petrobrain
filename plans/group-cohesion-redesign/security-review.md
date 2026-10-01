## Security Deep Analysis: group-cohesion-redesign

Branch `fix/group-undermerging`, tip `676f12c` (verified: `git rev-parse HEAD` in this
worktree landed on `main` (`35f1922`), so this review was built against an isolated
`git archive 676f12c` snapshot, per `AGENTS.md` rule 4 — the branch itself was already
checked out in the main checkout and another worktree, so it could not be checked out
here directly). Range reviewed: `63916e1..676f12c` in `body-layer/src/belief/{groups,
speech,callouts,contacts,crew_console}.py` and `body-layer/src/perception/object_model.py`.

### Dependency Status

No dependency change. `body-layer/pyproject.toml` at `676f12c` still declares only
`pyproj>=3.6` (the pre-existing world-model-seam transitive dependency, documented in
the file's own comment). The diff touches no import outside `belief`/`perception`/
stdlib (`math`, `enum.Enum`, `dataclasses`, `collections.abc`).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `object_model.py` `profile_for` (~line 550) | Substring keyword match drives `installation_component` | `text = object_type.lower()`; `if keyword in text`. Unmatched/mismatched type names fall through to `_DEFAULT_PROFILE`, whose `installation_component` defaults `False` — a matching failure (new DCS type string, adjacent name) fails **closed** (no merge), not open. `"s-125"`/`"kub "` keyed off the raw DCS `object_type` string, which originates in the mission/module data, not external untrusted network input; same substring-match mechanism as every pre-existing row in this table. | None |
| `groups.py` `_pair_backstop_m` | New per-pair cohesion policy (installation cap, `EAGER` infantry) | Only loosens merging for `OP_INFANTRY` (explicit user direction, cited in-code) and for pairs where **both** members resolve `installation_component=True` (a 500 m flat cap, still subject to `min(relative_threshold, pair_backstop)` — never an unconditional merge). A **mixed** pair (one installation component, one not) falls through to the ordinary backstop, not the cap. No path merges contacts whose profiles are unresolved/default into the eager or installation branches, since both default to `STRICT`/`False`. | None |
| `groups.py` `Group.last_spoken_member_contact_ids`/`.last_spoken_leading_contact_id`/`.last_spoken_differentiated` | New per-group state, candidate unbounded-growth shape | `GroupStore.mark_spoken` **reassigns** these fields each call (`group.last_spoken_member_contact_ids = member_contact_ids`), it does not union/accumulate into them. `reconcile`'s carry-over also copies the old value verbatim rather than merging. No growth over a sortie's length — bounded by current group membership at the moment last spoken, not history. | None |
| `speech.py` `_group_member_facts`/`_member_contacts_for`/composition functions | Could a merge/delta-taxonomy change leak an unperceived member or classification into a spoken callout? | All composition and delta-arrival logic (`_render_full_group_composition`, `render_group_disclosure`'s delta branch, `group_membership_state`) reads only from `member_facts` built by `_group_member_facts`, which in turn comes from `describe_contact` against the live `ContactStore` — i.e., only contacts Petrovich currently/previously actually tracked. Grouping itself (`_cluster_contacts`) clusters existing tracked `Contact` objects by observed position; it does not fabricate a member. No code path adds a contact id to a group's composition without that contact existing in the store with its own believed classification. The no-omniscience boundary (`envelope_for`, `profile_for` on `last_class_raw`, never a raw DCS `object_type`) is unchanged by this diff. | None |
| `speech.py` `OutgoingSpeech.content_signature` | New field, used only for re-disclosure gating | Derived entirely from the rendered `text`/composition, which is itself derived from already-spoken-eligible member facts above. Not attacker-reachable, not a new input-validation boundary. | None |

### Untrusted input / attack surface

This diff does not widen the aircraft-layer HTTP feed or speech-recognition text
surface — no new parsing of either. The new state fields are computed server-side from
already-trusted internal belief state (`ContactStore`), not deserialized from the wire
directly. `installation_component` is a static, hand-authored `bool` on ~2 of ~150
keyword rows, not data-driven.

### Verdict

APPROVED

No security-relevant change beyond what is already covered above. This is a
single-user, LAN-only, offline project under its current one-pass-per-feature cadence;
nothing in this diff introduces an external-input path, a new dependency, or a
mechanism that could speak unperceived information. The one thing worth naming for the
record, since it is exactly the project's core invariant: merging contacts more
aggressively never fabricates a member — `_cluster_contacts` only ever groups contacts
that are already individually tracked, and `render_group_disclosure`/`render_group_
full_disclosure` only ever compose from those same contacts' own believed
classifications.
