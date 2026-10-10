# G3-k2 -- the flat plane's read order eq_first (「E_Q が先、単位数は同点内」), both marks, the headline over the order-only run

Code: line3 HEAD `a9ce52d95b70` + the uncommitted G3-k2 work; bank3 sweep started 2026-10-10 11:14:49 (python 3.11.14, PYTHONHASHSEED=0, 10 workers, fast); code sha256: ask a56063338d, combined ffeaaa8d37, cycle f03a744e84, grammar fa724432f9, matryoshka 15ffb6b066, slide_flat fe809e80a1, slide_query c658f54648, wiring 6617a73069.

## 1. bank3 fulllead, unknown-word 18 + paraphrase 20, combined fast: gold in a candidate (t9 rule; the assembled strings do not count)

| kind | n | off | order-only (G3-k order = qcount_first) | order-only, eq_first (same-order attribution) | on, qcount_first (G3-k) | **on, eq_first** | **headline: on-eq_first minus order-only** | on-eq_first minus off |
|---|---|---|---|---|---|---|---|---|
| unknown-word | 18 | 6 | 6 | 6 | 7 | 5 | **-1** (+uw15 -uw18 -uw19) | -1 ( -uw19) |
| paraphrase | 20 | 3 | 3 | 4 | 6 | 5 | **+2** (+pa09 +pa18) | +2 (+pa09 +pa18) |
| all | 38 | 9 | 9 | 10 | 13 | 10 | **+1** (+pa09 +pa18 +uw15 -uw18 -uw19) | +1 (+pa09 +pa18 -uw19) |

Question-level differences, on-eq_first against on-qcount_first: gained none; lost pa06 uw18 uw19.
Order-only under eq_first against order-only under qcount_first: gained pa18 uw15; lost uw18 (the order alone, without stand-ins, now reads the tie by the original count only).

List size (non-assembled entries) median / max, off 44.5 / 184, order-only 38.5 / 185, on-qcount_first 33.0 / 191, **on-eq_first 51.0 / 163**; ANSWER verdicts off 0, order-only 0, on-qcount_first 0, on-eq_first 0.

## 2. The 9 questions whose flat/RUN block collapsed under G3-k (off >= 10 entries, on-qcount_first under a quarter): flat/RUN entries per order

| question | stand-in units added | flat/RUN off | flat/RUN order-only (qcount_first) | flat/RUN order-only (eq_first) | flat/RUN on qcount_first | flat/RUN **on eq_first** | window entries off / on-qcount / **on-eq** | gold off / on-qcount / on-eq |
|---|---|---|---|---|---|---|---|---|
| pa04 | 6 | 39 | 5 | 39 | 5 | 39 | 0 / 3 / 3 | - / - / - |
| pa05 | 14 | 88 | 8 | 88 | 8 | 88 | 0 / 0 / 0 | Y / Y / Y |
| pa10 | 6 | 63 | 35 | 63 | 13 | 13 | 0 / 0 / 0 | - / - / - |
| pa19 | 77 | 62 | 63 | 62 | 9 | 8 | 0 / 0 / 0 | - / - / - |
| uw02 | 0 | 37 | 0 | 37 | 0 | 37 | 8 / 8 / 8 | Y / Y / Y |
| uw08 | 284 | 35 | 28 | 35 | 0 | 35 | 0 / 3 / 3 | - / - / - |
| uw09 | 46 | 69 | 69 | 69 | 0 | 69 | 2 / 2 / 2 | - / - / - |
| uw10 | 4 | 91 | 4 | 91 | 4 | 91 | 0 / 0 / 0 | - / - / - |
| uw15 | 121 | 43 | 42 | 85 | 1 | 43 | 0 / 0 / 0 | Y / Y / Y |
| **total (9 questions)** | | 527 | 254 | 569 | 40 | 423 | 10 / 16 / 16 | |

Still under a quarter of off under eq_first: pa10 pa19.  flat/RUN entries over ALL 38 questions: off 1226, order-only 1012, on-qcount_first 935, **on-eq_first 1623**; questions where flat/RUN lists nothing: off 6, on-qcount_first 6, on-eq_first 1.

## 3. The marks (on-eq_first) and where the gained golds came from

Entries marked `via_standin`: 530 of 2510 (on-qcount_first 19); marked `read_via_standin` and not `via_standin`: 230 in 11 questions (on-qcount_first 306); both: 529.  The combined header's grammar row carries both counts per question (L-821).
Header grammar-row counts equal the counts of the marks over the list for 38 of 38 questions.

**bank3, on-eq_first against the ORDER-ONLY run (the headline)**: 3 questions gained.

| question | gold entries on-eq_first: origin (mark class) |
|---|---|
| pa09 | window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| pa18 | window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| uw15 | flat/RUN (read_via_standin) |

By mark (a question counts once per class it has): `via_standin` 0; `read_via_standin` (not `via_standin`) 3; layers entry (unmarked by design) 0; neither 0.  Exactly one class: via_standin 0, read_via_standin 3, layers 0, neither 0.  With any stand-in mark: 3 of 3.

**bank3, on-eq_first against the order-only run UNDER eq_first (same order, stand-ins dropped)**: 1 questions gained.

| question | gold entries on-eq_first: origin (mark class) |
|---|---|
| pa09 | window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |

By mark (a question counts once per class it has): `via_standin` 0; `read_via_standin` (not `via_standin`) 1; layers entry (unmarked by design) 0; neither 0.  Exactly one class: via_standin 0, read_via_standin 1, layers 0, neither 0.  With any stand-in mark: 1 of 1.

**bank3, on-eq_first against off**: 2 questions gained.

| question | gold entries on-eq_first: origin (mark class) |
|---|---|
| pa09 | window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| pa18 | window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |

By mark (a question counts once per class it has): `via_standin` 0; `read_via_standin` (not `via_standin`) 2; layers entry (unmarked by design) 0; neither 0.  Exactly one class: via_standin 0, read_via_standin 2, layers 0, neither 0.  With any stand-in mark: 2 of 2.

Golds lost: against order-only uw18 uw19; against off uw19.

## 4. bank2 fulllead intra2 (n = 69), combined fast

| system (intra2, n = 69) | flat block | flat + layers | combined (all blocks) |
|---|---|---|---|
| grammar off, this tree (stored) | 16 | 21 | 28 |
| on, qcount_first (stored, G3-k) | 18 | 25 | 33 |
| **on, eq_first** | 17 | 24 | 32 |

Combined gold: on-eq_first gained against off I2-025 R2-I007 R2-I018 R2-I019, lost none; against on-qcount_first gained R2-I007 R2-I020, lost I2-023 I2-033 R2-I017.
Gained against off (4 questions), mark classes of their gold entries (a question counts once per class): layers (unmarked by design) 1, read_via_standin 1, via_standin 3.  There is no bank2 order-only run, so `neither` also holds what the order alone brings.
Entries marked via_standin 411, read_via_standin and not via_standin 222 (on-qcount_first 11 / 347); list size median / max off 29.0 / 152, on-qcount_first 32.0 / 368, on-eq_first 32.0 / 166; ANSWER verdicts off 0 / on-qcount_first 0 / on-eq_first 0, of them without the gold off 0 / 0 / 0.
Unanswerable (unans, n = 25): a single (ANSWER) verdict off 0 / on-qcount_first 0 / on-eq_first 0; abstained (no candidate) off 0 / 0 / 0.

