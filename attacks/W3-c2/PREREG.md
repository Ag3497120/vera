# W3-c2 attack preregistration

Registered: 2026-10-03 22:08:38 +0900 (local `date` output), before creating attack inputs and before running the question observer.

## Targets

Read `docs/OBSERVATION.md` §「質問の観測（W3-c2）」 (match definition D9, output statuses D11, evidence D12, zero-WRONG acceptance D17, English limitations), `docs/EVENT_CROSS.md` §「穴の型」, and the question paths in `verantyx/semantic_read.py` and `verantyx/observe.py`.

## Frozen attack corpus and probes

I will author 10 documents of 5–10 single-sentence lines each and at least 100 questions. The documents will include Japanese and English facts that contrast polarity, voice, tense, adjuncts, quantity, argument direction, and topics. I will run all questions through the question entry twice: once with `VERA_PLACEMENT` unset and once with the configured coarse W3a placement path. I will separately reproduce any candidate hit through `python -m verantyx.cli observe --anchor-kind question --structure ...`.

Before the first observer run, the documents, questions, and explicit expected fact sets will be written under this attack directory; their SHA-256 values will be recorded here. A hit requires actual output that returns a wrong `FILLED`/`TIE`, collapses distinct candidates, changes the plain-sentence output, or violates the declared English refusal/reading behavior. Cases that abstain safely or correctly return `TIE` are misses. `VERA_PLACEMENT` alone does not make a type `direct`: a type-filter hit will only be claimed if the result carries direct type evidence.

## Hypotheses to test

- A1 (wrong fill): a PERSON wh question may be read into a non-person arm and return an artifact when the available placement is absent or is not carried into the structure reading.
- A2 (missed tie): two supported witnesses may fail to return `TIE`, or a multi-candidate result may select one.
- A3 (polarity/voice/causative/time/quantity/topic): a candidate with a different proposition may nevertheless match the question.
- A4 (type): a directly typed candidate of a type outside the hole's accepted types may remain in `FILLED`/`TIE`.
- A5 (English): `did` / `does` / `was`, stranded prepositions, and `which N` may produce an incorrect answer or an unsafe fill instead of a typed abstention.
- A6 (plain output): adding question support may change output bytes for declarative inputs, including punctuation or line endings.

The result set will include failed probes as misses. No product code or existing expectations will be modified.

## Frozen input hashes (before the first observer run)

The authoring source and every input below were written before any question was run through `read_question`, `observe`, or the CLI. SHA-256 values:

```text
1a1b5e93bf3ac219a7e355d1f15d6c8629c3da4e104b45b53eeb81d348278175  attacks/W3-c2/prepare_attack.py
2b683a384ba33da62128f394853c150fc00f03c67b24f87d35e0836daab466b5  attacks/W3-c2/data/questions.jsonl
4ad609a1899eaeb745f9860bbce9a42ba4f5406ed9cb00af5002548263102602  attacks/W3-c2/data/direct-types.json
ce393cf93acfc8d2a39177c7040398b669b9b1fe54bafeeea38363aac07ea069  attacks/W3-c2/data/docs/EN08.jsonl
f72ee581918f82910ddbd9ce52390f3a0dddb10535f390d3eb4c126524980abc  attacks/W3-c2/data/docs/EN09.jsonl
6e38f19a8353d32f13a894e2df28bbda975637ba67685d4fa81de6c24ae9e3de  attacks/W3-c2/data/docs/EN10.jsonl
b6ce2737fa795e22f45be89995b05db4511024736267c89812cb39198dd5e2b7  attacks/W3-c2/data/docs/JA01.jsonl
de7ca056aa7e42243cdd68a35e46ae4debb248e6082d87572399ce0d9a085bb2  attacks/W3-c2/data/docs/JA02.jsonl
30478ce21374fa57e18b638c03efd04b66672d3e543d640637d726ea5479c47e  attacks/W3-c2/data/docs/JA03.jsonl
e59e42c168070b45e4a2f62b9856e066c292426c9b283420e533d2007216dc4f  attacks/W3-c2/data/docs/JA04.jsonl
3997ba11422fa6ba5717cbb4112f1248b1be841bfc407d82e533659167f2febf  attacks/W3-c2/data/docs/JA05.jsonl
3c834c5c2293752c8519855135be41c13ad21571f5ba73ed390830390984edcb  attacks/W3-c2/data/docs/JA06.jsonl
7be6424cf18ef167cfc1205ae6dcc477fa151b9bf54036ff5170212325dc80c8  attacks/W3-c2/data/docs/JA07.jsonl
fdff4660f4b7bbddccee0bbd99fb4a91ba6cb12e63fe6004f9d273d1d71be99b  attacks/W3-c2/run_attack.py
f7e0a0deab11b5a130672f541308d628124ddbef2e10632a18a26edda9c84e24  attacks/W3-c2/test_attack_question_cross.py
```

The corpus contains 10 documents (7 Japanese, 3 English), 70 one-sentence records, and 120 questions. The four explicit reference cases are in `prepare_attack.py` / `questions.jsonl`; every other row is an exploratory probe and will be reported as a miss unless an independently obvious contract violation is observed.
