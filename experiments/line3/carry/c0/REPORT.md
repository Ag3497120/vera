# C0 — carry feasibility on S300 (measurement only, no product code)

Script: `c0.py` (run by `run_all.py`, 6 workers, while T8b ran: times are inflated by contention). Numbers: `SUMMARY.txt` (from `summarize.py`), raw per-run JSON in `results/`.
Settings: S300 (300 sentences), V2 default space, `placement.py` keys/classes/budgets as is, twin quotient off. Budget levels low / mid / high.
Owner answers applied: OP-2 (b) close only at sentence boundaries (a sentence that does not fit an empty black is split there); OP-3 (a) unstable = no settled tied class within the budget. Carry is EMPTY here (C0 ablation): this measures the black units alone.

## 1 sentence alone in an empty cross: does it settle?

| tier | low | mid | high | units per sentence (median / max) |
|---|---|---|---|---|
| RUN | 160/300 (53 %) | 199/300 (66 %) | 218/300 (73 %) | 7 / 28 |
| WORD | 51/300 (17 %) | 75/300 (25 %) | 102/300 (34 %) | 12 / 32 |
| CHAR | 10/300 (3 %) | 22/300 (7 %) | 37/300 (12 %) | 21 / 63 |

## Stream (word by word, close only at sentence boundaries)

| tier / level | blacks | units per black (median / max) | sentences per black (median / max) | blacks holding 1 sentence | sentences split across blacks | s per sentence (mean) | est. serial S3000 / S30000 |
|---|---|---|---|---|---|---|---|
| RUN low | 422 | 7 / 9 | 1 / 2 | 378 | 140 (47 %) | 0.05 | 0.0 h / 0.4 h |
| RUN mid | 316 | 9 / 13 | 1 / 3 | 242 | 88 (29 %) | 3.09 | 2.6 h / 26 h |
| RUN high | 265 | 10 / 15 | 1 / 3 | 170 | 65 (22 %) | 10.09 | 8.4 h / 84 h |
| WORD low | 676 | 7 / 8 | 1 / 2 | 665 | 249 (83 %) | 0.06 | 0.0 h / 0.5 h |
| WORD mid | 520 | 9 / 15 | 1 / 3 | 485 | 202 (67 %) | 5.04 | 4.2 h / 42 h |
| WORD high | 459 | 10 / 14 | 1 / 3 | 401 | 181 (60 %) | 16.24 | 13.5 h / 135 h |
| CHAR low | 1078 | 7 / 8 | 1 / 2 | 1075 | 290 (97 %) | 0.09 | 0.1 h / 0.8 h |
| CHAR mid | 851 | 9 / 12 | 1 / 2 | 840 | 267 (89 %) | 8.74 | 7.3 h / 73 h |
| CHAR high | 773 | 10 / 13 | 1 / 2 | 755 | 255 (85 %) | 22.53 | 18.8 h / 188 h |

No word was left unsettled (every word ended in some black) in any run.

## Reading

1. A black unit holds about 7–10 units (arm length about 2) and, in the median, ONE sentence or less. Raising the budget grows it only slightly (7 → 10).
2. Sentences often do not fit one black: RUN 22–47 %, WORD 60–83 %, CHAR 85–97 % are split. So in WORD/CHAR the sharing between words of one sentence is mostly visible only one layer up (design §10 consequence 2); the carry/upper layer is not an extra but where most sentence-internal structure lives.
3. RUN is the only tier where most sentences stay whole (mid: 71 % whole, 2.6 h serial for S3000). WORD/CHAR at mid or high cost 4–19 h for S3000 and 42–188 h for S30000 serially (about 1/8 of that with 8 workers).
4. Cost grows with the budget level much faster than black size: low is ~100× cheaper than mid for a 7 → 9 unit black.
