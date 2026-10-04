"""r3: the record of the tests that changed (AGENTS.md: the full text before and after goes into docs). Reads artifacts/w10-f04/r2_tests/*.r2.py.txt (before) and tests/test_w10f04_*.py (after) with `ast`, prints a Markdown block."""
import ast, os, sys
W = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
FILES = {'fill': 'test_w10f04_fill', 'ledger': 'test_w10f04_ledger', 'serve': 'test_w10f04_serve'}


def nodes(path):
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    lines = src.splitlines()
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.Assign)):
            name = n.name if isinstance(n, ast.FunctionDef) else n.targets[0].id if isinstance(n.targets[0], ast.Name) else None
            if name:
                start = (n.decorator_list[0].lineno if isinstance(n, ast.FunctionDef) and n.decorator_list else n.lineno) - 1
                out[name] = '\n'.join(lines[start:n.end_lineno])
    return out


print('#### テストの変更記録 r3（関数名・前後の全文。変えたのはここに書いた分だけ。他のテスト関数・定数は 1 文字も変えていない）')
total = 0
for key, base in FILES.items():
    before = nodes(os.path.join(W, 'artifacts/w10-f04/r2_tests/%s.r2.py.txt' % base))
    after = nodes(os.path.join(W, 'tests/%s.py' % base))
    for name in list(before) + [n for n in after if n not in before]:
        b, a = before.get(name), after.get(name)
        if b == a:
            continue
        total += 1
        kind = 'removed' if a is None else ('added' if b is None else 'changed')
        print('\n##### `tests/%s.py::%s` (%s)' % (base, name, kind))
        if b is not None:
            print('前:\n```python\n%s\n```' % b)
        if a is not None:
            print('後:\n```python\n%s\n```' % a)
print('\n(変更・追加・削除した定義: %d)' % total, file=sys.stderr)
