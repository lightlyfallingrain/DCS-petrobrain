---
name: measure-what-is-heard-not-what-folds
description: Association sweeps that count only gate folds miss the callout merge-echo rule, which silenced 50-60 points more of real second groups than the gate did (BL-B110 seventh pass)
metadata:
  type: feedback
---

When a plan's acceptance number is "what the pilot hears" (duplicates, missed second groups), the
harness must run the callout suppression rules too. Counting `len(store.contacts)` alone is not
enough. Check `callouts._is_merge_echo_of_earlier_contact`: A not lost, plus `contacts_plausibly_same`.

**Why:** BL-B110 went through six architect passes measuring only gate folds. The seventh pass
(2026-11-10) added the echo check and found it silences 50–60 points of correctly split different
groups (eye → eye, A < 120 s old). That is larger than the gate fold the whole Stage 2 trigger
targeted. It also showed that BL-B113's same-optic splits are heard only past `LOST_THRESHOLD_S`
(120 s), when the echo rule stops applying. Separately, the as-if trigger's earlier "catch" was the
indefinite-S bug. A trigger number taken on a gate later found defective must be re-taken, not
carried.

**How to apply:** for any plan whose goal names spoken outcomes, the measurement column is "heard",
and it includes certainty (lost/not lost) at the second look. Also check the harness for unsalted
hash draws beyond the field salt: `z_look`, `look:<id>`, and `bias:<object_id>` are all
salt-independent. See [[noise-field-sweeps-need-an-ensemble]].
