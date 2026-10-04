#!/usr/bin/env python3
"""W3-b1 第 4 ラウンド: ja_r10.jsonl の語の固定の配置の答え w3b1_placement_fixture_r10.json を作る(w3b1_placement_fixture.py の入力だけを ja_r10 の `input` に置き換えて
同じ手順で作る。ラウンド 1 の w3b1_placement_fixture.py と w3b1_placement_fixture.json は変えない)。
使い方: cd <木> && PYTHONPATH=<木> python tests/reading_soundness/w3b1_placement_fixture_r10.py --placement DIR [--out FILE]
"""
import importlib.util, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('w3b1_placement_fixture_round1', HERE / 'w3b1_placement_fixture.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mod.inputs = lambda: list(dict.fromkeys(json.loads(l)['input'] for l in (HERE / 'ja_r10.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()))
if '--out' not in sys.argv: sys.argv += ['--out', str(HERE / 'w3b1_placement_fixture_r10.json')]
mod.main()
