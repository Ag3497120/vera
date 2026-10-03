"""W3-b3: shared helpers of the w3b3_*.py scripts and tests (no rule of the reader is here). Nothing in this file decides what is read."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
PLACEMENT_R6 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6/run1'
DATA = ('relative', 'connective', 'parallel')           # rows with entry_expect / w3b3_expect
DATA_ALL = DATA + ('w1a4',)
BASE_COMMIT = 'c875ed3'


def isolation(exit_on_fail=True):
    """The loaded verantyx* modules must all be under the first entry of PYTHONPATH (the venv has an editable copy of another verantyx)."""
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign and exit_on_fail:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    return root, foreign


def data_path(name):
    return HERE / ('w3b3_%s.jsonl' % name)


def load_data(name):
    return [dict(r, _data=name) for r in (json.loads(l) for l in data_path(name).read_text(encoding='utf-8').splitlines() if l.strip())]


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]
