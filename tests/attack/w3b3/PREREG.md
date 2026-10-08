# W3-b3 attack preregistration

Registered: 2026-10-04 02:26:13 +0900, before writing the attack corpus and before reading any attack sentence through `semantic_read.read`, `clause_scope_explain_ja`, or `read_events`.

## Targets

- `docs/READING_SOUNDNESS.md` §10C, K114–K122: placement gating and base output parity; closed clause-boundary list and ambiguity abstention; head-role inference by exactly one typed empty argument arm; typed relation and ellipsis rules; registered W1-a4 refusal gates.
- `docs/READING_CONVENTIONS.md` §4.5, §4.8–4.10: relative-clause shape, role values, polarity, tense, voice, and relation semantics.
- `docs/EVENT_CROSS.md` W3-b3 preregistration: `Filler.embedded`, relation `head`, one-level nesting, and unchanged counts.
- `verantyx/semantic_reader.py`, `semantic_read.py`, and `event_cross.py` as the implementation under attack.

## Frozen corpus plan

`cases.jsonl` will contain 170 individually written Japanese and English sentences, each with a manually assigned expected class before the first reader run:

| Group | Count | Predeclared expectations |
|---|---:|---|
| Relative head and outer-relation challenges | 40 | Ambiguous, unsupported, non-event, or non-unique heads must abstain; the documented unambiguous `P_COMMUNICATE` patient-head example is an exact positive control (`from_role=patient`, `to_role=patient`). |
| Clause boundaries and relation types | 40 | Registered, unambiguous cause/contrast/condition cases must carry the registered relation; quote/condition ambiguity, unlisted boundaries, and multi-cut/three-clause inputs must abstain. |
| Negation, tense, and scope | 30 | Independent clause polarity and tense must remain local; unsupported negative relative or past-condition cases must abstain. |
| Subject/object ellipsis | 25 | Only the registered same-input topic antecedent may be restored; ambiguous subject handoff, absent antecedent, and unresolved transitive-object cases must abstain. |
| Parallel fillers and alternatives | 20 | Coordination/disjunction must not be silently distributed or collapsed into a single role value. |
| English relation/that-clause controls | 15 | The Japanese W3-b3 route must add no relation head/embedded cross and must preserve the base entry output. |

The categories are assigned sentence by sentence in the corpus. A `read` expectation includes the relation type and, for the positive relative control, both head roles. An `abstain` expectation forbids a readable W3-b3 relation and requires a typed diagnostic refusal where the trigger is reached. English cases are checked against the base commit `c875ed3` with the same placement argument. No result from the implementation will be used to alter an expected value.

## Execution and hit definition

Every corpus row will be run with `VERA_PLACEMENT` unset and with `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1`. The unset output will be compared byte-for-byte after JSON serialization with the base entry at `c875ed3`. Configured output will be checked against the row's frozen expectation. Readable relative cases will also be passed to `event_cross.build_crosses`; the relation's `head` must identify the same arm whose filler contains exactly the source cross, with unchanged counts and at most one embedded level.

A hit requires an executed counterexample: wrong or missing registered head arm; wrong local polarity/tense; ambiguous or W1-a4 case returned as a relation; unsupported/distributed parallel filler; Japanese relation/head added to English; placement-free byte mismatch; malformed or misplaced embedded cross; or changed cross counts. A case that abstains in line with its frozen class is a miss. Exploratory cases are labeled `probe` and are not counted unless their output directly violates one of these written contracts. No hidden bank or network will be used; no product code or existing test expectation will be edited.

Expected-value rule: the corpus labels above are the frozen oracle. `read` means the explicit relation/head required by that row; `abstain` means no W3-b3 read; `probe` means collect output only. Any additional semantic interpretation discovered after execution will be reported separately and will not be retrofitted into the frozen oracle.

## Frozen corpus

Frozen: 2026-10-04 02:37:35 +0900, before the first run through the implementation. The 170 rows and their per-row expectations were serialized by the authored source. SHA-256:

```text
7a6516fde029da88695a4e77d00e64bbddc6608040249352cd5c9c0315475c00  attacks/W3-b3/prepare_attack.py
b0a93fcdc17b6a17ec6336371f5780b965a25cc1e3836d3690a11b7d012036ed  attacks/W3-b3/cases.jsonl
```
