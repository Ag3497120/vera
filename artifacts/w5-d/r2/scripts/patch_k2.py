"""W5-d2 (K2): in the K2 test functions only, hand the made-up placement to the helpers: `std` -> `std_placed`, and `lookup=FakePlacement()` is added to a call
of explain_lines / rt.explain / explain / the local wrappers (two_rules_and_a_precedence, one_unit_status, run, statuses). A purely mechanical edit (AST positions);
the three functions whose subject is the absence of a placement are skipped (they are rewritten by hand). Usage: patch_k2.py <file> <function>... (run from the tree root)"""
import ast, sys
path, names = sys.argv[1], set(sys.argv[2:])
src = open(path, encoding='utf-8').read(); data = src.encode('utf-8')
starts = [0]
for line in data.split(b'\n')[:-1]: starts.append(starts[-1] + len(line) + 1)
pos = lambda ln, col: starts[ln - 1] + col
TARGET = {'explain_lines', 'explain', 'two_rules_and_a_precedence', 'one_unit_status', 'run', 'statuses'}
edits = []
for node in ast.parse(src).body:
    if not (isinstance(node, ast.FunctionDef) and node.name in names): continue
    for n in ast.walk(node):
        if isinstance(n, ast.arg) and n.arg == 'std': edits.append((pos(n.lineno, n.col_offset), 3, 'std_placed'))
        elif isinstance(n, ast.Name) and n.id == 'std': edits.append((pos(n.lineno, n.col_offset), 3, 'std_placed'))
        elif isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == 'rt' else None)
            if name == 'explain' and isinstance(f, ast.Attribute) or (isinstance(f, ast.Name) and f.id in TARGET):
                if any(k.arg == 'lookup' for k in n.keywords): continue
                close = pos(n.end_lineno, n.end_col_offset) - 1
                assert data[close:close + 1] == b')'
                before = data[:close].rstrip()
                edits.append((close, 0, (' ' if before.endswith(b',') else ', ') + 'lookup=FakePlacement()'))
for p, ln, text in sorted(edits, reverse=True):
    data = data[:p] + text.encode('utf-8') + data[p + ln:]
open(path, 'w', encoding='utf-8').write(data.decode('utf-8'))
print(path, len(edits), 'edits')
