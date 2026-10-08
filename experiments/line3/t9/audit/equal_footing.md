## (a) Keyword baselines graded at Vera's granularity (gold inside ONE word of the candidate sentences' words)

Candidate list = the distinct words of the B1 / B2 sentences (MeCab surface tokens, or Vera's own tier units of those sentences); hit = gold inside one word (Vera's rule). Size = number of distinct words.

### intra2 (fulllead, n = 69)

| baseline | sentence-level hits (T9 rule) | median sentences | chance at same sizes | MeCab words: hits (median size) | RUN words: hits (median size) | WORD words: hits (median size) | CHAR words: hits (median size) | RUN+WORD+CHAR words: hits (median size) |
|---|---|---|---|---|---|---|---|---|
| B1-mecab | 47 | 1 | 0.3 | 10 (27) | 33 (10) | 10 (15) | 0 (27) | 34 (44) |
| B2-mecab | 57 | 2 | 0.4 | 12 (35) | 38 (15) | 12 (20) | 1 (35) | 39 (58) |
| B1-bigram | 38 | 1 | 0.2 | 7 (24) | 26 (9) | 7 (14) | 0 (22) | 27 (35) |
| B2-bigram | 54 | 2 | 0.3 | 10 (32) | 36 (13) | 10 (19) | 1 (31) | 37 (56) |

### cross2 (s3000, n = 9)

| baseline | sentence-level hits (T9 rule) | median sentences | chance at same sizes | MeCab words: hits (median size) | RUN words: hits (median size) | WORD words: hits (median size) | CHAR words: hits (median size) | RUN+WORD+CHAR words: hits (median size) |
|---|---|---|---|---|---|---|---|---|
| B1-mecab | 2 | 1 | 0.1 | 1 (30) | 1 (11) | 1 (19) | 0 (33) | 1 (50) |
| B2-mecab | 8 | 3 | 0.1 | 5 (48) | 7 (19) | 5 (34) | 0 (41) | 7 (76) |
| B1-bigram | 1 | 1 | 0.0 | 1 (30) | 1 (10) | 1 (19) | 0 (26) | 1 (47) |
| B2-bigram | 9 | 2 | 0.1 | 5 (37) | 8 (17) | 5 (23) | 0 (37) | 8 (63) |

## (b) Vera graded at sentence granularity (gold inside the text of a source sentence of a candidate)

Word rule = T9 headline rule, recomputed on the re-run (must equal summary.md). Sentence rule: every entry -> its source sentences; size = distinct sentences per question (median over questions with >= 1 sentence). 'no CHAR' drops the CHAR tier's entries (their source lists cover most of the corpus). 'best' maps each entry to only those of its source sentences that hold the most of its words (ties kept): the sentence a user would read the entry back to. 'chance' = expected hits of a list of the same number of sentences drawn at random from the corpus (per question, from the number of corpus sentences holding the gold), summed over questions.

### intra2 (fulllead, n = 69)

| system | n run | word rule hits | sentence rule hits (all tiers) | median sentences (all tiers) | chance hits, same sizes (all tiers) | sentence rule hits (no CHAR) | median sentences (no CHAR) | chance (no CHAR) | best-sentence rule hits (all tiers) | median sentences (best) | chance (best) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| flat-fast | 69 | 7 | 34 | 57 | 10.8 | 25 | 8 | 4.0 | 15 | 3 | 0.4 |
| flat-standard | 69 | 9 | 43 | 77 | 15.2 | 33 | 36 | 5.8 | 19 | 4 | 0.7 |
| layers-path-fast | 69 | 7 | 37 | 81 | 12.6 | 27 | 48 | 5.5 | 16 | 3 | 0.5 |
| layers-path-standard | 69 | 10 | 52 | 213 | 24.0 | 36 | 78 | 9.6 | 23 | 6 | 1.0 |
| layers-ssp-fast | 69 | 9 | 63 | 476 | 47.9 | 38 | 51 | 10.1 | 18 | 4 | 0.6 |
| layers-ssp-standard | 69 | 16 | 69 | 508 | 60.4 | 61 | 187 | 19.6 | 32 | 8 | 1.3 |
| carry-close-index-fast | 69 | 0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 |
| carry-close-index-standard | 69 | 7 | 9 | 2 | 0.1 | 9 | 2 | 0.1 | 9 | 2 | 0.1 |
| carry-close-path-fast | 69 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-close-path-standard | 69 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-defer-index-fast | 69 | 0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 |
| carry-defer-index-standard | 69 | 10 | 16 | 2 | 0.1 | 16 | 2 | 0.1 | 16 | 2 | 0.1 |
| carry-defer-path-fast | 69 | 0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 | 0 | 1 | 0.0 |
| carry-defer-path-standard | 69 | 2 | 2 | 1 | 0.0 | 2 | 1 | 0.0 | 2 | 1 | 0.0 |

### cross2 (s3000, n = 9)

| system | n run | word rule hits | sentence rule hits (all tiers) | median sentences (all tiers) | chance hits, same sizes (all tiers) | sentence rule hits (no CHAR) | median sentences (no CHAR) | chance (no CHAR) | best-sentence rule hits (all tiers) | median sentences (best) | chance (best) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| flat-fast | 9 | 0 | 2 | 84 | 2.3 | 2 | 83 | 1.9 | 0 | 2 | 0.0 |
| flat-standard | 9 | 0 | 4 | 332 | 3.8 | 2 | 59 | 2.0 | 0 | 2 | 0.0 |
| layers-path-fast | 9 | 0 | 2 | 89 | 2.3 | 2 | 85 | 2.0 | 0 | 2 | 0.0 |
| layers-path-standard | 9 | 0 | 5 | 342 | 3.9 | 2 | 110 | 2.1 | 1 | 4 | 0.1 |
| layers-ssp-fast | 9 | 0 | 7 | 2716 | 6.4 | 4 | 172 | 2.8 | 0 | 3 | 0.1 |
| layers-ssp-standard | 9 | 0 | 9 | 2830 | 8.8 | 8 | 1407 | 6.7 | 1 | 15 | 0.3 |
| carry-close-index-fast | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-close-index-standard | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-close-path-fast | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-close-path-standard | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-defer-index-fast | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-defer-index-standard | 9 | 1 | 1 | 2 | 0.0 | 1 | 2 | 0.0 | 1 | 2 | 0.0 |
| carry-defer-path-fast | 9 | 0 | 0 | - | 0.0 | 0 | - | 0.0 | 0 | - | 0.0 |
| carry-defer-path-standard | 9 | 0 | 0 | 2 | 0.0 | 0 | 2 | 0.0 | 0 | 2 | 0.0 |

