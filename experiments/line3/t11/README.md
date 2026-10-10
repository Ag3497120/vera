# T11 -- bank3 ("unknown abilities") through the combined candidate list

Measurement only (verantyx/ and tests/ untouched). Results: `results/summary.md` (committed). Raw per-question jsonl (`results/*.jsonl*`: records, `.meta.json`, `.log`)
is git-ignored by one `.gitignore` line. Not committed by this run.

## What is measured
The 76 fulllead items of `../bank3/bank3.tsv` (two-facts 14, paraphrase 20, unknown-word 18, summary-choice 10, unans-kind 14) through
`ask(index, question, structure="combined", effort="fast")`: flat 3 tiers (RUN/WORD/CHAR, ordered/forward/stop placement cache `f1b`) + layers
(stable-seats-path, variant A, compress) + windows (RUN, representative members, plain AND window-evidence), merge="none" (per-origin blocks, `also_in`),
every option at its committed default (windows: z_deep order, arm_cap budget, seat_empty_axis deny = G3-i). `fast` only: standard was not run
(the fast run took 93 min wall under load 15-45; standard layer 0 is ~3.5x fast, so est. >5 h, over the 3 h bar).
NOT run: the 15 s3000 items (compare 14, one unans-kind): they need an S3000 ordered cache, which does not exist.
Grading = `../t9/scorer.py` (gold alternative in the normalised text of ONE word of an entry), per kind as in the task; summary-choice gold `LETTER|text` is
graded on the option text only (the letter cannot be produced: ask() returns corpus word sets, no option is scored). See `results/summary.md` for the
looser "gold in a sentence the entry cites" view (flat and windows only; layers entries cite ~255 sentences each) and the comparability caveat versus B1/B2.

## Files
| file | what |
|---|---|
| `measure_combined.py` | `PRESET OUT.jsonl --cache DIR [--workers N] [--ids] [--kinds] [--limit] [--resume] [--check]`; one `ask(structure="combined")` per question, records `answer_obj()` (header, blocks, entries with block/origins/words/also_in/source_sids, cited sentences). Refuses an incomplete flat cache. Worker errors are recorded as `{"id","error"}`. Resume-able per question. |
| `summarize.py` | -> `results/summary.md` (per kind, per origin, looser cited view, verdict/list shape, per-item tables, unans, per-source header, time). B1/B2 parsed from `../bank3/baselines.txt`. |
| `snapshot_md5.txt`, `snapshot_head.txt` | md5 of every `verantyx/**/*.py` of the frozen snapshot and the HEAD it was taken from (2ef8531f). |

## Provenance / how it was run (Pro, 2026-10-09)
- Frozen snapshot (`git archive HEAD` of `verantyx experiments/line3/{bank2,bank3,data,t10,g3/combined} t9/scorer.py`, plus t11) at
  `/Users/motonisihikoudai/Projects/vera-impl/t11_snapshot/` (`PRO_HEAD` = 2ef8531f; `experiments/line3/t11/results` there is a symlink into this worktree), because other
  agents edit `verantyx/line3/combined.py` and `.github/` in the worktree. `combined.py` md5 in the snapshot: `cdb4073b289d00ea858747b5c53aabc4`.
- bank3 intake sha re-verified before the run: `bank3.tsv` 42b3a110...905cd9 = `MANIFEST.json`; both corpora sha equal too.
- Cache dir `/Users/motonisihikoudai/Projects/vera-impl/cache/t11`: symlinks to the three `cache/f1b` ordered placements + the window placements
  `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_cf35f420cea6.pkl` (592 windows, z_deep order), placed once by the check run (58 s, 10 workers).
- Python 3.11.14 `/Users/motonisihikoudai/vera-wiring/env/bin/python`, `PYTHONPATH=. PYTHONHASHSEED=0`, 10 workers, whole machine shared with other agents (1-min load 7-46).

```
SNAP=/Users/motonisihikoudai/Projects/vera-impl/t11_snapshot ; cd $SNAP
export PYTHONPATH=. PYTHONHASHSEED=0 ; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
C=/Users/motonisihikoudai/Projects/vera-impl/cache/t11
$PY experiments/line3/t11/measure_combined.py fast /tmp/x.jsonl --cache $C --workers 10 --check          # builds/loads windows, lists the 76 ids
nohup $PY experiments/line3/t11/measure_combined.py fast experiments/line3/t11/results/ask_fulllead_fast.jsonl --cache $C --workers 10 --resume \
      > experiments/line3/t11/results/ask_fulllead_fast.jsonl.log 2>&1 &
PYTHONPATH=. $PY experiments/line3/t11/summarize.py          # -> results/summary.md
```
Time: `done 76 (0 errors) in 5584s`; per question median 669 s, max 1907 s (10 in parallel on a loaded machine).
