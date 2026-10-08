"""W5-c entrance demo: `python -m verantyx.cli ask` in a subprocess against synthetic indexes and a two-store root.
Usage: cli_demo.py TREE WORKDIR   (WORKDIR is created fresh by the caller under the scratchpad)."""
import hashlib, json, os, sqlite3, subprocess, sys
from pathlib import Path

tree, work = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(tree))
from tools.build_p4_corpus_index import build            # noqa: E402
from verantyx import sovereign as sov                    # noqa: E402

Q = "雨の日に傘を持たずに外出すると、どうなりますか？"
ROWS = ["雨の日に傘を持たずに出たら、髪が濡れた。", "雨の日に傘を持たずに出たら、服が濡れた。"]
work.mkdir(parents=True, exist_ok=True)
src = work / "local.jsonl"
src.write_text("".join(json.dumps({"text": t, "source": f"g{i}", "scene": "雨", "sha": f"h{i}"}, ensure_ascii=False)
                       + "\n" for i, t in enumerate(ROWS)), encoding="utf-8")
build(src, work / "idx_ok" / "local.db", "local")
build(src, work / "idx_null" / "local.db", "local")
with sqlite3.connect(work / "idx_null" / "local.db") as con:
    con.execute("UPDATE rows SET origin = NULL")
root = work / "sov"
assert sov.create(str(root), "store-a", "owner-a", consent_promote=True)["verdict"] == "CREATED"
assert sov.create(str(root), "store-b", "owner-b", consent_promote=True)["verdict"] == "CREATED"


def snap():
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def run(label, index, store, *args):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(work), "PYTHONPATH": str(tree),
           "PYTHONDONTWRITEBYTECODE": "1", "VERA_P4_INDEX": str(work / index),
           "VERA_SOVEREIGN_ROOT": str(root), "VERA_SOVEREIGN_STORE": store}
    cmd = [sys.executable, "-m", "verantyx.cli", "--store", str(work / "s.json"), "ask", Q, *args]
    before = snap()
    done = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=180)
    out = json.loads(done.stdout)
    changed = sorted(k for k in set(before) | set(snap()) if before.get(k) != snap().get(k))
    n = out.get("basis_policy", {})
    print(f"## {label}\n   argv: ask <Q> {' '.join(args)}   index={index} store={store}")
    print(f"   rc={done.returncode} kind={out.get('kind')} verdict={out.get('verdict')} outcome={n.get('outcome')} "
          f"wrote={out.get('wrote')} files_changed_under_root={changed}")
    return out, done.returncode


print("tree:", tree)
run("A1: index whose rows have NULL origin, plain", "idx_null", "store-a")
run("A1: same, human present", "idx_null", "store-a", "--human-present")
run("A1: same, human present + reference column", "idx_null", "store-a", "--human-present", "--show-generated-reference")
run("A1: same, request that claims no fact", "idx_null", "store-a", "--request-kind", "creative")
issued, _ = run("A2: question put for store-a (index with origin generated)", "idx_ok", "store-a", "--human-present")
cid = issued["confirm"]["id"]
print(f"   issued id {cid}  destination={issued['confirm']['destination']}")
run("A2: that id given to store-b", "idx_ok", "store-b", "--confirm", cid, "yes")
run("A2: that id given to store-a (the right destination)", "idx_ok", "store-a", "--confirm", cid, "yes")
run("A2: the same question afterwards, store-a", "idx_ok", "store-a")
print("events in store-a:", len(sov.open_ledger(str(root), "store-a").events()),
      " events in store-b:", len(sov.open_ledger(str(root), "store-b").events()))
