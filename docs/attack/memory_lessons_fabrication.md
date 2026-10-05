# Memory lessons fabrication attack

Scope: independent attack of `verantyx/memory_lessons.py`, using only constructed records. No external or sealed data was used.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| F-01 | ungrounded | Build an index with a LESSON for `printer jam`; mutate `index.lessons_for('printer jam')[0]['slots']['lesson']`; look up the same trigger again. | A later lookup should retain the source lesson text, `Power down first.` | The returned dict aliases the index's internal copied record. The later lookup returns the injected `Pour water into the printer.` text. The test reproduced this twice. |

F-01 is an xfailed test so the accepted suite remains green while keeping the defect visible. The mutation is performed through a prior return value; the index itself does not synthesize the injected text from its input.

## What held

- Exact trigger lookup returned only LESSON records for that trigger and sorted matching ids.
- A missing trigger match without an asker, and empty or non-string situations, abstained with an empty list.
- Explicit superseded ids and ids named by a record's `supersedes` slot were excluded.
- Mapping inputs and memory-like inputs with a `records` mapping were accepted; inherited superseded ids were applied.
- Mutating the input record after index construction did not change the indexed snapshot.

## Not covered

- Resolver/asker behavior for unmatched situations was not exercised.
- Normalization edge cases beyond an exact trigger were not tested.
- No production memory store, malformed serialized record, concurrency, or downstream answer generation was exercised.
