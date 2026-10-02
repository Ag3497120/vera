# Lattice differential attack

The reference implementation in `tests/attack/test_lattice_differential.py` is independent of the lattice functions. It checks the documented pair split and long-window rules, using generated vocabularies containing pairs and licensed long-word cuts.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| L-DIFF-1 | ungrounded | `build(["abc"])` | Only standalone vocabulary words and observed single-character atoms are lattice nodes; an unattested multi-character fragment must not enter a positional family. | `up` contains `("ab", "L")` and `("bc", "R")` even though neither fragment is in `words`. The regression test is marked xfail. |

## What held

- Generated cases matched the independent reference for pair indexing, licensed long cuts, split discovery, bounded analysis, positional kin, and facet ranking.
- Pair splits use observed atoms, and left and right kin slots remain separate.
- Long-word splits require attested word halves and avoid single-character halves.
- Facet prediction sums the available family counts, excludes source labels and the queried term, and sorts ties lexicographically.

## What was not covered

- Short split inventories at lengths 3–5 were not differentially enumerated because their measured cut inventory is supplied by the separate granularity module, outside this unit's allowed read-only reference. The fragment-admission finding uses the module's observed behavior and the lattice docstring's attestation rule.
- Corpus-scale measurements, performance under large vocabularies, and downstream use of lattice outputs were not evaluated.

## Acceptance run

Command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_lattice_differential.py`

Result: 10 passed, 1 xfailed in 0.09s.
