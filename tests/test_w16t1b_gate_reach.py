"""W16-t1b K800 (auditor ruling 2026-10-06, item 3): the gate wraps `semantic_reader.document_view` at the end of the module. Every module of the package that imports `document_view`
(at module level, or inside a function) must hold the wrapped function, whatever the order of the imports is; a module that holds the function of the base commit would answer from a reading the
gate has not touched. If one of them held the base function, the replacement would have to be given up and the gate put at the entrance (semantic_read and question, one call each) instead.
The modules are found by reading the source of the package (an `from .semantic_reader import document_view` anywhere), not from a list."""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import semantic_reader as R

TREE = Path(__file__).resolve().parents[1]


def _importers():
    top, inner = [], []
    for path in sorted((TREE / 'verantyx').rglob('*.py')):
        if path.name == 'semantic_reader.py': continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        mod = '.'.join(path.relative_to(TREE).with_suffix('').parts)
        mod = mod[:-len('.__init__')] if mod.endswith('.__init__') else mod
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split('.')[-1] == 'semantic_reader' and any(a.name == 'document_view' for a in node.names):
                (top if node in tree.body else inner).append(mod)
    return sorted(set(top)), sorted(set(inner) - set(top))


TOP, INNER = _importers()


def test_the_importers_are_found_from_the_source():
    assert len(TOP) >= 6 and {'verantyx.meaning_bridge', 'verantyx.meaning_goal_bridge', 'verantyx.compositional_goal', 'verantyx.memory_frame', 'verantyx.semantic_retrieve',
                              'verantyx.semantic_polarity'} <= set(TOP), TOP
    assert INNER, INNER


def test_the_module_attribute_is_the_wrapper_and_the_wrapper_reaches_the_function_of_the_base():
    assert R.document_view is R._w16t1b_document_view
    base = R._w16t1b_document_view.__kwdefaults__['_base_view']
    assert base is not R.document_view and base.__name__ == 'document_view'


@pytest.mark.parametrize('first', TOP, ids=lambda m: m.split('.')[-1])
def test_every_importer_holds_the_wrapper_whichever_module_is_imported_first(first):
    mods = TOP
    code = ("import importlib, sys\nimport %s\n" % first
            + "from verantyx import semantic_reader as R\n"
            + "assert R.document_view is R._w16t1b_document_view\n"
            + "bad = []\nfor m in %r:\n    v = importlib.import_module(m)\n    if v.document_view is not R._w16t1b_document_view: bad.append(m)\n" % (mods,)
            + "from verantyx import semantic_reader as R2   # the in-function importers read the attribute when they run: the same object\n"
            + "for m in %r:\n    from importlib import import_module\n    ns = {}\n    exec('from ' + m.rsplit('.', 1)[0] + ' import semantic_reader as _r; got = _r.document_view', ns)\n    if ns['got'] is not R._w16t1b_document_view: bad.append(m)\n" % (INNER,)
            + "assert not bad, bad\nfiles = sorted({getattr(m, '__file__', '') for k, m in sys.modules.items() if k.startswith('verantyx') and getattr(m, '__file__', None)})\n"
            + "assert all(f.startswith(%r) for f in files), [f for f in files if not f.startswith(%r)]\n" % (str(TREE), str(TREE)))
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=str(TREE), env={'PYTHONPATH': str(TREE), 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin'})
    assert r.returncode == 0, r.stderr[-1500:]
