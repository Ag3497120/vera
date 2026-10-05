# Semantic route real-text attack notes

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| R1 | robustness | A seven-leaf `View`; one clause binds `entity="Q"`; another leaf has unread text `A note mentions Q.`; route a Bind pattern for `entity="Q"`. | The unread-bearing leaf and its unread span are retained because the unread text contains the anchor. | Routing completes, but only the clause-bearing leaf is retained; the unread-only leaf and span are absent. The regression case is an expected xfail in the attack test. |

R1 is a false negative in unread-text indexing: `_grams("Q")` uses a unigram, while a longer unread span is indexed with bigrams, so that unigram is not found. The router returns a restricted view without the unread mention. No downstream answer was run, so this is not reported as an observed wrong answer or fabrication.

## What held

The required acceptance run completed with **9 passed and 1 xfailed** (10 test cases; 0.09 seconds). The passing checks cover literal anchor extraction, flat-view fallback for unanchored and small views, conjunctive anchor matching within one Bind pattern, union across Bind patterns, selective use of an anchor when another is common, fallback when all anchors are common, preservation of matching unread evidence, and the routed-view subset property. A multi-character anchor inside a longer unread span was found and retained.

These are small, hand-authored prose-shaped IR views that exercise `LeafTree` directly. They are not Wikipedia samples and do not measure real-lead crash, hang, or routing rates.

## Not covered

- Sampling the Wikipedia lead paragraphs from the `split == train` loader was not possible under this unit's read-only allowlist, which permits opening only `verantyx/semantic_route.py`. I therefore report no real-lead rates.
- The semantic reader and verifier were not run; these cases begin with constructed `View` objects.
- Large corpora, long paragraphs, performance under load, and downstream answer behavior were not evaluated.
- No crash or hang was observed in these bounded probes. This does not establish their absence on real lead data.
