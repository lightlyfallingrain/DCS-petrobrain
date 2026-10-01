## Security Deep Analysis: contact-store-pruning (BL-B23)

Branch `fix/contact-store-pruning`, tip `2992d91` (confirmed via `git rev-parse HEAD` as the first
action; worktree checked out directly on that commit, not via `main`'s default worktree landing).
Scope `main..fix/contact-store-pruning`: one code commit (`90057c4`, `exclude lost contacts from
group clustering`), a Reviewer approval note (`0561907`), and a backlog-filing-only commit
(`2992d91`, `BL-B24`, `body-layer/BACKLOG.md` only — no code).

### Dependency Status

No dependency change. `git diff main..fix/contact-store-pruning -- '**/pyproject.toml'
'**/*.lock' '**/requirements*.txt'` is empty.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/contacts.py:1450` (eighth block of `tick`) | New filter on `GroupStore.reconcile`'s input: `certainty_of(contact, now_sim) != "lost"` | Correctness/invariant check, not a classic vuln pattern — see narrative below | None |
| `body-layer/src/belief/contacts.py:699` (`contacts` property) | Unfiltered `list(self._contacts.values())`, unchanged | `describe_contact`/`get_contact_history` (`belief/tools.py:445,462` via `_find_contact` at `tools.py:184`) read this property, not `tick`'s local filtered comprehension | None — confirmed independently, not inherited from Reviewer's note |
| `body-layer/src/belief/groups.py:559-560` | `reconcile`'s own docstring: a group with no matching cluster is "simply dropped, no event fired (deferred, per the plan)" | Pre-existing behaviour, unchanged by this diff. No event means no false "destroyed"/"departed" claim is emitted either — the group-reporting delta taxonomy in `speech.py` (~line 1496-1524) treats a member leaving the cluster as silent-at-group-level, "told via that member's own lifecycle event if it matters," which is the existing `LOST` lifecycle event path, not a new one | None |
| `body-layer/src/belief/groups.py:375` (`_cluster_contacts`) | Still O(n²), unchanged, but now bounded by *live* contact count rather than total-ever-seen | This is the fix's point; confirmed by the implementation doc's measurement table (403 ms → 1.4 ms at n=1200) and independently reproduced by Reviewer (405.98 ms / 1.26 ms) | None |
| `body-layer/src/belief/contacts.py` `tick`'s first seven per-contact blocks (~1103 onward) | Untouched, still `for contact in self._contacts.values(): ...` — O(n_total), linear | Residual unbounded growth in the sense that `_contacts` has no delete path and this loop scans all of it every tick, but it is O(n) simple comparisons/event-append, not O(n²) clustering. The "after" benchmark column (which is full `tick()`, not just `reconcile`) stays flat at ~1.4 ms even at n=1200 total contacts, so this loop's cost is not currently visible against the DoS-shaped cost this fix removed | None this pass — noted as the honest residual, see below |

No hits in `security-grep`'s categories (dynamic code execution, subprocess, network, file writes,
hardcoded credentials, DCS `net.dostring_in` bridge) are touched by this diff at all — the change is
a pure in-memory filter on a list comprehension.

### Narrative verification (independent of Reviewer's note)

1. **Memory invariant (nothing forgotten).** Traced `describe_contact` and `get_contact_history`
   (`body-layer/src/belief/tools.py:445`, `:462`) through `_find_contact` (`:184`) to
   `store.contacts` (`contacts.py:699-701`), which returns `list(self._contacts.values())` —
   `self._contacts` itself is never filtered or pruned by this change; only a local comprehension
   passed inline to `self._groups.reconcile(...)` is. Checked brain-facing and crew-console paths
   too: `crew_console.py` and `speech.py`'s report-pull path both go through the same
   `describe_contact`/`get_contact_history`/`store.contacts` surface, not through
   `GroupStore`'s membership. A `lost` contact stays fully answerable everywhere outside
   clustering. `test_lost_contact_still_answerable_by_describe_contact` exercises exactly this.

2. **No false "departed/destroyed" claim.** `GroupStore.reconcile` fires no event on a cluster
   shrinking or disappearing (its own docstring, confirmed by reading `reconcile`'s body — it just
   rewrites `self._groups`). The group-level speech path (`speech.py`'s delta taxonomy, branch 5,
   "members only departed … silent") already treats membership loss as silent-at-group-level by
   design, deferring to that member's own `LOST` lifecycle event (an existing, pre-this-fix
   mechanism driven by `certainty_of`/`lifecycle_event_kind` in `tick`'s first block) for anything
   worth saying. This fix does not add or change any narration string; it only changes which
   contacts reach the clustering computation that feeds that pre-existing, already-careful
   reporting logic. "Not grouped" and "not there" are not conflated anywhere in the diff.

3. **DoS shape, inverted and bounded.** Confirmed via the implementation doc's measurement table
   and independently via my own run (`pytest`, `ruff`, `mypy` below) that the fix is behaviourally
   inert except for the clustering input — `_contacts` still accumulates for the whole sortie
   (no delete path exists or is added), but the one O(n²) consumer (`_cluster_contacts`) now only
   ever sees contacts with `certainty_of(...) != "lost"`. At realistic sortie lengths (the
   500-1200 total-contact band the original finding used), the remaining O(n_total) linear work in
   `tick`'s other seven blocks does not reproduce the original defect's shape — linear work over a
   dict of simple dataclasses is not what caused the 403 ms/tick figure; the O(n²) pairing was.
   Worth watching if sortie-length contact counts grow by an order of magnitude again, but that is
   a MONITOR note, not a finding against this diff.

4. **Reacquisition / re-admission.** `certainty_of` is a pure function of
   `now_sim - contact.last_seen_sim`, so a reobserved contact is automatically back in the
   clustering set next tick with no sticky exclusion state — verified by reading `belief/decay.py`'s
   `certainty_of` and by `test_lost_contact_rejoins_clustering_cleanly_on_reacquisition` passing.

5. **BL-B24 (filed in this branch's third commit) is correctly out of scope** — it documents a
   pre-existing `association_over_time` reacquisition-gate ambiguity, unrelated to this fix's
   clustering-input filter, and adds no code.

### Checks (independently run, fresh `.venv` built from `body-layer/pyproject.toml`, cwd
`body-layer/`)

- `ruff format --check src tests` — pass (114 files already formatted)
- `ruff check src tests` — pass
- `mypy src` — pass ("Success: no issues found in 53 source files")
- `pytest tests -q` — **1384 passed, 4 xfailed** (matches expected)

### Verdict
APPROVED

No security-relevant defect. This is a correctness/perf fix whose only attacker-shaped question —
"can a legitimate class of input (a long sortie) cause Petrovich to forget or misreport a
contact" — was the right question to ask and the diff answers it correctly: the filter is
clustering-input-only, `_contacts` is untouched, and no new narration path was added that could
state absence where only "not currently clustered" is true. Single-user, LAN-only, offline project;
nothing here needs an attacker with local code execution to matter, and there is none to flag.
