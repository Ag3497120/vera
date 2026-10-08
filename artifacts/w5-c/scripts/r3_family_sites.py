"""W5-c round 3: the product sites (verantyx/*.py) that build a source dict (or ``dict(..., family=...)``) with a literal
``family`` and no ``origin`` in the same dict. Since round 3 such a source is an unknown origin unless it is
``family == "user"`` or a ``family == "document"`` handed over in this call (round5 with documents).
Output: file:line  family=<literal>  origin=<absent>  index_family=<yes|no>  entrance=UNMEASURED  (nothing is estimated:
which entrance turns such a site into an abstention is stated in the report only where a test / demo measured it).
Usage: r3_family_sites.py TREE"""
import ast, sys
from pathlib import Path

tree = Path(sys.argv[1]); sys.path.insert(0, str(tree))
from verantyx import ability_corpus   # noqa: E402

n = 0
for p in sorted((tree / "verantyx").glob("*.py")):
    mod = ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(mod):
        fam = origin = None
        spread = False
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if k is None:
                    spread = True
                elif isinstance(k, ast.Constant) and k.value == "family" and isinstance(v, ast.Constant):
                    fam = v.value
                elif isinstance(k, ast.Constant) and k.value == "origin":
                    origin = "present"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
            for kw in node.keywords:
                if kw.arg is None:
                    spread = True
                elif kw.arg == "family" and isinstance(kw.value, ast.Constant):
                    fam = kw.value.value
                elif kw.arg == "origin":
                    origin = "present"
        if isinstance(fam, str) and origin is None:
            n += 1
            print(f"{p.relative_to(tree)}:{node.lineno}  family={fam!r}  origin=absent  spread={'yes' if spread else 'no'}"
                  f"  index_family={'yes' if fam in ability_corpus.FAMILIES else 'no'}  entrance=UNMEASURED")
print("sites:", n)
