# A predicate's granularity has to match the granularity of what it governs

`feature/sortie-refinements` spent three review rounds making a keeper-election predicate stronger
before anyone noticed it was the wrong *shape*. `may_be_callout_keeper(store, contact)` elects one
member of a watched group and the scheduler consumes the rest's events of that kind. Each round
asked the predicate to exclude one more wrong keeper — and each round's fix was correct — but the
residual failure was never about *which* contact may be keeper. It was that the elected contact
might have no event of that kind on that tick, which is a per-**event** question a `(store,
contact)` predicate cannot express at all.

The tell was available from round 1 and was read as a strength: the predicate's arguments. When a
fix for "the governed thing was wrongly dropped" keeps needing another condition, check whether the
predicate's parameters can even see the thing being dropped, before adding the condition. A
predicate one level coarser than its subject can be made arbitrarily accurate and still leave a
hole, because the hole is in the quantifier, not the test. The fix is to re-key the election
(per `(group, kind)` here), not to strengthen the gate.

Adjacent and worth not confusing with it: prose asserting a cardinality the code does not guarantee
("N lines becomes one", when it can become zero) is a *symptom* of this, and it is the shape the
reviews actually caught. The docstring was wrong because the design was one granularity off.
