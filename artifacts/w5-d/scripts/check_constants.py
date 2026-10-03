"""W5-d: the 21 frozen constants of routing_from_text (CONSTANT_NAMES) have the same values as in the base commit (compared in a canonical form)."""
import json, subprocess, sys
BASE = sys.argv[1]
PY = '/Users/motonisihikoudai/vera-wiring/env/bin/python'
code = ("import sys, json; sys.path.insert(0, %r); from verantyx import routing_from_text as rt\n"
        "def c(o):\n"
        "    if isinstance(o, (set, frozenset)): return sorted((c(x) for x in o), key=repr)\n"
        "    if isinstance(o, dict): return {str(k): c(v) for k, v in sorted(o.items(), key=lambda kv: str(kv[0]))}\n"
        "    if isinstance(o, (list, tuple)): return [c(x) for x in o]\n"
        "    return o\n"
        "print(json.dumps({n: c(getattr(rt, n)) for n in rt.CONSTANT_NAMES}, ensure_ascii=False, sort_keys=True), rt.__file__)" % BASE)
env = {'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin'}
def run(tree):
    out = subprocess.check_output([PY, '-c', code.replace(repr(BASE), repr(tree))], env=env, cwd=tree).decode().rsplit(' ', 1)
    return out[0], out[1].strip()
b, bf = run(BASE)
n, nf = run(sys.argv[2])
print('base file:', bf); print('now  file:', nf)
print('21 constants equal to the base:', b == n, '(%d names)' % len(json.loads(b)))
