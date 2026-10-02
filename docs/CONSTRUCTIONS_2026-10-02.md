# Writing a semantic construction

The registry separates reader additions from the shared semantic reader. Add a
module under `verantyx/constructions/`; importing the package discovers each
module with `pkgutil`, so the registry itself does not need an edit.

```python
from verantyx.constructions import Construction, Reading, TypedNote, register

def reads(ctx):
    # Inspect only ctx's bounded source text, tagged tokens, spans, and clauses.
    # Return None when this closed construction does not match.
    ...

def licenses(clause, source):
    # Independently check this clause against the original source string.
    # Do not call reads() or reuse its match decision.
    ...

register(Construction(
    name="example_rule",
    priority=20,
    reads=reads,
    licenses=licenses,
    refines=(),
))
```

## Reader contract

`reads(ctx)` is pure, deterministic, and bounded. It performs no file, network,
process, or model calls. The context contains:

- `sentence_text` and its source `sentence_span`;
- `tokens`, each a `TokenSpan(token, start, end)` from the repository tagger;
  token offsets are relative to `sentence_text`;
- `document_id` and clauses already read for that document, including native
  clauses for the current sentence;
- `budget` limits of 256 tokens, 128 clauses, and 4096 counted output items.

Keep scans linear in the supplied tokens and return `None` when a rule exceeds
its budget. Return `Reading(clauses, consumed_spans, notes)`, using tuples. Each
clause's `rule` must equal the construction name. Consumed spans and note spans
use absolute source offsets and must stay within this sentence. Notes are
`TypedNote(kind, span, detail)` records. A new construction is consulted only
after the native reader leaves a sentence unread or unsupported.

`VERA_CONSTRUCTIONS_OFF=example_rule,other_rule` disables those names at read
and verification time. The environment is checked for each operation, so it can
be changed to measure one rule off and on.

Priority orders calls; it never breaks a tie. If two constructions consume the
same span and produce different clause signatures, both readings are retained
as unsupported with an ambiguity reason. A more specific rule can declare
`refines=("base_rule",)`; only that explicit relation resolves the overlap.

## Independent licensing

The checker does not call `reads`. It finds the enabled construction whose name
matches `clause.rule` and calls only `licenses(clause, full_source)`. That
function must independently verify the construction's source grammar, exact
positions, role assignment, polarity, modality, time, and complete source
coverage. It must not trust the reader's unsupported flag or its match result.
An unknown rule, a disabled rule, or a rule without a licensor is rejected.
Common span, event type, role literal, and sentence-boundary checks run before
the construction-specific licensor. The built-in rule names `record`, `frame`,
`copula`, `identity`, and `measure` are reserved.

## Built-in coverage recovery

The native reader now recognizes closed particle sequences over tagger tokens
before trying their component particles as bare `と`, `に`, or `で`. The table
covers `として`, `について`, `による`, `によって`, `により`, `における`,
`において`, `に対して`, `と共に`, `ともに`, and topic-marked `では`. Predicate
tokens inside those exact sequences, such as `し` in `として`, are not treated
as separate events. The checker repeats this scan independently.

Exact numeric or era dates, optionally including month and day, can be typed as
time roles when they are attached with `に` or occur sentence-initially before
a comma. The exact `同日付で` form is also typed as a time role. Date ranges
and open time phrases are never extracted as time roles; outside a
source-bounded entity/value they remain ambiguous. A date already inside a
literal entity/value is preserved as part of that exact argument; it is not
converted into a time role. Relative-time scopes remain ambiguous.

## Measured reading coverage

Run with the configured train-lead corpus:

```sh
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
  python -B tools/read_coverage.py --n 1500 --stride 200
```

The run for this change reported **780 supported sentences out of 1,500 train
leads** (21.8%; 3,575 approximate sentences). The measured floor is recorded in
`docs/coverage/min_supported.txt`.
