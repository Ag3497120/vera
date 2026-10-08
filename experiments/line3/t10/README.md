# T10 -- bank2 sweep under the new placement rule (ordered group insertion, stop at the collapse)

Measurement only (verantyx/ and tests/ untouched). Results: `results/summary.md` (committed). Raw per-question jsonl
(`results/ask_*.jsonl`, `results/*.meta.json`) and `logs/` are git-ignored (lines in the repo `.gitignore`).
Where it ran: the owner first required the MacBook Air (`tools/air.sh`), then (2026-10-08) released the Pro and asked for 10 workers; the T10 sweep
RAN ON THE PRO (Python 3.11.14 `/Users/motonisihikoudai/vera-wiring/env/bin/python`, PYTHONPATH=., PYTHONHASHSEED=0, 10 workers, load 20-40), from a frozen
SNAPSHOT of the code so that the F1c agent's live edits in the worktree could not change a running sweep: `/Users/motonisihikoudai/Projects/vera-impl/t10_snapshot/`
(copy of `verantyx/`, `experiments/line3/{t10,bank2,data}`, `t9/scorer.py`; `SNAPSHOT_MD5` lists the md5 of every .py, `PRO_HEAD` = line3 HEAD be92351 plus the
uncommitted F1c work-in-progress of that moment, which does not change the ordered/stop path; `experiments/line3/t10/results` and `t9/results` there are symlinks
into this worktree). The ordered cache was copied from the Air (`~/vera-impl/cache/f1b` -> `/Users/motonisihikoudai/Projects/vera-impl/cache/f1b`, md5 identical).
The Air commands below also work (the same scripts ran there for the checks).

## What is measured
The 94 fulllead questions of bank2 (69 intra2 + 25 unans; the cross2 + s3000 unans questions are a later step: the script takes
`s3000` as CORPUS, the summary then also prints the cross2 table), with the t9 systems:
- `flat-P` (layers off), `layers-ssp-P` (layers on, stable-seats-path), `layers-path-P` (layers on, default path candidates), P = fast, standard,
- placement = the F1b/F1 rule: `group_insert=ordered`, `order=forward`, `on_collapse=stop` (growth stops just before the member that breaks the budget),
  read from the complete ordered cache `~/vera-impl/cache/f1b` on the Air (levels mid; RUN/WORD/CHAR built with `line3 build --group-insert ordered`).
  The skip variant (`--on-collapse skip`, F1c) needs its own cache directory and is a later run: same commands, other `--cache`/`--on-collapse`, other file tag.
- t9 baseline rows of the same configs (whole-group insertion, L-72) and B1/B2 (MeCab and bigram) are copied alongside in every table; the t9 rows are
  recomputed from t9's raw per-question records (`../t9/results/ask_fulllead_{fast,standard}.jsonl`), so they equal `../t9/results/summary.md`.
- Grading = t9's (`../t9/scorer.py`); tables = t9's (gold in a candidate, single right / wrong, list with / without gold, no candidate, list size,
  first-gold position, s/question, trace; the unans table; the 9 B2-hard items; system vs B2 overlap; normalisation effect; joined diagnostic), plus
  T10 vs t9 gained / lost ids per config, the time table (layer 0 / layers extra / total / load) and the layer-0 verdicts.

## Files
| file | what |
|---|---|
| `measure_ask.py` | t9/measure_ask.py parametrised: `CORPUS PRESET OUT --cache DIR --group-insert --order --on-collapse --layers ssp,path\|ssp\|none --workers N --ids --kinds --limit --resume --check`. Refuses an incomplete cache (the question path reads every cross of a tier; on-demand building would stall for hours, L-477). Worker errors are recorded as `{"id","error"}`, not fatal. |
| `summarize.py` | -> `results/summary.md` (t10 files + t9 files of the same corpus/preset + B1/B2). Labels `config-preset [tag]` with tag = `gi-oc` read from the records (`ordered-stop`) and `t9 whole`. |
| `sweep.sh` | driver for the Air: per preset, measure then summarize. |
| `results/summary.md` | the tables. |

## What was run
- fast: `flat` + `layers-ssp` + `layers-path` (ssp first), 94 questions, 3641 s wall.
- standard: `flat` + `layers-ssp` only (path is not cheap: it builds its own layer-1 crosses, extra ~0.5-1x ssp's at fast), 94 questions.

## Commands (Pro, as run)
```
SNAP=/Users/motonisihikoudai/Projects/vera-impl/t10_snapshot   # copy of the code; or run from the repo root with the same commands
cd $SNAP
export PY=/Users/motonisihikoudai/vera-wiring/env/bin/python PYTHONPATH=. PYTHONHASHSEED=0
C=/Users/motonisihikoudai/Projects/vera-impl/cache/f1b
$PY experiments/line3/t10/measure_ask.py fulllead fast /tmp/x.jsonl --cache $C --check       # cache complete? lists the 94 ids
nohup sh experiments/line3/t10/sweep.sh $C ordered stop 10 fast ssp,path     > logs/t10_fast.log 2>&1 &
nohup sh experiments/line3/t10/sweep.sh $C ordered stop 10 standard ssp      > logs/t10_standard.log 2>&1 &   # after fast (10 workers each)
$PY experiments/line3/t10/summarize.py                                          # -> results/summary.md (fugashi/MeCab needed for B1/B2)
```

## Commands (Air)
The Pro worktree is the source; the Air holds the tree and the cache. Push with `tools/air.sh push` (it excludes `results/`, `raw/`, `logs/`; it also
`--delete`s any Air file that is not in the Pro tree, so do not push while other jobs write files in untracked paths of the tree: T10 was started with
a copy of `experiments/line3/t10/` only, `rsync -a experiments/line3/t10/ air-tb:~/vera-impl/line3/experiments/line3/t10/`).
Once, copy the t9 raw to the Air (the push does not carry `results/`):
```
rsync -a experiments/line3/t9/results/ask_fulllead_fast.jsonl experiments/line3/t9/results/ask_fulllead_standard.jsonl \
      air-tb:~/vera-impl/line3/experiments/line3/t9/results/
```
Check (3 s: loads the index, asserts the cache is complete for the 3 tiers, lists the 94 ids):
```
tools/air.sh run 'python3.11 experiments/line3/t10/measure_ask.py fulllead fast /tmp/x.jsonl --cache ~/vera-impl/cache/f1b --check'
```
Sweep (start only when the Air is free: no probe.py, no builds, 1-min load < ~6; 4 workers keep the load around 5-9; PYTHONHASHSEED=0 is set by air.sh).
Fast first, summarize, then standard:
```
tools/air.sh bg t10_fast     sh experiments/line3/t10/sweep.sh ~/vera-impl/cache/f1b ordered stop 4 fast ssp,path
tools/air.sh bg t10_standard sh experiments/line3/t10/sweep.sh ~/vera-impl/cache/f1b ordered stop 4 standard ssp,path
```
(`sweep.sh CACHE GI OC WORKERS PRESETS LAYERS [CORPUS] [KINDS]`; log `~/vera-impl/logs/t10_*.log`; raw
`experiments/line3/t10/results/ask_fulllead_<preset>_ordered-stop.jsonl` on the Air; a killed sweep continues with the same command, `--resume`.)
Pull and summarize (summarize runs on the Air, MeCab is there):
```
tools/air.sh run 'python3.11 experiments/line3/t10/summarize.py'
tools/air.sh pull experiments/line3/t10/results/summary.md
tools/air.sh pull experiments/line3/t10/results/ask_fulllead_fast_ordered-stop.jsonl   # raw, git-ignored
```
Direct single run (any config): `python3.11 experiments/line3/t10/measure_ask.py fulllead standard OUT.jsonl --cache DIR --group-insert ordered --on-collapse stop --layers ssp --workers 4 --resume`.

## Notes on the design
- Layer 0 (`A.ask`) is read once per question and reused (`base=`) by every layers config. `--layers ssp,path` runs ssp first on that layer 0, then path.
  Measured at fast: path is NOT cheap (its extra is about 0.5-1x the ssp extra: the two configs do not share layer-1 builds; the F1b probe's "warm 4.7 s" was the
  SAME config asked twice). The records carry `layer_order`. At standard only `ssp` was run (README, "What was run").
- The upper-layer stacks are not cleared between questions (as t9). Results do not depend on that cache (the F1b probe asserts cold == warm).
- One process per worker, fork; the index is loaded once in the parent (cache check) and inherited.
- Times include contention from whatever else runs on the Air; the time table prints the 1-min load at each question's end.
- Cost estimate from the F1b probe (single process, Air load 6-9): layer 0 about 115-130 s at fast and about 430 s at standard per fulllead question
  (94 questions / 4 workers: about 50 min at fast; standard several hours, plus the cold layers builds).
