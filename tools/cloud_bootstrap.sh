# Cloud session bootstrap for Vera line 3 (Ubuntu, Python 3.13, 4 cores). Run from the repo root (branch line3).
set -e
python3 -m pip install --quiet fugashi unidic-lite pytest
export PYTHONPATH=. PYTHONHASHSEED=0
python3 tools/determinism_probe.py
# Expected (Pro / Air, identical):
#   RUN  ['1938年に', '1992年6月', '2016年から2020年まで'] 79b0a11f444ec220
#   WORD ['11', '121', '1938'] a44611defdd6bec4
#   CHAR ['0', '1', '2'] 51b97f502940dcc2
python3 -m pytest -q -p no:cacheprovider tests/line3/test_space.py tests/line3/test_placement_ordered.py
