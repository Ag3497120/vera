"""W5-c review r1 M2: do the CLI entrances reach round3's rule-made social frame (F1), and does the output change?

Usage: greeting_entrances.py BASE_TREE NEW_TREE WORKDIR
Each greeting is asked through `python -m verantyx.cli ask` in a subprocess (legacy and `--mode round5`),
once per tree, in the scorer's child environment (docs/BANK_SCORE.md section 1: HOME and VERA_CORPUS_ROOT are
empty temporary directories, no VERA_P4_INDEX / VERA_SOVEREIGN_*). The two trees' outputs are compared after
dropping the timing fields. Then the same sentence goes through `Vera().ask` directly (general=None), which is
NOT an entrance the policy covers; it only shows where `_social_frame` can be reached from."""
import json, os, subprocess, sys
from pathlib import Path

base, new, work = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
GREETINGS = ["こんにちは", "ありがとう。", "さようなら", "ごめんなさい"]
FLAGS = {"legacy": [], "round5": ["--mode", "round5"]}
VOLATILE = {"elapsed_ms", "ingest_ms"}


def scrub(o):
    if isinstance(o, dict):
        return {k: scrub(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    return o


def diff_paths(a, b, p=""):
    """Key paths where the two outputs differ; a key present on only one side is reported as such."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                yield f"{p}/{k} (only new)"
            elif k not in b:
                yield f"{p}/{k} (only base)"
            else:
                yield from diff_paths(a[k], b[k], f"{p}/{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff_paths(x, y, f"{p}[{i}]")
    elif a != b:
        yield f"{p} (value differs)"


def run(tree, label, text, flags):
    home = work / f"{label}_home"
    corpus = work / f"{label}_corpus"
    cwd = work / f"{label}_cwd"
    for d in (home, corpus, cwd):
        d.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(home), "VERA_CORPUS_ROOT": str(corpus), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    cmd = [sys.executable, "-m", "verantyx.cli", "--store", str(cwd / "store.json"), "ask", text, *flags]
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=240)
    try:
        out = json.loads(done.stdout)
    except ValueError:
        out = {"_unparsed_stdout": done.stdout[:300], "_stderr": done.stderr[-300:]}
    return done.returncode, out


print("base tree:", base)
print("new tree: ", new)
print("child env: PATH, PYTHONPATH=<tree>, PYTHONDONTWRITEBYTECODE=1, HOME=<empty tmp>, VERA_CORPUS_ROOT=<empty tmp>, LANG, PYTHONIOENCODING")
same = diff = 0
for mode, flags in FLAGS.items():
    for text in GREETINGS:
        rb, ob = run(base, f"base_{mode}", text, flags)
        rn, on = run(new, f"new_{mode}", text, flags)
        diffs = list(diff_paths(scrub(ob), scrub(on)))
        equal = rb == rn and not diffs
        # allowed difference: keys the new policy adds to its own note (basis_policy.*), nothing else
        only_new_note_keys = rb == rn and all(d.startswith("/basis_policy/") and d.endswith("(only new)") for d in diffs)
        same += only_new_note_keys
        diff += not only_new_note_keys
        print(f"[{mode}] {text!r}: rc base={rb} new={rn} | base kind={ob.get('kind')} verdict={ob.get('verdict')} "
              f"applied={ob.get('basis_policy', {}).get('applied')} outcome={ob.get('basis_policy', {}).get('outcome')} "
              f"| new kind={on.get('kind')} verdict={on.get('verdict')} "
              f"applied={on.get('basis_policy', {}).get('applied')} outcome={on.get('basis_policy', {}).get('outcome')} "
              f"| identical_without_timing={equal} | only_new_note_keys_differ={only_new_note_keys}")
        print(f"      differing key paths: {diffs}")
print(f"SUMMARY entrances: same_apart_from_new_basis_policy_note_keys={same} other_difference={diff} (greetings {len(GREETINGS)} x modes {len(FLAGS)})")

# Direct use, outside the policy: Vera() has general=None, so ask() reaches round3's _social_frame.
code = ("import json,sys\nfrom verantyx.one import Vera\n"
        "r=Vera().ask(sys.argv[1])\n"
        "print(json.dumps({'kind':r.get('kind'),'verdict':r.get('verdict'),'has_basis_policy':'basis_policy' in r,"
        "'source_families':[s.get('family') for s in r.get('sources',[])]},ensure_ascii=False))\n")
for tree in (base, new):
    home, corpus = work / "direct_home", work / "direct_corpus"
    for d in (home, corpus):
        d.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(tree), "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(home), "VERA_CORPUS_ROOT": str(corpus), "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    done = subprocess.run([sys.executable, "-c", code, GREETINGS[0]], cwd=work, env=env, capture_output=True,
                          text=True, stdin=subprocess.DEVNULL, timeout=240)
    print(f"[direct Vera().ask, no policy] tree={tree} rc={done.returncode} {done.stdout.strip() or done.stderr[-200:]}")
