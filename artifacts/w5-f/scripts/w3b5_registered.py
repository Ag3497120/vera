"""Run artifacts/w3-b5/tools/run_rows.py of <tree> with the 16 registered frame_required rows put back in memory (and, with 'de', the 3 removed W3-b4 place/で rows too)."""
import sys, runpy, importlib.util
from pathlib import Path
tree = Path(sys.argv[1]); out = sys.argv[2]; extra = sys.argv[3:] 
sys.path.insert(0, str(tree)); sys.path.insert(0, str(tree / 'tests'))
from verantyx import semantic_reader as R
assert R.__file__.startswith(str(tree))
spec = importlib.util.spec_from_file_location('tw5_reg', tree / 'tests' / 'test_semantic_read_w3b5.py'); tw = importlib.util.module_from_spec(spec); sys.modules['tw5_reg'] = tw; spec.loader.exec_module(tw)
R.TYPED_FRAMES_FRAME_REQUIRED_W3B5 = tw.registered_rows()
sys.argv = ['run_rows.py', '--data', str(tree / 'tests/reading_soundness/ja_r11.jsonl'), '--out', out]
try:
    runpy.run_path(str(tree / 'artifacts/w3-b5/tools/run_rows.py'), run_name='__main__')
except SystemExit as e:
    print('exit', e.code)
