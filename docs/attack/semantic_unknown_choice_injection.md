# Semantic unknown choice injection review

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| U1 | ungrounded | Adopt `alpha` from a `CANDIDATES` report, then change the same report's status to `NO_CANDIDATES` and call `choose` again with the same frame. | The current status gate returns `NONE` with no option. | The cached alias is returned as `ADOPT` for `alpha` before the status gate runs. Reproducer: `test_cached_alias_cannot_bypass_a_later_non_candidate_status` (xfail). |
| U2 | robustness | Put `safe\u202eoption` in a candidate unit and capture the asks. | Bidirectional formatting controls are inert in text shown to the asker. | U+202E remains in the rendered prompt because the option JSON preserves Unicode. Reproducer: `test_bidirectional_control_is_inert_in_rendered_choice_text` (xfail). |

## What held

- A report whose status is not exactly `CANDIDATES`, including one with an embedded instruction, returns `NONE` without asking.
- Candidate and frame vocabulary terms are the only choices that can map to an adopted option. Out-of-range and natural-language agent replies abstain.
- Newlines and quotes in the query and candidate terms remain inside JSON values; they do not create extra numbered prompt options.
- Candidate provenance containing instructions is retained in returned evidence but is not sent in either ask.
- A new adopted choice uses two distinct asks and is recorded with `support: testimony`; its candidate evidence has `counts_as_evidence: false`.
- Repeating the same closed choice reuses its alias without additional asks.

## Not covered

- Behavior of a live language model or hostile external agent; asks used controlled responders.
- The full `UnknownReport` construction path and end-to-end semantic pipeline; reports here used small typed-shape stand-ins.
- Exhaustive Unicode controls, homoglyphs, zero-width characters, all quote/nesting patterns, `supersede_alias`, and concurrent callers.

## Run

Acceptance command result: **10 passed, 2 xfailed in 0.16s**. The xfails are the two findings above; no target module changes were made.
