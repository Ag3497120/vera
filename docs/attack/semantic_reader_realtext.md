# Semantic reader real-text attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| R-01 | robustness | `load(8, 300)` from `tools/round5a_route_tune.py` | Load only the configured Wikipedia `split == train` leads for the attack run. | The loader raised `FileNotFoundError` for its configured `jawiki_leads.full.jsonl`; zero real paragraphs were available. No real-text crash, hang, or semantic-error rate can be estimated. |
| R-02 | ungrounded | `document_view({'q': '走れ。'})` and `document_view({'q': '逃げろ。'})` | Keep imperative speech as unread or typed non-assertive content. | Each imperative produced an `assert`, positive, nonpast frame with no unsupported marker. Reproduced with both inputs. |
| R-03 | ungrounded | `document_view({'q': '京都は日本にある。'})` and `document_view({'q': '奈良は日本にある。'})` | Treat the `に` phrase naming the place of existence as a location, or retain it unread. | Both readings assign `日本` the `recipient` role. Reproduced with both inputs. |
| R-04 | ungrounded | `document_view({'q': '芥川龍之介は1892年に東京で生まれた。'})`; `document_view({'q': '彼は2020年に賞を受けた。'})` | Keep a temporal phrase out of agent, patient, and recipient roles; type it as time or retain the clause unread. | `1892年` was assigned `recipient`; `2020年` was assigned `agent`. Reproduced with both inputs. |

The R-02 through R-04 examples are local Japanese contract probes, not Wikipedia samples. Their expected readings follow the clause and role distinctions represented by the reader's typed IR. They are preserved as non-strict xfails in the attack test file; this unit does not modify the reader.

## Rates from the run

| Input set | Read | Crashes | Hangs | Ungrounded / role-misclassified inputs |
| --- | ---: | ---: | ---: | ---: |
| Configured Wikipedia train leads | 0 | N/A | N/A | N/A |
| Local fallback probes | 8 | 0/8 | 0/8 | 3/8 |

The local fallback findings were the instruction probe (`2` assert frames from one command), the existence-location probe (`日本` as recipient), and the birth-year probe (`1892年` as recipient). In the separate targeted reproductions, each of the two imperative variants, two existence-location variants, and two temporal-role variants reproduced its corresponding finding (2/2 for each family). These rates describe only the listed probes.

## What held

- The specified loader was attempted with `n=8`, `stride=300`; it returned no documents because the configured corpus file was absent. The tests therefore use eight explicitly local probe sentences when no leads are available. If the loader has data, the tests use its train-only result instead.
- In the eight-probe run, `document_view` returned a typed view without a crash or timeout. It emitted nine candidate clauses and one unread span. The measured per-view ingest times ranged from 0.533 ms to 10.195 ms.
- The question probe `日本の首都はどこ？` remained unread with reason `interrogative source does not assert a fact`.
- The quantified probe `すべての鳥は飛ぶ。` retained `unsupported source quantifier/exception/time` on its candidate clause.
- The two-clause coordination probe preserved the separate agent and patient phrases for each predicate.
- In the run probes, all emitted clause and unread spans were inside their source strings. The test suite checks exact source slices for those spans.

## Not covered

- No Wikipedia lead paragraph was read: the configured loader file was unavailable. The local probes are not a substitute for a real-lead error rate.
- The run does not measure answer-level behavior through the verifier or router, corpus-wide rates, long-document scaling, or other Japanese dialects and writing styles.
- The tests do not fix `verantyx/semantic_reader.py`; this unit is limited to the attack tests and report.
