# Graded fabrication and provenance attack

## Findings

I exercised `GradedJudge` and `band_annotation` with small synthetic stores. All
12 attack tests passed; I found no confirmed fabrication defect in these cases.
The severity column uses `robustness` for checks where the expected refusal or
source trace held. There were no `wrong-ANSWER`, `ungrounded`, `crash`, or
`hang` findings.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| GF-01 | robustness | A topic has two facets and a source label; also put that label in `crosses` as a key. | Source labels are omitted; depth keeps the core name first. | `cores_as_items` omitted the label and returned the topic and sorted facets; depth 1 and 2 retained the core first. |
| GF-02 | robustness | `alpha` is a core and also a facet of `other`; ask for `alpha` with a name-only and a mentions setting. | The core-name reading can identify `alpha`; the mentions setting must not replace it. | The name-only reading returned `alpha`; the mentions reading abstained on its tie, and the strict verdict stayed `ANSWER alpha`. |
| GF-03 | robustness | `topic` has facet `alias`; use a setting that indexes facets and ask for `alias`. | Any returned item is a store core connected to the query term. | `ANSWER topic`; `topic` is a core key and its record contains `alias`. |
| GF-04 | robustness | Two cores both have facet `handle`; ask for `handle` using the mentions setting. | Do not select one of the equally supported cores. | No item was returned; the setting had no reading. |
| GF-05 | robustness | `source.xml` appears as a facet but is listed in `source_labels`; ask for it. | A source label must not become an answer or covered term. | `UNKNOWN_NOT_PRESENT`, no item, no covered term, and `source.xml` listed as missing. |
| GF-06 | robustness | Store core `アルファ`; ask `アルファではない`. | The lexical item may identify only the named core; it must not establish a predicate or a different entity. | The result was `ANSWER アルファ`, with term `アルファ`; that item is a core key. The module does not check the negative predicate, so this test establishes entity traceability only. |
| GF-07 | robustness | Store core `abcd`; a custom reader emits `ab`; compare whole-grain and g2 settings. | A partial-window match must remain typed as coarsening and expose that `ab` is not held exactly. | `ANSWER_BY_COARSENING abcd`; whole reading was absent, g2 read `abcd`, and `ab` was missing. |
| GF-08 | robustness | Store core `weather`; ask `today` with terms resolving to `weather`. | A time-dependent query has no item band. | `UNKNOWN_TIME_DEPENDENT`; `band_annotation` returned `None`. A normal exact core query returned only an annotation (`agree`, `of`, item, concord), with no verdict field. |
| GF-09 | robustness | Use a reader that returns no terms for an empty query and for `hello`. | Distinguish unparsed empty input from readable input with no subject; neither gets a band. | Empty input was `UNKNOWN_UNPARSED`; `hello` was `UNKNOWN_NO_SUBJECT`; no band was returned. |

## What held

- Source labels were excluded from both the core item pool and coverage terms.
- A name-only match remained distinct from a facet mention, and a shared facet
  did not choose between two cores.
- A facet-based answer pointed to a core whose stored record contains that
  facet.
- The tested partial-span match stayed `ANSWER_BY_COARSENING` and reported its
  exact query term as missing; it was not promoted to strict `ANSWER`.
- Time-dependent and termless queries produced no band annotation.

## What I did not cover

- These were synthetic stores, not a corpus run. I did not exercise large
  stores, unusual `crosses` shapes, custom ladder grammars beyond whole and g2,
  or long-running build behavior.
- No revision or supersession metadata was modeled, so stale-record precedence
  was not tested.
- The negation case tested core identity only. This module's lexical reading
  does not validate predicate polarity; I did not treat its core lookup as a
  truth judgment.
- I did not test multi-sentence questions, swapped role labels, or a semantic
  reader that preserves case-frame roles.

## Run

Command used:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_graded_fabrication.py
```

Result: **12 passed in 0.09s**.
