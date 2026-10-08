# T9 audit — why line 3 loses on bank2 (Opus audit, 2026-10-08)

Audit of experiments/line3/t9 at line3 HEAD d114dde. Measurement only: verantyx/ and tests/ were not changed, nothing
was committed, hidden/ was not opened. The re-runs used the T9 placement cache (level mid) and PYTHONHASHSEED=0. The re-run
reproduces the T9 headline exactly: every word-rule count below equals results/summary.md.

## Files

| file | what |
|---|---|
| `rerun_ask.py` | flat + layers (path, stable-seats-path) as measure_ask.py, plus per-entry source sentences and a per-tier gold cascade |
| `rerun_carry.py` | carry systems as measure_carry.py, plus per-entry source_sids |
| `equal_footing.py` -> `equal_footing.md` | question 1: baselines at word granularity, Vera at sentence granularity, with chance levels |
| `tokenisation.py` -> `tokenisation.jsonl` | cause (i): is the gold inside ONE unit of RUN / WORD / CHAR in its evidence sentence |
| `cascade.py` -> `cascade_{standard,fast}.md/.json` | question 2: the furthest stage each gold reached |
| `examples.py` -> `examples_standard.md` | up to 4 examples per cause (question, gold sentence, units, verdicts, what was listed) |
| `cross_sizes.txt`, `reach.txt`, `cost.txt` | cross capacity, one-hop reachability, and cost breakdown |
| `raw/` | re-run records and logs (raw/*.jsonl are large; do not commit them) |

Commands (repo root; `T9_CACHE` = the T9 placement cache directory):
```
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
PYTHONHASHSEED=0 $PY experiments/line3/t9/audit/rerun_ask.py fulllead standard experiments/line3/t9/audit/raw/ask_fulllead_standard.jsonl 4 intra2   # 2587 s wall
PYTHONHASHSEED=0 $PY experiments/line3/t9/audit/rerun_ask.py fulllead fast     experiments/line3/t9/audit/raw/ask_fulllead_fast.jsonl 2 intra2
PYTHONHASHSEED=0 $PY experiments/line3/t9/audit/rerun_ask.py s3000 {fast|standard} experiments/line3/t9/audit/raw/ask_s3000_{fast|standard}.jsonl 3 cross2
PYTHONPATH=. PYTHONHASHSEED=0 $PY experiments/line3/t9/audit/rerun_carry.py fulllead fast:none,fast:index,standard:none,standard:index experiments/line3/t9/audit/raw/carry_fulllead {close|defer}
cd experiments/line3/t9/audit && $PY tokenisation.py && $PY cascade.py standard && $PY cascade.py fast && $PY examples.py && $PY equal_footing.py
```

## 1. Equal footing (intra2, n = 69). The gap survives both ways.

(a) Baselines graded by Vera's rule: the candidates are the words of the B1/B2 sentences, and a hit needs the gold inside one word.

| baseline | sentence hits (T9) | MeCab tokens | Vera RUN units | Vera WORD units | all 3 tiers |
|---|---|---|---|---|---|
| B1-mecab | 47 | 10 (27 words) | **33 (10 words)** | 10 (15) | 34 (44) |
| B2-mecab | 57 | 12 (35) | **38 (15)** | 12 (20) | 39 (58) |
| B1-bigram | 38 | 7 (24) | 26 (9) | 7 (14) | 27 (35) |
| B2-bigram | 54 | 10 (32) | 36 (13) | 10 (19) | 37 (56) |

At word granularity, Vera gets 9 (flat-standard, about 20 distinct words per question) and 16 (ssp-standard, about 224 words).
The fair counterpart is B1 or B2 on RUN units: 33–38 with 10–15 words. The word rule costs everyone. The drop with MeCab/WORD tokens (47 -> 10) is the same tokenisation loss Vera suffers (§2 cause i).

(b) Vera graded by the baseline rule: every entry is mapped to its source sentences, and a hit is the gold in one of them.

| system | word rule | sentence rule (all sources) | median sentences | chance at that size | best-sentence rule | median sentences | chance |
|---|---|---|---|---|---|---|---|
| flat-standard | 9 | 43 | 77 | 15.2 | 19 | 4 | 0.7 |
| layers-path-standard | 10 | 52 | 213 | 24.0 | 23 | 6 | 1.0 |
| layers-ssp-standard | 16 | 69 | 508 (of 592) | 60.4 | **32** | 8 | 1.3 |
| carry-defer-index-standard | 10 | 16 | 2 | 0.1 | 16 | 2 | 0.1 |
| carry-close-index-standard | 7 | 9 | 2 | 0.1 | 9 | 2 | 0.1 |
| B1-mecab / B2-mecab | – | 47 / 57 | 1 / 2 | 0.3 / 0.4 | – | – | – |

The "all sources" mapping is uninformative. Path-edge provenance of frequent units (and of every CHAR entry) cites most of the corpus: ssp-standard's 69/69 sits on lists of 508 of 592 sentences, where chance alone gives 60. A usable mapping is "best sentence": the source sentences that hold most of the entry's words. That gives ssp-standard 32 on 8 sentences, against B1 47 on 1 and B2 57 on 2. Carry is the only system with B-sized lists, and it gets 16 on 2 against B2's 57.
cross2 (n = 9, s3000): the sentence rule is at chance (ssp-standard 9/9 on 2830 of 3000 sentences, chance 8.8). Best-sentence gives 0–1 of 9, against B2 8–9. Carry gets 0, except defer-index-standard with 1 of 9, on 2 sentences.

## 2. Failure cascade (intra2, standard; full lists in cascade_standard.md, examples in examples_standard.md)

Each question is placed at the furthest stage its gold reached, taken over the three tiers.

| stage | flat-std | ssp-std | meaning |
|---|---|---|---|
| (i) tok | 18 | 18 | the gold is not inside ONE unit of any tier (RUN: 14 span 2 units, 5 absent because of the punctuation/funcword cut; WORD 51/69 not one unit; CHAR 68/69) |
| (ii) noquery | 20 | 20 | a gold unit exists, but no cross that holds a question unit seats it, at any budget |
| (ii) budget | 6 | 6 | a cross holding a question unit seats it, but the node budget (10) did not read that cross |
| (iv) nofix | 3 | 1 | it is in a read cross, but no member of that cross reached a fixed point |
| (iii) noagree | 11 | 7 | a fixed-point state holds it, but no ANSWERING member does (sections disagree / AMBIGUOUS / ungrounded) |
| (iii) select | 2 | 1 | an answering state holds it, but the query-share state choice adopted other states |
| (iii) path | 0 | 0 | an adopted state holds it off the section path |
| hit | 9 | 16 | |

Read-out after adoption never drops the gold: (iii)-path = 0. The layers win back 7 noagree/nofix/select items.
In the 7 remaining ssp misses at stages 3–5, the upper layer read a bundle holding the gold and still did not list it.

Mechanism behind (ii), from cross_sizes.txt and reach.txt:
- **Most crosses hold only their seed.** In the fulllead RUN tier, 1946 of 3653 crosses (53%) hold only their seed; the median is 1 unit. WORD has 2187 of 3557.
  2169 RUN crosses stopped on budget: 1785 on max_moves, 380 on max_states. Of these, 1941 broke on the FIRST share-group: a median of 13 units all tied at n(seed,v) = 1.
  L-72 inserts every member of a tied share-group at once with all tied placements. For a unit seen in one sentence, that means its whole sentence at once, which blows the budget, and the cross is restored to the bare seed.
- **Gold units are exactly such units.** Gold units have a median corpus frequency of 1, are seated in a median of 1 cross besides their own, and 13 of 53 sit in none. 1646 of 3653 RUN units sit in no cross other than their own.
- **The read is unit identity, and these questions are cross-sentence.** In 10 of the 20 noquery items, no question unit (RUN or WORD) shares a sentence with the gold at all (e.g. 出身地 vs 出身). The gold is two hops away, and line 3 has no sentence-adjacency or document link (B2's "next sentence"). The other 10 are one hop away: the question unit and the gold share the evidence sentence. Each was lost only because the question unit's cross is a bare seed (I2-010: the crosses of ヨーロッパ and 規模 hold just themselves, though 3位 is in their sentence).

Examples, each with gold, gold sentence and what ssp-standard listed:
- tok: I2-001 ハッシュ表 (ハッシュ / 表) -> 1つ/のうち/ハッシュテーブル…; I2-008 カール・マルクス (カール / マルクス; the entry 19世紀/えた/カール/マルクス/唱/歴史観 holds the sentence but no single unit); R2-I009 3万2,500キロワット (最大3万2 / 500キロワット, split at the comma).
- noquery: I2-010 3位 (crosses of ヨーロッパ and 規模 = seed only) -> Google/LaMDA/…; I2-011 改称 (question 改名/同/じ/意味/語 shares nothing with 改称（かいしょう）も同義) -> という/意味/語; I2-020 17代目 (現在は17代目。 shares no unit) -> 17/2005/FIFA/….
- budget: I2-012 深川八幡宮 and I2-028 大曲輪遺跡. The read order (E_Q) spends the 10 crosses on frequent units: 呼, とも, ばれる, ぶ, 用い, 英語, データ. Both list とも/言/訳. I2-033 王リュカーオーン: only 2 of 13 crosses read.
- noagree: I2-003, I2-005, I2-006 駅番号 JR-Y13 / JA16 / OR08. The gold is seated in the read 駅番号 cross, but RUN is AMBIGUOUS / NO_EVIDENCE, and the list is WORD/CHAR noise (えき/き/位置/共和/…). I2-013 県社: RUN UNKNOWN_NO_FIXED_POINT.
- nofix: I2-036 1785年10月25日に (in the read 発見 cross; the RUN members of that cross have no fixed point). flat also has I2-048 and R2-I016.
- select: R2-I018 20万人. Adopted: 6つ/ウガンダ/テレゴ/副郡/… (more sentences shared with the question).

## 3. Cost (cost.txt)

**The CHAR tier is the cost.** It is 73% of layer-0 time at standard (1819 of 2508 s) and 71% at fast. It is also most of the layer time: path CHAR 3271 s and ssp CHAR 2553 s, against 240–533 s for RUN/WORD. It contributes **0 hits** in any system or preset, because a gold is one CHAR unit for 1/69 questions.
- **Why CHAR is slow.** A CHAR cross holds a median of 78 units, against 4–8 for RUN/WORD. Settling one member under the query tests 23 rotations plus all seat swaps of an ~80-seat cross: about 2.5 s per member.
- **Why full takes 473 s.** The V1 read takes every cross holding a question unit, and the question's kana and kanji sit in most CHAR crosses. "Would read in full" is a median of 360 CHAR crosses (max 585), against 12 RUN and 31 WORD. I2-001 at full read 542 CHAR crosses: 435 of the 473 s. Its upper CHAR layer bundled 544 crosses: 105–157 of the 206–300 s.
- **RUN/WORD outliers are tied classes.** RUN/WORD outliers (50–150 s) come from tied classes expanded into members: I2-004 RUN 2211 members, I2-047 3679, I2-031 WORD 2418 members and 52k states. Read classes go up to 735 arrangements.
- **Full also rebuilds.** Full additionally rebuilds budget-stopped crosses (raise on): WORD went from 11 ms to 20 s on I2-001.

## 4. Verdict

On this bank, line 3 as built does not use structure to cross sentences; it does worse than a keyword index restricted to the question's own words.
- Every Vera hit is a gold that shares a sentence with a question unit (41/69 are one-hop reachable; 0 hits outside them).
- The lists that hold the gold either are larger than B1/B2 at equal granularity or score at chance (sentence mapping).
- cross2 is 0 for flat and layers.

The losses are not in the read-out; it never drops an adopted gold. They come from the placement. Under L-72 a tied share-group is inserted whole, which exceeds the budget for every rare unit, so 53% of crosses are the bare seed. The specific, low-frequency answer words are therefore almost never seated where a question can reach them.

The single fix that would move the number most is making crosses hold their co-occurring units: grow tied groups piecewise, or stop the tie explosion instead of restoring to the seed. Rough upper bound:
- It reopens the 10 one-hop noquery items, plus up to 6 budget items whose gold would then also sit in the frequently read crosses: at most +16.
- At the current downstream conversion for ssp-standard (16 hits of 25 golds that reached a read cross, 64%), that is about +10, so ~26/69. The ceiling is 41/69, all one-hop items.
- That is still below B1-RUN-words (33) and far below B2 (57). The 18 tokenisation items, worth at most +11 even with one-hop reach, and the 10 two-hop items are out of reach for the current unit-identity design.

Dropping CHAR would cut cost by ~70% with no loss of hits.
