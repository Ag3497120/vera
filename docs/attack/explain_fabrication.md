# Explain fabrication and provenance attack

## Findings

No reproducible defect was confirmed, so there are no finding rows.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|

## What held

The attack tests replace `reach` with a controlled `UNITS` result and give `explain` synthetic slots, held crosses, labels, and a word set. They check that:

- non-`UNITS` results are returned unchanged;
- the chosen split retains its left/right roles, and the subject tracks the only speakable unit when just one unit passes the vocabulary gate;
- source labels are not reported as held units;
- shared facets come from the two units' intersection, while facets outside the vocabulary gate stay out of the draft text;
- the edge lookup receives the selected subject and shown units, and an unavailable lookup does not change the typed explanation;
- bare-suffix, no-word, and tied-split cases abstain;
- a slot containing only a partial candidate span does not match that unit.

Acceptance run from the worktree root:

```text
13 passed in 0.07s
```

## What was not covered

The tests stub `reach` and use synthetic store data. They do not establish provenance in a live corpus, whether an edge lookup filters stale or superseded records, whether source records preserve negation, or how the explanation behaves through the full storage and `reach` path. The optional lattice neighbourhood path was also not exercised.
