Run an implement–verify iteration loop against GOAL.md until every acceptance
criterion is checked or you hit the iteration cap.

Each iteration:
1. PICK the single highest-value unchecked criterion in GOAL.md.
2. IMPLEMENT the smallest change that could satisfy it.
3. VERIFY by actually running the test suite (pytest -q) and, when relevant, hitting
   the route with a request. Never mark a criterion done from reading code — only
   from a passing run.
4. If verification fails: diagnose, fix, re-run. Max 3 fix attempts per criterion,
   then mark it BLOCKED in GOAL.md with the exact error and move on.
5. UPDATE GOAL.md (check the box, note the proving test) and append one line to
   LOOPLOG.md: iteration #, criterion, result, files touched.

Stop when: all boxes checked, or $ARGUMENTS iterations reached (default 10), or
everything remaining is BLOCKED. Then print a final scoreboard: criteria passed /
blocked, full test output, and anything needing my manual attention.

Never weaken or delete a test to make it pass. If a test seems wrong, mark the
criterion BLOCKED and explain instead.
