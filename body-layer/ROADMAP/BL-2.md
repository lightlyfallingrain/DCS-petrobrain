# BL-2 — Contact memory and association (= PB-2)

- [x] **BL-2 — Contact memory and association (= PB-2, done, merged 2026-09-09).** #status/done Persistent
  contact identities, detected/lost/reacquired, observation-vs-belief split, decay/certainty ladder,
  cross-channel fusion, a debug console (`belief/console.py`). Stages: **-1** aircraft-layer
  `is_ownship` flag (replacing the proximity-heuristic exclusion); **0** scope-channel type-namespace
  repair (`association._type_match_score` resolves DCS type names through `reporting_names` before
  scoring); **1** belief core (`belief/percept.py`'s `Percept` structurally drops DCS truth fields,
  `belief/contacts.py`'s `ContactStore`, `belief/association_over_time.py`'s gating); **2**
  decay/certainty ladder + lifecycle events; **3** `emit_mode` + `--console` wiring; **4**
  `belief/tools.py`'s `get_contacts`/`describe_contact`/`get_contact_history`/`find_contact`; **5**
  cross-channel fusion (fixture-validated); **6** live acceptance (a real sortie against
  `--console`; one real bug found and fixed — `--console`'s poll thread crashed on a
  main-thread-opened `sqlite3.Connection`, since `sqlite3.Connection` is thread-affine). Core design
  decision: contact identity is geometric, from perceived attributes only — never `object_id` or any
  truth field, so Petrovich can confuse two identical trucks (the omniscience CLAUDE.md forbids).
  Full history: `plans/pb2-contact-memory/`.

