"""W16-t2 (T2-3): the answer path is one function in `doc_answer`; `decode_grammar` and `doc_answer` do not import `cli` (not at the top, not inside a function, not by a string)."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('verantyx/decode_grammar.py', 'verantyx/doc_answer.py')


def cli_imports(path):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [a.name for a in node.names if a.name.split('.')[-1] == 'cli' or a.name == 'verantyx.cli']
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ''
            if mod == 'cli' or mod.endswith('.cli') or mod == 'verantyx.cli':
                found.append(mod)
            if node.level and any(a.name == 'cli' for a in node.names) or (mod in ('verantyx', '') and any(a.name == 'cli' for a in node.names)):
                found.append('from %s import cli' % ('.' * node.level + mod))
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            if name in ('import_module', '__import__') and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                if node.args[0].value.split('.')[-1] == 'cli':
                    found.append('%s(%r)' % (name, node.args[0].value))
    return found


@pytest.mark.parametrize('path', MODULES)
def test_the_module_does_not_import_cli(path):
    assert cli_imports(path) == []


def test_the_detector_sees_every_form_of_a_cli_import(tmp_path):
    """the check above is not vacuous: each way of importing cli is found in a sample."""
    sample = tmp_path / 's.py'
    sample.write_text('from . import cli\nfrom .cli import x\nimport verantyx.cli\nimport importlib\nimportlib.import_module("verantyx.cli")\ndef f():\n    from . import cli\n', encoding='utf-8')
    global ROOT
    old = ROOT
    ROOT = tmp_path
    try:
        found = cli_imports('s.py')
    finally:
        ROOT = old
    assert len(found) == 5


def test_decode_grammar_has_no_private_cli_name():
    text = (ROOT / 'verantyx/decode_grammar.py').read_text(encoding='utf-8')
    for name in ('cli._qc_run', 'cli._qc_records', 'cli._QC_SPLIT'):
        assert name not in text


def test_the_surface_rule_of_serve_is_gone():
    """serve's own check of the written predicate against the end of the question (PREDICATE_FORM_DIFFERS) is not in decode_grammar any more: the reading of the question is round5's."""
    text = (ROOT / 'verantyx/decode_grammar.py').read_text(encoding='utf-8')
    assert 'PREDICATE_FORM_DIFFERS' not in text and 'rstrip("？?")' not in text
