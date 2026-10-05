# Writer fabrication and provenance attack

The probes use small synthetic Japanese prose and store-shaped inputs. They
exercise `Writer.sentence` and `Writer.passage`; generated strings remain
drafts, not answers.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| WF-01 | ungrounded | Build from `東京は関東地方にある。京都は近畿地方にある。大阪は近畿地方にある。名古屋は中部地方にある。札幌は北海道にある。`; attest those terms under `wiki`; provide `crosses={"東京": {"近畿地方"}}`; call `sentence("東京")`. | Do not emit a location assertion unless a record supports that Tokyo is in Kinki. | Reproduced twice: `東京は近畿地方にある。`; `content_from` is only `東京`, `form_from` is the shape corpus `wiki`, and the draft note says the citations do not make it true. The cross supplies terms without a typed location relation. |

## What held

- A subject absent from the vocabulary returns no sentence and does not reach the composer.
- The composer receives only the selected subject's facets; source labels are filtered out.
- The writer passes its record, norm, or unknown licence according to vocabulary attestation.
- Draft dictionaries retain separate content and form source labels through the writer.
- Passage paths preserve the walk trace and count only sentences the writer produced.
- A negative sentence shape kept its negative ending in the synthetic probe.

## What was not covered

These probes do not use a production store or corpus. They do not test stale or
superseded record metadata, partial-span or tampered saved forms, or the
composer's full selection restrictions for semantic roles. The subject routing
probe covers entity swapping at the writer boundary, not every role assignment
inside composition. The output observed in WF-01 is a draft and is not shown to
reach an answer path.
