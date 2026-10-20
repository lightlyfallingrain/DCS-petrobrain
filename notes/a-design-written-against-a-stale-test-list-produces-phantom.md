# A design written against a stale test list produces phantom expectations

Stage 3b-i rev.2's design named a test as an xfail it expected to flip. The test did not exist: it
had been folded into another test by an earlier, unrelated commit. The design was not careless — it
was written against a test inventory that had already moved. When a plan specifies "test X should
now assert Y", confirm X exists at that moment rather than at the moment the surrounding reasoning
was formed.
