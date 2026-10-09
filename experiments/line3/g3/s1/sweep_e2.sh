#!/bin/sh
# G3-e2 sweep: S1 fast on bank2 fulllead RUN, mid, the G3-c3 placements, for {answer_shape unit, path} x {agreement three, two_if_single_edge} x
# {z_deep slide, order} with the NEW read order (qcount_first), plus path + three + slide with the OLD read order (grammar_first) for attribution.
# usage: sweep_e2.sh CACHE_ROOT [WORKERS=6]      CACHE_ROOT holds slide/ and order/ (window caches; built with --build when absent)
# (run from the repository root; PYTHONHASHSEED=0 is set here; PY = the Pro python)
set -e
CACHE=${1:?cache root}; W=${2:-6}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
R=experiments/line3/g3/s1/results; M=experiments/line3/g3/s1/measure_e2.py
mkdir -p "$R"
for zd in slide order; do
  mkdir -p "$CACHE/$zd"
  for ag in three two_if_single_edge; do
    for sh in unit path; do
      echo "== z_deep $zd, $ag, $sh, qcount_first: load $(uptime | sed 's/.*averages: //')" >&2
      $PY $M fast "$R/e2_z${zd}-${ag}-${sh}.jsonl" --cache "$CACHE/$zd" --z-deep $zd --workers "$W" --agreement $ag --answer-shape $sh --read-order qcount_first --build
    done
  done
done
echo "== attribution: z_deep slide, three, path, grammar_first: load $(uptime | sed 's/.*averages: //')" >&2
$PY $M fast "$R/e2_zslide-three-path-gfirst.jsonl" --cache "$CACHE/slide" --z-deep slide --workers "$W" --agreement three --answer-shape path --read-order grammar_first
