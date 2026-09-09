"""Belief: the *consumption* side of the observation/belief split (plan
`plans/pb2-contact-memory/plan.md` §1) -- `perception/` produces
`Observation`s, this package turns them into persistent contact beliefs.
Only `belief.percept.Percept`s (never a raw `Observation`, never a DCS truth
field) may drive any decision in this package -- see `percept.py`'s
docstring for the mechanical enforcement of that rule.
"""
