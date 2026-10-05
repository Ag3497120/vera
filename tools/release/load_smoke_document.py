"""既存 semantic reader テストの一文を smoke の constructed 入力として再利用する。"""
from __future__ import annotations

import ast
from pathlib import Path
import sys


def main(argv):
    source_path, output_path = map(Path, argv[1:])
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    selected = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or "unresolved_exception" not in node.name:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id != "document_view" or not call.args:
                continue
            data = call.args[0]
            if not isinstance(data, ast.Dict):
                continue
            for value in data.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    selected.append(value.value)
    if len(selected) != 1:
        raise SystemExit("既存 semantic reader smoke 文書の候補数が 1 ではありません")
    output_path.write_text(selected[0] + "\n", encoding="utf-8")
    print("既存 semantic reader fixture を constructed 入力に使います")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
