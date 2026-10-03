"""List product sites (verantyx/*.py) that write a literal family name of ability_corpus.FAMILIES as a source's
family ("family": "<name>" / family="<name>" / 'family': '<name>'). Output: file:line:text, grep-like."""
import re, sys
from pathlib import Path
from verantyx import ability_corpus

root = Path(sys.argv[1])
names = "|".join(re.escape(f) for f in ability_corpus.FAMILIES)
pat = re.compile(r"""['"]?family['"]?\s*[:=]\s*['"](%s)['"]""" % names)
n = 0
for p in sorted((root / "verantyx").glob("*.py")):
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if pat.search(line):
            n += 1
            print(f"{p.relative_to(root)}:{i}:{line.strip()}")
print("sites:", n)
