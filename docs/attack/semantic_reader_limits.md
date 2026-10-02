# Semantic reader limits attack

The independent checks below target bounded inputs, typed refusal behavior, deterministic results, and concurrent use of `verantyx/semantic_reader.py`. The acceptance run completed with **12 passed in 0.14s**. No defect reproduced in these cases, so the suite has no xfails.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| Empty mapping | robustness | `document_view({})` | Empty view, with no clauses or unread spans | Held |
| Empty source | robustness | `document_view({"empty": " \n "})` | Preserve the source but emit no reading | Held |
| Question source | robustness | `document_view({"question": "誰が来た？"})` | Do not assert a fact; retain one typed unread span | Held |
| Colon scope | robustness | `document_view({"scoped": "仮説:太郎は花子を呼んだ。"})` | Retain the whole scoped sentence as unread | Held |
| Empty request | robustness | `read_request(" \n ")` | Return a typed request with no plan and an unread span | Held |
| Unsupported quantifier | robustness | `read_request("すべての人は誰ですか？")` | Refuse the unsupported scope with typed unread output | Held |
| Quantity digit cap | robustness | `quantity("9" * 129 + "kg")` | Return `None` without a Decimal exception; keep `1.25kg` exact | Held |
| Repeated document read | robustness | Read `{"copula": "富士山は山です。"}` twice | Clause and unread results remain identical; elapsed time may differ | Held; one copula clause each time |
| Repeated request read | robustness | Read `富士山は何ですか？` twice | Produce the same plan on each call | Held |
| Mapping insertion order | robustness | Reverse the three source entries in the test | Per-source clauses and unread spans stay the same | Held |
| Concurrent readers | robustness | Two workers each read the same document and question inputs | Results match the serial results | Held across four concurrent calls |
| Bulk scoped sentences | robustness | Read `"未定義:scope。" * 512` | Keep every sentence typed unread, without emitting clauses | Held; 512 unread spans |

## What held

- Empty and unsupported inputs returned empty or typed-unread results rather than fabricated clauses or uncaught exceptions.
- Repeated document reads and request reads were stable. Reversing document mapping insertion order preserved each source's results.
- Two concurrent readers returned the same clauses, unread spans, and request plan as a serial read.
- The bulk colon-scope input retained one unread span per sentence. The exact quantity contract accepted `1.25kg` and rejected the tested 129-digit value.

## What was not covered

- This run did not measure resident memory, test an unbounded stream, or stress very large single sentences. The bulk case was bounded to the input shown above.
- It did not establish a hard wall-clock bound for arbitrary pathological text, exhaust every `Budget` boundary, or test concurrent mutation of a shared input mapping.
- It did not cover the full Japanese grammar, corpus behavior, or any material outside the permitted reader source and constructed inputs.
