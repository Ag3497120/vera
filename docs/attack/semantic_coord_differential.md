# Semantic coordination differential attack

The tests compare coordination and aligned phrase spans against small reference rules derived from `semantic_coord.py`'s documented contract. The coordination cases are generated deterministically across the listed te/renyō separators and two renyō inflection labels. The reference does not call production helpers.

Acceptance run: `11 passed, 3 xfailed` using the required pytest command and the unit environment.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| `coord-empty-body` | ungrounded | Predicate `見` tagged `連用形`, then particle `て`, then predicate `走る`; predicate indices select `見` and `走る`. | Reject: the later clause has no new noun phrase chunk. | `coordination_ok` returns `True`. |
| `coord-late-connective` | ungrounded | Predicate `見` tagged `連用形`, particle `て`, conjunction `しかし`, noun `猫`, predicate `走る`; predicate indices select `見` and `走る`. | Reject: a connective occurs between the te tail and the next predicate. | `coordination_ok` returns `True`. |
| `phrase-interior-edges` | robustness | One noun token `クククル` spans the full token; ask whether the substring from its interior start to its interior end is phrase-bounded. | Reject: both phrase edges split one token. | `phrase_bounded` returns `True`. |

The two coordination findings conflict with the contract's requirement for a new noun phrase chunk after the tail and no connective before the next predicate. The phrase finding shows that offsets not aligned to token edges pass because the boundary scan finds no token exactly at either offset. These are reported as defects, not as justified differences.

## What held

- The generated supported te/で forms, optional comma forms, and bare renyō-plus-comma form matched the independent reference when a noun phrase appeared in the later clause.
- The tested non-te separators, missing separator, and non-renyō first predicate were rejected.
- `chunk` began the later clause after the previous predicate tail in the tested chain.
- The subject check recognized は/が with the expected particle tags, and topic extraction returned the contiguous noun span before は.
- Aligned phrase spans passed or failed the tested neighboring-token boundary cases as expected.

## Not covered

- Tokenizer output beyond hand-built token tuples, including real-world segmentation and offsets.
- Invalid predicate indices, overlapping or non-contiguous offsets, and malformed token records.
- Broader Japanese clause syntax, chained predicates outside this module's licensed pattern, or end-to-end sidecar interpretation.
- Runtime, learning, or evidence behavior elsewhere in Vera.
