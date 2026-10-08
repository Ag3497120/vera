# T9 -- bank2 (cross-sentence questions) on Vera line 3, with keyword baselines

Measurement only (verantyx/ and tests/ untouched). Results: `results/summary.md` (committed). Raw per-question jsonl in
`results/*.jsonl` and `logs/` are git-ignored (line in the repo `.gitignore`).

## Inputs
- Bank: `../bank2/bank2.tsv` (128 questions: intra2 69 / cross2 9 / unans 50), sha256 in `../bank2/MANIFEST.json`.
- fulllead corpus for line 3: `../bank2/data/fulllead_sents.jsonl`, derived by `make_fulllead_sents.py` from
  `../data/S300_fulllead.jsonl`: split field `text` on 「。」, keep 「。」 on each piece, drop empty/whitespace-only pieces
  (a trailing piece without 「。」 would be kept; none occurs), fields `sha` (= sha256 of the sentence, utf-8), `title`, `sent`,
  `source` = `title#i` (0-based). 592 rows (same 592 sentences as baselines.py), **sha256 of the file:
  45efdaedb7abc8f43762ea0c237fca709b7a7b11710203fdeed7ab60c446cefe**. All 69 intra2 evidence `title#i` map to a row containing the gold.
- s3000 corpus: `../data/S3000.jsonl` (3000 rows, one sentence each). Each question runs only against its own corpus
  (intra2 + fulllead unans on fulllead_sents = 94 questions; cross2 + s3000 unans on S3000 = 34).

## Systems
- `flat-P`: layers off, `ask.ask(effort=P)`, 3 tiers (RUN/WORD/CHAR), candidates = every entry of the 3 tiers (as T7b).
- `layers-path-P`: layers on, `LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate="path")`,
  layer 0 reused (`base=`), as t8e/measure.py; candidates = layer-0 entries + upper entries.
- `layers-ssp-P`: same with `candidate="stable-seats-path"`.
- `carry-{close|defer}-{path|index}-P`: RUN tower, level `low`, `unit_filter="default"`, `pack_overflow` close/defer (as carry/c5);
  `carry_query.ask`, path descent (`fallback=None`) or index descent (`fallback="index"`); candidates = entries.
- B1/B2: `../bank2/baselines.py` functions (MeCab and bigram tokenizers), graded with the same normaliser.
- P = fast, standard. `full` NOT run: one fulllead question (I2-001, 1 worker) took 473 s flat + 206 s path + 300 s stable-seats-path
  (`results/probe_full_fulllead_I2-001.jsonl`), ~16 min per question, ~25 h for the 94 fulllead questions; killed after 1 of 5 probe questions.
  Carry full not run either (C5 showed full = standard for the path descent; index descent not asked for beyond standard).

## Scorer (`scorer.py`)
Candidate = one entry (word set). Hit = a normalised gold alternative is a substring of one normalised word of the entry (oracle rule of T6ab..C5).
Normalisation: NFKC, casefold, remove whitespace, thousands commas, 「・」; 万 amounts -> digits (3万2,500 -> 32500); kanji digit runs
〇一..九 -> ASCII. Units are not stripped. For B1/B2 a candidate is one sentence (a much longer unit than a word set; keep that in mind).
`summary.md` lists, per system, items that hit only thanks to normalisation (none for any system), and a looser "concatenated words" diagnostic.

## Commands (repo root `/Users/motonisihikoudai/Projects/vera-impl/wt/line3`; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python)
```
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
$PY experiments/line3/t9/make_fulllead_sents.py
export T9_CACHE=<scratch>/t9cache         # placement cache (level mid), keyed by data sha, shared by both corpora
PYTHONHASHSEED=0 $PY experiments/line3/t9/precompute.py experiments/line3/bank2/data/fulllead_sents.jsonl $T9_CACHE 5   # 784 s wall
PYTHONHASHSEED=0 $PY experiments/line3/t9/precompute.py experiments/line3/data/S3000.jsonl $T9_CACHE 4                    # 4611 s wall
# flat + layers (path, stable-seats-path), per corpus and preset (4 workers):
for p in fast standard; do
  PYTHONHASHSEED=0 $PY experiments/line3/t9/measure_ask.py fulllead $p experiments/line3/t9/results/ask_fulllead_$p.jsonl 4
  PYTHONHASHSEED=0 $PY experiments/line3/t9/measure_ask.py s3000    $p experiments/line3/t9/results/ask_s3000_$p.jsonl 4
done
# carry (one tower per process, 1 worker, all four combos; run close and defer):
for c in fulllead s3000; do for po in close defer; do
  PYTHONPATH=. PYTHONHASHSEED=0 $PY experiments/line3/t9/measure_carry.py $c fast:none,fast:index,standard:none,standard:index \
      experiments/line3/t9/results/carry_$c 1 none all $po
done; done
(cd experiments/line3/t9 && $PY summarize.py)      # -> results/summary.md
```
Without a cache, crosses are built on demand and the layers build every cross of the tier (S3000: hours); precompute first.

## Cost notes
Precompute CPU: fulllead RUN 1522 s / WORD 1455 s / CHAR 925 s; S3000 RUN 8243 / WORD 6965 / CHAR 3221 s. Carry tower build: fulllead 71 s cpu
(close), S3000 968 s cpu (close). Times in summary.md are wall seconds per question inside a worker with 4 workers + other jobs running
(1-min load 5-15), so they include contention; carry runs used 1 worker per tower. Carry times exclude the tower build.
