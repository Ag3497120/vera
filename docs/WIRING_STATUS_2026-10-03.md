# Vera wiring status — 2026-10-03

## Scope and run record

This is a snapshot audit of the wave 3 demos and the two required evaluations.
The prior status is `docs/WIRING_STATUS_2026-10-02.md`. Runs used the prescribed
interpreter with `VERA_CORPUS_ROOT=/tmp/vera-empty-materials`,
`PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=.`, and `-B` from the worktree root.
No live model or network call was made.

The eleven wave 3 demos beyond the set listed in the prior audit all exited 0
and ended with `DEMO OK`:

| Demo | Result from this run |
| --- | --- |
| `tools/demo_constructions.py` | `DEMO OK` |
| `tools/demo_decision_writer.py` | `DEMO OK` |
| `tools/demo_driver.py` | `DEMO OK` |
| `tools/demo_impact.py` | `DEMO OK` |
| `tools/demo_names_fix.py` | `DEMO OK` |
| `tools/demo_polarity.py` | `DEMO OK` |
| `tools/demo_question_kinds.py` | `DEMO OK` |
| `tools/demo_runtime.py` | `DEMO OK` |
| `tools/demo_testimony.py` | `DEMO OK` |
| `tools/demo_variants.py` | `DEMO OK` |
| `tools/demo_verifier_evidence.py` | `DEMO OK` |

`tools/demo_decision_writer.py` also printed 66 askable exchanges of 130 (50.8%),
72 recorded answer strings, 6 typed refusals, 0 later exact-record matches out
of 0, and 0 wrong answers from nonmatching keys. Those are demo counters, not
the conductor evaluation result. `demo_question_kinds.py` and
`demo_variants.py` printed held-aside counters; I do not treat those counters as
held-out evaluation evidence.

The required train coverage run read 1,500 documents and reported approximately
3,575 sentences, with 1,365 supported sentences (38.2%), 1,439 sentences with
only unsupported material, and 772 unread spans. The unit-provided pre-wave-3
reference is 596 supported sentences, so the observed net difference is +769.
The provided pre-wave-2 reference is 678, so the observed difference from that
reference is +687. The older numbers are comparison points from the task context;
they were not rerun in this audit.

The required real-question evaluation read 130 rows, including 72 recorded
human answers and 27 exact option labels. Accumulated-frame results were:
**agreed 0, WRONG 0, escalated 72**. Thus the 0 wrong result reflects abstaining
on all 72 known-answer rows; it is not evidence of answer accuracy.

## Capability matrix

Counts below are outputs from this run or the explicit baseline references above.
The rule counts are supported clauses attributed by `read_coverage.py`; they
are not sentence counts and should not be summed into a coverage total.

| Capability | Measured result | What the measurement establishes |
| --- | --- | --- |
| Train-lead semantic support | 1,365 / approximately 3,575 sentences; 38.2% | Current supported-sentence count on 1,500 train documents |
| Net change from pre-wave-3 reference | +769 sentences (596 to 1,365) | Aggregate change only; not an isolated registry ablation |
| Net change from pre-wave-2 reference | +687 sentences (678 to 1,365) | Aggregate change only; not an isolated registry ablation |
| Construction demo | 1 demo passed | Its assertions passed; stdout contained no per-construction counts |
| Conductor on real questions | 0 agreed, 0 wrong, 72 escalated | No known-answer row was answered by the accumulated frame |
| Wave 3 demo set | 11 passed of 11 run | Script assertions completed; not a corpus-wide precision result |
| Free-text realization | No new independent human-quality measure run | The prior audit's narrow, checked-template description remains the limit |
| Stereo-cross speed | No timing comparison run | No speedup or query-equivalence claim is measured here |

### Construction registry and precision evidence

The train coverage output attributed supported clauses to these rules:

| Rule | Supported clauses reported |
| --- | ---: |
| quote | 445 |
| adnominal | 81 |
| copula | 639 |
| frame | 146 |
| paren_gloss | 84 |
| connective_rel | 10 |
| diathesis | 17 |
| zero_subject | 7 |
| te_chain | 14 |
| modality | 16 |
| measure | 7 |
| np_internal | 7 |
| light_verb | 20 |
| time_expr | 8 |
| quantifier | 7 |

This is the registry's observed contribution in the current reader run: the
reader emitted supported clauses under each listed rule, and overall coverage
was 1,365 sentences. The mandated output does not expose a registry-off run or
incremental sentence count for each construction. Therefore +769 is the net
change against the pre-wave-3 reference, not a causal per-rule allocation.

The construction precision audit available in this unit was
`tools/demo_constructions.py`; it exited successfully and printed `DEMO OK`.
That is a pass/fail result for its embedded assertions. The run printed no
per-construction gold count, precision numerator/denominator, or independent
corpus precision estimate, so none is inferred here. The aggregate coverage
count measures reader support, not precision by itself.

### Conductor on real questions

The evaluation has 130 rows; 72 include a human answer and 27 have exact option
labels. The accumulated-frame exact outcomes were 0 agreed, 0 WRONG, and 72
escalated. Every recorded-answer row escalated. This is consistent with a
conservative abstention path, but does not establish that the conductor can
recover the answers from these records. The decision-writer demo's askable and
recorded-string counts are not substituted for these outcomes.

## What is wired, stubbed, and not demonstrated

- The semantic reader currently supports the train-lead count reported above.
  Most unsupported sentences remain typed as unsupported or ambiguous; the run
  reported 1,439 sentences with only unsupported material and 772 unread spans.
- Construction rules are active in the coverage run, and the construction demo
  passed. There is no isolated registry ablation or per-rule delta in the
  captured output.
- Per the 2026-10-02 audit, `semantic_band.band()` returned `None`, and
  `tools/demo_band.py` failed at its first expected-answer assertion. This
  stub/failure was not rerun for this audit.
- The prior audit observed checked, bounded realization for answer, summary,
  and compare requests. The current wave 3 demo runs add no independent judgment
  of arbitrary generated language.
- The prior audit described the conductor demos as using fake adapters and a
  fake command witness. The new real-question result still escalates every row
  with a recorded answer; no live agent or verifier was run here.
- The prior audit found memory helpers that remain standalone, including
  lesson, merge, and revalidation paths. The wave 3 demo passes do not show that
  these helpers have become part of the semantic answer path.
- The older writer, graded, polarity, stacked, reach, and meaning-descent paths
  are not shown by these runs to form a general semantic answer route.

### Weak demo claims

`DEMO OK` means the demo's assertions passed on its own inputs. It does not
measure general coverage or precision unless the run reports an independent
gold set and numeric outcomes. The construction demo reports neither numeric
precision nor a corpus delta by construction. The decision-writer demo's
matching denominator was 0, so its zero wrong count has no matched-answer
coverage behind it. The question-kind and variants demos printed held-aside
counters; these are deliberately excluded from the held-out evidence and from
the capability matrix. The real-question accumulated-frame evaluation is the
only measured conductor outcome reported here.

## LLM reach audit

No live LLM was called in the eleven demos or the two required evaluation
commands. This establishes only what these runs did; it does not certify every
reachable path in the repository.

| Reach point | Evidence from this audit | Rule status |
| --- | --- | --- |
| Semantic producer/checker and checked realization | Train coverage and local demos ran without a live model call | Observed runs are deterministic; this is not a full call-graph proof |
| Closed-choice asker routes | No live asker was invoked by these runs | Allowed only when two closed asks agree and the selected option remains testimony; no live accuracy measured |
| Conductor agent adapter | Real-question evaluation escalated 72 rows; no live agent ran | External-hands behavior is not demonstrated here |
| Verifier adapter | Verifier-evidence demo passed on its demo inputs; no live verifier ran | Any model-produced PASS/FAIL remains an unresolved model decision, not a closed-choice ask |
| Legacy arbitrary agent answer path | No run exercised it | The 2026-10-02 audit identified it as a reachable arbitrary-text path; that remains a rule violation if used as a Vera answer path |
| Legacy module authoring and corpus tools | Not run | They are not evidence of a model-free runtime answer path |

The demonstrations do not justify a claim that the repository as a whole obeys
the LLM rule. In particular, typed storage does not turn a model decision into
independent evidence, and a passing fake-adapter protocol does not demonstrate
a production human-framed agent run.

## Not completed by this audit

- I did not calculate per-construction newly supported sentence deltas or
  numeric precision rates: the permitted run outputs provide current rule counts
  and a pass/fail demo, but no per-rule baseline, ablation, or precision table.
- I did not rerun the prior audit's inherited demos, `demo_frame.py`, or
  `memory_frame_demo.py`. The 2026-10-02 status records that the latter two read
  additional project/frame files outside its then-permitted reference scope.
- I did not rerun the pre-wave-2 or pre-wave-3 coverage snapshots, inspect
  restricted evaluation material, or claim general completion of Vera wiring.
