---
name: group_cohesion_reassign_not_accumulate
description: Group.last_spoken_member_contact_ids/leading_contact_id/differentiated are reassigned per mark_spoken call, not unioned -- checked clean, no leak.
metadata:
  type: project
---

`plans/group-cohesion-redesign` (`fix/group-undermerging`, tip `676f12c`) added three
new `Group` fields for the speech delta-taxonomy (`last_spoken_member_contact_ids`,
`last_spoken_leading_contact_id`, `last_spoken_differentiated`). These looked, on first
read, like the "per-group set that accumulates every contact id ever seen" leak shape
this project has flagged before (see
[[project_body_layer_bounded_growth_accepted_pattern]]).

**Checked and confirmed not that**: `GroupStore.mark_spoken` *reassigns*
`last_spoken_member_contact_ids = member_contact_ids` each call rather than unioning
into it, and `reconcile`'s carry-over copies the old value verbatim for an unchanged
group rather than merging. So the field tracks "what was spoken last time," bounded by
current membership, never sortie-length history.

**Why this matters for future passes**: the accumulating-state shape is common enough
in this belief-state code (Contacts/optic-policy maps, membership sets) that it's worth
checking *which* operation a new per-group/per-contact collection field uses
(assignment vs. union/add) before flagging it, rather than assuming growth from the
field's name alone.

Also confirmed in the same pass: `object_model.ObjectTypeProfile.installation_component`
(new `bool`, keyed by substring match on `object_type`/reporting name) fails **closed**
-- an unmatched or mismatched type name falls to `_DEFAULT_PROFILE` with
`installation_component=False`, never an open/permissive default. Grouping logic
(`belief.groups._cluster_contacts`/`_pair_backstop_m`) only ever clusters contacts
already individually tracked in `ContactStore`; no path fabricates a group member that
was never perceived. Full review: `plans/group-cohesion-redesign/security-review.md`.
